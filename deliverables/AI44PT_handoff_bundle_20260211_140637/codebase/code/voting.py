"""
多数投票模块 - 处理多次AI运行结果的投票和共识分析
"""
import re
from collections import Counter
from typing import Dict, List, Tuple, Optional
import pandas as pd

from config import Config
from response_parser import ResponseParser


class MajorityVoter:
    """多数投票处理器"""

    def __init__(self, config: Config = None):
        """
        初始化投票器

        Args:
            config: 批处理配置对象
        """
        self.config = config or Config()
        self.parser = ResponseParser(config)

    def perform_vote(
        self,
        ai_results_list: List[Tuple[Optional[Dict], str]],
        column_mapping: Dict[int, str]
    ) -> Tuple[Dict[int, str], Dict[int, Dict], Dict[int, Dict]]:
        """
        对多次AI运行结果进行多数投票

        Args:
            ai_results_list: AI结果列表，每个元素是(answers_dict, timestamp)的元组
            column_mapping: 问题编号到列名的映射

        Returns:
            (majority_answers, vote_details, numeric_stats) 三元组
            - majority_answers: 投票结果字典
            - vote_details: 详细投票信息
            - numeric_stats: 数值型问题的统计信息
        """
        if not ai_results_list or len(ai_results_list) < 2:
            return {}, {}, {}

        # 只考虑成功的AI结果
        successful_results = [answers for answers, _ in ai_results_list if answers is not None]

        if len(successful_results) < 2:
            return {}, {}, {}

        majority_answers = {}
        vote_details = {}
        numeric_stats = {}

        # 对客观问题进行投票
        majority_answers, vote_details = self._vote_objective_questions(
            successful_results, column_mapping
        )

        # 计算数值型问题的平均值
        numeric_stats = self._calculate_numeric_stats(successful_results)

        return majority_answers, vote_details, numeric_stats

    def _vote_objective_questions(
        self,
        successful_results: List[Dict],
        column_mapping: Dict[int, str]
    ) -> Tuple[Dict[int, str], Dict[int, Dict]]:
        """
        对客观问题进行投票

        Args:
            successful_results: 成功的AI结果列表
            column_mapping: 问题编号到列名的映射

        Returns:
            (majority_answers, vote_details) 二元组
        """
        majority_answers = {}
        vote_details = {}

        for q_num in self.config.OBJECTIVE_QUESTIONS:
            if q_num not in column_mapping:
                continue

            # 收集所有AI对这个问题的答案
            answers_for_question = []
            for ai_answers in successful_results:
                if q_num in ai_answers and ai_answers[q_num]:
                    answer = ai_answers[q_num].strip()
                    if answer:
                        answers_for_question.append(answer)

            if not answers_for_question:
                continue

            # 标准化答案
            normalized_answers = self._normalize_answers_for_voting(
                answers_for_question, q_num
            )

            if not normalized_answers:
                continue

            # 统计答案频次
            answer_counts = Counter(normalized_answers)
            vote_details[q_num] = {
                'original_answers': answers_for_question,
                'normalized_answers': normalized_answers,
                'vote_counts': dict(answer_counts)
            }

            # 选择多数投票结果
            most_common = answer_counts.most_common()
            if most_common:
                winner_answer, winner_count = most_common[0]

                # 格式化计数文本供平票使用
                counts_text = ", ".join(f"{cnt}*{ans}" for ans, cnt in most_common)

                # 检查是否有平票情况
                if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                    majority_answers[q_num] = f"Tie ({counts_text})"
                else:
                    majority_answers[q_num] = winner_answer

        return majority_answers, vote_details

    def _normalize_answers_for_voting(
        self,
        answers: List[str],
        q_num: int
    ) -> List[str]:
        """
        为投票标准化答案

        Args:
            answers: 原始答案列表
            q_num: 问题编号

        Returns:
            标准化后的答案列表
        """
        normalized = []

        for answer in answers:
            if q_num in [1, 3, 6, 9, 12, 15] or q_num in self.config.TYPE_CLASS_YN_QUESTIONS:
                # Yes/No问题
                normalized.append(self._normalize_yes_no_for_vote(answer))
            elif q_num == self.config.Q_ID_CLASSIFICATION:
                # Type分类问题
                normalized.append(self._normalize_type_for_vote(answer))
            elif q_num == self.config.Q_ID_CONFIDENCE:
                # 全局置信度问题
                normalized.append(self._normalize_confidence_for_vote(answer))
            elif q_num in self.config.TYPE_CONFIDENCE_QUESTIONS:
                # Type Confidence问题
                normalized.append(self._normalize_confidence_for_vote(answer))
            else:
                normalized.append(answer)

        return normalized

    def _normalize_yes_no_for_vote(self, answer: str) -> str:
        """标准化Yes/No答案用于投票"""
        text = answer or ""
        lowered = text.lower()

        # 优先匹配开头的 yes/no 词
        leading = re.match(r'\s*(yes|no)\b', lowered)
        if leading:
            return 'Yes' if leading.group(1) == 'yes' else 'No'

        # 其次匹配独立词边界，避免匹配到 "not", "none" 等
        if re.search(r'\byes\b', lowered):
            return 'Yes'
        if re.search(r'\bno\b', lowered):
            return 'No'

        return answer

    def _normalize_type_for_vote(self, answer: str) -> str:
        """标准化Type分类用于投票"""
        text = str(answer or "").strip()
        if not text:
            return text

        lowered = text.lower()
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
            return text

        type_matches = re.findall(r"\btype\s*([1-4])\b", text, re.IGNORECASE)
        unique_types = list(dict.fromkeys(type_matches))
        if len(unique_types) == 1:
            return f"Type {unique_types[0]}"
        if len(unique_types) > 1:
            return text

        numeric_match = re.match(r"^\s*([1-4])(?:\b|[).:\-])", text)
        if numeric_match:
            return f"Type {numeric_match.group(1)}"

        return text

    def _normalize_confidence_for_vote(self, answer: str) -> str:
        """标准化置信度量表用于投票"""
        labels = self.config.CONFIDENCE_LABELS
        answer_str = answer or ""

        match = re.match(r'\s*([1-5])', answer_str)
        if match:
            rating = int(match.group(1))
            rating = min(max(rating, 1), 5)
            remainder = answer_str[match.end():].strip(" -:;")
            label = labels.get(rating, "")
            if remainder:
                if label and label.lower() not in remainder.lower():
                    remainder = f"{label}; {remainder}"
                return f"{rating} - {remainder}"
            return f"{rating} - {label}" if label else f"{rating}"

        lower_answer = answer_str.lower()
        for rating, label in labels.items():
            if label.lower() in lower_answer:
                return f"{rating} - {label}"

        return answer

    def _calculate_numeric_stats(
        self,
        successful_results: List[Dict]
    ) -> Dict[int, Dict]:
        """
        计算数值型问题的统计信息

        Args:
            successful_results: 成功的AI结果列表

        Returns:
            数值统计字典
        """
        numeric_stats = {}

        # 计算Confidence量表的平均值
        for q_num in self.config.TYPE_CONFIDENCE_QUESTIONS:
            values = []
            for ai_answers in successful_results:
                raw = ai_answers.get(q_num)
                val = ResponseParser.extract_confidence_value(raw)
                if val is not None:
                    values.append(val)
            if values:
                avg_val = sum(values) / len(values)
                numeric_stats[q_num] = {"average": avg_val, "count": len(values)}

        return numeric_stats


