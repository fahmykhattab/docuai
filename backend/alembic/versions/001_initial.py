"""Initial migration — create all tables with pgvector extension.

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create document status enum
    op.execute("CREATE TYPE documentstatus AS ENUM ('pending', 'processing', 'done', 'error')")

    # Correspondents
    op.create_table(
        "correspondents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_correspondents_slug", "correspondents", ["slug"])

    # Document types
    op.create_table(
        "document_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(256), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_document_types_slug", "document_types", ["slug"])

    # Tags
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#3b82f6"),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"])

    # Documents (without embedding — added via raw SQL for vector type)
    op.execute("""
        CREATE TABLE documents (
            id UUID NOT NULL PRIMARY KEY,
            title VARCHAR(512),
            content TEXT,
            original_filename VARCHAR(512) NOT NULL,
            file_path VARCHAR(1024) NOT NULL,
            thumbnail_path VARCHAR(1024),
            document_type_id INTEGER REFERENCES document_types(id) ON DELETE SET NULL,
            correspondent_id INTEGER REFERENCES correspondents(id) ON DELETE SET NULL,
            created_date TIMESTAMPTZ,
            added_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            status documentstatus NOT NULL DEFAULT 'pending',
            embedding vector(384),
            page_count INTEGER,
            file_size BIGINT,
            mime_type VARCHAR(128)
        )
    """)

    op.create_index("ix_documents_title", "documents", ["title"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_added_date", "documents", ["added_date"])
    op.create_index("ix_documents_created_date", "documents", ["created_date"])

    # Full-text search index
    op.execute(
        "CREATE INDEX ix_documents_content_fts ON documents USING gin (to_tsvector('english', COALESCE(content, '')))"
    )
    # HNSW index for vector similarity search
    op.execute(
        "CREATE INDEX ix_documents_embedding_hnsw ON documents USING hnsw (embedding vector_cosine_ops)"
    )

    # Document-Tag association
    op.create_table(
        "document_tags",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
    )

    # Custom fields
    op.create_table(
        "custom_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(256), nullable=False),
        sa.Column("field_value", sa.Text(), nullable=True),
        sa.Column("field_type", sa.String(64), nullable=False, server_default="string"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_custom_fields_document_id", "custom_fields", ["document_id"])

    # Chat history
    op.create_table(
        "chat_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Processing logs
    op.create_table(
        "processing_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_processing_logs_document_id", "processing_logs", ["document_id"])


def downgrade() -> None:
    op.drop_table("processing_logs")
    op.drop_table("chat_history")
    op.drop_table("custom_fields")
    op.drop_table("document_tags")
    op.drop_table("documents")
    op.drop_table("tags")
    op.drop_table("document_types")
    op.drop_table("correspondents")
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP EXTENSION IF EXISTS vector")
