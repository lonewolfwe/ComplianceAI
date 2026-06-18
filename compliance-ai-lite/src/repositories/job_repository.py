"""
In-memory repository for tracking background analysis jobs.
"""

from typing import Dict, Optional, Any
from src.schemas.job import JobState
from src.utils.logger import get_logger

logger = get_logger(__name__)

class JobRepository:
    """
    Stores background job states in memory.
    In a real distributed system, this would be backed by Redis or PostgreSQL.
    For this prototype, memory is sufficient.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, JobState] = {}

    def create_job(self, circular_hash: str) -> JobState:
        """Create a new job for the given circular hash."""
        import uuid
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = JobState(
            job_id=job_id,
            circular_hash=circular_hash,
            status="queued",
            progress=0,
            step="Queued for processing"
        )
        self._jobs[job_id] = job
        logger.info("Created job %s for circular %s", job_id, circular_hash)
        return job

    def get_job(self, job_id: str) -> Optional[JobState]:
        """Retrieve a job by ID."""
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        step: Optional[str] = None,
        error_message: Optional[str] = None,
        result_hash: Optional[str] = None,
        heuristics: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update job tracking details."""
        job = self._jobs.get(job_id)
        if not job:
            return

        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if step is not None:
            job.step = step
        if error_message is not None:
            job.error_message = error_message
        if result_hash is not None:
            job.result_hash = result_hash
        if heuristics is not None:
            job.heuristics = heuristics

        logger.debug("Job %s updated: status=%s, progress=%s%%, step='%s'", 
                     job_id, job.status, job.progress, job.step)
