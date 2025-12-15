"""
批量分析流水线主程序 - 4PT框架批量文章分析
"""
import argparse
import logging
from datetime import datetime
from pathlib import Path

from .config import Config
from .pipeline.batch_analyzer import BatchAnalyzer
from .utils.logging_utils import setup_logging, get_logger


def parse_cli_args():
    parser = argparse.ArgumentParser(description="4PT batch analysis pipeline")
    parser.add_argument(
        "--config",
        dest="config_path",
        help="Path to YAML config (supports 'extends')",
    )
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
    parser.add_argument(
        "--parse-all-runs",
        dest="parse_all_runs",
        action="store_true",
        help="During parse, include every run found in JSON instead of limiting to configured ai_runs",
    )
    return parser.parse_args()


def main():
    """批量分析主入口"""
    setup_logging(logging.INFO)
    logger = get_logger(__name__)

    args = parse_cli_args()
    stage = args.stage
    config_path = Path(args.config_path).expanduser() if args.config_path else Config.DEFAULT_CONFIG_PATH
    excel_override = Path(args.excel_path).expanduser() if args.excel_path else None
    raw_path_input = args.raw_path
    raw_path_arg = Path(raw_path_input).expanduser() if raw_path_input else None
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
    logger.info("=" * 60)
    logger.info("Start time: %s", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # 初始化配置（YAML 单一真源）
    Config.load_from_yaml(config_path)
    config = Config()
    if excel_override:
        logger.warning("--excel-path overrides YAML config (prefer using a dedicated YAML profile).")
        Config.EXCEL_PATH = excel_override
        config.EXCEL_PATH = excel_override
    if debug_mode:
        logger.warning("--debug overrides YAML config (prefer using a dedicated YAML profile).")
        Config.DEBUG_MODE = True
        config.DEBUG_MODE = True

    # 显示配置信息
    logger.info("📋 Configuration:")
    logger.info("   Config YAML: %s", config_path)
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

    # 验证配置
    if not config.validate():
        logger.error("Configuration validation failed!")
        logger.error("Please check:")
        logger.error("  - OPENAI_API_KEY is set in .env file")
        logger.error("  - Codebook file exists at: %s", config.CODINGTASK_MD)
        logger.error("  - Excel file exists at: %s", config.EXCEL_PATH)
        return 1

    logger.info("✅ Configuration validated")

    raw_output_path = None
    parse_targets = []

    if stage in {"raw", "full"}:
        if raw_path_arg:
            if raw_path_arg.is_dir():
                raw_path_arg.mkdir(parents=True, exist_ok=True)
                raw_output_path = raw_path_arg / f"raw_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
                logger.info("📁 Raw output target: %s", raw_output_path)
            else:
                raw_output_path = raw_path_arg
                logger.info("📁 Raw output target: %s", raw_output_path)
    elif stage == "parse":
        def _collect_parse_targets(directory: Path):
            aggregated_dir = directory / "aggregated"
            if aggregated_dir.exists() and aggregated_dir.is_dir():
                aggregated_files = sorted(aggregated_dir.glob("*.json"))
                if aggregated_files:
                    logger.info("📁 Found %s aggregated JSON file(s) in %s", len(aggregated_files), aggregated_dir)
                    return aggregated_files

            aggregated_files = sorted(directory.glob("raw_responses_*.json"))
            if aggregated_files:
                logger.info("📁 Found %s aggregated JSON file(s) in %s", len(aggregated_files), directory)
                return aggregated_files

            json_files = sorted(directory.glob("*.json"))
            if json_files:
                logger.info("📁 Found %s JSON file(s) in %s; will merge during parse", len(json_files), directory)
                return [directory]
            logger.error("No JSON files found in directory: %s", directory)
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
    if stage in {"raw", "full"}:
        raw_input_param = str(raw_output_path) if raw_output_path else None
    elif stage == "parse" and len(parse_targets) == 1:
        raw_input_param = str(parse_targets[0])

    # 创建批量分析器
    analyzer = BatchAnalyzer(config)
    skipped_batches = []

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

                tie_detected = False
                human_rows = article_rows[article_rows['source'] == 'human']
                if not human_rows.empty:
                    human_record = human_rows.iloc[0]
                    ai_agreement = str(human_record.get(analyzer.AI_AGREEMENT_COL, '') or '').lower()
                    human_vs_ai_text = str(human_record.get(analyzer.HUMAN_VS_AI_COL, '') or '').lower()
                    if 'split consensus' in ai_agreement or 'tie' in human_vs_ai_text:
                        tie_detected = True

                expected_ai = expected_runs
                if (config.ENABLE_MAJORITY_VOTE and expected_runs > 1 and not tie_detected):
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

        if stage == "parse" and len(parse_targets) > 1:
            total_runs = len(parse_targets)
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
                    logger.warning("  ⚠️ %s", message)
                    if skip_bad:
                        skipped_batches.append((jsonl_path, message))
                        continue

                verify_results(results_df)

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
            return 0

        try:
            results_df = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_data_path=raw_input_param,
                stage=stage,
                use_all_runs=parse_all_runs
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
