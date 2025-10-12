"""
4PT批量分析系统 - 模块化批处理架构

这个包提供了一个完整的模块化批量分析系统，用于处理学术论文的4PT框架分类。

核心模块：
- Config: 完整配置管理（包含所有批处理参数）
- DocumentReader: PDF和Markdown文档读取器

批处理模块：
- ResponseParser: AI响应解析与标准化
- MajorityVoter: 多次运行的投票机制
- ConsensusAnalyzer: 类型共识分析
- DecisionTreeClassifier: 决策树分类器
- BatchAnalyzer: 批处理协调器

使用示例:
    from batch_analyzer import BatchAnalyzer
    from config import Config

    config = Config()
    analyzer = BatchAnalyzer(config)
    results = analyzer.process_batch()

或直接运行:
    python pipeline_main.py
"""

__version__ = "3.0.0"
__author__ = "4PT Analysis Team"
__all__ = [
    "Config",
    "DocumentReader",
    "ResponseParser",
    "BatchAnalyzer",
]
