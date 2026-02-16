from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Document, DocumentStatus, DocumentType
from app.schemas import (
    DashboardStats,
    DocumentListResponse,
    MonthCount,
    StatusCount,
    TypeCount,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
settings = get_settings()


def _dir_size(path: str) -> int:
    total = 0
    if not os.path.exists(path):
        return 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    # Total documents
    total_result = await db.execute(select(func.count(Document.id)))
    total_documents = total_result.scalar() or 0

    # By status
    status_result = await db.execute(
        select(Document.status, func.count(Document.id))
        .group_by(Document.status)
    )
    by_status = [
        StatusCount(status=str(row[0].value) if hasattr(row[0], 'value') else str(row[0]), count=row[1])
        for row in status_result.all()
    ]

    # By type
    type_result = await db.execute(
        select(DocumentType.name, func.count(Document.id))
        .join(Document, Document.document_type_id == DocumentType.id)
        .group_by(DocumentType.name)
        .order_by(func.count(Document.id).desc())
        .limit(10)
    )
    by_type = [TypeCount(name=row[0], count=row[1]) for row in type_result.all()]

    # By month (last 12 months)
    month_result = await db.execute(
        select(
            func.to_char(Document.added_date, "YYYY-MM").label("month"),
            func.count(Document.id),
        )
        .group_by(func.to_char(Document.added_date, "YYYY-MM"))
        .order_by(func.to_char(Document.added_date, "YYYY-MM").desc())
        .limit(12)
    )
    by_month = [MonthCount(month=row[0], count=row[1]) for row in month_result.all()]

    # Recent documents
    recent_result = await db.execute(
        select(Document).order_by(Document.added_date.desc()).limit(10)
    )
    recent_docs = recent_result.scalars().all()
    recent_documents = [DocumentListResponse.model_validate(d) for d in recent_docs]

    # Storage used
    storage_used = _dir_size(settings.MEDIA_DIR) + _dir_size(settings.THUMBNAIL_DIR)

    return DashboardStats(
        total_documents=total_documents,
        by_status=by_status,
        by_type=by_type,
        by_month=by_month,
        recent_documents=recent_documents,
        storage_used=storage_used,
    )
