from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import get_settings
from app.models import (
    Correspondent,
    CustomField,
    Document,
    DocumentStatus,
    DocumentTag,
    DocumentType,
    ProcessingLog,
    Tag,
)

logger = logging.getLogger(__name__)
settings = get_settings()


_sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)


def _get_sync_session() -> Session:
    return Session(_sync_engine)


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "untitled"


def _log_step(session: Session, document_id: uuid.UUID, step: str, status: str, message: str = "") -> None:
    log = ProcessingLog(
        document_id=document_id,
        step=step,
        status=status,
        message=message,
    )
    session.add(log)
    session.flush()


@celery_app.task(name="app.tasks.process.process_document", bind=True, max_retries=3)
def process_document(self, document_id: str) -> dict:
    """Full document processing pipeline: OCR → classify → fields → embeddings → thumbnail."""
    doc_uuid = uuid.UUID(document_id)
    session = _get_sync_session()

    try:
        doc = session.execute(select(Document).where(Document.id == doc_uuid)).scalar_one_or_none()
        if doc is None:
            logger.error("Document %s not found", document_id)
            return {"status": "error", "message": "Document not found"}

        doc.status = DocumentStatus.processing
        session.flush()
        _log_step(session, doc_uuid, "start", "info", "Processing started")

        # ── Step 1: OCR ─────────────────────────────────────────────────────
        try:
            from app.services.ocr import OCRService
            ocr = OCRService()
            text = ocr.extract_text(doc.file_path)
            doc.content = text
            session.flush()
            _log_step(session, doc_uuid, "ocr", "success", f"Extracted {len(text)} characters")
        except Exception as e:
            logger.exception("OCR failed for %s", document_id)
            _log_step(session, doc_uuid, "ocr", "error", str(e))
            doc.status = DocumentStatus.error
            session.commit()
            return {"status": "error", "step": "ocr", "message": str(e)}

        # ── Step 2: Classification ──────────────────────────────────────────
        try:
            from app.services.classifier import ClassifierService
            classifier = ClassifierService()

            existing_tags = [t.name for t in session.execute(select(Tag)).scalars().all()]
            existing_types = [t.name for t in session.execute(select(DocumentType)).scalars().all()]
            existing_corr = [c.name for c in session.execute(select(Correspondent)).scalars().all()]

            result = classifier.classify(text, existing_tags, existing_types, existing_corr)

            if result.title:
                doc.title = result.title

            if result.date:
                try:
                    doc.created_date = datetime.fromisoformat(result.date)
                except ValueError:
                    pass

            # Document type
            if result.document_type:
                slug = _slugify(result.document_type)
                dt = session.execute(select(DocumentType).where(DocumentType.slug == slug)).scalar_one_or_none()
                if dt is None:
                    dt = DocumentType(name=result.document_type, slug=slug)
                    session.add(dt)
                    session.flush()
                doc.document_type_id = dt.id

            # Correspondent
            if result.correspondent:
                slug = _slugify(result.correspondent)
                corr = session.execute(select(Correspondent).where(Correspondent.slug == slug)).scalar_one_or_none()
                if corr is None:
                    corr = Correspondent(name=result.correspondent, slug=slug)
                    session.add(corr)
                    session.flush()
                doc.correspondent_id = corr.id

            # Tags
            for tag_name in result.tags:
                slug = _slugify(tag_name)
                if not slug:
                    continue
                tag = session.execute(select(Tag).where(Tag.slug == slug)).scalar_one_or_none()
                if tag is None:
                    tag = Tag(name=tag_name, slug=slug, color="#3b82f6")
                    session.add(tag)
                    session.flush()
                # Check if association exists
                existing_assoc = session.execute(
                    select(DocumentTag).where(
                        DocumentTag.document_id == doc_uuid,
                        DocumentTag.tag_id == tag.id,
                    )
                ).scalar_one_or_none()
                if existing_assoc is None:
                    session.add(DocumentTag(document_id=doc_uuid, tag_id=tag.id))
                    session.flush()

            session.flush()
            _log_step(session, doc_uuid, "classify", "success", f"Title: {result.title}")
        except Exception as e:
            logger.exception("Classification failed for %s", document_id)
            _log_step(session, doc_uuid, "classify", "error", str(e))
            # Non-fatal: continue processing

        # ── Step 3: Field Extraction ────────────────────────────────────────
        try:
            from app.services.fields import FieldExtractor
            extractor = FieldExtractor()
            fields = extractor.extract_fields(text)
            for field in fields:
                cf = CustomField(
                    document_id=doc_uuid,
                    field_name=field.name,
                    field_value=field.value,
                    field_type=field.type,
                )
                session.add(cf)
            session.flush()
            _log_step(session, doc_uuid, "fields", "success", f"Extracted {len(fields)} fields")
        except Exception as e:
            logger.exception("Field extraction failed for %s", document_id)
            _log_step(session, doc_uuid, "fields", "error", str(e))

        # ── Step 4: Generate Embeddings ─────────────────────────────────────
        try:
            from app.services.embeddings import EmbeddingService
            emb_service = EmbeddingService()
            embedding = emb_service.embed_text(text)
            doc.embedding = embedding
            session.flush()
            _log_step(session, doc_uuid, "embeddings", "success", "Generated 384-dim embedding")
        except Exception as e:
            logger.exception("Embedding generation failed for %s", document_id)
            _log_step(session, doc_uuid, "embeddings", "error", str(e))

        # ── Step 5: Generate Thumbnail ──────────────────────────────────────
        try:
            from app.services.pdf import PDFService
            pdf_service = PDFService()

            thumb_relative = f"{doc_uuid.hex}.png"
            thumb_abs = os.path.join(settings.THUMBNAIL_DIR, thumb_relative)
            os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)

            success = pdf_service.generate_thumbnail(doc.file_path, thumb_abs)
            if success:
                doc.thumbnail_path = thumb_relative

            file_info = pdf_service.get_file_info(doc.file_path)
            doc.page_count = file_info.get("pages", 0)
            if not doc.file_size:
                doc.file_size = file_info.get("size", 0)
            if not doc.mime_type:
                doc.mime_type = file_info.get("mime_type", "")

            session.flush()
            _log_step(session, doc_uuid, "thumbnail", "success", "Thumbnail generated")
        except Exception as e:
            logger.exception("Thumbnail generation failed for %s", document_id)
            _log_step(session, doc_uuid, "thumbnail", "error", str(e))

        # ── Done ────────────────────────────────────────────────────────────
        doc.status = DocumentStatus.done
        doc.modified_date = datetime.utcnow()
        _log_step(session, doc_uuid, "complete", "success", "Processing complete")
        session.commit()

        logger.info("Document %s processed successfully", document_id)
        return {"status": "done", "document_id": document_id}

    except Exception as e:
        logger.exception("Unhandled error processing document %s", document_id)
        try:
            doc = session.execute(select(Document).where(Document.id == doc_uuid)).scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.error
                _log_step(session, doc_uuid, "fatal", "error", str(e))
                session.commit()
        except Exception:
            session.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        session.close()


