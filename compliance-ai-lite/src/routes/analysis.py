"""
API endpoints for asynchronous AI analysis tracking.
"""

from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, status
from src.schemas.circular import CircularMeta, CircularSummary
from src.schemas.job import JobStartResponse, JobStatusResponse
from src.services.circular_service import CircularService
from src.repositories.job_repository import JobRepository
from src.repositories.summary_repository import SummaryRepository

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])

@router.post("/start", response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
def start_analysis(meta: CircularMeta, request: Request, background_tasks: BackgroundTasks) -> JobStartResponse:
    """Queues a background job to generate an AI summary."""
    job_repo: JobRepository = request.app.state.job_repo
    circular_service: CircularService = request.app.state.circular_service

    # First check if the summary already exists
    summary_repo: SummaryRepository = request.app.state.summary_repo
    if summary_repo.get_summary(meta.hash):
        # Already completed, still return a job so the frontend can immediately fetch it
        job = job_repo.create_job(meta.hash)
        job_repo.update_job(job.job_id, status="completed", progress=100, step="Completed", result_hash=meta.hash)
        return JobStartResponse(job_id=job.job_id, status="completed", message="Cache hit")

    job = job_repo.create_job(meta.hash)

    background_tasks.add_task(
        circular_service.generate_summary_background,
        meta=meta,
        job_id=job.job_id,
        force_regenerate=False
    )

    return JobStartResponse(job_id=job.job_id, status="queued", message="Analysis queued")

@router.post("/regenerate", response_model=JobStartResponse, status_code=status.HTTP_202_ACCEPTED)
def regenerate_analysis(meta: CircularMeta, request: Request, background_tasks: BackgroundTasks) -> JobStartResponse:
    """Forces regeneration of an AI summary."""
    job_repo: JobRepository = request.app.state.job_repo
    circular_service: CircularService = request.app.state.circular_service

    job = job_repo.create_job(meta.hash)

    background_tasks.add_task(
        circular_service.generate_summary_background,
        meta=meta,
        job_id=job.job_id,
        force_regenerate=True
    )

    return JobStartResponse(job_id=job.job_id, status="queued", message="Regeneration queued")

@router.get("/status/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, request: Request) -> JobStatusResponse:
    """Polls the status of a background job."""
    job_repo: JobRepository = request.app.state.job_repo
    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        step=job.step,
        error_message=job.error_message,
        heuristics=job.heuristics
    )

@router.get("/result/{job_id}", response_model=CircularSummary)
def get_job_result(job_id: str, request: Request) -> CircularSummary:
    """Retrieves the final AI summary if the job is completed."""
    job_repo: JobRepository = request.app.state.job_repo
    summary_repo: SummaryRepository = request.app.state.summary_repo

    job = job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is {job.status}")

    if not job.result_hash:
        raise HTTPException(status_code=500, detail="Job marked completed but missing result hash")

    summary = summary_repo.get_summary(job.result_hash)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary artifact not found")

    return summary
