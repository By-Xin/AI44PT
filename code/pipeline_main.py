"""
批量分析流水线主程序 - 4PT框架批量文章分析
"""
from datetime import datetime
from config import Config
from batch_analyzer import BatchAnalyzer


def main():
    """批量分析主入口"""
    print("=" * 60)
    print("4PT BATCH ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 初始化配置
    config = Config()

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
        return

    print("\n✅ Configuration validated")

    # 创建批量分析器
    analyzer = BatchAnalyzer(config)

    # 执行批量分析
    print("\n" + "=" * 60)
    print("STARTING BATCH ANALYSIS")
    print("=" * 60)

    try:
        results_df = analyzer.process_batch()

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
