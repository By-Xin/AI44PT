"""
Compatibility shim for legacy imports:
`from logging_utils import setup_logging`.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = (Path(__file__).resolve().parents[1] / "src").as_posix()
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai44pt.utils.logging_utils import get_logger, setup_logging  # noqa: F401

__all__ = ["setup_logging", "get_logger"]

