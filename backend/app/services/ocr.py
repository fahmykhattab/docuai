from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
from typing import List

import httpx
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OCRService:
    """Extracts text from documents using Tesseract with Ollama vision fallback."""

    def extract_text(self, file_path: str) -> str:
        """
        Extract text from a file. Tries Tesseract first; if result is poor
        quality (< 50 chars), falls back to Ollama vision model.
        """
        abs_path = self._resolve_path(file_path)
        if not os.path.exists(abs_path):
            logger.error("File not found: %s", abs_path)
            return ""

        text = ""
        try:
            text = self._tesseract_ocr(abs_path)
        except Exception as e:
            logger.warning("Tesseract OCR failed for %s: %s", abs_path, e)

        if len(text.strip()) < 50:
            logger.info("Tesseract result too short (%d chars), trying Ollama vision", len(text.strip()))
            try:
                vision_text = self._ollama_vision_ocr(abs_path)
                if len(vision_text.strip()) > len(text.strip()):
                    text = vision_text
            except Exception as e:
                logger.warning("Ollama vision OCR failed for %s: %s", abs_path, e)

        return text.strip()

    def _resolve_path(self, file_path: str) -> str:
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(settings.MEDIA_DIR, file_path)

    def _tesseract_ocr(self, abs_path: str) -> str:
        mime = self._detect_mime(abs_path)
        if mime == "application/pdf" or abs_path.lower().endswith(".pdf"):
            images = self._pdf_to_images(abs_path)
            texts: list[str] = []
            for img in images:
                page_text = pytesseract.image_to_string(img, lang=settings.OCR_LANGUAGE)
                texts.append(page_text)
            return "\n\n".join(texts)
        else:
            img = Image.open(abs_path)
            return pytesseract.image_to_string(img, lang=settings.OCR_LANGUAGE)

    def _ollama_vision_ocr(self, abs_path: str) -> str:
        mime = self._detect_mime(abs_path)
        if mime == "application/pdf" or abs_path.lower().endswith(".pdf"):
            images = self._pdf_to_images(abs_path)
            if not images:
                return ""
            # Process first page for vision OCR
            img = images[0]
        else:
            img = Image.open(abs_path)

        # Convert image to base64
        buf = io.BytesIO()
        img_format = "PNG" if img.mode == "RGBA" else "JPEG"
        img.save(buf, format=img_format)
        b64_image = base64.b64encode(buf.getvalue()).decode("utf-8")

        prompt = (
            "Extract ALL text from this document image. Return only the extracted text, "
            "preserving the original structure and formatting as much as possible. "
            "Do not add any commentary or explanation."
        )

        response = httpx.post(
            f"{settings.OLLAMA_URL}/api/generate",
            json={
                "model": settings.OLLAMA_VISION_MODEL,
                "prompt": prompt,
                "images": [b64_image],
                "stream": False,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")

    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        try:
            images = convert_from_path(pdf_path, dpi=300)
            return images
        except Exception as e:
            logger.error("pdf2image conversion failed: %s", e)
            return []

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
