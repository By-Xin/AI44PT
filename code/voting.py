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

                # 检查是否有平票情况
                if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                    majority_answers[q_num] = f"{winner_answer} [TIE]"
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
                # 难度等级问题
                normalized.append(self._normalize_difficulty_for_vote(answer))
            else:
                normalized.append(answer)

        return normalized

    def _normalize_yes_no_for_vote(self, answer: str) -> str:
        """标准化Yes/No答案用于投票"""
        answer_lower = answer.lower()
        if 'yes' in answer_lower:
            return 'Yes'
        elif 'no' in answer_lower:
            return 'No'
        return answer

    def _normalize_type_for_vote(self, answer: str) -> str:
        """标准化Type分类用于投票"""
        answer_upper = answer.upper()
        if 'TYPE' in answer_upper:
            match = re.search(r'TYPE\s*([1-4])', answer_upper)
            if match:
                return f'Type {match.group(1)}'
        else:
            match = re.search(r'[1-4]', answer)
            if match:
                return f'Type {match.group()}'
        return answer

    def _normalize_difficulty_for_vote(self, answer: str) -> str:
        """标准化难度等级用于投票"""
        answer_lower = answer.lower()
        difficulty_map = {
            'very easy': '1 - Very Easy',
            'very hard': '5 - Very Hard',
            'easy': '2 - Easy',
            'hard': '4 - Hard',
            'medium': '3 - Medium',
        }

        for key, value in difficulty_map.items():
            if key in answer_lower:
                # 处理 "very easy" vs "easy" 等情况
                if key == 'easy' and 'very' in answer_lower:
                    continue
                if key == 'hard' and 'very' in answer_lower:
                    continue
                return value

        # 尝试提取数字
        match = re.search(r'[1-5]', answer)
        if match:
            num = match.group()
            num_map = {
                '1': '1 - Very Easy',
                '2': '2 - Easy',
                '3': '3 - Medium',
                '4': '4 - Hard',
                '5': '5 - Very Hard'
            }
            return num_map.get(num, answer)

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

        # 计算类型强度（0-1范围）的平均值
        for q_num in self.config.TYPE_EXTENT_QUESTIONS:
            values = []
            for ai_answers in successful_results:
                raw = ai_answers.get(q_num)
                val = ResponseParser.extract_extent_value(raw)
                if val is not None:
                    values.append(val)
            if values:
                avg_val = sum(values) / len(values)
                numeric_stats[q_num] = {"average": avg_val, "count": len(values)}

        # 计算Likert量表的平均值
        for q_num in self.config.TYPE_LIKERT_QUESTIONS:
            values = []
            for ai_answers in successful_results:
                raw = ai_answers.get(q_num)
                val = ResponseParser.extract_likert_value(raw)
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
            extent_col = column_mapping.get(q_map["extent"])
            likert_col = column_mapping.get(q_map["likert"])

            support_raw = row.get(support_col) if support_col else None
            extent_raw = row.get(extent_col) if extent_col else None
            likert_raw = row.get(likert_col) if likert_col else None

            # 处理缺失值
            if pd.isna(support_raw):
                support_raw = None
            if pd.isna(extent_raw):
                extent_raw = None
            if pd.isna(likert_raw):
                likert_raw = None

            # 解析support
            support_flag = None
            if support_raw is not None:
                support_text = str(support_raw).strip().lower()
                if re.search(r'\byes\b', support_text):
                    support_flag = True
                elif re.search(r'\bno\b', support_text):
                    support_flag = False

            # 提取数值
            extent_value = ResponseParser.extract_extent_value(extent_raw)
            likert_value = ResponseParser.extract_likert_value(likert_raw)

            type_details.append({
                "type": type_id,
                "support": support_flag,
                "extent": extent_value,
                "likert": likert_value,
            })

        if not type_details:
            return ''

        # 检查是否有任何信号
        has_signal = any(
            info["support"] is not None or
            info["extent"] is not None or
            info["likert"] is not None
            for info in type_details
        )
        if not has_signal:
            return "No data"

        # 找到得分最高的Type
        best_key = None
        best_types = []
        for info in type_details:
            support_score = 1 if info["support"] is True else (-1 if info["support"] is False else 0)
            extent_score = info["extent"] if info["extent"] is not None else -1
            likert_score = info["likert"] if info["likert"] is not None else -1
            key = (support_score, extent_score, likert_score)

            if best_key is None or key > best_key:
                best_key = key
                best_types = [info]
            elif key == best_key:
                best_types.append(info)

        if not best_types or best_key == (-1, -1, -1):
            return "No clear consensus"
        if best_key == (0, -1, -1):
            return "No clear consensus"

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

        if info["extent"] is not None:
            descriptors.append(f"extent={info['extent']:.2f}")
        if info["likert"] is not None:
            descriptors.append(f"likert={info['likert']:.2f}")

        detail = "; ".join(descriptors)
        return f"Type {info['type']} ({detail})"


class DecisionTreeClassifier:
    """决策树分类器 - 基于Q3和Q9的简单决策树"""

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

        q3_answer = str(row.get(q3_col, '')).strip().lower()
        q9_answer = str(row.get(q9_col, '')).strip().lower()

        q3_yes = 'yes' in q3_answer
        q3_no = 'no' in q3_answer
        q9_yes = 'yes' in q9_answer
        q9_no = 'no' in q9_answer

        # 应用决策树逻辑
        if q3_yes and q9_yes:
            return 'Type 1'
        elif q3_yes and q9_no:
            return 'Type 4'
        elif q3_no and q9_yes:
            return 'Type 2'
        elif q3_no and q9_no:
            return 'Type 3'
        else:
            return ''
