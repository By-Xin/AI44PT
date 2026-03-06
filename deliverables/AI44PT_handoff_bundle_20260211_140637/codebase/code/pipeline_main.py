"""
批量分析流水线主程序 - 4PT框架批量文章分析
"""
import argparse
import logging
from datetime import datetime
from pathlib import Path

from config import Config
from batch_analyzer import BatchAnalyzer
from logging_utils import setup_logging, get_logger


def parse_cli_args():
    parser = argparse.ArgumentParser(description="4PT batch analysis pipeline")
    parser.add_argument(
        "--stage",
        choices=["raw", "parse", "full", "challenge"],
        default="full",
        help=(
            "Processing stage to run: raw generation, parse from raw, full pipeline, "
            "or dynamic challenge report"
        ),
    )
    parser.add_argument(
        "--raw-path",
        dest="raw_path",
        help=(
            "Path to raw JSON file or directory (input for parse stage, "
            "output path for raw/full/challenge stages)"
        ),
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
    parser.add_argument(
        "--parse-all-runs",
        dest="parse_all_runs",
        action="store_true",
        help="During parse, include every run found in JSON instead of limiting to configured ai_runs",
    )
    parser.add_argument(
        "--challenge-report-path",
        dest="challenge_report_path",
        help="Optional output path for challenge report markdown (or directory for default filenames)",
    )
    return parser.parse_args()


def main():
    """批量分析主入口"""
    setup_logging(logging.INFO)
    logger = get_logger(__name__)

    args = parse_cli_args()
    stage = args.stage
    excel_override = Path(args.excel_path).expanduser() if args.excel_path else None
    raw_path_input = args.raw_path
    raw_path_arg = Path(raw_path_input).expanduser() if raw_path_input else None
    challenge_report_path = (
        Path(args.challenge_report_path).expanduser() if args.challenge_report_path else None
    )
    debug_mode = bool(args.debug)
    skip_bad = bool(args.skip_bad)
    parse_all_runs = bool(args.parse_all_runs)

    logger.info("=" * 60)
    logger.info("4PT BATCH ANALYSIS PIPELINE")
    logger.info("=" * 60)
    logger.info("Selected stage: %s", stage.upper())
    if raw_path_input:
        logger.info("Raw path: %s", raw_path_input)
    if excel_override:
        logger.info("Excel override: %s", excel_override)
    if challenge_report_path:
        logger.info("Challenge report path: %s", challenge_report_path)
    logger.info("=" * 60)
    logger.info("Start time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # 初始化配置
    config = Config()
    if excel_override:
        Config.EXCEL_PATH = excel_override
        config.EXCEL_PATH = excel_override
    if debug_mode:
        Config.DEBUG_MODE = True
        config.DEBUG_MODE = True

    # 显示配置信息
    logger.info("📋 Configuration:")
    logger.info("   Model: %s", config.CLS_MODEL)
    logger.info("   Temperature: %s", config.TEMPERATURE)
    logger.info("   AI Runs: %s", config.get_ai_runs())
    logger.info("   Reasoning Effort: %s", config.get_reasoning_effort())
    logger.info("   Text Verbosity: %s", config.get_text_verbosity())
    logger.info("   Majority Vote: %s", config.ENABLE_MAJORITY_VOTE)
    logger.info("   Debug Mode: %s", config.DEBUG_MODE)
    logger.info("   Excel Path: %s", config.EXCEL_PATH)
    logger.info("   Output Directory: %s", config.RESULTS_DIR)
    if stage == "parse":
        logger.info("   Skip Bad JSON: %s", skip_bad)
        logger.info("   Parse All Runs: %s", parse_all_runs)

    # 验证配置（按阶段）
    if not config.validate(stage=stage):
        logger.error("Configuration validation failed!")
        logger.error("Please check stage-specific dependencies for '%s'.", stage)
        if stage in {"raw", "full", "challenge"}:
            logger.error("  - Provider API keys are set in .env file")
            logger.error("  - Prompt guide files exist under data/instructions/")
            logger.error("  - PDF folder exists at: %s", config.PDF_FOLDER)
        logger.error("  - Excel file exists at: %s", config.EXCEL_PATH)
        return 1

    logger.info("✅ Configuration validated")

    raw_output_path = None
    parse_targets = []

    if stage in {"raw", "full", "challenge"}:
        if raw_path_arg:
            if raw_path_arg.is_dir():
                raw_path_arg.mkdir(parents=True, exist_ok=True)
                raw_output_path = raw_path_arg / f"raw_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                logger.info("📁 Raw output target: %s", raw_output_path)
            else:
                raw_output_path = raw_path_arg
                logger.info("📁 Raw output target: %s", raw_output_path)
    elif stage == "parse":
        def _collect_parse_targets(directory: Path):
            def _list_aggregated_files(base_dir: Path):
                json_files = sorted(base_dir.glob("*.json"))
                jsonl_files = sorted(base_dir.glob("*.jsonl"))
                if not json_files and not jsonl_files:
                    return []

                # Prefer JSON arrays that have a matching streaming JSONL twin (same stem).
                jsonl_stems = {p.stem for p in jsonl_files}
                paired_json_files = [p for p in json_files if p.stem in jsonl_stems]
                if paired_json_files:
                    return paired_json_files

                # Fallback for legacy naming.
                legacy_json_files = [p for p in json_files if p.name.startswith("raw_responses_")]
                if legacy_json_files:
                    return legacy_json_files
                legacy_jsonl_files = [p for p in jsonl_files if p.name.startswith("raw_responses_")]
                if legacy_jsonl_files:
                    return legacy_jsonl_files

                # If only JSONL exists (e.g., interrupted raw stage before final JSON dump), accept it.
                if jsonl_files:
                    return jsonl_files

                return []

            aggregated_dir = directory / "aggregated"
            if aggregated_dir.exists() and aggregated_dir.is_dir():
                aggregated_files = _list_aggregated_files(aggregated_dir)
                if aggregated_files:
                    logger.info(
                        "📁 Found %s aggregated raw file(s) in %s",
                        len(aggregated_files),
                        aggregated_dir,
                    )
                    return aggregated_files

            aggregated_files = _list_aggregated_files(directory)
            if aggregated_files:
                logger.info("📁 Found %s aggregated raw file(s) in %s", len(aggregated_files), directory)
                return aggregated_files

            nested_targets = []
            for child_dir in sorted(p for p in directory.iterdir() if p.is_dir()):
                child_aggregated_dir = child_dir / "aggregated"
                child_files = []
                if child_aggregated_dir.exists() and child_aggregated_dir.is_dir():
                    child_files = _list_aggregated_files(child_aggregated_dir)
                if not child_files:
                    child_files = _list_aggregated_files(child_dir)
                nested_targets.extend(child_files)

            if nested_targets:
                logger.info(
                    "📁 Found %s aggregated raw file(s) under run directories in %s",
                    len(nested_targets),
                    directory,
                )
                return nested_targets

            loose_json_files = sorted(directory.glob("*.json"))
            loose_jsonl_files = sorted(directory.glob("*.jsonl"))
            if loose_json_files or loose_jsonl_files:
                logger.error(
                    "Directory %s contains non-aggregated JSON/JSONL files. "
                    "Please pass an explicit aggregated file (raw_responses_*.json/jsonl) or run directory.",
                    directory,
                )
                return []

            logger.error("No aggregated raw files found in directory: %s", directory)
            return []

        if raw_path_arg:
            if raw_path_arg.is_dir():
                parse_targets = _collect_parse_targets(raw_path_arg)
                if not parse_targets:
                    return 1
            elif raw_path_arg.is_file():
                suffix = raw_path_arg.suffix.lower()
                if suffix in {".json", ".jsonl"}:
                    parse_targets = [raw_path_arg]
                    logger.info("📁 Parsing raw file: %s", raw_path_arg)
                else:
                    logger.error("Unsupported raw file type: %s", raw_path_arg.suffix)
                    return 1
            else:
                logger.error("Raw path not found: %s", raw_path_arg)
                return 1
        else:
            default_dir = config.RAW_OUTPUT_DIR
            parse_targets = _collect_parse_targets(default_dir)
            if not parse_targets:
                return 1
            logger.info("📁 Using default raw directory: %s", default_dir)

    raw_input_param = None
    if stage in {"raw", "full", "challenge"}:
        raw_input_param = str(raw_output_path) if raw_output_path else None
    elif stage == "parse" and len(parse_targets) == 1:
        raw_input_param = str(parse_targets[0])

    # 创建批量分析器
    analyzer = BatchAnalyzer(config)
    skipped_batches = []
    failed_batches = []

    # 执行批量分析
    logger.info("=" * 60)
    logger.info("STARTING BATCH ANALYSIS")
    logger.info("=" * 60)

    def verify_results(results_df):
        if results_df is not None and not results_df.empty:
            logger.info("=" * 60)
            logger.info("FINAL VERIFICATION")
            logger.info("=" * 60)

            article_ids = results_df['#'].unique()
            logger.info("Unique articles: %s", len(article_ids))

            # 检查前3篇文章
            for article_id in article_ids[:3]:
                article_rows = results_df[results_df['#'] == article_id]
                sources = article_rows['source'].tolist()
                logger.info("Article #%s: %s rows (%s, ...)", article_id, len(sources), sources[0])

                if 'human' not in sources:
                    logger.warning("  ⚠️ WARNING: Missing human row")

                ai_sources = [s for s in sources if s != 'human']
                expected_runs = analyzer.last_parse_run_counts.get(str(article_id))
                if expected_runs is None:
                    expected_runs = analyzer.last_parse_run_counts.get(article_id)
                if expected_runs is None:
                    expected_runs = config.get_ai_runs()

                majority_row_present = any("majority-vote" in str(src).lower() for src in ai_sources)
                success_count = None
                human_rows = article_rows[article_rows['source'] == 'human']
                if not human_rows.empty:
                    human_record = human_rows.iloc[0]
                    success_raw = human_record.get(analyzer.AI_SUCCESS_COUNT_COL, '')
                    try:
                        success_count = int(float(success_raw))
                    except (TypeError, ValueError):
                        success_count = None

                expected_ai = expected_runs
                should_have_majority = (
                    config.ENABLE_MAJORITY_VOTE
                    and expected_runs > 1
                    and (
                        majority_row_present
                        or (success_count is not None and success_count >= 2)
                    )
                )
                if should_have_majority:
                    expected_ai += 1  # +1 for majority vote row

                if len(ai_sources) != expected_ai:
                    logger.warning("  ⚠️ WARNING: Expected %s AI rows, found %s", expected_ai, len(ai_sources))
        else:
            logger.warning("⚠️ No results dataframe produced.")

    try:
        if stage == "raw":
            raw_output = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_data_path=raw_input_param,
                stage="raw",
                use_all_runs=parse_all_runs
            )
            logger.info("📦 Raw responses written to: %s", raw_output)
            logger.info("⏰ End time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            logger.info("=" * 60)
            logger.info("✅ RAW GENERATION COMPLETED")
            logger.info("=" * 60)
            return 0

        if stage == "challenge":
            challenge_output = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_data_path=raw_input_param,
                stage="challenge",
                challenge_report_path=str(challenge_report_path) if challenge_report_path else None,
            )
            if isinstance(challenge_output, dict):
                for key, value in challenge_output.items():
                    logger.info("📄 %s: %s", key, value)
            logger.info("⏰ End time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            logger.info("=" * 60)
            logger.info("✅ CHALLENGE REPORT COMPLETED")
            logger.info("=" * 60)
            return 0

        if stage == "parse" and len(parse_targets) > 1:
            total_runs = len(parse_targets)
            successful_batches = 0
            for idx, jsonl_path in enumerate(parse_targets, start=1):
                logger.info("-" * 60)
                logger.info("BATCH %s/%s: %s", idx, total_runs, jsonl_path)
                logger.info("-" * 60)
                try:
                    results_df = analyzer.process_batch(
                        excel_path=str(config.EXCEL_PATH),
                        raw_data_path=str(jsonl_path),
                        stage="parse",
                        use_all_runs=parse_all_runs
                    )
                except Exception as exc:
                    logger.exception("Failed to parse %s: %s", jsonl_path, exc)
                    if skip_bad:
                        skipped_batches.append((jsonl_path, str(exc)))
                        continue
                    raise

                if (results_df is None) or results_df.empty:
                    message = "Parse returned no results"
                    logger.error("  ❌ %s", message)
                    if skip_bad:
                        skipped_batches.append((jsonl_path, message))
                        continue
                    failed_batches.append((jsonl_path, message))
                    continue

                verify_results(results_df)
                successful_batches += 1

                if analyzer.last_raw_source_path:
                    logger.info("📁 Raw source path: %s", analyzer.last_raw_source_path)

                logger.info("⏰ End time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                logger.info("=" * 60)
                logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
                logger.info("=" * 60)

            if skipped_batches:
                logger.info("-" * 60)
                logger.info("SKIPPED BATCHES SUMMARY")
                logger.info("-" * 60)
                for path, reason in skipped_batches:
                    logger.info("⏭️ %s -> %s", path, reason)
            if failed_batches:
                logger.error("-" * 60)
                logger.error("FAILED BATCHES SUMMARY")
                logger.error("-" * 60)
                for path, reason in failed_batches:
                    logger.error("❌ %s -> %s", path, reason)
                return 1

            if successful_batches == 0 and total_runs > 0 and not skip_bad:
                logger.error("No parse batch produced valid results.")
                return 1

            return 0

        try:
            results_df = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_data_path=raw_input_param,
                stage=stage,
                use_all_runs=parse_all_runs,
                challenge_report_path=str(challenge_report_path) if challenge_report_path else None,
            )
        except Exception as exc:
            if stage == "parse" and skip_bad:
                logger.exception("Failed to parse %s: %s", raw_input_param, exc)
                logger.info("⏭️ Skipping per --skip-bad flag")
                return 0
            raise

        if stage == "parse" and ((results_df is None) or results_df.empty):
            message = "Parse returned no results"
            logger.error("%s", message)
            if skip_bad:
                logger.info("⏭️ Skipping per --skip-bad flag")
                return 0
            return 1

        verify_results(results_df)

        if stage in {"parse", "full"} and analyzer.last_raw_source_path:
            logger.info("📁 Raw source path: %s", analyzer.last_raw_source_path)

        logger.info("⏰ End time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        logger.info("=" * 60)
        logger.info("✅ PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception("Pipeline failed with error: %s", e)
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
