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
    CODEBOOK_MD = PROJECT_ROOT / "data" / "processed" / "TheCodingTask.md"

    # Excel和PDF路径配置
    EXCEL_PATH = PROJECT_ROOT / "data" / "processed" / "JRGsamples" / "JRG40.xlsx"
    PDF_FOLDER = PROJECT_ROOT / "data" / "processed" / "JRGsamples"

    # 输出配置
    RESULTS_DIR = PROJECT_ROOT / "results"
    RAW_OUTPUT_DIR = RESULTS_DIR / "raw_responses"

    # ==================== OpenAI配置 ====================
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    CLS_MODEL = "gpt-5-2025-08-07"
    TEMPERATURE = 0.1  # 0.0为完全确定性，0.1为轻微随机性

    # OpenAI API高级参数（适用于支持的模型）
    DEFAULT_REASONING_EFFORT = "medium"  # "low", "medium", "high"
    DEFAULT_TEXT_VERBOSITY = "low"  # "low", "medium", "high"

    # ==================== 批处理参数 ====================
    DEBUG_MODE = False  # 设为True将限制处理数量并降低模型开销
    DEFAULT_AI_RUNS = 3  # 每篇文章的独立AI运行次数

    # ==================== Majority Vote配置 ====================
    ENABLE_MAJORITY_VOTE = True
    OBJECTIVE_QUESTIONS = [1, 3, 6, 9, 12, 15, 16, 17, 20, 23, 26]
    SUBJECTIVE_QUESTIONS = [2, 4, 5, 7, 8, 10, 11, 13, 14, 18, 19, 21, 22, 24, 25, 27, 28]
    TOTAL_QUESTIONS = 28

    # 问题类型分组
    TYPE_CLASS_YN_QUESTIONS = [17, 20, 23, 26]
    TYPE_EXTENT_QUESTIONS = [18, 21, 24, 27]
    TYPE_LIKERT_QUESTIONS = [19, 22, 25, 28]

    # Likert量表标签
    LIKERT_LABELS = {
        1: "Strongly disagree",
        2: "Somewhat disagree",
        3: "Neutral",
        4: "Somewhat agree",
        5: "Strongly agree",
    }

    # 额外问题列映射（Q17-Q28）
    ADDITIONAL_QUESTION_COLUMNS = {
        17: "Type 1 classification support (Yes/No) [Q17]",
        18: "Type 1 classification extent (0-1) [Q18]",
        19: "Type 1 classification Likert (1-5) [Q19]",
        20: "Type 2 classification support (Yes/No) [Q20]",
        21: "Type 2 classification extent (0-1) [Q21]",
        22: "Type 2 classification Likert (1-5) [Q22]",
        23: "Type 3 classification support (Yes/No) [Q23]",
        24: "Type 3 classification extent (0-1) [Q24]",
        25: "Type 3 classification Likert (1-5) [Q25]",
        26: "Type 4 classification support (Yes/No) [Q26]",
        27: "Type 4 classification extent (0-1) [Q27]",
        28: "Type 4 classification Likert (1-5) [Q28]",
    }

    # Type问题分组
    TYPE_QUESTION_GROUPS = {
        1: {"support": 17, "extent": 18, "likert": 19},
        2: {"support": 20, "extent": 21, "likert": 22},
        3: {"support": 23, "extent": 24, "likert": 25},
        4: {"support": 26, "extent": 27, "likert": 28},
    }

    # ==================== 4PT问题字典（28个问题）====================
    QUESTION_TEXTS = {
        1: "Does the article fit in the universe of sustainability analyses we seek to assess? (Yes/No)",
        2: "What problems or set of problems is the article trying to address?",
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
        15: "Based on your analysis above, what is your final 4PT Type classification? (Type 1 / Type 2 / Type 3 / Type 4)",
        16: "What is the difficulty level of this classification? (1 - Very Easy / 2 - Easy / 3 - Medium / 4 - Hard / 5 - Very Hard)",
        17: "Based on your analysis, do you think this article should be classified as Type 1? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        18: "To what extent does this article align with Type 1? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale, e.g., \"0.82 - rationale\".",
        19: "On a 1-5 Likert scale (1 = Strongly disagree, 2 = Somewhat disagree, 3 = Neutral, 4 = Somewhat agree, 5 = Strongly agree), how strongly do you agree that this article fits Type 1? Provide the number, the matching label, and a short justification.",
        20: "Based on your analysis, do you think this article should be classified as Type 2? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        21: "To what extent does this article align with Type 2? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale, e.g., \"0.82 - rationale\".",
        22: "On a 1-5 Likert scale (1 = Strongly disagree, 2 = Somewhat disagree, 3 = Neutral, 4 = Somewhat agree, 5 = Strongly agree), how strongly do you agree that this article fits Type 2? Provide the number, the matching label, and a short justification.",
        23: "Based on your analysis, do you think this article should be classified as Type 3? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        24: "To what extent does this article align with Type 3? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale, e.g., \"0.82 - rationale\".",
        25: "On a 1-5 Likert scale (1 = Strongly disagree, 2 = Somewhat disagree, 3 = Neutral, 4 = Somewhat agree, 5 = Strongly agree), how strongly do you agree that this article fits Type 3? Provide the number, the matching label, and a short justification.",
        26: "Based on your analysis, do you think this article should be classified as Type 4? (Yes/No) Why or why not. Provide your answer as \"Yes - ...\" or \"No - ...\" followed by a short justification.",
        27: "To what extent does this article align with Type 4? Respond with a score between 0 and 1 (three decimal places) followed by a brief rationale, e.g., \"0.82 - rationale\".",
        28: "On a 1-5 Likert scale (1 = Strongly disagree, 2 = Somewhat disagree, 3 = Neutral, 4 = Somewhat agree, 5 = Strongly agree), how strongly do you agree that this article fits Type 4? Provide the number, the matching label, and a short justification.",
    }

    # 需要保持相邻的问题组
    SUPPORT_QUESTION_GROUPS = [
        [3, 4, 5],
        [6, 7, 8],
    ]

    # 结构化响应模板
    STRUCTURED_RESPONSE_TEMPLATE = """
- Produce your answers using the exact XML-style template below.
- Do not add any commentary or text outside the template.
- Keep all citations, bullet lists, and supporting evidence inside the corresponding <Q#> tags.
- Preserve multi-line structure within a tag when presenting multiple bullet points or citations.

<BEGIN_4PT_RESPONSE>
<Q1>[Answer here]</Q1>
<Q2>[Answer here]</Q2>
<Q3>[Answer here]</Q3>
<Q4>[Answer here]</Q4>
<Q5>[Answer here]</Q5>
<Q6>[Answer here]</Q6>
<Q7>[Answer here]</Q7>
<Q8>[Answer here]</Q8>
<Q9>[Answer here]</Q9>
<Q10>[Answer here]</Q10>
<Q11>[Answer here]</Q11>
<Q12>[Answer here]</Q12>
<Q13>[Answer here]</Q13>
<Q14>[Answer here]</Q14>
<Q15>[Answer here]</Q15>
<Q16>[Answer here]</Q16>
<Q17>[Answer here]</Q17>
<Q18>[Answer here]</Q18>
<Q19>[Answer here]</Q19>
<Q20>[Answer here]</Q20>
<Q21>[Answer here]</Q21>
<Q22>[Answer here]</Q22>
<Q23>[Answer here]</Q23>
<Q24>[Answer here]</Q24>
<Q25>[Answer here]</Q25>
<Q26>[Answer here]</Q26>
<Q27>[Answer here]</Q27>
<Q28>[Answer here]</Q28>
</END_4PT_RESPONSE>
"""

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
        return f"{cls.CLS_MODEL}-temp{cls.TEMPERATURE}-reasoning_{reasoning}-verbosity_{verbosity}"

    @classmethod
    def generate_question_order(cls) -> List[int]:
        """生成随机问题顺序，保证Q15置顶且依赖题目紧邻"""
        first_question = 15

        used_numbers = {first_question}
        units = []

        for group in cls.SUPPORT_QUESTION_GROUPS:
            units.append(list(group))
            used_numbers.update(group)

        for q_num in sorted(cls.QUESTION_TEXTS.keys()):
            if q_num in used_numbers:
                continue
            units.append([q_num])

        random.shuffle(units)

        ordered_questions: List[int] = [first_question]
        for unit in units:
            if first_question in unit:
                continue
            ordered_questions.extend(unit)

        return ordered_questions

    @classmethod
    def format_questions_prompt(cls, question_order: List[int]) -> str:
        """根据指定顺序构建问题提示文本"""
        header_lines = [
            "Please analyze this article using the 4PT framework by answering the questions below.",
            "Questions are listed in a randomized order (except Q15 first). Treat each independently despite ordering.",
        ]

        question_lines = [
            f"Q{q_num}. {cls.QUESTION_TEXTS[q_num]}"
            for q_num in question_order
        ]

        footer_lines = [
            "Answer each question clearly and provide specific evidence or reasoning when requested."
        ]

        return "\n\n".join(header_lines + question_lines + footer_lines)

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
        if not cls.OPENAI_API_KEY:
            print("Error: OPENAI_API_KEY not found in environment")
            print("Please set it in .env file")
            return False

        if not cls.CODEBOOK_MD.exists():
            print(f"Error: Codebook not found at {cls.CODEBOOK_MD}")
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
        print(f"Codebook: {cls.CODEBOOK_MD}")
        print(f"Excel Path: {cls.EXCEL_PATH}")
        print(f"PDF Folder: {cls.PDF_FOLDER}")
        print(f"Results Dir: {cls.RESULTS_DIR}")
        print(f"Model: {cls.CLS_MODEL}")
        print(f"Temperature: {cls.TEMPERATURE}")
        print(f"AI Runs: {cls.get_ai_runs()}")
        print(f"Reasoning Effort: {cls.get_reasoning_effort()}")
        print(f"Text Verbosity: {cls.get_text_verbosity()}")
        print(f"Majority Vote: {cls.ENABLE_MAJORITY_VOTE}")
        print(f"Debug Mode: {cls.DEBUG_MODE}")
        print(f"API Key: {'✓ Set' if cls.OPENAI_API_KEY else '✗ Missing'}")
        print("=" * 60)
