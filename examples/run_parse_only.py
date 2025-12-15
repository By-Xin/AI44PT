from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai44pt.config import Config
from ai44pt.pipeline.batch_analyzer import BatchAnalyzer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-path", required=True, help="Raw JSON file or directory")
    parser.add_argument("--config", default=str(ROOT / "config" / "parse.yaml"), help="YAML config path")
    parser.add_argument("--parse-all-runs", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    Config.load_from_yaml(Path(args.config).expanduser())
    config = Config()
    analyzer = BatchAnalyzer(config)
    analyzer.process_batch(stage="parse", raw_data_path=args.raw_path, use_all_runs=args.parse_all_runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

