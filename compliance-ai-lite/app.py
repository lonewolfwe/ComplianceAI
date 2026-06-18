"""
ComplianceAI Lite — FastAPI Application Entry Point.

This module:
  1. Creates the FastAPI application instance.
  2. Configures logging.
  3. Mounts static files and templates.
  4. Registers application routes.
  5. Initialises shared services on startup.
  6. Exposes a health-check endpoint.

Start the server with:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config import get_settings, Settings
from src.parsers.pdf_downloader import PDFDownloader
from src.parsers.pdf_parser import PDFParser
from src.routes.circulars import router as circulars_router
from src.scraper.rbi_scraper import RBIScraper
from src.schemas.circular import CircularMeta
from src.services.circular_service import CircularService
from src.services.ai_service import AIService
from src.repositories.summary_repository import SummaryRepository
from src.utils.cache_manager import CacheManager
from src.utils.logger import configure_logging, get_logger

# ── Bootstrap logging before anything else ────────────────────────────────────
settings: Settings = get_settings()
configure_logging(level=settings.log_level)
logger = get_logger(__name__)


# ── Application Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    """Manages the startup and shutdown lifecycle of the application."""
    logger.info(
        "Starting %s [env=%s, model=%s, limit=%d circulars].",
        settings.app_name,
        settings.app_env,
        settings.gemini_model,
        settings.rbi_circular_limit,
    )

    # Build the new Dependency Graph
    meta_cache = CacheManager[list[CircularMeta]](ttl_seconds=settings.cache_ttl_minutes * 60)
    summary_repo = SummaryRepository(data_dir="data/summaries")
    scraper = RBIScraper(settings=settings)
    downloader = PDFDownloader(settings=settings)
    pdf_parser = PDFParser(settings=settings, downloader=downloader)
    ai_service = AIService(settings=settings)

    circular_service = CircularService(
        settings=settings,
        scraper=scraper,
        pdf_parser=pdf_parser,
        ai_service=ai_service,
        summary_repo=summary_repo,
        meta_cache=meta_cache,
    )

    # Attach to app.state
    app.state.circular_service = circular_service

    logger.info("%s is ready to serve requests.", settings.app_name)

    yield  # Application runs here.

    logger.info("%s is shutting down.", settings.app_name)


# ── FastAPI Application ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Registers routes, mounts static files, and attaches the lifespan
    context manager for startup/shutdown handling.

    Returns:
        A fully configured FastAPI application instance.
    """
    _settings = get_settings()

    application = FastAPI(
        title=_settings.app_name,
        description=(
            "AI-powered RBI regulatory monitoring tool for Indian fintech companies. "
            "Automatically fetches, summarizes, and displays the latest RBI circulars."
        ),
        version="1.0.0",
        docs_url="/docs" if _settings.app_env != "production" else None,
        redoc_url="/redoc" if _settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    # Mount the static files directory.
    application.mount("/static", StaticFiles(directory="static"), name="static")

    # Register routers.
    application.include_router(circulars_router)

    return application


app: FastAPI = create_app()


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    description="Returns application health status. Used by Render for uptime monitoring.",
)
async def health_check() -> dict[str, str]:
    """
    Lightweight health-check endpoint.

    Returns:
        A JSON object with status and application name.
    """
    return {"status": "ok", "app": settings.app_name}
