from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://docuai:docuai@localhost:5432/docuai"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://docuai:docuai@localhost:5432/docuai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Ollama
    OLLAMA_URL: str = "http://192.168.178.38:11434"
    OLLAMA_MODEL: str = "qwen3-vl:235b-cloud"
    OLLAMA_VISION_MODEL: str = "qwen3-vl:235b-cloud"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS_STR: str = "pdf,png,jpg,jpeg,tiff,tif,webp,bmp,gif"

    @property
    def ALLOWED_EXTENSIONS(self) -> List[str]:
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS_STR.split(",") if ext.strip()]

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # OCR
    OCR_LANGUAGE: str = "eng+deu+ara"

    # Directories
    MEDIA_DIR: str = "/data/media"
    CONSUME_DIR: str = "/data/consume"
    THUMBNAIL_DIR: str = "/data/thumbnails"

    # CORS
    CORS_ORIGINS: str = "*"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
