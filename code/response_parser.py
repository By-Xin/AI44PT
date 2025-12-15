"""
Compatibility shim for legacy imports:
`from response_parser import ResponseParser`.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = (Path(__file__).resolve().parents[1] / "src").as_posix()
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai44pt.handlers.response_parser import ResponseParser  # noqa: F401

__all__ = ["ResponseParser"]

