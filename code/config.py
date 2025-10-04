"""
配置模块 - 集中管理所有配置信息
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """系统配置类"""
    
    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent
    
    # 文件路径
    CODEBOOK_MD = PROJECT_ROOT / "data" / "processed" / "TheCodingTask.md"
    PAPER_PDF = PROJECT_ROOT / "data" / "processed" / "sample_paper.pdf"
    
    # OpenAI配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CLS_MODEL = "gpt-5-2025-08-07"
    
    # 分析设置
    MAX_ITEMS = 1  # 每次处理的项目数量
    SEED = 7       # 随机种子
    
    # 输出配置
    RESULTS_DIR = PROJECT_ROOT / "results"
    
    @classmethod
    def validate(cls) -> bool:
        """验证必要的配置是否存在"""
        if not cls.OPENAI_API_KEY:
            return False
        if not cls.CODEBOOK_MD.exists():
            print(f"Warning: Codebook not found at {cls.CODEBOOK_MD}")
            return False
        if not cls.PAPER_PDF.exists():
            print(f"Warning: Paper not found at {cls.PAPER_PDF}")
            return False
        return True