from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("DocuAI backend starting up...")

    # Ensure directories exist
    for d in [settings.MEDIA_DIR, settings.CONSUME_DIR, settings.THUMBNAIL_DIR]:
        os.makedirs(d, exist_ok=True)
        logger.info("Ensured directory: %s", d)

    # Run alembic migrations
    try:
        import subprocess
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            logger.info("Database migrations applied")
        else:
            logger.warning("Alembic migration output: %s", result.stderr)
    except Exception as e:
        logger.warning("Could not run alembic migrations (DB may not be ready): %s", e)

    yield

    # Shutdown
    logger.info("DocuAI backend shutting down...")
    from app.database import engine
    await engine.dispose()


app = FastAPI(
    title="DocuAI",
    description="AI-powered document management system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = settings.CORS_ORIGINS
if origins == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
from app.api.documents import router as documents_router
from app.api.tags import router as tags_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.correspondents import router as correspondents_router
from app.api.document_types import router as document_types_router
from app.api.backup import router as backup_router

app.include_router(documents_router, prefix="/api")
app.include_router(tags_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(correspondents_router, prefix="/api")
app.include_router(document_types_router, prefix="/api")
app.include_router(backup_router, prefix="/api")


# Static file serving for media and thumbnails
for mount_path, dir_path in [("/data/media", settings.MEDIA_DIR), ("/data/thumbnails", settings.THUMBNAIL_DIR)]:
    if os.path.isdir(dir_path):
        app.mount(mount_path, StaticFiles(directory=dir_path), name=mount_path.replace("/", "_"))


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Health check
@app.get("/api/health")
async def health_check():
    health = {
        "status": "healthy",
        "service": "docuai-backend",
        "version": "1.0.0",
        "database": "unknown",
    }
    try:
        from app.database import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            health["database"] = "connected"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "degraded"
    return health


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
