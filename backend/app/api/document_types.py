from __future__ import annotations

import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DocumentType
from app.schemas import DocumentTypeCreate, DocumentTypeResponse, DocumentTypeUpdate

router = APIRouter(prefix="/document-types", tags=["document-types"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@router.get("/", response_model=List[DocumentTypeResponse])
async def list_document_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentType).order_by(DocumentType.name))
    return result.scalars().all()


@router.post("/", response_model=DocumentTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_document_type(data: DocumentTypeCreate, db: AsyncSession = Depends(get_db)):
    slug = _slugify(data.name)
    existing = await db.execute(select(DocumentType).where(DocumentType.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Document type '{data.name}' already exists")

    dt = DocumentType(name=data.name, slug=slug)
    db.add(dt)
    await db.flush()
    await db.refresh(dt)
    return dt


@router.get("/{dt_id}", response_model=DocumentTypeResponse)
async def get_document_type(dt_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentType).where(DocumentType.id == dt_id))
    dt = result.scalar_one_or_none()
    if dt is None:
        raise HTTPException(status_code=404, detail="Document type not found")
    return dt


@router.delete("/{dt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_type(dt_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocumentType).where(DocumentType.id == dt_id))
    dt = result.scalar_one_or_none()
    if dt is None:
        raise HTTPException(status_code=404, detail="Document type not found")
    await db.delete(dt)
    await db.flush()
