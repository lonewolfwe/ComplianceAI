"""
FastAPI route handlers for circular-related endpoints.

All routes in this module:
  - Receive the HTTP request.
  - Validate input where required.
  - Delegate to CircularService for all business logic.
  - Return the response.

No business logic lives here.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.schemas.circular import CircularSummary, ErrorResponse
from src.services.pipeline import CompliancePipeline
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_pipeline(request: Request) -> CompliancePipeline:
    """
    FastAPI dependency that retrieves the CompliancePipeline from app state.

    The pipeline is registered on the app instance at startup and shared
    across all requests.

    Args:
        request: The current FastAPI request object.

    Returns:
        The application-wide CompliancePipeline instance.
    """
    return request.app.state.pipeline


@router.get(
    "/",
    response_class=HTMLResponse,
    summary="Homepage",
    description="Render the main page displaying the latest RBI circular summaries.",
)
async def index(
    request: Request,
    pipeline: CompliancePipeline = Depends(get_pipeline),
) -> HTMLResponse:
    """
    Serve the homepage with the latest RBI circular summary cards.

    Fetches circular summaries from the pipeline (which may return cached
    data) and renders the Jinja2 index template.

    Args:
        request: The incoming HTTP request.
        pipeline: The CompliancePipeline dependency.

    Returns:
        An HTMLResponse containing the rendered index.html template.
    """
    logger.info("GET / — Serving homepage.")
    circulars: list[CircularSummary] = pipeline.get_circulars()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "circulars": circulars,
            "total": len(circulars),
        },
    )


@router.get(
    "/api/circulars",
    response_model=list[CircularSummary],
    summary="List circular summaries",
    description="Return the latest RBI circular summaries as a JSON array.",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def list_circulars(
    pipeline: CompliancePipeline = Depends(get_pipeline),
) -> list[CircularSummary]:
    """
    Return the latest RBI circular summaries as JSON.

    Serves from cache when available. Runs the full pipeline on a cache miss.

    Args:
        pipeline: The CompliancePipeline dependency.

    Returns:
        A list of CircularSummary objects ordered most-recent first.

    Raises:
        HTTPException (503): If the pipeline fails entirely (no circulars available).
    """
    logger.info("GET /api/circulars — Fetching circular list.")
    circulars: list[CircularSummary] = pipeline.get_circulars()
    if not circulars:
        logger.warning("No circulars available. Returning 503.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No circulars are currently available. The RBI website may be unreachable.",
        )
    return circulars


@router.post(
    "/api/refresh",
    response_model=list[CircularSummary],
    summary="Force refresh",
    description="Invalidate the cache and re-fetch all circulars immediately.",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def refresh_circulars(
    pipeline: CompliancePipeline = Depends(get_pipeline),
) -> list[CircularSummary]:
    """
    Invalidate the cache and trigger a fresh fetch of all circulars.

    This endpoint is intended for the manual refresh button in the UI.
    It bypasses the TTL cache and re-runs the full scrape → parse →
    summarize pipeline.

    Args:
        pipeline: The CompliancePipeline dependency.

    Returns:
        A freshly-fetched list of CircularSummary objects.

    Raises:
        HTTPException (503): If the refresh pipeline yields no results.
    """
    logger.info("POST /api/refresh — Manual cache invalidation requested.")
    circulars: list[CircularSummary] = pipeline.refresh()
    if not circulars:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Refresh failed. The RBI website may be temporarily unreachable.",
        )
    return circulars
