"""
API endpoints for managing and retrieving RBI compliance circulars.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.schemas.circular import CircularMeta, CircularSummary, ErrorResponse
from src.services.circular_service import CircularService
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_circular_service(request: Request) -> CircularService:
    """Dependency injector for CircularService."""
    return request.app.state.circular_service


@router.get(
    "/",
    response_class=HTMLResponse,
    summary="Homepage",
    description="Render the main page displaying the latest RBI circular titles.",
)
def index(
    request: Request,
    circular_service: CircularService = Depends(get_circular_service),
) -> HTMLResponse:
    logger.info("GET / — Rendering homepage.")
    circulars: list[CircularMeta] = circular_service.get_latest_metadata()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"circulars": circulars},
    )


@router.get(
    "/api/circulars",
    response_model=list[CircularMeta],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def list_circulars(
    circular_service: CircularService = Depends(get_circular_service),
) -> list[CircularMeta]:
    """Retrieve the latest RBI circular metadata."""
    logger.info("GET /api/circulars — Fetching circular metadata.")
    circulars: list[CircularMeta] = circular_service.get_latest_metadata()

    if not circulars:
        logger.error("No circular metadata could be fetched.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch circulars. The RBI website may be temporarily unreachable.",
        )

    return circulars


@router.get("/circular/{circular_hash}", response_class=HTMLResponse)
def circular_detail(
    circular_hash: str,
    request: Request,
    circular_service: CircularService = Depends(get_circular_service),
) -> HTMLResponse:
    """Serves the new Premium SaaS Copilot detail page."""
    # Try to find the circular meta in the memory cache
    metas = circular_service.get_latest_metadata()
    meta = next((m for m in metas if m.hash == circular_hash), None)
    
    if not meta:
        raise HTTPException(status_code=404, detail="Circular not found in recent index.")

    return templates.TemplateResponse(
        request=request,
        name="detail.html",
        context={"meta": meta},
    )

@router.post(
    "/api/summarize",
    response_model=CircularSummary,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
def summarize_circular(
    meta: CircularMeta,
    circular_service: CircularService = Depends(get_circular_service),
) -> CircularSummary:
    """Lazy-load the AI summary for a specific circular."""
    logger.info("POST /api/summarize — Requesting summary for %s", meta.hash)
    try:
        return circular_service.get_or_generate_summary(meta)
    except Exception as exc:
        logger.error("Failed to summarize circular %s: %s", meta.hash, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing the circular."
        ) from exc

@router.post(
    "/api/regenerate",
    response_model=CircularSummary,
)
def regenerate_circular(
    meta: CircularMeta,
    circular_service: CircularService = Depends(get_circular_service),
) -> CircularSummary:
    """Force regenerate the AI summary, overwriting the cache."""
    logger.info("POST /api/regenerate — Forcing AI regeneration for %s", meta.hash)
    try:
        return circular_service.get_or_generate_summary(meta, force_regenerate=True)
    except Exception as exc:
        logger.error("Failed to regenerate circular %s: %s", meta.hash, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analyzing the circular."
        ) from exc


@router.post(
    "/api/refresh",
    response_model=list[CircularMeta],
    responses={
        status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
def refresh_circulars(
    request: Request,
    circular_service: CircularService = Depends(get_circular_service),
) -> list[CircularMeta]:
    """Force a manual refresh of the circular metadata cache."""
    now = time.time()
    last_refresh_time = getattr(request.app.state, "last_refresh_time", 0.0)
    if now - last_refresh_time < 60.0:
        logger.warning("Rate limit hit on /api/refresh. Rejecting request.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Refresh rate limit exceeded. Please wait 60 seconds before refreshing again."
        )
    request.app.state.last_refresh_time = now

    logger.info("POST /api/refresh — Manual cache invalidation requested.")
    circulars: list[CircularMeta] = circular_service.get_latest_metadata(force_refresh=True)
    if not circulars:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh failed. The RBI website may be temporarily unreachable.",
        )
    return circulars
