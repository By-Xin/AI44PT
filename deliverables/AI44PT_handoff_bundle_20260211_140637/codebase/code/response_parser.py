"""
AI响应解析模块 - 处理AI模型返回的结构化响应
"""
import re
import logging
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
        self.logger = logging.getLogger(__name__)
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
            self.logger.warning(
                "⚠️ AI response format error: Only parsed %s/%s questions",
                len(answers),
                self.config.TOTAL_QUESTIONS
            )
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
        yes_no_questions = [1, 3, 6, 9, 12, 15] + self.config.TYPE_CLASS_YN_QUESTIONS
        for q_num in yes_no_questions:
            if q_num in answers:
                answers[q_num] = self._normalize_yes_no(answers[q_num])

        # 标准化Confidence量表问题 (1-5)
        for q_num in self.config.TYPE_CONFIDENCE_QUESTIONS:
            if q_num in answers:
                answers[q_num] = self._normalize_confidence(answers[q_num])

        # 标准化Type分类 (Q16)
        if self.config.Q_ID_CLASSIFICATION in answers:
            answers[self.config.Q_ID_CLASSIFICATION] = self._normalize_type_classification(answers[self.config.Q_ID_CLASSIFICATION])

        # 标准化全局置信度 (Q17)
        if self.config.Q_ID_CONFIDENCE in answers:
            answers[self.config.Q_ID_CONFIDENCE] = self._normalize_global_confidence(
                answers[self.config.Q_ID_CONFIDENCE]
            )

        return answers

    def _normalize_yes_no(self, text: str) -> str:
        """标准化Yes/No答案，同时保留原文理由"""
        if text is None:
            return text

        # 优先解析开头 token 的 yes/no
        leading = re.match(r'\s*(yes|no)\b[ \t:.-]*', text, re.IGNORECASE)
        if leading:
            label = "Yes" if leading.group(1).lower() == "yes" else "No"
            remainder = text[leading.end():].strip(" \t-:;")
            return f"{label} - {remainder}" if remainder else label

        # 若首词无法解析，则保持原文以便审计/回溯
        return text

    def _normalize_confidence(self, text: str) -> str:
        """标准化 Type Confidence 量表答案 (1-5)"""
        return self._normalize_confidence_scale(text, self.config.CONFIDENCE_LABELS)

    def _normalize_confidence_scale(self, text: str, label_map: Dict[int, str]) -> str:
        """通用的 1-5 置信度量表标准化"""
        if text is None:
            return text

        match = re.match(r'\s*([1-5])', text)
        if match:
            rating = int(match.group(1))
            rating = min(max(rating, 1), 5)
            remainder = text[match.end():].strip(" -:;")
            label = label_map.get(rating, "")

            if remainder:
                if label and label.lower() not in remainder.lower():
                    formatted_remainder = f"{label}; {remainder}"
                else:
                    formatted_remainder = remainder
                return f"{rating} - {formatted_remainder}"
            return f"{rating} - {label}" if label else f"{rating}"

        text_lower = text.lower()
        for rating, label in label_map.items():
            if label.lower() in text_lower:
                return f"{rating} - {label}"

        return text

    def _normalize_type_classification(self, text: str) -> str:
        """标准化Type分类答案，避免把模糊答案误判为单一Type。"""
        if text is None:
            return text

        raw_text = str(text).strip()
        if not raw_text:
            return raw_text

        lowered = raw_text.lower()
        non_decisive_patterns = [
            r"\buncertain\b",
            r"\bnot\s+applicable\b",
            r"\bn/?a\b",
            r"\bno\s+clear\b",
            r"\bcannot\s+classify\b",
            r"\bambig",
            r"\btie\b",
            r"\bsplit\b",
            r"\bmulti(?:ple)?\b",
        ]
        if any(re.search(pattern, lowered) for pattern in non_decisive_patterns):
            return raw_text

        type_matches = re.findall(r"\btype\s*([1-4])\b", raw_text, re.IGNORECASE)
        unique_types = list(dict.fromkeys(type_matches))
        if len(unique_types) == 1:
            return f"Type {unique_types[0]}"
        if len(unique_types) > 1:
            return raw_text

        numeric_match = re.match(r"^\s*([1-4])(?:\b|[).:\-])", raw_text)
        if numeric_match:
            return f"Type {numeric_match.group(1)}"

        return raw_text

    def _normalize_global_confidence(self, text: str) -> str:
        """标准化全局置信度 (Q17)"""
        return self._normalize_confidence_scale(text, self.config.CONFIDENCE_LABELS)

    @staticmethod
    def extract_confidence_value(text: Optional[str]) -> Optional[float]:
        """
        从文本中提取Confidence量表数值

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
