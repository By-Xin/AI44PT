"""
配置模块 - 4PT批量分析系统的完整配置
"""
import os
import re
import random
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


@dataclass
class QuestionMaps:
    """统一管理人类/AI/概念问题的列映射"""
    human: Dict[int, str]
    ai: Dict[int, str]
    pkey: Dict[str, str]

    def as_qnum_map(self, prefer_human: bool = True) -> Dict[int, str]:
        """返回综合的题号到列名映射，支持优先人类列"""
        merged: Dict[int, str] = dict(self.ai)
        if prefer_human:
            merged.update(self.human)
        else:
            for k, v in self.human.items():
                merged.setdefault(k, v)
        return merged


class Config:
    """4PT分析系统配置类"""

    # ==================== 项目路径配置 ====================
    PROJECT_ROOT = Path(__file__).parent.parent

    # 核心文件路径
    CODINGTASK_MD = PROJECT_ROOT / "data" / "instructions" / "TheCodingTask.md"
    EXECUTIVESUMMARY_MD = PROJECT_ROOT / "data" / "instructions" / "ExecutiveSummary.md"
    MAINBODY_MD = PROJECT_ROOT / "data" / "instructions" / "MainBody.md"

    # Excel和PDF路径配置
    EXCEL_PATH = PROJECT_ROOT / "data" / "processed" / "JRGsamples" / "JRG_full.xlsx"
    PDF_FOLDER = PROJECT_ROOT / "data" / "processed" / "JRGsamples"

    # 输出配置
    RESULTS_DIR = PROJECT_ROOT / "results"
    RAW_OUTPUT_DIR = RESULTS_DIR / "raw_responses"

    # ==================== OpenAI配置 ====================
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CLS_MODEL = "gpt-5-2025-08-07"
    # CLS_MODEL = "gpt-5.1"
    TEMPERATURE = 0.1  # 0.0为完全确定性，0.1为轻微随机性

    # OpenAI API高级参数（适用于支持的模型）
    DEFAULT_REASONING_EFFORT = "high"  # "low", "medium", "high"
    DEFAULT_TEXT_VERBOSITY = "high"  # "low", "medium", "high"

    # ==================== Gemini配置 ====================
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-3-pro-preview"

    # ==================== LLM Provider配置 ====================
    # 可选值: "openai", "gemini"
    # LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
    LLM_PROVIDER = "openai"  # Primary provider (kept for backward compatibility)
    
    # List of providers to run simultaneously
    # Options: "openai", "gemini"
    # ENABLED_PROVIDERS = ["openai", "gemini"]
    ENABLED_PROVIDERS = ["openai"]

    # ==================== 批处理参数 ====================
    DEBUG_MODE = False  # 设为True将限制处理数量并降低模型开销
    DEFAULT_AI_RUNS = 2  # 每篇文章的独立AI运行次数
    ENABLE_SHUFFLE = False  # 是否启用问题随机排序

    # ==================== 并发/输出配置 ====================
    # 是否启用多线程并发调用（禁用时退回串行执行）
    ENABLE_CONCURRENT_CALLS = True
    # 最大拼接的文章正文字符数（防止超长prompt导致截断/成本），None 表示不截断
    ARTICLE_TEXT_MAX_CHARS = 120000
    # 同时在飞的文章数（0 或 None 表示不限制文章层）
    MAX_PARALLEL_ARTICLES = 8
    # 全局在飞的 API 调用上限（0 或 None 表示不限制）
    MAX_TOTAL_CONCURRENT_CALLS = 8
    # 各 provider 单独的并发上限（0 或 None 表示不限制）
    MAX_CONCURRENT_OPENAI = 6
    MAX_CONCURRENT_GEMINI = 6
    # JSONL 追加写入时，每条都刷盘（确保崩溃损失最小，代价是更多 IO）
    JSONL_FLUSH_EACH_WRITE = True

    # ==================== Majority Vote配置 ====================
    ENABLE_MAJORITY_VOTE = True
    # Q15 is new Uncertainty Check (Objective)
    # Q16 is Classification (Objective)
    # Q17 is Global Confidence (Objective)
    # Q18, Q20, Q22, Q24 are Type Support (Objective - Yes/No)
    # Q19, Q21, Q23, Q25 are Type Confidence (Objective - 1-5)
    OBJECTIVE_QUESTIONS = [1, 3, 6, 9, 12, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]
    SUBJECTIVE_QUESTIONS = [2, 4, 5, 7, 8, 10, 11, 13, 14]
    TOTAL_QUESTIONS = 25

    # Key Question IDs
    Q_ID_UNCERTAINTY = 15
    Q_ID_CLASSIFICATION = 16
    Q_ID_CONFIDENCE = 17

    # 问题类型分组
    TYPE_CLASS_YN_QUESTIONS = [18, 20, 22, 24]
    TYPE_CONFIDENCE_QUESTIONS = [19, 21, 23, 25]

    # Confidence量表标签
    CONFIDENCE_LABELS = {
        1: "Very Unconfident",
        2: "Unconfident",
        3: "Neutral",
        4: "Confident",
        5: "Very Confident",
    }

    # 概念问题键（P_KEY）
    P_KEYS = {
        "IN_UNIVERSE": "P_IN_UNIVERSE",
        "PROBLEM_DESCRIPTION": "P_PROBLEM_DESCRIPTION",
        "GROUND_PROBLEM_YN": "P_GROUND_PROBLEM_YN",
        "GROUND_PROBLEM_ARGS": "P_GROUND_PROBLEM_ARGS",
        "GROUND_PROBLEM_QUOTES": "P_GROUND_PROBLEM_QUOTES",
        "BEYOND_GROUND_YN": "P_BEYOND_GROUND_YN",
        "BEYOND_GROUND_ARGS": "P_BEYOND_GROUND_ARGS",
        "BEYOND_GROUND_QUOTES": "P_BEYOND_GROUND_QUOTES",
        "SELF_INTEREST_YN": "P_SELF_INTEREST_YN",
        "SELF_INTEREST_ARGS": "P_SELF_INTEREST_ARGS",
        "SELF_INTEREST_QUOTES": "P_SELF_INTEREST_QUOTES",
        "BEYOND_SELF_YN": "P_BEYOND_SELF_YN",
        "BEYOND_SELF_ARGS": "P_BEYOND_SELF_ARGS",
        "BEYOND_SELF_QUOTES": "P_BEYOND_SELF_QUOTES",
        "FINAL_TYPE": "P_FINAL_TYPE",
        "UNCERTAINTY_CHECK": "P_UNCERTAINTY_CHECK",
        "FINAL_TYPE_CONFIDENCE": "P_FINAL_TYPE_CONFIDENCE",
        "TYPE1_SUPPORT": "P_TYPE1_SUPPORT",
        "TYPE1_CONFIDENCE": "P_TYPE1_CONFIDENCE",
        "TYPE2_SUPPORT": "P_TYPE2_SUPPORT",
        "TYPE2_CONFIDENCE": "P_TYPE2_CONFIDENCE",
        "TYPE3_SUPPORT": "P_TYPE3_SUPPORT",
        "TYPE3_CONFIDENCE": "P_TYPE3_CONFIDENCE",
        "TYPE4_SUPPORT": "P_TYPE4_SUPPORT",
        "TYPE4_CONFIDENCE": "P_TYPE4_CONFIDENCE",
    }

    HUMAN_QNUM_TO_PKEY = {
        1: P_KEYS["IN_UNIVERSE"],
        2: P_KEYS["PROBLEM_DESCRIPTION"],
        3: P_KEYS["GROUND_PROBLEM_YN"],
        4: P_KEYS["GROUND_PROBLEM_ARGS"],
        5: P_KEYS["GROUND_PROBLEM_QUOTES"],
        6: P_KEYS["BEYOND_GROUND_YN"],
        7: P_KEYS["BEYOND_GROUND_ARGS"],
        8: P_KEYS["BEYOND_GROUND_QUOTES"],
        9: P_KEYS["SELF_INTEREST_YN"],
        10: P_KEYS["SELF_INTEREST_ARGS"],
        11: P_KEYS["SELF_INTEREST_QUOTES"],
        12: P_KEYS["BEYOND_SELF_YN"],
        13: P_KEYS["BEYOND_SELF_ARGS"],
        14: P_KEYS["BEYOND_SELF_QUOTES"],
        15: P_KEYS["FINAL_TYPE"],
    }

    AI_QNUM_TO_PKEY = {
        1: P_KEYS["IN_UNIVERSE"],
        2: P_KEYS["PROBLEM_DESCRIPTION"],
        3: P_KEYS["GROUND_PROBLEM_YN"],
        4: P_KEYS["GROUND_PROBLEM_ARGS"],
        5: P_KEYS["GROUND_PROBLEM_QUOTES"],
        6: P_KEYS["BEYOND_GROUND_YN"],
        7: P_KEYS["BEYOND_GROUND_ARGS"],
        8: P_KEYS["BEYOND_GROUND_QUOTES"],
        9: P_KEYS["SELF_INTEREST_YN"],
        10: P_KEYS["SELF_INTEREST_ARGS"],
        11: P_KEYS["SELF_INTEREST_QUOTES"],
        12: P_KEYS["BEYOND_SELF_YN"],
        13: P_KEYS["BEYOND_SELF_ARGS"],
        14: P_KEYS["BEYOND_SELF_QUOTES"],
        15: P_KEYS["UNCERTAINTY_CHECK"],
        16: P_KEYS["FINAL_TYPE"],
        17: P_KEYS["FINAL_TYPE_CONFIDENCE"],
        18: P_KEYS["TYPE1_SUPPORT"],
        19: P_KEYS["TYPE1_CONFIDENCE"],
        20: P_KEYS["TYPE2_SUPPORT"],
        21: P_KEYS["TYPE2_CONFIDENCE"],
        22: P_KEYS["TYPE3_SUPPORT"],
        23: P_KEYS["TYPE3_CONFIDENCE"],
        24: P_KEYS["TYPE4_SUPPORT"],
        25: P_KEYS["TYPE4_CONFIDENCE"],
    }

    # 额外问题列映射（Q18-Q25及AI专属列）
    ADDITIONAL_QUESTION_COLUMNS = {
        18: "Type 1 classification support (Yes/No) [Q18]",
        19: "Type 1 classification confidence (1-5) [Q19]",
        20: "Type 2 classification support (Yes/No) [Q20]",
        21: "Type 2 classification confidence (1-5) [Q21]",
        22: "Type 3 classification support (Yes/No) [Q22]",
        23: "Type 3 classification confidence (1-5) [Q23]",
        24: "Type 4 classification support (Yes/No) [Q24]",
        25: "Type 4 classification confidence (1-5) [Q25]",
    }

    AI_ONLY_PKEY_COLUMNS = {
        P_KEYS["UNCERTAINTY_CHECK"]: "Uncertainty check (ambiguous signals?) [AI Q15]",
        P_KEYS["FINAL_TYPE_CONFIDENCE"]: "4PT classification confidence (1-5) [AI Q17]",
        P_KEYS["TYPE1_SUPPORT"]: ADDITIONAL_QUESTION_COLUMNS[18],
        P_KEYS["TYPE1_CONFIDENCE"]: ADDITIONAL_QUESTION_COLUMNS[19],
        P_KEYS["TYPE2_SUPPORT"]: ADDITIONAL_QUESTION_COLUMNS[20],
        P_KEYS["TYPE2_CONFIDENCE"]: ADDITIONAL_QUESTION_COLUMNS[21],
        P_KEYS["TYPE3_SUPPORT"]: ADDITIONAL_QUESTION_COLUMNS[22],
        P_KEYS["TYPE3_CONFIDENCE"]: ADDITIONAL_QUESTION_COLUMNS[23],
        P_KEYS["TYPE4_SUPPORT"]: ADDITIONAL_QUESTION_COLUMNS[24],
        P_KEYS["TYPE4_CONFIDENCE"]: ADDITIONAL_QUESTION_COLUMNS[25],
    }

    LEGACY_AI_FINAL_TYPE_COLUMN = "AI final 4PT Type [Q16]"

    QUESTION_COLUMN_PATTERN = re.compile(r"\[Q(\d+)\]")

    # Type问题分组
    TYPE_QUESTION_GROUPS = {
        1: {"support": 18, "confidence": 19},
        2: {"support": 20, "confidence": 21},
        3: {"support": 22, "confidence": 23},
        4: {"support": 24, "confidence": 25},
    }

    # ==================== 4PT问题字典（25个问题）====================
    QUESTION_TEXTS = {
        1: "Does the article fit in the universe of sustainability analyses we seek to assess? (Yes/No)",
        2: "What problems or set of problems is the article trying to address? Provide a concise description of the main on-the-ground problem(s).",
        3: "Do the analysis, conclusions, and theories derived from, and directed to, understanding and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)",
        4: "Provide arguments that support your response to Q3 (Does the article address a clearly specified on-ground problem?)",
        5: "Provide some key text passages from the article that support your Q3 response",
        6: "Are the analysis, conclusions, and theories generated to apply beyond understanding, and/or managing a clearly specified 'on the ground' problem or class of problems? (Yes/No)",
        7: "Provide arguments that support your response to Q6 (Does the article generate analysis, conclusions, and theories to apply beyond understanding/managing a clearly specified on-ground problem?)",
        8: "Provide some key text passages from the article that support your Q6 response",
        9: "Do the analysis, conclusions, and theories treat individuals, organizations and states as largely self-interested, satisfaction driven entities that seek to maximize some kind of 'utility' outcome? (Yes/No)",
        10: "Provide arguments that support your response to Q9 (Does the article treat entities as self-interested, utility-maximizing agents?)",
        11: "Provide some key text passages from the article that support your Q9 response",
        12: "Do the analysis incorporate theories and conclusions incorporate an assessment of individuals, organizations and/or states that extends beyond self-interested satisfaction seeking motivations? (Yes/No)",
        13: "Provide arguments that support your response to Q12 (Does the article extend beyond self-interested satisfaction seeking motivations?)",
        14: "Provide some key text passages from the article that support your Q12 response",
        15: "Uncertainty Check: Before classifying, look for ambiguity. Does the article contain competing messages that fit multiple quadrants? Does it lack clear indicators for any specific type? (Yes/No). If Yes, describe the specific ambiguity.",
        16: "Based on your analysis above, what is your final 4PT Type classification? (Type 1 / Type 2 / Type 3 / Type 4 / Uncertain or Not Applicable)",
        17: "How confident are you in your Type classification from Q16? Respond with a confidence level from 1 (Very Unconfident) to 5 (Very Confident), followed by a brief rationale, e.g., \"4 - rationale\".",
        18: "Based on your analysis, do you think this article should be classified as Type 1? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        19: "How confident are you on stating this article should (or should not) be classified as Type 1? Respond with a confidence level from 1 (Very Unconfident) to 5 (Very Confident), followed by a brief rationale, e.g., \"4 - rationale\".",
        20: "Based on your analysis, do you think this article should be classified as Type 2? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        21: "How confident are you on stating this article should (or should not) be classified as Type 2? Respond with a confidence level from 1 (Very Unconfident) to 5 (Very Confident), followed by a brief rationale, e.g., \"4 - rationale\".",
        22: "Based on your analysis, do you think this article should be classified as Type 3? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        23: "How confident are you on stating this article should (or should not) be classified as Type 3? Respond with a confidence level from 1 (Very Unconfident) to 5 (Very Confident), followed by a brief rationale, e.g., \"4 - rationale\".",
        24: "Based on your analysis, do you think this article should be classified as Type 4? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        25: "How confident are you on stating this article should (or should not) be classified as Type 4? Respond with a confidence level from 1 (Very Unconfident) to 5 (Very Confident), followed by a brief rationale, e.g., \"4 - rationale\".",
    }

    # 需要保持相邻的问题组
    SUPPORT_QUESTION_GROUPS = [
        [3, 4, 5],
        [6, 7, 8],
    ]

    # ==================== 问题/列映射辅助 ====================

    @classmethod
    def get_required_ai_columns(cls) -> List[str]:
        """返回需要自动追加的AI专属列"""
        # 去重保持顺序
        seen = set()
        cols: List[str] = []
        for col in cls.AI_ONLY_PKEY_COLUMNS.values():
            if col not in seen:
                cols.append(col)
                seen.add(col)
        return cols

    @classmethod
    def build_question_maps(cls, columns: Iterable[str]) -> QuestionMaps:
        """
        构建统一的列映射：
        - human: 人类Excel中的题号 -> 列名
        - ai: AI题号 -> 列名（通过P_KEY桥接到人类列或AI专属列）
        - pkey: 概念问题键 -> 列名
        """
        human_map: Dict[int, str] = {}
        pkey_map: Dict[str, str] = {}

        for col in columns:
            match = cls.QUESTION_COLUMN_PATTERN.search(str(col))
            if not match:
                continue
            q_num = int(match.group(1))
            pkey = cls.HUMAN_QNUM_TO_PKEY.get(q_num)
            if not pkey:
                continue
            human_map[q_num] = col
            pkey_map[pkey] = col

        # 先把已存在的AI专属列加入pkey映射
        for pkey, col_name in cls.AI_ONLY_PKEY_COLUMNS.items():
            if col_name in columns and pkey not in pkey_map:
                pkey_map[pkey] = col_name

        ai_map: Dict[int, str] = {}
        for q_num, pkey in cls.AI_QNUM_TO_PKEY.items():
            ai_only_col = cls.AI_ONLY_PKEY_COLUMNS.get(pkey)
            col_name = pkey_map.get(pkey) or ai_only_col
            if not col_name and ai_only_col:
                col_name = ai_only_col
                pkey_map.setdefault(pkey, col_name)
            if col_name:
                ai_map[q_num] = col_name

        return QuestionMaps(human=human_map, ai=ai_map, pkey=pkey_map)

    # ==================== 类方法 ====================

    @classmethod
    def get_ai_runs(cls):
        """获取AI运行次数（考虑调试模式）"""
        return 2 if cls.DEBUG_MODE else cls.DEFAULT_AI_RUNS

    @classmethod
    def get_reasoning_effort(cls):
        """获取推理努力程度（考虑调试模式）"""
        return "low" if cls.DEBUG_MODE else cls.DEFAULT_REASONING_EFFORT

    @classmethod
    def get_text_verbosity(cls):
        """获取文本详细程度（考虑调试模式）"""
        return "low" if cls.DEBUG_MODE else cls.DEFAULT_TEXT_VERBOSITY

    @classmethod
    def get_source_id(cls):
        """构建基础source标识（包含模型和参数信息）"""
        ai_runs = cls.get_ai_runs()
        reasoning = cls.get_reasoning_effort()
        verbosity = cls.get_text_verbosity()
        model = cls.GEMINI_MODEL if cls.LLM_PROVIDER == "gemini" else cls.CLS_MODEL
        return f"{model}-temp{cls.TEMPERATURE}-reasoning_{reasoning}-verbosity_{verbosity}"

    @classmethod
    def generate_question_order(cls) -> List[int]:
        """生成问题顺序（支持随机或顺序，依赖题目紧邻）"""
        units = []
        used_numbers = set()

        # 1. 处理必须相邻的问题组
        for group in cls.SUPPORT_QUESTION_GROUPS:
            units.append(list(group))
            used_numbers.update(group)

        # 2. 处理剩余的独立问题
        for q_num in sorted(cls.QUESTION_TEXTS.keys()):
            if q_num in used_numbers:
                continue
            units.append([q_num])

        # 3. 根据配置决定顺序
        if cls.ENABLE_SHUFFLE:
            random.shuffle(units)
        else:
            # 如果不随机，按题号排序（确保问题组按首题号排序）
            units.sort(key=lambda x: x[0])

        # 4. 展平列表
        ordered_questions: List[int] = []
        for unit in units:
            ordered_questions.extend(unit)

        return ordered_questions

    @classmethod
    def setup_directories(cls):
        """确保所有必要的目录存在"""
        cls.RESULTS_DIR.mkdir(exist_ok=True)
        cls.RAW_OUTPUT_DIR.mkdir(exist_ok=True)

    @classmethod
    def validate(cls, stage: str = "full") -> bool:
        """
        按处理阶段验证必要配置

        Returns:
            bool: 配置是否有效
        """
        logger = logging.getLogger(__name__)
        stage_norm = (stage or "full").strip().lower()
        if stage_norm not in {"raw", "parse", "full"}:
            logger.warning("Unknown stage '%s'; fallback to full validation", stage)
            stage_norm = "full"

        needs_generation = stage_norm in {"raw", "full"}
        needs_parse = stage_norm in {"parse", "full"}

        if needs_generation:
            # Validate all enabled providers
            if "openai" in cls.ENABLED_PROVIDERS and not cls.OPENAI_API_KEY:
                logger.error("OPENAI_API_KEY not found in environment. Please set it in .env file.")
                return False

            if "gemini" in cls.ENABLED_PROVIDERS and not cls.GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not found in environment. Please set it in .env file.")
                return False

            # Legacy validation for single provider if ENABLED_PROVIDERS is empty (fallback)
            if not cls.ENABLED_PROVIDERS:
                if cls.LLM_PROVIDER == "openai" and not cls.OPENAI_API_KEY:
                    logger.error("OPENAI_API_KEY not found in environment")
                    return False
                if cls.LLM_PROVIDER == "gemini" and not cls.GEMINI_API_KEY:
                    logger.error("GEMINI_API_KEY not found in environment")
                    return False

            if not cls.CODINGTASK_MD.exists():
                logger.error("Coding Task not found at %s", cls.CODINGTASK_MD)
                return False

            if not cls.EXECUTIVESUMMARY_MD.exists():
                logger.error("Executive Summary not found at %s", cls.EXECUTIVESUMMARY_MD)
                return False

            if not cls.MAINBODY_MD.exists():
                logger.error("Main Body not found at %s", cls.MAINBODY_MD)
                return False

        if needs_parse or needs_generation:
            if not cls.EXCEL_PATH.exists():
                logger.error("Excel file not found at %s", cls.EXCEL_PATH)
                return False

        if needs_generation and not cls.PDF_FOLDER.exists():
            logger.error("PDF folder not found at %s", cls.PDF_FOLDER)
            return False

        return True

    @classmethod
    def display_config(cls):
        """显示当前配置（用于调试）"""
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("CONFIGURATION")
        logger.info("=" * 60)
        logger.info("Project Root: %s", cls.PROJECT_ROOT)
        logger.info("Coding Task: %s", cls.CODINGTASK_MD)
        logger.info("Exec Summary: %s", cls.EXECUTIVESUMMARY_MD)
        logger.info("Main Body: %s", cls.MAINBODY_MD)
        logger.info("Excel Path: %s", cls.EXCEL_PATH)
        logger.info("PDF Folder: %s", cls.PDF_FOLDER)
        logger.info("Results Dir: %s", cls.RESULTS_DIR)
        logger.info("LLM Provider: %s", cls.LLM_PROVIDER)
        logger.info("Enabled Providers: %s", cls.ENABLED_PROVIDERS)
        
        if "openai" in cls.ENABLED_PROVIDERS:
            logger.info("OpenAI Model: %s", cls.CLS_MODEL)
            logger.info("OpenAI Key: %s", "✓ Set" if cls.OPENAI_API_KEY else "✗ Missing")
            
        if "gemini" in cls.ENABLED_PROVIDERS:
            logger.info("Gemini Model: %s", cls.GEMINI_MODEL)
            logger.info("Gemini Key: %s", "✓ Set" if cls.GEMINI_API_KEY else "✗ Missing")
            
        logger.info("Temperature: %s", cls.TEMPERATURE)
        logger.info("AI Runs: %s", cls.get_ai_runs())
        logger.info("Reasoning Effort: %s", cls.get_reasoning_effort())
        logger.info("Text Verbosity: %s", cls.get_text_verbosity())
        logger.info("Majority Vote: %s", cls.ENABLE_MAJORITY_VOTE)
        logger.info("Shuffle Questions: %s", cls.ENABLE_SHUFFLE)
        logger.info("Debug Mode: %s", cls.DEBUG_MODE)
        logger.info("API Key: %s", "✓ Set" if cls.OPENAI_API_KEY else "✗ Missing")
        logger.info("=" * 60)