@celery_app.task(name="app.tasks.process.reprocess_document", bind=True, max_retries=3)
def reprocess_document(self, document_id: str) -> dict:
    """Re-run AI analysis on a document that already has extracted text."""
    doc_uuid = uuid.UUID(document_id)
    session = _get_sync_session()

    try:
        doc = session.execute(select(Document).where(Document.id == doc_uuid)).scalar_one_or_none()
        if doc is None:
            return {"status": "error", "message": "Document not found"}

        doc.status = DocumentStatus.processing
        session.flush()
        _log_step(session, doc_uuid, "reprocess_start", "info", "Reprocessing started")

        text = doc.content or ""

        # If no content, re-run OCR first
        if not text.strip():
            try:
                from app.services.ocr import OCRService
                ocr = OCRService()
                text = ocr.extract_text(doc.file_path)
                doc.content = text
                session.flush()
            except Exception as e:
                logger.exception("Re-OCR failed: %s", e)

        # Re-classify
        try:
            from app.services.classifier import ClassifierService
            classifier = ClassifierService()

            existing_tags = [t.name for t in session.execute(select(Tag)).scalars().all()]
            existing_types = [t.name for t in session.execute(select(DocumentType)).scalars().all()]
            existing_corr = [c.name for c in session.execute(select(Correspondent)).scalars().all()]

            result = classifier.classify(text, existing_tags, existing_types, existing_corr)

            if result.title:
                doc.title = result.title
            if result.date:
                try:
                    doc.created_date = datetime.fromisoformat(result.date)
                except ValueError:
                    pass

            _log_step(session, doc_uuid, "reclassify", "success", f"Title: {result.title}")
        except Exception as e:
            logger.exception("Reclassification failed: %s", e)
            _log_step(session, doc_uuid, "reclassify", "error", str(e))

        # Re-extract fields: remove old ones first
        old_fields = session.execute(select(CustomField).where(CustomField.document_id == doc_uuid)).scalars().all()
        for cf in old_fields:
            session.delete(cf)
        session.flush()

        try:
            from app.services.fields import FieldExtractor
            extractor = FieldExtractor()
            fields = extractor.extract_fields(text)
            for field in fields:
                session.add(CustomField(
                    document_id=doc_uuid,
                    field_name=field.name,
                    field_value=field.value,
                    field_type=field.type,
                ))
            session.flush()
            _log_step(session, doc_uuid, "reextract_fields", "success", f"{len(fields)} fields")
        except Exception as e:
            logger.exception("Field re-extraction failed: %s", e)
            _log_step(session, doc_uuid, "reextract_fields", "error", str(e))

        # Re-generate embeddings
        try:
            from app.services.embeddings import EmbeddingService
            emb_service = EmbeddingService()
            doc.embedding = emb_service.embed_text(text)
            session.flush()
            _log_step(session, doc_uuid, "reembed", "success", "Embedding regenerated")
        except Exception as e:
            logger.exception("Re-embedding failed: %s", e)
            _log_step(session, doc_uuid, "reembed", "error", str(e))

        doc.status = DocumentStatus.done
        doc.modified_date = datetime.utcnow()
        _log_step(session, doc_uuid, "reprocess_complete", "success", "Reprocessing complete")
        session.commit()

        return {"status": "done", "document_id": document_id}

    except Exception as e:
        logger.exception("Reprocessing error for %s", document_id)
        try:
            doc = session.execute(select(Document).where(Document.id == doc_uuid)).scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.error
                session.commit()
        except Exception:
            session.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        session.close()
