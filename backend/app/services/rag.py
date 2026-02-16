from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Document
from app.schemas import ChatSource
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)
settings = get_settings()


class RAGService:
    """Retrieval-Augmented Generation for document Q&A."""

    def __init__(self) -> None:
        self.embedding_service = EmbeddingService()

    async def answer(self, question: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Answer a question using RAG:
        1. Embed the question
        2. Find top-5 similar documents via pgvector
        3. Build context
        4. Send to Ollama
        5. Return answer with sources
        """
        # 1. Embed the question
        query_embedding = self.embedding_service.embed_text(question)

        # 2. Find similar documents
        stmt = (
            select(
                Document,
                Document.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(Document.embedding.isnot(None))
            .order_by("distance")
            .limit(5)
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            return {
                "answer": "I don't have any documents to search through yet. Please upload some documents first.",
                "sources": [],
            }

        # 3. Build context from matched documents
        context_parts: list[str] = []
        sources: list[ChatSource] = []
        for doc, distance in rows:
            similarity = 1 - (distance if distance is not None else 1.0)
            if similarity < 0.1:
                continue
            snippet = (doc.content or "")[:800]
            title = doc.title or doc.original_filename
            context_parts.append(f"[Document: {title}]\n{snippet}")
            sources.append(ChatSource(
                doc_id=doc.id,
                title=title,
                snippet=snippet[:200],
            ))

        if not context_parts:
            return {
                "answer": "I couldn't find any relevant documents for your question. Try rephrasing or uploading more documents.",
                "sources": [],
            }

        context = "\n\n---\n\n".join(context_parts)

        # 4. Send to Ollama
        system_prompt = (
            "You are a helpful document assistant. Answer questions based ONLY on the provided document context. "
            "If the context doesn't contain enough information to answer the question, say so clearly. "
            "Always cite which document(s) you used in your answer. "
            "Be concise and accurate."
        )

        user_prompt = f"""Context from documents:
{context}

Question: {question}

Answer based on the documents above:"""

        try:
            response = httpx.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            answer_text = data.get("response", "Sorry, I couldn't generate an answer.")
        except httpx.ConnectError:
            logger.warning("Ollama not available for RAG")
            answer_text = (
                "The AI model is currently unavailable. Here are the most relevant documents I found:\n\n"
                + "\n".join(f"- {s.title}: {s.snippet}" for s in sources)
            )
        except Exception as e:
            logger.exception("Ollama RAG error: %s", e)
            answer_text = f"Error generating answer: {str(e)}"

        return {
            "answer": answer_text,
            "sources": sources,
        }
