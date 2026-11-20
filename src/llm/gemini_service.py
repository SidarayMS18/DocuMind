"""
Gemini LLM service — uses Google Gemini API (free tier).
Get your free API key at: https://aistudio.google.com/app/apikey
"""

import logging
import time
import os
import re
import json
from dataclasses import dataclass
from typing import List, Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class GeminiResponse:
    text: str
    confidence_score: float
    grounded: bool
    sources: List[Any]
    processing_time_ms: int
    model_name: str


class GeminiService:
    MODEL = "gemini-2.0-flash-lite"  # highest free quota model

    def __init__(self, api_key: Optional[str] = None):
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self._client = None

        if self.api_key:
            try:
                # Try new SDK first
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                self._sdk = "new"
                logger.info(f"Gemini (new SDK) initialized: {self.MODEL}")
            except Exception:
                try:
                    # Fallback to old SDK
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=self.api_key)
                    self._client = genai_old.GenerativeModel("gemini-1.5-flash")
                    self._sdk = "old"
                    logger.info("Gemini (old SDK) initialized: gemini-1.5-flash")
                except Exception as e:
                    logger.error(f"Gemini init failed: {e}")
                    self._client = None
        else:
            logger.warning("GEMINI_API_KEY not set")

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate_response(self, query: str, search_results: List[Any]) -> GeminiResponse:
        start = time.time()

        if not search_results:
            return GeminiResponse(
                text="No relevant documents found. Please upload documents first.",
                confidence_score=0.0, grounded=False, sources=[],
                processing_time_ms=0, model_name=self.MODEL
            )

        context = self._build_context(search_results)
        raw = self._call(query, context) if self._client else None

        if raw is None:
            # Quota hit or unavailable — use extractive fallback
            answer = self._extractive(query, search_results)
            model_used = "extractive (quota exceeded)"
            conf = 0.6
        else:
            answer = raw
            model_used = self.MODEL
            conf = 0.92

        return GeminiResponse(
            text=answer,
            confidence_score=conf,
            grounded=True,
            sources=self._build_sources(search_results),
            processing_time_ms=int((time.time() - start) * 1000),
            model_name=model_used
        )

    def structure_for_document(self, query: str, context: str) -> Dict[str, Any]:
        if not self._client:
            return {}

        prompt = f"""You are an expert document analyst.
Read the context and return ONLY a valid JSON object (no markdown, no code fences):
{{
  "title": "clear descriptive title",
  "abstract": "3-4 sentence comprehensive summary",
  "introduction": "detailed introduction paragraph",
  "methodology": "detailed methodology paragraph",
  "results": "detailed results paragraph",
  "conclusion": "strong conclusion paragraph",
  "points": ["specific finding 1","specific finding 2","specific finding 3","specific finding 4","specific finding 5"]
}}

Rules: Use ONLY info from context. Be specific. Each section 2-4 sentences minimum.

=== CONTEXT ===
{context[:5000]}

=== QUERY ===
{query}

JSON only:"""

        try:
            raw = None
            for model in [self.MODEL, "gemini-1.5-flash-8b", "gemini-1.5-flash"]:
                try:
                    raw = self._generate_text(prompt, model)
                    break
                except Exception as e:
                    if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                        continue
                    raise
            if not raw:
                return {}
            raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'^```\s*',     '', raw, flags=re.MULTILINE)
            raw = re.sub(r'\s*```$',     '', raw, flags=re.MULTILINE)
            result = json.loads(raw.strip())
            logger.info(f"Gemini structured: '{result.get('title','')[:60]}'")
            return result
        except Exception as e:
            logger.error(f"Gemini structure failed: {e}")
            return {}

    def _call(self, query: str, context: str) -> str:
        prompt = f"""Answer based ONLY on the document context below.
Be accurate and well-structured. Use bullet points where helpful.

=== CONTEXT ===
{context}

=== QUESTION ===
{query}

=== ANSWER ==="""
        # Try main model, fallback to lite on quota error
        for model in [self.MODEL, "gemini-1.5-flash-8b", "gemini-1.0-pro"]:
            try:
                return self._generate_text(prompt, model)
            except Exception as e:
                err = str(e)
                if "RESOURCE_EXHAUSTED" in err or "429" in err or "quota" in err.lower():
                    logger.warning(f"Quota exceeded on {model}, trying next model...")
                    continue
                logger.error(f"Gemini call failed on {model}: {e}")
                return None
        # All models exhausted
        logger.warning("All Gemini models quota exceeded — using extractive fallback")
        self._client = None
        return None

    def _generate_text(self, prompt: str, model: str = None) -> str:
        """Generate text using whichever SDK is available."""
        model = model or self.MODEL
        if self._sdk == "new":
            from google import genai
            resp = self._client.models.generate_content(
                model=model,
                contents=prompt
            )
            return resp.text
        else:
            # old SDK — model is set at init time
            resp = self._client.generate_content(prompt)
            return resp.text

    def _build_context(self, results: List[Any]) -> str:
        parts = []
        for i, r in enumerate(results[:6], 1):
            parts.append(
                f"[Source {i} — {getattr(r,'document_name','Doc')}, "
                f"Page {getattr(r,'page_number',0)}]:\n{getattr(r,'text','')}"
            )
        return "\n\n---\n\n".join(parts)

    def _build_sources(self, results: List[Any]) -> List[Any]:
        return [type('Src', (), {
            'document_name':   getattr(r, 'document_name', 'Document'),
            'page_number':     getattr(r, 'page_number', 0),
            'text_excerpt':    getattr(r, 'text', '')[:300],
            'relevance_score': getattr(r, 'score', 0.0),
            'highlighted_image_url': None
        })() for r in results[:5]]

    def _extractive(self, query: str, results: List[Any]) -> str:
        """Smart extractive answer when API quota is hit."""
        if not results:
            return "No content found."

        query_words = set(query.lower().split()) - {'what','is','the','a','an','this','that','about','how','why','when','where'}
        
        scored = []
        for r in results[:6]:
            text = getattr(r, 'text', '')
            doc  = getattr(r, 'document_name', 'Doc')
            page = getattr(r, 'page_number', 0)
            for sent in re.split(r'(?<=[.!?])\s+', text.replace('\n', ' ')):
                sent = sent.strip()
                if len(sent) < 40:
                    continue
                sw = set(sent.lower().split())
                overlap = len(query_words & sw)
                if overlap > 0:
                    scored.append((overlap, sent, doc, page))

        scored.sort(reverse=True)
        top = scored[:6]

        if not top:
            r = results[0]
            return f"📄 From {getattr(r,'document_name','Document')}:\n\n{getattr(r,'text','')[:500]}\n\n---\n⚠️ Gemini quota exceeded — using extractive mode."

        # Group by document
        by_doc = {}
        for _, sent, doc, page in top:
            key = f"{doc} (Page {page})"
            by_doc.setdefault(key, []).append(sent)

        answer = "**Based on your documents:**\n\n"
        for doc_key, sents in list(by_doc.items())[:3]:
            answer += f"📄 **{doc_key}**\n"
            for s in sents[:2]:
                answer += f"• {s}\n"
            answer += "\n"

        answer += "---\n⚠️ *Gemini API quota exceeded — using extractive mode. Wait 1 minute or use Grok instead.*"
        return answer
