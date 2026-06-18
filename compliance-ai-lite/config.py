"""
Configuration management for ComplianceAI Lite.

All settings are loaded from environment variables with sane defaults.
Sensitive values (API keys, secrets) must never be hardcoded.
"""

from functools import lru_cache

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All fields are typed and validated at startup. Missing required
    values will raise a descriptive error before the app begins serving.
    """

    # ── Application ──────────────────────────────────────────────────────
    app_name: str = Field(default="ComplianceAI Lite", description="Display name of the application.")
    app_env: str = Field(default="development", description="Runtime environment: development | production.")
    port: int = Field(default=8000, description="Port the uvicorn server will bind to.")
    debug: bool = Field(default=False, description="Enable FastAPI debug mode.")

    # ── Google Gemini ─────────────────────────────────────────────────────
    google_api_key: str = Field(..., description="Google Gemini API key. Required.")
    gemini_model: str = Field(default="gemini-flash-latest", description="Gemini model identifier.")

    # ── Scraper ───────────────────────────────────────────────────────────
    rbi_circular_limit: int = Field(default=5, ge=1, le=20, description="Number of latest circulars to fetch.")
    rbi_base_url: str = Field(
        default="https://www.rbi.org.in",
        description="Base URL of the RBI website.",
    )
    scraper_timeout_seconds: int = Field(default=10, description="HTTP timeout for scraper requests.")
    scraper_user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User-Agent header sent with scraper requests.",
    )

    # ── PDF Parser ────────────────────────────────────────────────────────
    pdf_download_timeout_seconds: int = Field(default=15, description="HTTP timeout for PDF downloads.")
    pdf_max_tokens: int = Field(
        default=8000,
        description="Maximum characters of extracted PDF text to send to Gemini.",
    )

    # ── Cache ─────────────────────────────────────────────────────────────
    cache_ttl_minutes: int = Field(default=30, ge=1, description="Time-to-live for the in-memory circular cache.")

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Python logging level: DEBUG | INFO | WARNING | ERROR.")

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        """Ensure app_env is one of the accepted values."""
        allowed = {"development", "production", "testing"}
        if value not in allowed:
            raise ValueError(f"app_env must be one of {allowed}. Got: {value!r}")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Ensure log_level is a valid Python logging level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}. Got: {value!r}")
        return upper

    @field_validator("google_api_key", mode="before")
    @classmethod
    def clean_google_api_key(cls, value: str) -> str:
        """Clean the Google API key by stripping quotes and whitespace."""
        if not isinstance(value, str):
            return value
        cleaned = value.strip().strip("'").strip('"')
        return cleaned

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings instance.

    Uses lru_cache to ensure settings are loaded from the environment
    exactly once per process lifetime.

    Returns:
        A fully validated Settings instance.
    """
    return Settings()  # type: ignore[call-arg]