class ConsensusAnalyzer:
    """共识分析器 - 基于Q17-Q28推导Type共识"""

    def __init__(self, config: Config = None):
        """
        初始化共识分析器

        Args:
            config: 批处理配置对象
        """
        self.config = config or Config()

    def derive_consensus(
        self,
        row: pd.Series,
        column_mapping: Dict[int, str]
    ) -> str:
        """
        综合模型对Type 1-4的回答，推导一致性认识

        Args:
            row: DataFrame行数据
            column_mapping: 问题编号到列名的映射

        Returns:
            共识描述字符串
        """
        if not column_mapping:
            return ''

        type_details = []

        for type_id, q_map in self.config.TYPE_QUESTION_GROUPS.items():
            support_col = column_mapping.get(q_map["support"])
            confidence_col = column_mapping.get(q_map["confidence"])

            support_raw = row.get(support_col) if support_col else None
            confidence_raw = row.get(confidence_col) if confidence_col else None

            # 处理缺失值
            if pd.isna(support_raw):
                support_raw = None
            if pd.isna(confidence_raw):
                confidence_raw = None

            # 解析support
            support_flag = None
            if support_raw is not None:
                support_text = str(support_raw).strip().lower()
                if re.search(r'\byes\b', support_text):
                    support_flag = True
                elif re.search(r'\bno\b', support_text):
                    support_flag = False

            # 提取数值
            confidence_value = ResponseParser.extract_confidence_value(confidence_raw)

            type_details.append({
                "type": type_id,
                "support": support_flag,
                "confidence": confidence_value,
            })

        if not type_details:
            return ''

        # 检查是否有任何信号
        has_signal = any(
            info["support"] is not None or
            info["confidence"] is not None
            for info in type_details
        )
        if not has_signal:
            return "No data"

        # 仅当有正向支持信号时才推导共识；避免“全No”被误判为某个Type
        candidates = []
        for info in type_details:
            confidence_score = info["confidence"] if info["confidence"] is not None else -1
            if info["support"] is True:
                candidates.append(((2, confidence_score), info))
            elif info["support"] is None and info["confidence"] is not None:
                # 回退路径：支持信号缺失时，允许置信度参与但降级处理
                candidates.append(((1, confidence_score), info))

        if not candidates:
            return "No clear consensus"

        best_key = max(key for key, _ in candidates)
        best_types = [info for key, info in candidates if key == best_key]

        # 格式化结果
        if len(best_types) == 1:
            return self._format_type_info(best_types[0])

        formatted = " | ".join(self._format_type_info(info) for info in best_types)
        return f"Tie between {formatted}"

    def _format_type_info(self, info: Dict) -> str:
        """格式化Type信息"""
        descriptors = []
        if info["support"] is True:
            descriptors.append("Yes")
        elif info["support"] is False:
            descriptors.append("No")
        else:
            descriptors.append("Unknown")

        if info["confidence"] is not None:
            descriptors.append(f"confidence={info['confidence']:.2f}")

        detail = "; ".join(descriptors)
        return f"Type {info['type']} ({detail})"


