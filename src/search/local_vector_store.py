"""Local FAISS + BM25 vector store (no Azure needed)."""

import json
import logging
import pickle
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

STORE_DIR = Path("local_store")
FAISS_INDEX_FILE = STORE_DIR / "faiss.index"
METADATA_FILE = STORE_DIR / "metadata.pkl"


@dataclass
class SearchResult:
    """A search result with text and metadata."""
    id: str
    text: str
    score: float
    document_name: str
    page_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalVectorStore:
    """FAISS-based local vector store with BM25 hybrid search."""

    def __init__(self):
        self._index = None          # FAISS index
        self._metadata: List[dict] = []   # parallel list of metadata
        self._texts: List[str] = []       # parallel list of texts
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        STORE_DIR.mkdir(exist_ok=True)
        if FAISS_INDEX_FILE.exists() and METADATA_FILE.exists():
            try:
                import faiss
                self._index = faiss.read_index(str(FAISS_INDEX_FILE))
                with open(METADATA_FILE, "rb") as f:
                    data = pickle.load(f)
                    self._metadata = data.get("metadata", [])
                    self._texts = data.get("texts", [])
                logger.info(f"Loaded local store: {len(self._texts)} chunks")
            except Exception as e:
                logger.warning(f"Could not load existing store: {e}")
                self._index = None
                self._metadata = []
                self._texts = []

    def _save(self):
        try:
            import faiss
            STORE_DIR.mkdir(exist_ok=True)
            faiss.write_index(self._index, str(FAISS_INDEX_FILE))
            with open(METADATA_FILE, "wb") as f:
                pickle.dump({"metadata": self._metadata, "texts": self._texts}, f)
            logger.info(f"Saved local store: {len(self._texts)} chunks")
        except Exception as e:
            logger.error(f"Failed to save store: {e}")

    # ── Indexing ──────────────────────────────────────────────────────────────

    def add_embeddings(self, embeddings, chunks):
        """Add embeddings + chunks to the FAISS index."""
        import faiss

        vectors = np.array([e.vector for e in embeddings], dtype=np.float32)
        dim = vectors.shape[1]

        if self._index is None:
            self._index = faiss.IndexFlatIP(dim)  # Inner product (cosine after norm)

        # Normalize for cosine similarity
        faiss.normalize_L2(vectors)
        self._index.add(vectors)

        for chunk, emb in zip(chunks, embeddings):
            self._metadata.append({
                "id": chunk.id,
                "document_id": chunk.document_id,
                "document_name": getattr(chunk, "document_name", chunk.document_id),
                "page_number": chunk.page_number,
                "chunk_metadata": chunk.metadata or {}
            })
            self._texts.append(chunk.text)

        self._save()
        logger.info(f"Indexed {len(chunks)} chunks. Total: {len(self._texts)}")

    # ── Search ────────────────────────────────────────────────────────────────

    def vector_search(self, query_vector: List[float], k: int = 5) -> List[SearchResult]:
        if self._index is None or len(self._texts) == 0:
            return []

        import faiss
        vec = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(vec)
        k = min(k, len(self._texts))
        scores, indices = self._index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self._metadata[idx]
            results.append(SearchResult(
                id=meta["id"],
                text=self._texts[idx],
                score=float(score),
                document_name=meta.get("document_name", "unknown"),
                page_number=meta.get("page_number", 0),
                metadata=meta
            ))
        return results

    def bm25_search(self, query: str, k: int = 5) -> List[SearchResult]:
        if not self._texts:
            return []
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [t.lower().split() for t in self._texts]
            bm25 = BM25Okapi(tokenized)
            scores = bm25.get_scores(query.lower().split())
            top_k = min(k, len(self._texts))
            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in top_indices:
                if scores[idx] <= 0:
                    continue
                meta = self._metadata[idx]
                results.append(SearchResult(
                    id=meta["id"],
                    text=self._texts[idx],
                    score=float(scores[idx]),
                    document_name=meta.get("document_name", "unknown"),
                    page_number=meta.get("page_number", 0),
                    metadata=meta
                ))
            return results
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def hybrid_search(self, query: str, query_vector: List[float], k: int = 5) -> List[SearchResult]:
        """Combine FAISS + BM25 with Reciprocal Rank Fusion."""
        vec_results = self.vector_search(query_vector, k * 2)
        bm25_results = self.bm25_search(query, k * 2)

        # RRF scoring
        rrf_scores: Dict[str, float] = {}
        id_to_result: Dict[str, SearchResult] = {}

        for rank, r in enumerate(vec_results):
            rrf_scores[r.id] = rrf_scores.get(r.id, 0) + 1 / (60 + rank + 1)
            id_to_result[r.id] = r

        for rank, r in enumerate(bm25_results):
            rrf_scores[r.id] = rrf_scores.get(r.id, 0) + 1 / (60 + rank + 1)
            id_to_result[r.id] = r

        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:k]
        results = []
        for rid in sorted_ids:
            r = id_to_result[rid]
            r.score = rrf_scores[rid]
            results.append(r)
        return results

    def get_stats(self) -> dict:
        return {
            "total_chunks": len(self._texts),
            "index_ready": self._index is not None,
            "store_path": str(STORE_DIR.absolute())
        }

    def clear(self):
        self._index = None
        self._metadata = []
        self._texts = []
        for f in [FAISS_INDEX_FILE, METADATA_FILE]:
            if f.exists():
                f.unlink()
        logger.info("Local store cleared")
