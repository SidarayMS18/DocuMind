"""
Local FastAPI application — 100% offline, no Azure required.
Uses: FAISS + BM25 (search), sentence-transformers (embeddings),
      Ollama/extractive (LLM), local filesystem (storage),
      ReportLab/python-pptx/openpyxl (document generation)
"""

import io
import uuid
import time
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.processing.document_processor import DocumentProcessor
from src.search.local_embedding_service import LocalEmbeddingService
from src.search.local_vector_store import LocalVectorStore
from src.llm.local_llm_service import LocalLLMService
from src.llm.gemini_service import GeminiService
from src.llm.grok_service import GrokService
from src.llm.groq_service import GroqService
from src.structuring.content_structurer import ContentStructurer
from src.template.template_engine import TemplateEngine
from src.generation.document_generator import DocumentGeneratorService
from src.automation.n8n_client import N8nClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Document Generator (Local Mode)",
    description="Template-Driven Document Generator — 100% local, no cloud required",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def preload_models():
    """Pre-load embedding model at startup so first upload is fast."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: svc("embedder")._get_model())
    logger.info("Embedding model pre-loaded at startup")

# ── Lazy services ─────────────────────────────────────────────────────────────

_svc: Dict[str, Any] = {}


def _get_best_llm():
    """Return best available LLM: Groq (free) > Gemini > Local extractive."""
    groq = GroqService()
    if groq.available:
        logger.info("Using Groq as LLM (free)")
        return groq
    gemini = GeminiService()
    if gemini.available:
        logger.info("Using Gemini as LLM")
        return gemini
    logger.info("Using local extractive fallback")
    return LocalLLMService()


def svc(name: str):
    if name not in _svc:
        if name == "processor":
            _svc[name] = DocumentProcessor()
        elif name == "embedder":
            _svc[name] = LocalEmbeddingService()
        elif name == "store":
            _svc[name] = LocalVectorStore()
        elif name == "llm":
            _svc[name] = _get_best_llm()
        elif name == "structurer":
            _svc[name] = ContentStructurer()
        elif name == "template":
            _svc[name] = TemplateEngine()
        elif name == "generator":
            _svc[name] = DocumentGeneratorService()
        elif name == "n8n":
            _svc[name] = N8nClient()
        elif name == "grok":
            _svc[name] = GrokService()
        elif name == "gemini":
            _svc[name] = GeminiService()
    return _svc[name]


# ── Request / Response models ─────────────────────────────────────────────────

class QueryGenerateRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    output_format: str = Field(default="pdf", pattern="^(pdf|pptx|xlsx)$")
    template: Optional[str] = None
    max_results: int = Field(default=5, ge=1, le=20)
    use_n8n: bool = False


class DataGenerateRequest(BaseModel):
    data: Dict[str, Any]
    output_format: str = Field(default="pdf", pattern="^(pdf|pptx|xlsx)$")
    template: Optional[str] = None
    use_n8n: bool = False


class StructureRequest(BaseModel):
    text: str
    query: Optional[str] = ""


class TemplateValidateRequest(BaseModel):
    template: str
    data: Dict[str, Any]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stream_file(content: bytes, mime: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _generate_doc(data: dict, fmt: str, template: Optional[str]):
    """Apply template + generate document bytes."""
    content_for_gen = None
    if template:
        mapping = svc("template").map_data_to_template(template, data, fmt)
        if not mapping.success:
            raise HTTPException(400, detail={"error": {"message": mapping.error_message}})
        content_for_gen = mapping.output

    result = svc("generator").generate(data, fmt, content_for_gen)
    if not result.success:
        raise HTTPException(500, detail={"error": {"message": result.error_message}})
    return result


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    store_stats = svc("store").get_stats()
    groq   = GroqService()
    gemini = GeminiService()

    if groq.available:
        llm_mode = "groq"
    elif gemini.available:
        llm_mode = "gemini"
    else:
        llm_mode = "extractive"

    return {
        "status": "healthy",
        "mode": "local",
        "version": "2.0.0",
        "documents_indexed": store_stats["total_chunks"],
        "llm_mode": llm_mode,
        "groq_available": groq.available,
        "gemini_available": gemini.available,
        "store": store_stats
    }


@app.get("/status", tags=["System"])
def system_status():
    return health()


# ── Document Upload & Indexing ────────────────────────────────────────────────

@app.post("/documents/upload", tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF, encrypt it, extract text, embed, and index locally."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail={"error": {"message": "Only PDF files supported"}})

    start = time.time()
    content = await file.read()
    doc_id = str(uuid.uuid4())

    # ── AES-256-GCM Encrypt the raw PDF bytes ────────────────────────────────
    aes = get_aes_service()
    encrypted_bytes = aes.encrypt_bytes(content)

    # Save encrypted file to disk
    enc_dir = Path("local_store/encrypted_docs")
    enc_dir.mkdir(parents=True, exist_ok=True)
    enc_path = enc_dir / f"{doc_id}.enc"
    enc_path.write_bytes(encrypted_bytes)
    logger.info(f"PDF encrypted → {enc_path} ({len(content)} → {len(encrypted_bytes)} bytes)")

    # Decrypt in-memory for processing (never write plaintext to disk)
    decrypted = aes.decrypt_bytes(encrypted_bytes)

    # Process PDF from decrypted bytes
    processor = svc("processor")
    result = processor.process_document(decrypted, doc_id)
    if not result.success:
        raise HTTPException(422, detail={"error": {"message": result.error_message}})

    # Attach document name to chunks
    for chunk in result.chunks:
        chunk.document_name = file.filename

    # Embed chunks
    embedder = svc("embedder")
    embeddings = embedder.generate_embeddings(result.chunks)

    # Attach vectors to chunks
    for chunk, emb in zip(result.chunks, embeddings):
        chunk.embedding = emb.vector

    # Index in FAISS
    store = svc("store")
    store.add_embeddings(embeddings, result.chunks)

    elapsed = int((time.time() - start) * 1000)
    logger.info(f"Indexed '{file.filename}': {len(result.chunks)} chunks in {elapsed}ms")

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "status": "indexed",
        "chunks_created": len(result.chunks),
        "processing_time_ms": elapsed,
        "encrypted": True,
        "encryption": "AES-256-GCM",
        "original_size_bytes": len(content),
        "encrypted_size_bytes": len(encrypted_bytes),
        "message": f"Successfully encrypted and indexed {len(result.chunks)} chunks from '{file.filename}'"
    }


@app.get("/documents/list", tags=["Documents"])
def list_documents():
    """Return list of all indexed documents with their chunk counts."""
    store = svc("store")
    if not store._metadata:
        return {"documents": [], "total_chunks": 0}

    # Group chunks by document name
    doc_map = {}
    for meta in store._metadata:
        name = meta.get("document_name", meta.get("document_id", "Unknown"))
        if name not in doc_map:
            doc_map[name] = {"name": name, "chunks": 0, "pages": set()}
        doc_map[name]["chunks"] += 1
        doc_map[name]["pages"].add(meta.get("page_number", 0))

    docs = []
    for name, info in doc_map.items():
        docs.append({
            "name": name,
            "chunks": info["chunks"],
            "pages": len(info["pages"])
        })

    return {"documents": docs, "total_chunks": len(store._metadata)}


# ── Query (RAG) ───────────────────────────────────────────────────────────────

@app.post("/query", tags=["Query"])
def query_documents(query: str, max_results: int = 5):
    """Search indexed documents and return answer with sources."""
    store = svc("store")
    embedder = svc("embedder")

    # Embed query
    q_emb = embedder.embed_query(query)

    # Hybrid search
    results = store.hybrid_search(query, q_emb.vector, max_results)

    if not results:
        return {
            "answer": "No documents found. Please upload PDFs first using /documents/upload",
            "sources": [],
            "confidence_score": 0.0
        }

    # Generate answer
    llm = svc("llm")
    response = llm.generate_response(query, results)

    return {
        "answer": response.text,
        "sources": [
            {
                "document_name": s.document_name,
                "page_number": s.page_number,
                "text_excerpt": s.text_excerpt[:300],
                "relevance_score": s.relevance_score
            }
            for s in response.sources
        ],
        "confidence_score": response.confidence_score,
        "model": response.model_name,
        "processing_time_ms": response.processing_time_ms
    }


# ── Document Generation ───────────────────────────────────────────────────────

@app.post("/generate/from-query", tags=["Generate"])
async def generate_from_query(req: QueryGenerateRequest):
    """Query RAG → Gemini Structure → Generate PDF/PPT/Excel."""
    store = svc("store")
    embedder = svc("embedder")

    # Step 1: Search
    q_emb = embedder.embed_query(req.query)
    results = store.hybrid_search(req.query, q_emb.vector, req.max_results)

    if not results:
        raise HTTPException(400, detail={"error": {"message": "No documents indexed. Upload a PDF first."}})

    # Step 2: Build raw context from search results
    context = "\n\n".join([
        f"[{getattr(r,'document_name','Doc')}, Page {getattr(r,'page_number',0)}]:\n{getattr(r,'text','')}"
        for r in results[:8]
    ])

    # Step 3: Use best available LLM to structure intelligently (Grok > Gemini > fallback)
    ai = svc("llm")
    data = {}
    if hasattr(ai, 'structure_for_document'):
        data = ai.structure_for_document(req.query, context)

    # Fallback: use basic structurer if AI failed or unavailable
    if not data or not data.get("title"):
        llm_resp = ai.generate_response(req.query, results)
        sources_list = [
            {"document_name": s.document_name, "text_excerpt": s.text_excerpt}
            for s in llm_resp.sources
        ]
        structured = svc("structurer").structure_from_llm_response(llm_resp.text, sources_list)
        data = structured.to_dict()

    if req.use_n8n:
        n8n_result = await svc("n8n").trigger_document_generation(data, req.template, req.output_format)
        return {"status": "triggered", "n8n_success": n8n_result.success,
                "message": n8n_result.error_message or "Workflow triggered", "structured_data": data}

    result = _generate_doc(data, req.output_format, req.template)
    return _stream_file(result.content, result.mime_type, result.filename)

    result = _generate_doc(data, req.output_format, req.template)
    return _stream_file(result.content, result.mime_type, result.filename)


@app.post("/generate/from-data", tags=["Generate"])
async def generate_from_data(req: DataGenerateRequest):
    """Structured JSON → Generate PDF/PPT/Excel."""
    if req.use_n8n:
        n8n_result = await svc("n8n").trigger_document_generation(req.data, req.template, req.output_format)
        return {"status": "triggered", "n8n_success": n8n_result.success,
                "message": n8n_result.error_message or "Workflow triggered"}

    result = _generate_doc(req.data, req.output_format, req.template)
    return _stream_file(result.content, result.mime_type, result.filename)


@app.post("/generate/upload-and-generate", tags=["Generate"])
async def upload_and_generate(
    file: UploadFile = File(...),
    output_format: str = Form(default="pdf"),
    template_file: Optional[UploadFile] = File(default=None)
):
    """Upload PDF → Extract → Gemini Structure → Generate output document."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail={"error": {"message": "Only PDF files supported"}})

    content = await file.read()
    doc_id = str(uuid.uuid4())

    # Step 1: Extract text from PDF
    proc = svc("processor")
    proc_result = proc.process_document(content, doc_id)
    if not proc_result.success:
        raise HTTPException(422, detail={"error": {"message": proc_result.error_message}})

    # Step 2: Use best available LLM to structure intelligently
    ai = svc("llm")
    data = {}
    if hasattr(ai, 'structure_for_document'):
        data = ai.structure_for_document(
            f"Structure this document: {file.filename}",
            proc_result.text[:6000]
        )

    # Fallback to basic structurer
    if not data or not data.get("title"):
        structured = svc("structurer").structure_rag_output(proc_result.text, file.filename)
        data = structured.to_dict()

    # Step 3: Custom template
    custom_template = None
    if template_file:
        tmpl_bytes = await template_file.read()
        custom_template = tmpl_bytes.decode("utf-8")

    base_name = file.filename.replace(".pdf", "")
    result = _generate_doc(data, output_format, custom_template)
    filename = f"{base_name}.{output_format}"
    return _stream_file(result.content, result.mime_type, filename)


