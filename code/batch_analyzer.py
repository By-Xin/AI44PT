"""
Compatibility shim for legacy imports:
`from batch_analyzer import BatchAnalyzer`.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = (Path(__file__).resolve().parents[1] / "src").as_posix()
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai44pt.pipeline.batch_analyzer import BatchAnalyzer  # noqa: F401

__all__ = ["BatchAnalyzer"]

