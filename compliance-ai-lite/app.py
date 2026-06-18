from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# SlowAPI imports for rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings, Settings
from src.parsers.pdf_downloader import PDFDownloader
from src.parsers.pdf_parser import PDFParser
from src.routes.circulars import router as circulars_router
from src.routes.analysis import router as analysis_router
from src.scraper.rbi_scraper import RBIScraper
from src.schemas.circular import CircularMeta
from src.services.circular_service import CircularService
from src.services.ai_service import AIService
from src.repositories.summary_repository import SummaryRepository
from src.repositories.job_repository import JobRepository
from src.utils.cache_manager import CacheManager
from src.utils.logger import configure_logging, get_logger

# Initialize Limiter (10 requests per minute per IP)
limiter = Limiter(key_func=get_remote_address)

# ── Bootstrap logging before anything else ────────────────────────────────────
settings: Settings = get_settings()
configure_logging(level=settings.log_level)
logger = get_logger(__name__)

# ── Application Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    """Manages the startup and shutdown lifecycle of the application."""
    # Step 3: Verify .env loading at startup
    import os
    env_exists = os.path.exists(".env")
    key_exists = bool(settings.google_api_key)
    raw_key = os.getenv("GOOGLE_API_KEY") or ""
    has_whitespace = raw_key != raw_key.strip() if raw_key else False
    has_quotes = (raw_key.startswith('"') or raw_key.startswith("'") or raw_key.endswith('"') or raw_key.endswith("'")) if raw_key else False
    key_len = len(settings.google_api_key) if key_exists else 0
    
    logger.info("--- AI PIPELINE STARTUP DIAGNOSTICS ---")
    logger.info(".env file exists: %s", env_exists)
    logger.info("GOOGLE_API_KEY configured in environment: %s", bool(raw_key))
    logger.info("GOOGLE_API_KEY loaded into settings: %s", key_exists)
    if key_exists:
        logger.info("GOOGLE_API_KEY length: %d characters", key_len)
        logger.info("GOOGLE_API_KEY contains whitespaces before cleaning: %s", has_whitespace)
        logger.info("GOOGLE_API_KEY contains quotes before cleaning: %s", has_quotes)
        from src.services.ai_service import GENAI_AVAILABLE
        logger.info("Gemini SDK (google-generativeai) available: %s", GENAI_AVAILABLE)
    logger.info("----------------------------------------")

    logger.info(
        "%s [env=%s, model=%s, limit=%d circulars].",
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
    job_repo = JobRepository()

    circular_service = CircularService(
        settings=settings,
        scraper=scraper,
        pdf_parser=pdf_parser,
        ai_service=ai_service,
        summary_repo=summary_repo,
        meta_cache=meta_cache,
        job_repo=job_repo,
    )

    # Attach to app.state
    fastapi_app.state.circular_service = circular_service
    fastapi_app.state.job_repo = job_repo
    fastapi_app.state.summary_repo = summary_repo

    logger.info("%s is ready to serve requests.", settings.app_name)

    yield  # Application runs here.

    logger.info("%s is shutting down.", settings.app_name)

# ── FastAPI Application ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Registers routes, mounts static files, and attaches the lifespan
    context manager for startup/shutdown handling.
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

    # Attach limiter to app state and register exception handler
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Mount the static files directory.
    application.mount("/static", StaticFiles(directory="static"), name="static")

    # Register routers.
    application.include_router(circulars_router)
    application.include_router(analysis_router)

    return application

app: FastAPI = create_app()