# ── Template & Structuring ────────────────────────────────────────────────────

@app.post("/structure/text", tags=["Tools"])
def structure_text(req: StructureRequest):
    structured = svc("structurer").structure_rag_output(req.text, req.query or "")
    return {"structured_data": structured.to_dict()}


@app.post("/template/validate", tags=["Tools"])
def validate_template(req: TemplateValidateRequest):
    result = svc("template").validate_template(req.template, req.data)
    return {"valid": result.valid, "missing_fields": result.missing_fields,
            "extra_fields": result.extra_fields, "message": result.message}


@app.get("/template/default/{format_type}", tags=["Tools"])
def get_default_template(format_type: str):
    if format_type not in ("pdf", "ppt", "excel"):
        raise HTTPException(400, detail={"error": {"message": f"Unsupported format: {format_type}"}})
    return {"format": format_type, "template": svc("template").get_default_template(format_type)}


@app.get("/n8n/workflow-definition", tags=["Automation"])
def get_n8n_workflow():
    return svc("n8n").get_n8n_workflow_json()


@app.post("/webhook/generate", tags=["Automation"])
async def webhook_generate(req: DataGenerateRequest):
    return await generate_from_data(req)


# ── Settings ──────────────────────────────────────────────────────────────────

class GeminiKeyRequest(BaseModel):
    api_key: str
    provider: str = "grok"   # "grok" or "gemini"


