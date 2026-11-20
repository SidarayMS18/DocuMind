"""Local embedding service using sentence-transformers (no Azure needed)."""

import logging
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VectorEmbedding:
    """A vector embedding with metadata."""
    id: str
    vector: List[float]
    text: str
    metadata: dict


class LocalEmbeddingService:
    """Generate embeddings locally using sentence-transformers."""

    MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, small, good quality — 384 dims
    _cached_model = None  # Class-level cache — loads once, reused forever

    def __init__(self):
        self._model = None
        logger.info(f"LocalEmbeddingService initialized (model: {self.MODEL_NAME})")

    def _get_model(self):
        # Use class-level cache so model loads only once per process
        if LocalEmbeddingService._cached_model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model '{self.MODEL_NAME}'...")
            LocalEmbeddingService._cached_model = SentenceTransformer(self.MODEL_NAME)
            logger.info("Embedding model loaded and cached.")
        return LocalEmbeddingService._cached_model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return vectors.tolist()

    def embed_query(self, query: str) -> VectorEmbedding:
        vectors = self.embed_texts([query])
        return VectorEmbedding(
            id="query",
            vector=vectors[0],
            text=query,
            metadata={"type": "query", "model": self.MODEL_NAME}
        )

    def generate_embeddings(self, chunks) -> List[VectorEmbedding]:
        """Generate embeddings for document chunks."""
        texts = [c.text for c in chunks]
        vectors = self.embed_texts(texts)
        embeddings = []
        for chunk, vec in zip(chunks, vectors):
            embeddings.append(VectorEmbedding(
                id=chunk.id,
                vector=vec,
                text=chunk.text,
                metadata={
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number,
                    "chunk_id": chunk.id,
                    "model": self.MODEL_NAME
                }
            ))
        return embeddings
