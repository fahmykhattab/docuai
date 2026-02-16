from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from datetime import datetime

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class _NewFileHandler(FileSystemEventHandler):
    """Handles new files appearing in the consume directory."""

    ALLOWED_EXTENSIONS = None

    def __init__(self) -> None:
        super().__init__()
        self.ALLOWED_EXTENSIONS = set(settings.ALLOWED_EXTENSIONS)
        self._engine = None

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return

        file_path = event.src_path
        filename = os.path.basename(file_path)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in self.ALLOWED_EXTENSIONS:
            logger.info("Ignoring file with extension '.%s': %s", ext, filename)
            return

        logger.info("New file detected: %s", file_path)

        # Wait for write to complete (check file size stability)
        self._wait_for_write(file_path)

        try:
            self._process_new_file(file_path, filename)
        except Exception as e:
            logger.exception("Error processing watched file %s: %s", file_path, e)

    def _wait_for_write(self, file_path: str, check_interval: float = 1.0, max_wait: int = 60) -> None:
        """Wait until the file size stabilizes (write is complete)."""
        previous_size = -1
        waited = 0
        while waited < max_wait:
            try:
                current_size = os.path.getsize(file_path)
            except OSError:
                time.sleep(check_interval)
                waited += check_interval
                continue

            if current_size == previous_size and current_size > 0:
                return
            previous_size = current_size
            time.sleep(check_interval)
            waited += check_interval

        logger.warning("File %s did not stabilize within %ds", file_path, max_wait)

    def _process_new_file(self, source_path: str, filename: str) -> None:
        """Move file to media dir and create DB entry + trigger processing."""
        now = datetime.utcnow()
        year_month = now.strftime("%Y/%m")
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        relative_path = os.path.join(year_month, unique_name)
        dest_path = os.path.join(settings.MEDIA_DIR, relative_path)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.move(source_path, dest_path)
        logger.info("Moved %s → %s", source_path, dest_path)

        file_size = os.path.getsize(dest_path)

        # Detect MIME type
        try:
            import magic
            mime_type = magic.from_file(dest_path, mime=True)
        except Exception:
            mime_type = "application/octet-stream"

        # Create DB entry using sync session (watcher runs as standalone process)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.models import Document, DocumentStatus

        if not hasattr(self, '_engine') or self._engine is None:
            self._engine = create_engine(settings.SYNC_DATABASE_URL, pool_pre_ping=True, pool_size=2)

        doc_id = uuid.uuid4()
        with Session(self._engine) as session:
            doc = Document(
                id=doc_id,
                original_filename=filename,
                file_path=relative_path,
                file_size=file_size,
                mime_type=mime_type,
                status=DocumentStatus.pending,
            )
            session.add(doc)
            session.commit()
            logger.info("Created document record: %s", doc_id)

        # Trigger Celery task
        from app.celery_app import celery_app
        celery_app.send_task("app.tasks.process.process_document", args=[str(doc_id)])
        logger.info("Triggered processing for document %s", doc_id)


class FolderWatcher:
    """Watches the consume directory for new files."""

    def __init__(self) -> None:
        self.observer = Observer()
        self.handler = _NewFileHandler()

    def start(self) -> None:
        """Start watching the consume directory."""
        watch_dir = settings.CONSUME_DIR
        os.makedirs(watch_dir, exist_ok=True)
        self.observer.schedule(self.handler, watch_dir, recursive=False)
        self.observer.start()
        logger.info("Folder watcher started, watching: %s", watch_dir)

    def stop(self) -> None:
        """Stop the folder watcher."""
        self.observer.stop()
        self.observer.join()
        logger.info("Folder watcher stopped")

    def run_forever(self) -> None:
        """Run the watcher until interrupted."""
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    watcher = FolderWatcher()
    watcher.run_forever()
