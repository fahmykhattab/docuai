from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates text embeddings using sentence-transformers (all-MiniLM-L6-v2)."""

    _model = None

    def __init__(self) -> None:
        pass

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            logger.info("Loading sentence-transformers model all-MiniLM-L6-v2...")
            from sentence_transformers import SentenceTransformer
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded successfully")
        return cls._model

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a 384-dim vector."""
        if not text or not text.strip():
            return [0.0] * 384
        model = self._load_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_chunks(self, chunks: List[str]) -> List[List[float]]:
        """Embed multiple text chunks at once."""
        if not chunks:
            return []
        model = self._load_model()
        embeddings = model.encode(chunks, normalize_embeddings=True, batch_size=32)
        return [e.tolist() for e in embeddings]

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks by character count."""
        if not text:
            return []
        chunks: list[str] = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start += chunk_size - overlap
        return chunks
