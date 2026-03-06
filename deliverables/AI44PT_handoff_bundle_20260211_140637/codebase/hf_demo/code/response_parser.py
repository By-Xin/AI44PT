"""
AI响应解析模块 - 处理AI模型返回的结构化响应
"""
import re
from typing import Dict, Optional
from config import Config


class ResponseParser:
    """AI响应解析器"""

    def __init__(self, config: Config = None):
        """
        初始化响应解析器

        Args:
            config: 批处理配置对象
        """
        self.config = config or Config()

    def parse_response(self, response_text: str) -> Dict[int, str]:
        """
        解析AI的响应文本，提取每个问题的答案

        Args:
            response_text: AI返回的原始响应文本

        Returns:
            问题编号到答案的字典映射
        """
        if not response_text:
            return {}

        answers = {}

        # 提取结构化模板块
        structured_block = re.search(
            r'<BEGIN_4PT_RESPONSE>(.*?)</END_4PT_RESPONSE>',
            response_text,
            re.DOTALL | re.IGNORECASE
        )
        template_body = structured_block.group(1) if structured_block else response_text

        # 提取所有Q标签
        structured_matches = re.findall(
            r'<Q(\d+)>(.*?)</Q\1>',
            template_body,
            re.DOTALL | re.IGNORECASE
        )

        for q_str, raw_answer in structured_matches:
            try:
                q_num = int(q_str)
                # 清理答案文本
                answer = self._clean_answer_text(raw_answer)
                answers[q_num] = answer
            except ValueError:
                continue

        # 验证解析完整性
        if len(answers) < self.config.TOTAL_QUESTIONS:
            print(f"    ⚠️ AI response format error: Only parsed {len(answers)}/{self.config.TOTAL_QUESTIONS} questions")
            return {}

        # 标准化特定类型的答案
        answers = self._normalize_answers(answers)

        return answers

    def _clean_answer_text(self, text: str) -> str:
        """
        清理答案文本

        Args:
            text: 原始答案文本

        Returns:
            清理后的文本
        """
        # 统一换行符
        text = re.sub(r'\r\n?', '\n', text).strip()
        # 移除行尾空格
        text = re.sub(r'[ \t]+\n', '\n', text)
        # 压缩多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _normalize_answers(self, answers: Dict[int, str]) -> Dict[int, str]:
        """
        标准化不同类型问题的答案格式

        Args:
            answers: 原始答案字典

        Returns:
            标准化后的答案字典
        """
        # 标准化Yes/No问题
        yes_no_questions = [1, 3, 6, 9, 12] + self.config.TYPE_CLASS_YN_QUESTIONS
        for q_num in yes_no_questions:
            if q_num in answers:
                answers[q_num] = self._normalize_yes_no(answers[q_num])

        # 标准化概率/范围问题 (0-1)
        for q_num in self.config.TYPE_EXTENT_QUESTIONS:
            if q_num in answers:
                answers[q_num] = self._normalize_extent(answers[q_num])

        # 标准化Likert量表问题 (1-5)
        for q_num in self.config.TYPE_LIKERT_QUESTIONS:
            if q_num in answers:
                answers[q_num] = self._normalize_likert(answers[q_num])

        # 标准化Type分类 (Q15)
        if 15 in answers:
            answers[15] = self._normalize_type_classification(answers[15])

        # 标准化难度等级 (Q16)
        if 16 in answers:
            answers[16] = self._normalize_difficulty(answers[16])

        return answers

    def _normalize_yes_no(self, text: str) -> str:
        """标准化Yes/No答案"""
        if re.search(r'\byes\b', text, re.IGNORECASE):
            return "Yes"
        elif re.search(r'\bno\b', text, re.IGNORECASE):
            return "No"
        return text

    def _normalize_extent(self, text: str) -> str:
        """标准化0-1范围的答案"""
        match = re.match(r'\s*(0?\.\d+|1(?:\.0+)?)', text)
        if match:
            prob = float(match.group(1))
            prob = min(max(prob, 0.0), 1.0)
            remainder = text[match.end():].strip(" -:")
            return f"{prob:.2f}" + (f" - {remainder}" if remainder else "")
        return text

    def _normalize_likert(self, text: str) -> str:
        """标准化Likert量表答案 (1-5)"""
        match = re.match(r'\s*([1-5])', text)
        if match:
            rating = int(match.group(1))
            rating = min(max(rating, 1), 5)
            remainder = text[match.end():].strip(" -:;")
            label = self.config.LIKERT_LABELS.get(rating, "")

            if remainder:
                if label and label.lower() not in remainder.lower():
                    formatted_remainder = f"{label}; {remainder}"
                else:
                    formatted_remainder = remainder
                return f"{rating} - {formatted_remainder}"
            else:
                return f"{rating} - {label}" if label else f"{rating}"
        return text

    def _normalize_type_classification(self, text: str) -> str:
        """标准化Type分类答案"""
        text_upper = text.upper()
        if 'TYPE' in text_upper:
            match = re.search(r'TYPE\s*([1-4])', text_upper)
            if match:
                return f"Type {match.group(1)}"
        else:
            match = re.search(r'[1-4]', text)
            if match:
                return f"Type {match.group()}"
        return text

    def _normalize_difficulty(self, text: str) -> str:
        """标准化难度等级答案"""
        text_lower = text.lower()
        difficulty_map = {
            'very easy': '1 - Very Easy',
            'easy': '2 - Easy',
            'medium': '3 - Medium',
            'hard': '4 - Hard',
            'very hard': '5 - Very Hard',
        }

        # 先尝试直接匹配文本
        if "very easy" in text_lower:
            return "1 - Very Easy"
        elif "very hard" in text_lower:
            return "5 - Very Hard"
        elif "easy" in text_lower:
            return "2 - Easy"
        elif "hard" in text_lower:
            return "4 - Hard"
        elif "medium" in text_lower:
            return "3 - Medium"
        else:
            # 尝试提取数字
            match = re.search(r'[1-5]', text)
            if match:
                num = match.group()
                num_map = {
                    '1': '1 - Very Easy',
                    '2': '2 - Easy',
                    '3': '3 - Medium',
                    '4': '4 - Hard',
                    '5': '5 - Very Hard'
                }
                return num_map.get(num, text)
        return text

    @staticmethod
    def extract_extent_value(text: Optional[str]) -> Optional[float]:
        """
        从文本中提取0-1范围的数值

        Args:
            text: 包含数值的文本

        Returns:
            提取的浮点数值，如果无法提取则返回None
        """
        if text is None:
            return None
        match = re.match(r'\s*(0?\.\d+|1(?:\.0+)?)', str(text))
        if not match:
            return None
        try:
            value = float(match.group(1))
            return min(max(value, 0.0), 1.0)
        except ValueError:
            return None

    @staticmethod
    def extract_likert_value(text: Optional[str]) -> Optional[float]:
        """
        从文本中提取Likert量表数值

        Args:
            text: 包含数值的文本

        Returns:
            提取的浮点数值，如果无法提取则返回None
        """
        if text is None:
            return None
        match = re.match(r'\s*([1-5](?:\.\d+)?)', str(text))
        if not match:
            return None
        try:
            value = float(match.group(1))
            return value
        except ValueError:
            return None
