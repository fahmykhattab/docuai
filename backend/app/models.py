from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    BigInteger,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    error = "error"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(512), nullable=True, index=True)
    content = Column(Text, nullable=True)
    original_filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    thumbnail_path = Column(String(1024), nullable=True)
    document_type_id = Column(Integer, ForeignKey("document_types.id", ondelete="SET NULL"), nullable=True)
    correspondent_id = Column(Integer, ForeignKey("correspondents.id", ondelete="SET NULL"), nullable=True)
    created_date = Column(DateTime(timezone=True), nullable=True)
    added_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.pending, nullable=False, index=True)
    embedding = Column(Vector(384), nullable=True)
    page_count = Column(Integer, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String(128), nullable=True)

    # Relationships
    document_type = relationship("DocumentType", back_populates="documents", lazy="selectin")
    correspondent = relationship("Correspondent", back_populates="documents", lazy="selectin")
    tags = relationship("Tag", secondary="document_tags", back_populates="documents", lazy="selectin")
    custom_fields = relationship("CustomField", back_populates="document", cascade="all, delete-orphan", lazy="selectin")
    processing_logs = relationship("ProcessingLog", back_populates="document", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("ix_documents_added_date", "added_date"),
        Index("ix_documents_created_date", "created_date"),
        Index("ix_documents_content_fts", func.to_tsvector("english", func.coalesce(content, "")), postgresql_using="gin"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    color = Column(String(7), default="#3b82f6", nullable=False)
    slug = Column(String(128), unique=True, nullable=False, index=True)

    documents = relationship("Document", secondary="document_tags", back_populates="tags", lazy="selectin")


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Correspondent(Base):
    __tablename__ = "correspondents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    slug = Column(String(256), unique=True, nullable=False, index=True)

    documents = relationship("Document", back_populates="correspondent", lazy="selectin")


class DocumentType(Base):
    __tablename__ = "document_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    slug = Column(String(256), unique=True, nullable=False, index=True)

    documents = relationship("Document", back_populates="document_type", lazy="selectin")


class CustomField(Base):
    __tablename__ = "custom_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(256), nullable=False)
    field_value = Column(Text, nullable=True)
    field_type = Column(String(64), default="string", nullable=False)

    document = relationship("Document", back_populates="custom_fields")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    step = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", back_populates="processing_logs")
