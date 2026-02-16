from __future__ import annotations

import math
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import (
    Correspondent,
    CustomField,
    Document,
    DocumentStatus,
    DocumentTag,
    DocumentType,
    Tag,
)
from app.schemas import (
    DocumentCreate,
    DocumentListResponse,
    DocumentPaginatedResponse,
    DocumentResponse,
    DocumentUpdate,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    TagResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


def _get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.post("/upload", response_model=List[DocumentListResponse], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    results: list[Document] = []

    for upload in files:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        ext = _get_extension(upload.filename)
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Extension '.{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}",
            )

        content_bytes = await upload.read()
        if len(content_bytes) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload.filename}' exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
            )

        now = datetime.utcnow()
        year_month = now.strftime("%Y/%m")
        unique_name = f"{uuid.uuid4().hex}_{upload.filename}"
        relative_path = os.path.join(year_month, unique_name)
        abs_path = os.path.join(settings.MEDIA_DIR, relative_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(content_bytes)

        import magic
        mime = magic.from_buffer(content_bytes[:2048], mime=True)

        doc = Document(
            id=uuid.uuid4(),
            title=None,
            original_filename=upload.filename,
            file_path=relative_path,
            file_size=len(content_bytes),
            mime_type=mime,
            status=DocumentStatus.pending,
        )
        db.add(doc)
        await db.flush()
        results.append(doc)

    await db.commit()

    # Trigger Celery tasks
    from app.celery_app import celery_app
    for doc in results:
        celery_app.send_task("app.tasks.process.process_document", args=[str(doc.id)])

    return results


@router.get("/", response_model=DocumentPaginatedResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    tag_id: Optional[int] = Query(None),
    document_type_id: Optional[int] = Query(None),
    correspondent_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    sort_by: str = Query("added_date", pattern=r"^(added_date|modified_date|created_date|title)$"),
    sort_order: str = Query("desc", pattern=r"^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Document)
    count_query = select(func.count(Document.id))

    filters = []
    if tag_id is not None:
        query = query.join(DocumentTag, DocumentTag.document_id == Document.id)
        count_query = count_query.join(DocumentTag, DocumentTag.document_id == Document.id)
        filters.append(DocumentTag.tag_id == tag_id)
    if document_type_id is not None:
        filters.append(Document.document_type_id == document_type_id)
    if correspondent_id is not None:
        filters.append(Document.correspondent_id == correspondent_id)
    if status_filter is not None:
        filters.append(Document.status == status_filter)
    if date_from is not None:
        filters.append(Document.added_date >= date_from)
    if date_to is not None:
        filters.append(Document.added_date <= date_to)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    sort_col = getattr(Document, sort_by, Document.added_date)
    if sort_order == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    docs = result.scalars().all()

    return DocumentPaginatedResponse(
        items=[DocumentListResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if size else 0,
    )


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: uuid.UUID,
    data: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if data.title is not None:
        doc.title = data.title
    if data.document_type_id is not None:
        doc.document_type_id = data.document_type_id
    if data.correspondent_id is not None:
        doc.correspondent_id = data.correspondent_id
    if data.created_date is not None:
        doc.created_date = data.created_date

    if data.tag_ids is not None:
        # Remove existing tags
        await db.execute(
            DocumentTag.__table__.delete().where(DocumentTag.document_id == doc_id)
        )
        for tid in data.tag_ids:
            db.add(DocumentTag(document_id=doc_id, tag_id=tid))

    if data.custom_fields is not None:
        # Remove existing custom fields
        existing = await db.execute(
            select(CustomField).where(CustomField.document_id == doc_id)
        )
        for cf in existing.scalars().all():
            await db.delete(cf)
        for cf_data in data.custom_fields:
            db.add(CustomField(
                document_id=doc_id,
                field_name=cf_data.field_name,
                field_value=cf_data.field_value,
                field_type=cf_data.field_type,
            ))

    doc.modified_date = datetime.utcnow()
    await db.flush()

    # Re-fetch to get relationships
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one()
    return DocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove files from disk
    abs_path = os.path.join(settings.MEDIA_DIR, doc.file_path)
    if os.path.exists(abs_path):
        os.remove(abs_path)
    if doc.thumbnail_path:
        thumb_abs = os.path.join(settings.THUMBNAIL_DIR, doc.thumbnail_path)
        if os.path.exists(thumb_abs):
            os.remove(thumb_abs)

    await db.delete(doc)
    await db.flush()


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    abs_path = os.path.join(settings.MEDIA_DIR, doc.file_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=abs_path,
        filename=doc.original_filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.get("/{doc_id}/thumbnail")
async def get_thumbnail(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    abs_path = os.path.join(settings.THUMBNAIL_DIR, doc.thumbnail_path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Thumbnail file not found")

    return FileResponse(path=abs_path, media_type="image/png")


@router.post("/{doc_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = DocumentStatus.pending
    await db.flush()

    from app.celery_app import celery_app
    celery_app.send_task("app.tasks.process.reprocess_document", args=[str(doc_id)])

    return {"detail": "Reprocessing started", "document_id": str(doc_id)}


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    body: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    offset = (body.page - 1) * body.size
    items: list[SearchResultItem] = []

    if body.mode == "fulltext":
        ts_query = func.plainto_tsquery("english", body.query)
        stmt = (
            select(
                Document,
                func.ts_rank(
                    func.to_tsvector("english", func.coalesce(Document.content, "")),
                    ts_query,
                ).label("rank"),
            )
            .where(
                func.to_tsvector("english", func.coalesce(Document.content, "")).op("@@")(ts_query)
            )
            .order_by(func.ts_rank(
                func.to_tsvector("english", func.coalesce(Document.content, "")),
                ts_query,
            ).desc())
            .offset(offset)
            .limit(body.size)
        )
        result = await db.execute(stmt)
        rows = result.all()

        count_stmt = (
            select(func.count(Document.id))
            .where(
                func.to_tsvector("english", func.coalesce(Document.content, "")).op("@@")(ts_query)
            )
        )
        total = (await db.execute(count_stmt)).scalar() or 0

        for doc, rank in rows:
            snippet = (doc.content or "")[:200]
            items.append(SearchResultItem(
                id=doc.id,
                title=doc.title,
                original_filename=doc.original_filename,
                snippet=snippet,
                score=float(rank),
                tags=[TagResponse.model_validate(t) for t in doc.tags],
            ))

    elif body.mode == "semantic":
        from app.services.embeddings import EmbeddingService
        emb_service = EmbeddingService()
        query_embedding = emb_service.embed_text(body.query)

        stmt = (
            select(
                Document,
                Document.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(Document.embedding.isnot(None))
            .order_by("distance")
            .offset(offset)
            .limit(body.size)
        )
        result = await db.execute(stmt)
        rows = result.all()

        count_stmt = select(func.count(Document.id)).where(Document.embedding.isnot(None))
        total = (await db.execute(count_stmt)).scalar() or 0

        for doc, distance in rows:
            snippet = (doc.content or "")[:200]
            items.append(SearchResultItem(
                id=doc.id,
                title=doc.title,
                original_filename=doc.original_filename,
                snippet=snippet,
                score=float(1 - distance) if distance is not None else 0.0,
                tags=[TagResponse.model_validate(t) for t in doc.tags],
            ))

    else:  # hybrid
        from app.services.embeddings import EmbeddingService
        emb_service = EmbeddingService()
        query_embedding = emb_service.embed_text(body.query)
        ts_query = func.plainto_tsquery("english", body.query)

        # Full-text search results
        ft_stmt = (
            select(
                Document.id,
                func.ts_rank(
                    func.to_tsvector("english", func.coalesce(Document.content, "")),
                    ts_query,
                ).label("ft_rank"),
            )
            .where(
                func.to_tsvector("english", func.coalesce(Document.content, "")).op("@@")(ts_query)
            )
        )
        ft_result = await db.execute(ft_stmt)
        ft_scores = {row[0]: float(row[1]) for row in ft_result.all()}

        # Semantic search results
        sem_stmt = (
            select(
                Document.id,
                Document.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(Document.embedding.isnot(None))
        )
        sem_result = await db.execute(sem_stmt)
        sem_scores = {row[0]: float(1 - row[1]) if row[1] is not None else 0.0 for row in sem_result.all()}

        # Combine scores
        all_ids = set(ft_scores.keys()) | set(sem_scores.keys())
        combined: list[tuple[uuid.UUID, float]] = []
        for did in all_ids:
            ft = ft_scores.get(did, 0.0)
            sem = sem_scores.get(did, 0.0)
            # Normalize ft_rank (usually 0-1 range) and combine
            combined.append((did, ft * 0.4 + sem * 0.6))

        combined.sort(key=lambda x: x[1], reverse=True)
        total = len(combined)
        page_ids = [c[0] for c in combined[offset : offset + body.size]]
        score_map = {c[0]: c[1] for c in combined}

        if page_ids:
            docs_result = await db.execute(select(Document).where(Document.id.in_(page_ids)))
            docs_map = {d.id: d for d in docs_result.scalars().all()}
            for did in page_ids:
                doc = docs_map.get(did)
                if doc:
                    snippet = (doc.content or "")[:200]
                    items.append(SearchResultItem(
                        id=doc.id,
                        title=doc.title,
                        original_filename=doc.original_filename,
                        snippet=snippet,
                        score=score_map.get(did, 0.0),
                        tags=[TagResponse.model_validate(t) for t in doc.tags],
                    ))

    return SearchResponse(
        items=items,
        total=total,
        page=body.page,
        size=body.size,
        query=body.query,
    )
