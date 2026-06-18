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
from src.routes.analysis import router as analysis_router
from src.scraper.rbi_scraper import RBIScraper
from src.schemas.circular import CircularMeta
from src.services.circular_service import CircularService
from src.services.ai_service import AIService
from src.repositories.summary_repository import SummaryRepository
from src.repositories.job_repository import JobRepository
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
    app.state.circular_service = circular_service
    app.state.job_repo = job_repo
    app.state.summary_repo = summary_repo

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
    application.include_router(analysis_router)

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


@app.get(
    "/api/health",
    tags=["System"],
    summary="Detailed Health check",
    description="Diagnoses configuration issues and returns detailed pipeline status.",
)
async def api_health() -> dict:
    """Diagnoses configuration issues and returns detailed pipeline status."""
    import os
    import socket
    from config import get_settings
    from src.parsers.pdf_parser import PYPDF_AVAILABLE
    
    current_settings = get_settings()
    
    # 1. Environment
    env = current_settings.app_env
    
    # 2. Key checks
    raw_key = os.getenv("GOOGLE_API_KEY") or ""
    key_loaded = bool(current_settings.google_api_key)
    key_valid_len = len(current_settings.google_api_key) >= 20
    key_no_whitespace = raw_key == raw_key.strip() if raw_key else True
    key_no_quotes = not (raw_key.startswith('"') or raw_key.startswith("'") or raw_key.endswith('"') or raw_key.endswith("'")) if raw_key else True
    
    key_ok = key_loaded and key_valid_len and key_no_whitespace and key_no_quotes
    
    # 3. Client init
    client_init = False
    if hasattr(app.state, "circular_service") and app.state.circular_service:
        ai_service = app.state.circular_service._ai_service
        if ai_service and ai_service._model is not None:
            client_init = True

    # 4. Internet connection
    internet = False
    try:
        socket.setdefaulttimeout(2.0)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        internet = True
    except Exception:
        try:
            import requests
            requests.get("https://www.google.com", timeout=2.0)
            internet = True
        except Exception:
            internet = False

    # 5. Quota Status
    quota = "ok"
    if not key_loaded:
        quota = "invalid_key"
    elif not internet:
        quota = "unknown"
    else:
        try:
            from src.services.ai_service import GENAI_AVAILABLE
            if GENAI_AVAILABLE:
                import google.generativeai as genai
                genai.configure(api_key=current_settings.google_api_key)
                genai.list_models()
                quota = "ok"
            else:
                quota = "client_error"
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower() or "exhausted" in err_str.lower():
                quota = "exhausted"
            elif "401" in err_str or "api key" in err_str.lower() or "unauthenticated" in err_str.lower():
                quota = "invalid_key"
            elif "403" in err_str or "permission" in err_str.lower():
                quota = "permission_denied"
            else:
                quota = f"error: {err_str}"

    # 6. Cache Dir checks
    cache_dir = "data/summaries"
    cache_exists = os.path.exists(cache_dir)
    cache_writable = False
    if cache_exists:
        try:
            test_file = os.path.join(cache_dir, ".health_check_temp")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("test")
            os.remove(test_file)
            cache_writable = True
        except Exception:
            cache_writable = False

    # 7. PDF Parser check
    pdf_parser_status = "ok" if PYPDF_AVAILABLE else "missing_dependencies"

    # Status summary
    is_healthy = (
        key_ok and
        client_init and
        internet and
        (quota == "ok") and
        cache_exists and
        cache_writable and
        (pdf_parser_status == "ok")
    )
    status_str = "healthy" if is_healthy else "unhealthy"

    return {
        "environment": env,
        "gemini_api_key_loaded": key_loaded,
        "gemini_client_initialized": client_init,
        "internet_connection": internet,
        "quota_status": quota,
        "cache_directory_exists": cache_exists,
        "cache_writable": cache_writable,
        "pdf_parser": pdf_parser_status,
        "status": status_str
    }


@app.get(
    "/api/diagnostics",
    tags=["System"],
    summary="AI pipeline metrics",
    description="Returns real-time AI generation metrics, including request count, latency, error details, and cache stats.",
)
async def api_diagnostics() -> dict:
    """Returns real-time AI generation metrics."""
    from src.utils.diagnostics import diagnostics_tracker
    from config import get_settings
    
    current_settings = get_settings()
    stats = diagnostics_tracker.get_stats()
    health = await api_health()
    
    return {
        "api_key_loaded": health["gemini_api_key_loaded"],
        "gemini_reachable": health["internet_connection"] and (health["quota_status"] not in ["invalid_key", "permission_denied"]),
        "current_model": current_settings.gemini_model,
        "current_model_status": "active" if health["gemini_client_initialized"] else "inactive",
        "quota_status": health["quota_status"],
        "requests_today": stats["requests_today"],
        "successful_requests": stats["successful_requests"],
        "failed_requests": stats["failed_requests"],
        "average_response_time": stats["average_response_time"],
        "last_error": stats["last_error"],
        "last_successful_call": stats["last_success_time"],
        "cache_hits": stats["cache_hits"],
        "cache_misses": stats["cache_misses"]
    }


@app.get(
    "/diagnostics",
    tags=["System"],
    summary="Diagnostics dashboard",
    description="Renders the AI Diagnostics dashboard HTML page.",
)
async def diagnostics_page(request: Request):
    """Renders the AI Diagnostics dashboard HTML page."""
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    data = await api_diagnostics()
    return templates.TemplateResponse(
        name="diagnostics.html",
        context={"request": request, "metrics": data}
    )
