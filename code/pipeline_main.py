"""
批量分析流水线主程序 - 4PT框架批量文章分析
"""
import argparse
from datetime import datetime
from pathlib import Path
from config import Config
from batch_analyzer import BatchAnalyzer


def parse_cli_args():
    parser = argparse.ArgumentParser(description="4PT batch analysis pipeline")
    parser.add_argument(
        "--stage",
        choices=["raw", "parse", "full"],
        default="full",
        help="Processing stage to run: raw generation, parse from raw, or full pipeline",
    )
    parser.add_argument(
        "--raw-path",
        dest="raw_path",
        help="Path to raw JSON file or directory (input for parse stage, output path for raw/full stages)",
    )
    parser.add_argument(
        "--excel-path",
        dest="excel_path",
        help="Optional override for Excel source file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (limits article count and reduces AI effort)",
    )
    parser.add_argument(
        "--skip-bad",
        dest="skip_bad",
        action="store_true",
        help="Skip JSON files that fail to parse (useful for batch parse runs)",
    )
    return parser.parse_args()


def main():
    """批量分析主入口"""
    args = parse_cli_args()
    stage = args.stage
    excel_override = Path(args.excel_path).expanduser() if args.excel_path else None
    raw_path_input = args.raw_path
    raw_path_arg = Path(raw_path_input).expanduser() if raw_path_input else None
    debug_mode = bool(args.debug)
    skip_bad = bool(args.skip_bad)

    print("=" * 60)
    print("4PT BATCH ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Selected stage: {stage.upper()}")
    if raw_path_input:
        print(f"Raw path: {raw_path_input}")
    if excel_override:
        print(f"Excel override: {excel_override}")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化配置
    config = Config()
    if excel_override:
        Config.EXCEL_PATH = excel_override
        config.EXCEL_PATH = excel_override
    if debug_mode:
        Config.DEBUG_MODE = True
        config.DEBUG_MODE = True

    # 显示配置信息
    print("\n📋 Configuration:")
    print(f"   Model: {config.CLS_MODEL}")
    print(f"   Temperature: {config.TEMPERATURE}")
    print(f"   AI Runs: {config.get_ai_runs()}")
    print(f"   Reasoning Effort: {config.get_reasoning_effort()}")
    print(f"   Text Verbosity: {config.get_text_verbosity()}")
    print(f"   Majority Vote: {config.ENABLE_MAJORITY_VOTE}")
    print(f"   Debug Mode: {config.DEBUG_MODE}")
    print(f"   Excel Path: {config.EXCEL_PATH}")
    print(f"   Output Directory: {config.RESULTS_DIR}")
    if stage == "parse":
        print(f"   Skip Bad JSON: {skip_bad}")

    # 验证配置
    if not config.validate():
        print("\n❌ Configuration validation failed!")
        print("Please check:")
        print("  - OPENAI_API_KEY is set in .env file")
        print("  - Codebook file exists at:", config.CODEBOOK_MD)
        print("  - Excel file exists at:", config.EXCEL_PATH)
        return 1

    print("\n✅ Configuration validated")

    raw_output_path = None
    parse_targets = []

    if stage in {"raw", "full"}:
        if raw_path_arg:
            if raw_path_arg.is_dir():
                raw_path_arg.mkdir(parents=True, exist_ok=True)
                raw_output_path = raw_path_arg / f"raw_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
                print(f"\n📁 Raw output target: {raw_output_path}")
            else:
                raw_output_path = raw_path_arg
                print(f"\n📁 Raw output target: {raw_output_path}")
    elif stage == "parse":
        def _collect_parse_targets(directory: Path):
            aggregated_dir = directory / "aggregated"
            if aggregated_dir.exists() and aggregated_dir.is_dir():
                aggregated_files = sorted(aggregated_dir.glob("*.json"))
                if aggregated_files:
                    print(f"\n📁 Found {len(aggregated_files)} aggregated JSON file(s) in {aggregated_dir}")
                    return aggregated_files

            aggregated_files = sorted(directory.glob("raw_responses_*.json"))
            if aggregated_files:
                print(f"\n📁 Found {len(aggregated_files)} aggregated JSON file(s) in {directory}")
                return aggregated_files

            json_files = sorted(directory.glob("*.json"))
            if json_files:
                print(f"\n📁 Found {len(json_files)} JSON file(s) in {directory}; will merge during parse")
                return [directory]
            print(f"\n❌ No JSON files found in directory: {directory}")
            return []

        if raw_path_arg:
            if raw_path_arg.is_dir():
                parse_targets = _collect_parse_targets(raw_path_arg)
                if not parse_targets:
                    return 1
            elif raw_path_arg.is_file():
                suffix = raw_path_arg.suffix.lower()
                if suffix == ".json":
                    parse_targets = [raw_path_arg]
                    print(f"\n📁 Parsing raw file: {raw_path_arg}")
                else:
                    print(f"\n❌ Unsupported raw file type: {raw_path_arg.suffix}")
                    return 1
            else:
                print(f"\n❌ Raw path not found: {raw_path_arg}")
                return 1
        else:
            default_dir = config.RAW_OUTPUT_DIR
            parse_targets = _collect_parse_targets(default_dir)
            if not parse_targets:
                return 1
            print(f"\n📁 Using default raw directory: {default_dir}")

    raw_input_param = None
    if stage in {"raw", "full"}:
        raw_input_param = str(raw_output_path) if raw_output_path else None
    elif stage == "parse" and len(parse_targets) == 1:
        raw_input_param = str(parse_targets[0])

    # 创建批量分析器
    analyzer = BatchAnalyzer(config)
    skipped_batches = []

    # 执行批量分析
    print("\n" + "=" * 60)
    print("STARTING BATCH ANALYSIS")
    print("=" * 60)

    def verify_results(results_df):
        if results_df is not None and not results_df.empty:
            print("\n" + "=" * 60)
            print("FINAL VERIFICATION")
            print("=" * 60)

            article_ids = results_df['#'].unique()
            print(f"Unique articles: {len(article_ids)}")

            # 检查前3篇文章
            for article_id in article_ids[:3]:
                article_rows = results_df[results_df['#'] == article_id]
                sources = article_rows['source'].tolist()
                print(f"Article #{article_id}: {len(sources)} rows ({sources[0]}, ...)")

                if 'human' not in sources:
                    print(f"  ⚠️ WARNING: Missing human row")

                ai_sources = [s for s in sources if s != 'human']
                expected_ai = config.get_ai_runs()
                if config.ENABLE_MAJORITY_VOTE and config.get_ai_runs() > 1:
                    expected_ai += 1  # +1 for majority vote row

                if len(ai_sources) != expected_ai:
                    print(f"  ⚠️ WARNING: Expected {expected_ai} AI rows, found {len(ai_sources)}")
        else:
            print("\n⚠️ No results dataframe produced.")

    try:
        if stage == "raw":
            raw_output = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_data_path=raw_input_param,
                stage="raw"
            )
            print(f"\n📦 Raw responses written to: {raw_output}")
            print(f"\n⏰ End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print("✅ RAW GENERATION COMPLETED")
            print("=" * 60)
            return 0

        if stage == "parse" and len(parse_targets) > 1:
            total_runs = len(parse_targets)
            for idx, jsonl_path in enumerate(parse_targets, start=1):
                print("\n" + "-" * 60)
                print(f"BATCH {idx}/{total_runs}: {jsonl_path}")
                print("-" * 60)
                try:
                    results_df = analyzer.process_batch(
                        excel_path=str(config.EXCEL_PATH),
                        raw_data_path=str(jsonl_path),
                        stage="parse"
                    )
                except Exception as exc:
                    print(f"\n❌ Failed to parse {jsonl_path}: {exc}")
                    if skip_bad:
                        skipped_batches.append((jsonl_path, str(exc)))
                        continue
                    raise

                if (results_df is None) or results_df.empty:
                    message = "Parse returned no results"
                    print(f"  ⚠️ {message}")
                    if skip_bad:
                        skipped_batches.append((jsonl_path, message))
                        continue

                verify_results(results_df)

                if analyzer.last_raw_source_path:
                    print(f"\n📁 Raw source path: {analyzer.last_raw_source_path}")

                print(f"\n⏰ End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 60)
                print("✅ PIPELINE COMPLETED SUCCESSFULLY")
                print("=" * 60)

            if skipped_batches:
                print("\n" + "-" * 60)
                print("SKIPPED BATCHES SUMMARY")
                print("-" * 60)
                for path, reason in skipped_batches:
                    print(f"⏭️ {path} -> {reason}")
            return 0

        try:
            results_df = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_data_path=raw_input_param,
                stage=stage
            )
        except Exception as exc:
            if stage == "parse" and skip_bad:
                print(f"\n❌ Failed to parse {raw_input_param}: {exc}")
                print("⏭️ Skipping per --skip-bad flag")
                return 0
            raise

        if stage == "parse" and ((results_df is None) or results_df.empty):
            message = "Parse returned no results"
            print(f"❌ {message}")
            if skip_bad:
                print("⏭️ Skipping per --skip-bad flag")
                return 0
            return 1

        verify_results(results_df)

        if stage in {"parse", "full"} and analyzer.last_raw_source_path:
            print(f"\n📁 Raw source path: {analyzer.last_raw_source_path}")

        print(f"\n⏰ End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print("✅ PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
