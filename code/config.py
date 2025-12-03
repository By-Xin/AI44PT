"""
配置模块 - 4PT批量分析系统的完整配置
"""
import os
import random
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """4PT分析系统配置类"""

    # ==================== 项目路径配置 ====================
    PROJECT_ROOT = Path(__file__).parent.parent

    # 核心文件路径
    CODINGTASK_MD = PROJECT_ROOT / "data" / "instructions" / "TheCodingTask.md"
    EXECUTIVESUMMARY_MD = PROJECT_ROOT / "data" / "instructions" / "ExecutiveSummary.md"
    MAINBODY_MD = PROJECT_ROOT / "data" / "instructions" / "MainBody.md"

    # Excel和PDF路径配置
    EXCEL_PATH = PROJECT_ROOT / "data" / "processed" / "JRGsamples" / "JRG40.xlsx"
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
    DEFAULT_TEXT_VERBOSITY = "medium"  # "low", "medium", "high"

    # ==================== Gemini配置 ====================
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-3-pro-preview"

    # ==================== LLM Provider配置 ====================
    # 可选值: "openai", "gemini"
    # LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
    LLM_PROVIDER = "openai"  # Primary provider (kept for backward compatibility)
    
    # List of providers to run simultaneously
    # Options: "openai", "gemini"
    ENABLED_PROVIDERS = ["openai", "gemini"]
    

    # ==================== 批处理参数 ====================
    DEBUG_MODE = False  # 设为True将限制处理数量并降低模型开销
    DEFAULT_AI_RUNS = 3  # 每篇文章的独立AI运行次数
    ENABLE_SHUFFLE = False  # 是否启用问题随机排序

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

    # 额外问题列映射（Q18-Q25）
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
        2: "Provide arguments that support your response to Q1 (Does the article fit in the universe of sustainability analyses we seek to assess?)",
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
    def validate(cls) -> bool:
        """
        验证必要的配置是否存在

        Returns:
            bool: 配置是否有效
        """
        # Validate all enabled providers
        if "openai" in cls.ENABLED_PROVIDERS:
            if not cls.OPENAI_API_KEY:
                print("Error: OPENAI_API_KEY not found in environment")
                print("Please set it in .env file")
                return False
        
        if "gemini" in cls.ENABLED_PROVIDERS:
            if not cls.GEMINI_API_KEY:
                print("Error: GEMINI_API_KEY not found in environment")
                print("Please set it in .env file")
                return False

        # Legacy validation for single provider if ENABLED_PROVIDERS is not used/empty (fallback)
        if not cls.ENABLED_PROVIDERS:
            if cls.LLM_PROVIDER == "openai":
                if not cls.OPENAI_API_KEY:
                    print("Error: OPENAI_API_KEY not found in environment")
                    return False
            elif cls.LLM_PROVIDER == "gemini":
                if not cls.GEMINI_API_KEY:
                    print("Error: GEMINI_API_KEY not found in environment")
                    return False

        if not cls.CODINGTASK_MD.exists():
            print(f"Error: Coding Task not found at {cls.CODINGTASK_MD}")
            return False

        if not cls.EXECUTIVESUMMARY_MD.exists():
            print(f"Error: Executive Summary not found at {cls.EXECUTIVESUMMARY_MD}")
            return False

        if not cls.MAINBODY_MD.exists():
            print(f"Error: Main Body not found at {cls.MAINBODY_MD}")
            return False

        if not cls.EXCEL_PATH.exists():
            print(f"Error: Excel file not found at {cls.EXCEL_PATH}")
            return False

        if not cls.PDF_FOLDER.exists():
            print(f"Error: PDF folder not found at {cls.PDF_FOLDER}")
            return False

        return True

    @classmethod
    def display_config(cls):
        """显示当前配置（用于调试）"""
        print("=" * 60)
        print("CONFIGURATION")
        print("=" * 60)
        print(f"Project Root: {cls.PROJECT_ROOT}")
        print(f"Coding Task: {cls.CODINGTASK_MD}")
        print(f"Exec Summary: {cls.EXECUTIVESUMMARY_MD}")
        print(f"Main Body: {cls.MAINBODY_MD}")
        print(f"Excel Path: {cls.EXCEL_PATH}")
        print(f"PDF Folder: {cls.PDF_FOLDER}")
        print(f"Results Dir: {cls.RESULTS_DIR}")
        print(f"LLM Provider: {cls.LLM_PROVIDER}")
        print(f"Enabled Providers: {cls.ENABLED_PROVIDERS}")
        
        if "openai" in cls.ENABLED_PROVIDERS:
            print(f"OpenAI Model: {cls.CLS_MODEL}")
            print(f"OpenAI Key: {'✓ Set' if cls.OPENAI_API_KEY else '✗ Missing'}")
            
        if "gemini" in cls.ENABLED_PROVIDERS:
            print(f"Gemini Model: {cls.GEMINI_MODEL}")
            print(f"Gemini Key: {'✓ Set' if cls.GEMINI_API_KEY else '✗ Missing'}")
            
        print(f"Temperature: {cls.TEMPERATURE}")
        print(f"AI Runs: {cls.get_ai_runs()}")
        print(f"Reasoning Effort: {cls.get_reasoning_effort()}")
        print(f"Text Verbosity: {cls.get_text_verbosity()}")
        print(f"Majority Vote: {cls.ENABLE_MAJORITY_VOTE}")
        print(f"Shuffle Questions: {cls.ENABLE_SHUFFLE}")
        print(f"Debug Mode: {cls.DEBUG_MODE}")
        print(f"API Key: {'✓ Set' if cls.OPENAI_API_KEY else '✗ Missing'}")
        print("=" * 60)
