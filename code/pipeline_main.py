"""
Compatibility shim.

Keeps legacy entrypoint `python code/pipeline_main.py ...` working after migrating
the implementation to `src/ai44pt/cli.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = (Path(__file__).resolve().parents[1] / "src").as_posix()
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai44pt.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

