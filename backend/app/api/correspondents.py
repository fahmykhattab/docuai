from __future__ import annotations

import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Correspondent
from app.schemas import CorrespondentCreate, CorrespondentResponse, CorrespondentUpdate

router = APIRouter(prefix="/correspondents", tags=["correspondents"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@router.get("/", response_model=List[CorrespondentResponse])
async def list_correspondents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Correspondent).order_by(Correspondent.name))
    return result.scalars().all()


@router.post("/", response_model=CorrespondentResponse, status_code=status.HTTP_201_CREATED)
async def create_correspondent(data: CorrespondentCreate, db: AsyncSession = Depends(get_db)):
    slug = _slugify(data.name)
    existing = await db.execute(select(Correspondent).where(Correspondent.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Correspondent '{data.name}' already exists")

    corr = Correspondent(name=data.name, slug=slug)
    db.add(corr)
    await db.flush()
    await db.refresh(corr)
    return corr


@router.get("/{corr_id}", response_model=CorrespondentResponse)
async def get_correspondent(corr_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Correspondent).where(Correspondent.id == corr_id))
    corr = result.scalar_one_or_none()
    if corr is None:
        raise HTTPException(status_code=404, detail="Correspondent not found")
    return corr


@router.delete("/{corr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_correspondent(corr_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Correspondent).where(Correspondent.id == corr_id))
    corr = result.scalar_one_or_none()
    if corr is None:
        raise HTTPException(status_code=404, detail="Correspondent not found")
    await db.delete(corr)
    await db.flush()
