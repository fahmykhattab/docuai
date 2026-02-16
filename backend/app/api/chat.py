from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ChatHistory
from app.schemas import ChatHistoryResponse, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    from app.services.rag import RAGService

    rag = RAGService()
    try:
        result = await rag.answer(body.question, db)
    except Exception as e:
        logger.exception("RAG service error")
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    # Persist to history
    history = ChatHistory(
        question=body.question,
        answer=result["answer"],
        sources=[s.model_dump() if hasattr(s, "model_dump") else s for s in result.get("sources", [])],
    )
    db.add(history)
    await db.flush()

    return ChatResponse(
        answer=result["answer"],
        sources=result.get("sources", []),
    )


@router.get("/history", response_model=List[ChatHistoryResponse])
async def get_chat_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
