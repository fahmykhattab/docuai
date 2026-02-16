from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PDFService:
    """Utilities for PDF and image file processing."""

    def generate_thumbnail(
        self,
        file_path: str,
        output_path: str,
        size: Tuple[int, int] = (300, 400),
    ) -> bool:
        """Generate a thumbnail image for a document. Returns True on success."""
        abs_path = self._resolve_path(file_path)
        if not os.path.exists(abs_path):
            logger.error("File not found for thumbnail generation: %s", abs_path)
            return False

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            mime = self._detect_mime(abs_path)
            if mime == "application/pdf" or abs_path.lower().endswith(".pdf"):
                images = convert_from_path(abs_path, first_page=1, last_page=1, dpi=150)
                if not images:
                    return False
                img = images[0]
            else:
                img = Image.open(abs_path)

            img.thumbnail(size, Image.Resampling.LANCZOS)

            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img.save(output_path, "PNG", optimize=True)
            logger.info("Thumbnail generated: %s", output_path)
            return True

        except Exception as e:
            logger.exception("Thumbnail generation failed for %s: %s", abs_path, e)
            return False

    def get_page_count(self, file_path: str) -> int:
        """Get the number of pages in a document."""
        abs_path = self._resolve_path(file_path)
        if not os.path.exists(abs_path):
            return 0

        mime = self._detect_mime(abs_path)
        if mime == "application/pdf" or abs_path.lower().endswith(".pdf"):
            try:
                info = pdfinfo_from_path(abs_path)
                return int(info.get("Pages", 0))
            except Exception as e:
                logger.warning("Could not get PDF page count: %s", e)
                return 0
        else:
            # Image files are 1 page
            return 1

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file metadata: size, mime_type, pages."""
        abs_path = self._resolve_path(file_path)
        if not os.path.exists(abs_path):
            return {"size": 0, "mime_type": "unknown", "pages": 0}

        size = os.path.getsize(abs_path)
        mime = self._detect_mime(abs_path)
        pages = self.get_page_count(file_path)

        return {
            "size": size,
            "mime_type": mime,
            "pages": pages,
        }

    def _resolve_path(self, file_path: str) -> str:
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(settings.MEDIA_DIR, file_path)

    def _detect_mime(self, path: str) -> str:
        try:
            import magic
            return magic.from_file(path, mime=True)
        except Exception:
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            mime_map = {
                "pdf": "application/pdf",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "tiff": "image/tiff",
                "tif": "image/tiff",
                "webp": "image/webp",
                "bmp": "image/bmp",
                "gif": "image/gif",
            }
            return mime_map.get(ext, "application/octet-stream")
