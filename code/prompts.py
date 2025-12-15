"""
Compatibility shim for legacy imports:
`from prompts import build_user_prompt`.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = (Path(__file__).resolve().parents[1] / "src").as_posix()
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai44pt.prompt_engineering.prompts import (  # noqa: F401
    build_system_prompt,
    build_user_prompt,
    format_questions_prompt,
)

__all__ = ["build_system_prompt", "build_user_prompt", "format_questions_prompt"]

