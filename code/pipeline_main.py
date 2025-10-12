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
        help="Path to raw JSONL file (input for parse stage, output path for raw/full stages)",
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
    return parser.parse_args()


def main():
    """批量分析主入口"""
    args = parse_cli_args()
    stage = args.stage
    excel_override = Path(args.excel_path).expanduser() if args.excel_path else None
    raw_path = args.raw_path
    debug_mode = bool(args.debug)

    print("=" * 60)
    print("4PT BATCH ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Selected stage: {stage.upper()}")
    if raw_path:
        print(f"Raw path: {raw_path}")
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

    # 验证配置
    if not config.validate():
        print("\n❌ Configuration validation failed!")
        print("Please check:")
        print("  - OPENAI_API_KEY is set in .env file")
        print("  - Codebook file exists at:", config.CODEBOOK_MD)
        print("  - Excel file exists at:", config.EXCEL_PATH)
        return 1

    if stage == "parse" and not raw_path:
        print("\n❌ Parse stage requires --raw-path to be specified")
        return 1

    print("\n✅ Configuration validated")

    # 创建批量分析器
    analyzer = BatchAnalyzer(config)

    # 执行批量分析
    print("\n" + "=" * 60)
    print("STARTING BATCH ANALYSIS")
    print("=" * 60)

    try:
        if stage == "raw":
            raw_output = analyzer.process_batch(
                excel_path=str(config.EXCEL_PATH),
                raw_jsonl_path=raw_path,
                stage="raw"
            )
            print(f"\n📦 Raw responses written to: {raw_output}")
            print(f"\n⏰ End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            print("✅ RAW GENERATION COMPLETED")
            print("=" * 60)
            return 0

        results_df = analyzer.process_batch(
            excel_path=str(config.EXCEL_PATH),
            raw_jsonl_path=raw_path,
            stage=stage
        )

        # 最终验证
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

        if stage in {"parse", "full"} and analyzer.last_raw_jsonl_path:
            print(f"\n📁 Raw JSONL path: {analyzer.last_raw_jsonl_path}")

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
