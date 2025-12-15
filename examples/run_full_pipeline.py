from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai44pt.config import Config
from ai44pt.pipeline.batch_analyzer import BatchAnalyzer


def main() -> int:
    Config.load_from_yaml(ROOT / "config" / "full.yaml")
    config = Config()
    analyzer = BatchAnalyzer(config)
    analyzer.process_batch(stage="full")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