@app.post("/settings/gemini-key", tags=["Settings"])
def save_api_key(req: GeminiKeyRequest):
    """Save Grok or Gemini API key to .env file."""
    env_path = Path(".env")
    key = req.api_key.strip()
    provider = req.provider.lower()

    # Determine env var name
    env_var = "GROQ_API_KEY" if provider == "groq" else ("GROK_API_KEY" if provider == "grok" else "GEMINI_API_KEY")

    if env_path.exists():
        content = env_path.read_text()
        import re
        if f"{env_var}=" in content:
            content = re.sub(rf'{env_var}=.*', f'{env_var}={key}', content)
        else:
            content += f"\n{env_var}={key}\n"
        env_path.write_text(content)
    else:
        env_path.write_text(f"{env_var}={key}\n")

    # Apply immediately without restart
    import os
    os.environ[env_var] = key

    # Clear cached LLM services so they reinitialize with new key
    for k in ["llm", "grok", "gemini", "groq"]:
        _svc.pop(k, None)

    # Verify it works
    if provider == "groq":
        test = GroqService()
        ok = test.available
    elif provider == "grok":
        test = GrokService()
        ok = test.available
    else:
        test = GeminiService()
        ok = test.available

    logger.info(f"{env_var} saved. Available: {ok}")
    return {
        "status": "saved",
        "provider": provider,
        "active": ok,
        "message": f"{'✅ ' + provider.capitalize() + ' AI is now active!' if ok else '❌ Key saved but connection failed — check the key'}"
    }


