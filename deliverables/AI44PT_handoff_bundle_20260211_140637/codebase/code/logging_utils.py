"""
Logging utilities for the 4PT batch pipeline.
Provides a single place to configure root logging without touching builtins.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(message)s"


def setup_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> logging.Logger:
    """
    Configure the root logger with a stdout handler (and optional file handler).
    Idempotent: handlers are added only if a matching one is not present.

    Args:
        level: Logging level to set on the root logger.
        log_file: Optional file path to also write logs.

    Returns:
        The configured root logger.
    """
    root_logger = logging.getLogger()
    formatter = logging.Formatter(LOG_FORMAT)

    # Stream handler to stdout
    has_stdout_handler = any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
        for h in root_logger.handlers
    )
    if not has_stdout_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    # Optional file handler
    if log_file:
        log_path = Path(log_file)
        has_file_handler = any(
            isinstance(h, logging.FileHandler)
            and Path(getattr(h, "baseFilename", "")) == log_path
            for h in root_logger.handlers
        )
        if not has_file_handler:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

    root_logger.setLevel(level)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Wrapper for logging.getLogger for consistency."""
    return logging.getLogger(name)
