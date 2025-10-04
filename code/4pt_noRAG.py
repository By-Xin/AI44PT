#!/usr/bin/env python3
"""
4PT分析系统 - 模块化版本
从 notebooks/4pt_noRAG.ipynb 转换而来
"""

# 导入模块化组件
try:
    from config import Config
    from document_reader import DocumentReader
    from analyzer import FourPTAnalyzer
    from result_saver import ResultSaver
except ImportError:
    # 如果作为独立脚本运行，直接导入
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    
    from config import Config
    from document_reader import DocumentReader
    from analyzer import FourPTAnalyzer
    from result_saver import ResultSaver

from main import FourPTSystem


# 模块化版本不需要重复定义这些函数，它们已经在独立模块中实现


# 4PT问题和分析函数已模块化到 analyzer.py 中


def run_legacy_mode():
    """
    运行传统模式分析（保持向后兼容）
    """
    print("🔄 Running in legacy compatibility mode...")
    system = FourPTSystem()
    system.run()


if __name__ == '__main__':
    # 使用新的模块化系统
    run_legacy_mode()

        

# For reference, the human coder's answer for this paper is provided below as comments:
# 1. Yes
# 2. Interaction of program design conditions in affecting performance of voluntary programs
# 3. No
# 4. Geographical focus in several countries with no clearly specified on the ground problem
# 5. Looks at the topic of low carbon building and city development across cases in Australia, the Netherlands and the US
# 6. Yes
# 7. Explores implications on voluntary program performance of the diffusion network
# 8. This article has introduced the diffusion network perspective as a critical condition to understand voluntary program performance
# 9. Analysis on generalizability is valid. Proceed to the next questions on utility.
# 10. Yes
# 11. Key objective: determinants of voluntary program performance, which originates from high cost of direct regulatory intervention
# 12. Voluntary programs aim to change the behavior of individuals and organizations, but without the force of law. They have rapidly become popular governance instruments in situations in which it is too costly or difficult to implement direct regulatory interventions, for instance because of political unwillingness (Darnall & Carmin 2005). They also provide an opportunity to showcase and market desired “beyond compliance” behavior, or to reward leading firms (Saurwein 2011).
# 13. No
# 14. Looks at how diffusion network perspective can relate to better voluntary program results
# 15. The diffusion network perspective, as conceptualized in this article, brings together these insights and argues that the stronger the diffusion network, the more likely it is that a voluntary program will achieve the desired results.
# 16. Analysis on generalizability is valid. Proceed to the next questions on utility.
# 17. Type 2
# 18. 4 - Hard
