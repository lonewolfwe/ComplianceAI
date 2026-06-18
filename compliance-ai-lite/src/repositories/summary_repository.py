import json
import os
from pathlib import Path
from typing import Optional

from src.schemas.circular import CircularSummary
from src.utils.logger import get_logger

logger = get_logger(__name__)

class SummaryRepository:
    """
    Handles persistent storage and retrieval of AI-generated summaries.
    Writes summaries to local JSON files keyed by their hash.
    """

    def __init__(self, data_dir: str = "data/summaries"):
        self.data_dir = Path(data_dir)
        # Ensure the directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, hash_id: str) -> Path:
        return self.data_dir / f"{hash_id}.json"

    def get_summary(self, hash_id: str) -> Optional[CircularSummary]:
        """Retrieve a cached summary by its hash."""
        file_path = self._get_file_path(hash_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CircularSummary(**data)
        except Exception as exc:
            logger.error("Failed to read cached summary from %s: %s", file_path, exc, exc_info=True)
            return None

    def save_summary(self, summary: CircularSummary) -> None:
        """Save a generated summary to the persistent cache."""
        file_path = self._get_file_path(summary.hash)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                # Dump Pydantic model to JSON
                json.dump(summary.model_dump(), f, indent=2, ensure_ascii=False)
            logger.info("Saved AI summary to persistent cache: %s", file_path)
        except Exception as exc:
            logger.error("Failed to save summary to %s: %s", file_path, exc, exc_info=True)
