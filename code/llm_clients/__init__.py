"""
Compatibility shim for legacy imports:
`from llm_clients.openai_client import OpenAIClient`.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = (Path(__file__).resolve().parents[2] / "src").as_posix()
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai44pt.llm.base_client import BaseLLMClient  # noqa: F401
from ai44pt.llm.gemini_client import GeminiClient  # noqa: F401
from ai44pt.llm.openai_client import OpenAIClient  # noqa: F401

__all__ = ["BaseLLMClient", "OpenAIClient", "GeminiClient"]

