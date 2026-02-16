from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import (
    Correspondent,
    CustomField,
    Document,
    DocumentTag,
    DocumentType,
    Tag,
)

router = APIRouter(prefix="/backup", tags=["backup"])
logger = logging.getLogger(__name__)
settings = get_settings()

BACKUP_DIR = os.environ.get("DOCUAI_BACKUP_DIR", "/data/backups")


class BackupInfo(BaseModel):
    filename: str
    type: str
    size: int
    created_at: str


class BackupListResponse(BaseModel):
    backups: List[BackupInfo]
    total_size: int
    backup_dir: str


class ExportDocumentItem(BaseModel):
    id: str
    title: Optional[str]
    original_filename: str
    content: Optional[str]
    file_path: str
    status: str
    mime_type: Optional[str]
    created_date: Optional[str]
    added_date: str
    document_type: Optional[str]
    correspondent: Optional[str]
    tags: List[str]
    custom_fields: List[dict]


@router.get("/list", response_model=BackupListResponse)
async def list_backups():
    """List all available backups."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    backups = []
    total_size = 0

    for f in sorted(Path(BACKUP_DIR).iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and (f.suffix in (".gz", ".dump", ".json", ".zip")):
            stat = f.stat()
            total_size += stat.st_size

            # Detect type from filename
            btype = "unknown"
            if f.name.startswith("full_"):
                btype = "full"
            elif f.name.startswith("db_"):
                btype = "database"
            elif f.name.startswith("files_"):
                btype = "files"
            elif f.name.startswith("export_"):
                btype = "export"

            backups.append(BackupInfo(
                filename=f.name,
                type=btype,
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            ))

    return BackupListResponse(
        backups=backups,
        total_size=total_size,
        backup_dir=BACKUP_DIR,
    )


@router.post("/export-json")
async def export_documents_json(db: AsyncSession = Depends(get_db)):
    """Export all document metadata as a downloadable JSON file."""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    result = await db.execute(
        select(Document).order_by(Document.added_date)
    )
    docs = result.scalars().all()

    export_data = []
    for doc in docs:
        export_data.append({
            "id": str(doc.id),
            "title": doc.title,
            "original_filename": doc.original_filename,
            "content": doc.content,
            "file_path": doc.file_path,
            "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
            "mime_type": doc.mime_type,
            "page_count": doc.page_count,
            "file_size": doc.file_size,
            "created_date": doc.created_date.isoformat() if doc.created_date else None,
            "added_date": doc.added_date.isoformat() if doc.added_date else None,
            "modified_date": doc.modified_date.isoformat() if doc.modified_date else None,
            "document_type": doc.document_type.name if doc.document_type else None,
            "correspondent": doc.correspondent.name if doc.correspondent else None,
            "tags": [t.name for t in doc.tags],
            "custom_fields": [
                {"name": cf.field_name, "value": cf.field_value, "type": cf.field_type}
                for cf in doc.custom_fields
            ],
        })

    # Save to file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"export_{timestamp}.json"
    filepath = os.path.join(BACKUP_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "version": "1.0.0",
            "exported_at": datetime.utcnow().isoformat(),
            "document_count": len(export_data),
            "documents": export_data,
        }, f, indent=2, ensure_ascii=False)

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/json",
    )


@router.get("/download/{filename}")
async def download_backup(filename: str):
    """Download a specific backup file."""
    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(filename)
    filepath = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Backup file not found")

    return FileResponse(
        path=filepath,
        filename=safe_name,
        media_type="application/octet-stream",
    )


@router.delete("/delete/{filename}")
async def delete_backup(filename: str):
    """Delete a specific backup file."""
    safe_name = os.path.basename(filename)
    filepath = os.path.join(BACKUP_DIR, safe_name)

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Backup file not found")

    os.remove(filepath)
    return {"detail": f"Deleted {safe_name}"}


@router.get("/export-document/{doc_id}")
async def export_single_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Export a single document (metadata + original file) as JSON."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    export = {
        "id": str(doc.id),
        "title": doc.title,
        "original_filename": doc.original_filename,
        "content": doc.content,
        "file_path": doc.file_path,
        "status": doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        "mime_type": doc.mime_type,
        "created_date": doc.created_date.isoformat() if doc.created_date else None,
        "added_date": doc.added_date.isoformat() if doc.added_date else None,
        "document_type": doc.document_type.name if doc.document_type else None,
        "correspondent": doc.correspondent.name if doc.correspondent else None,
        "tags": [t.name for t in doc.tags],
        "custom_fields": [
            {"name": cf.field_name, "value": cf.field_value, "type": cf.field_type}
            for cf in doc.custom_fields
        ],
    }

    return export
