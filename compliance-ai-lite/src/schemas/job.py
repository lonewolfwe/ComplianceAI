"""
Schemas for background job tracking.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class JobState(BaseModel):
    """Internal state of a background job."""
    job_id: str
    circular_hash: str
    status: str = Field(description="queued, processing, completed, failed")
    progress: int = Field(default=0, description="Percentage 0-100")
    step: str = Field(default="Initializing...", description="Current human-readable step")
    error_message: Optional[str] = None
    result_hash: Optional[str] = None
    heuristics: Optional[Dict[str, Any]] = None

class JobStartResponse(BaseModel):
    """Response returned when a job is queued."""
    job_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    """Response returned when polling job status."""
    job_id: str
    status: str
    progress: int
    step: str
    error_message: Optional[str] = None
    heuristics: Optional[Dict[str, Any]] = None
