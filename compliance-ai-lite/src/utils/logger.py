"""
Centralised logging configuration for ComplianceAI Lite.

All modules must obtain their logger through get_logger() rather than
calling logging.getLogger() directly. This ensures consistent formatting
and level configuration across the entire application.
"""

import logging
import sys
from typing import Final

# Module-level sentinel to ensure configure_logging() runs exactly once.
_LOGGING_CONFIGURED: bool = False

LOG_FORMAT: Final[str] = (
    "[%(asctime)s] %(levelname)-8s %(name)-40s %(message)s"
)
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    """
    Configure the root logger for the application.

    Must be called once at application startup (inside app.py) before
    any module-level loggers are used. Subsequent calls are no-ops.

    Args:
        level: A valid Python logging level string (e.g., "INFO", "DEBUG").
    """
    global _LOGGING_CONFIGURED  # noqa: PLW0603
    if _LOGGING_CONFIGURED:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger for the given module.

    Convention: pass __name__ as the argument so the logger hierarchy
    mirrors the Python module hierarchy.

    Args:
        name: The logger name, typically the calling module's __name__.

    Returns:
        A configured logging.Logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Starting RBI scraper.")
    """
    return logging.getLogger(name)
