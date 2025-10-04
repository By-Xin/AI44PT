"""
4PT分析系统 - 模块化版本

这个包提供了一个模块化的4PT框架分析系统，包含以下组件：

- Config: 配置管理
- DocumentReader: 文档读取器
- FourPTAnalyzer: 4PT分析器
- ResultSaver: 结果保存器
- FourPTSystem: 主系统类

用法示例:
    from main import FourPTSystem
    
    system = FourPTSystem()
    system.run()
"""

# 模块导入在实际使用时进行，避免循环导入问题

__version__ = "2.0.0"
__all__ = ["Config", "DocumentReader", "FourPTAnalyzer", "ResultSaver"]