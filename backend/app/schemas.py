from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Pagination ──────────────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: List[Any] = []
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0


# ── Tag ─────────────────────────────────────────────────────────────────────

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    color: str = Field("#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")


class TagResponse(BaseModel):
    id: int
    name: str
    color: str
    slug: str

    model_config = {"from_attributes": True}


# ── Correspondent ───────────────────────────────────────────────────────────

class CorrespondentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)


class CorrespondentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)


class CorrespondentResponse(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


# ── DocumentType ────────────────────────────────────────────────────────────

class DocumentTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)


class DocumentTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)


class DocumentTypeResponse(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


# ── CustomField ─────────────────────────────────────────────────────────────

class CustomFieldCreate(BaseModel):
    field_name: str = Field(..., min_length=1, max_length=256)
    field_value: Optional[str] = None
    field_type: str = Field("string", max_length=64)


class CustomFieldResponse(BaseModel):
    id: int
    field_name: str
    field_value: Optional[str] = None
    field_type: str

    model_config = {"from_attributes": True}


# ── ProcessingLog ───────────────────────────────────────────────────────────

class ProcessingLogResponse(BaseModel):
    id: int
    step: str
    status: str
    message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Document ────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: Optional[str] = None
    tag_ids: List[int] = []
    document_type_id: Optional[int] = None
    correspondent_id: Optional[int] = None


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    tag_ids: Optional[List[int]] = None
    document_type_id: Optional[int] = None
    correspondent_id: Optional[int] = None
    created_date: Optional[datetime] = None
    custom_fields: Optional[List[CustomFieldCreate]] = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    content: Optional[str] = None
    original_filename: str
    file_path: str
    thumbnail_path: Optional[str] = None
    status: str
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_date: Optional[datetime] = None
    added_date: datetime
    modified_date: datetime
    document_type: Optional[DocumentTypeResponse] = None
    correspondent: Optional[CorrespondentResponse] = None
    tags: List[TagResponse] = []
    custom_fields: List[CustomFieldResponse] = []
    processing_logs: List[ProcessingLogResponse] = []

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    original_filename: str
    thumbnail_path: Optional[str] = None
    status: str
    page_count: Optional[int] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    added_date: datetime
    modified_date: datetime
    document_type: Optional[DocumentTypeResponse] = None
    correspondent: Optional[CorrespondentResponse] = None
    tags: List[TagResponse] = []

    model_config = {"from_attributes": True}


class DocumentPaginatedResponse(BaseModel):
    items: List[DocumentListResponse] = []
    total: int = 0
    page: int = 1
    size: int = 20
    pages: int = 0


# ── Search ──────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: str = Field("hybrid", pattern=r"^(fulltext|semantic|hybrid)$")
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


class SearchResultItem(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    original_filename: str
    snippet: Optional[str] = None
    score: float = 0.0
    tags: List[TagResponse] = []

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    items: List[SearchResultItem] = []
    total: int = 0
    page: int = 1
    size: int = 20
    query: str = ""


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


class ChatSource(BaseModel):
    doc_id: uuid.UUID
    title: Optional[str] = None
    snippet: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: List[ChatSource] = []


class ChatHistoryResponse(BaseModel):
    id: int
    question: str
    answer: str
    sources: Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard ───────────────────────────────────────────────────────────────

class StatusCount(BaseModel):
    status: str
    count: int


class TypeCount(BaseModel):
    name: str
    count: int


class MonthCount(BaseModel):
    month: str
    count: int


class DashboardStats(BaseModel):
    total_documents: int = 0
    by_status: List[StatusCount] = []
    by_type: List[TypeCount] = []
    by_month: List[MonthCount] = []
    recent_documents: List[DocumentListResponse] = []
    storage_used: int = 0