class DecisionTreeClassifier:
    """决策树分类器 - 基于Q3和Q9的简单决策树"""

    @staticmethod
    def _parse_yes_no(value: object) -> Optional[bool]:
        """从文本中解析 Yes/No，冲突或缺失时返回 None。"""
        text = str(value or "").strip().lower()
        if not text:
            return None

        leading_match = re.match(r'^(yes|no)\b', text)
        if leading_match:
            return leading_match.group(1) == 'yes'

        has_yes = bool(re.search(r'\byes\b', text))
        has_no = bool(re.search(r'\bno\b', text))
        if has_yes and not has_no:
            return True
        if has_no and not has_yes:
            return False
        return None

    @staticmethod
    def calculate_4pt_type(
        row: pd.Series,
        column_mapping: Dict[int, str]
    ) -> str:
        """
        根据决策树逻辑计算4PT类型

        决策树逻辑:
        - Q3=Yes, Q9=Yes -> Type 1
        - Q3=Yes, Q9=No -> Type 4
        - Q3=No, Q9=Yes -> Type 2
        - Q3=No, Q9=No -> Type 3

        Args:
            row: DataFrame行数据
            column_mapping: 问题编号到列名的映射

        Returns:
            计算出的4PT类型
        """
        q3_col = column_mapping.get(3)
        q9_col = column_mapping.get(9)

        if not q3_col or not q9_col:
            return ''

        q3_answer = row.get(q3_col, '')
        q9_answer = row.get(q9_col, '')
        q3_flag = DecisionTreeClassifier._parse_yes_no(q3_answer)
        q9_flag = DecisionTreeClassifier._parse_yes_no(q9_answer)

        if q3_flag is None or q9_flag is None:
            return ''

        # 应用决策树逻辑
        if q3_flag and q9_flag:
            return 'Type 1'
        elif q3_flag and not q9_flag:
            return 'Type 4'
        elif not q3_flag and q9_flag:
            return 'Type 2'
        elif not q3_flag and not q9_flag:
            return 'Type 3'
        return ''