from src.security.aes_service import get_aes_service


# ── AES Encryption Endpoints ──────────────────────────────────────────────────

class AESEncryptRequest(BaseModel):
    text: str = Field(..., min_length=1)


class AESDecryptRequest(BaseModel):
    ciphertext: str = Field(..., min_length=1)


@app.post("/security/encrypt", tags=["Security"])
def encrypt_text(req: AESEncryptRequest):
    """Encrypt text using AES-256-GCM."""
    aes = get_aes_service()
    result = aes.encrypt_text(req.text)
    if not result.success:
        raise HTTPException(500, detail={"error": {"message": result.error}})
    return {
        "success": True,
        "ciphertext": result.ciphertext_b64,
        "iv": result.iv_b64,
        "key_preview": result.key_b64[:16] + "...",
        "algorithm": result.algorithm,
        "key_size_bits": result.key_size_bits,
        "iv_size_bits": result.iv_size_bits,
        "original_size_bytes": result.original_size,
        "encrypted_size_bytes": result.encrypted_size
    }


@app.post("/security/decrypt", tags=["Security"])
def decrypt_text(req: AESDecryptRequest):
    """Decrypt AES-256-GCM ciphertext."""
    aes = get_aes_service()
    result = aes.decrypt_text(req.ciphertext)
    if not result.success:
        raise HTTPException(400, detail={"error": {"message": "Decryption failed — invalid ciphertext or wrong key"}})
    return {"success": True, "plaintext": result.plaintext}


@app.get("/security/info", tags=["Security"])
def get_encryption_info():
    """Get AES encryption configuration details."""
    aes = get_aes_service()
    return aes.get_key_info()


@app.post("/security/encrypt-document", tags=["Security"])
async def encrypt_document(file: UploadFile = File(...)):
    """Encrypt an uploaded file using AES-256-GCM and return encrypted bytes."""
    content = await file.read()
    aes = get_aes_service()
    encrypted = aes.encrypt_bytes(content)
    encrypted_b64 = base64.b64encode(encrypted).decode()
    return {
        "success": True,
        "filename": file.filename,
        "original_size_bytes": len(content),
        "encrypted_size_bytes": len(encrypted),
        "encrypted_b64": encrypted_b64,
        "algorithm": "AES-256-GCM",
        "note": "Store the encrypted_b64 securely. Use /security/decrypt-document to recover."
    }


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.local_main:app", host="0.0.0.0", port=8000, reload=True)

