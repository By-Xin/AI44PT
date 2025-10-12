"""
批量分析器模块 - 协调批量文章的4PT分析流程
"""
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
from openai import OpenAI

from config import Config
from document_reader import DocumentReader
from response_parser import ResponseParser
from voting import MajorityVoter, ConsensusAnalyzer, DecisionTreeClassifier


class BatchAnalyzer:
    """批量分析协调器"""

    def __init__(self, config: Config = None):
        """
        初始化批量分析器

        Args:
            config: 批处理配置对象
        """
        self.config = config or Config()
        self.config.setup_directories()

        # 初始化组件
        self.client = OpenAI(api_key=self.config.OPENAI_API_KEY)
        self.document_reader = DocumentReader()
        self.parser = ResponseParser(self.config)
        self.voter = MajorityVoter(self.config)
        self.consensus_analyzer = ConsensusAnalyzer(self.config)

        # 统计信息
        self.stats = {
            'success': 0,
            'pdf_not_found': 0,
            'pdf_error': 0,
            'analysis_error': 0
        }

    def analyze_single_article(
        self,
        article_pages: List[Dict],
        codebook_pages: List[Dict],
        article_meta: Dict,
        run_index: int
    ) -> Tuple[Optional[Dict], str]:
        """
        分析单篇文章（单次运行）

        Args:
            article_pages: 文章页面列表
            codebook_pages: 编码手册页面列表
            article_meta: 文章元数据
            run_index: 运行索引

        Returns:
            (answers_dict, timestamp) 元组
        """
        if not article_pages:
            return None, self._get_timestamp()

        # 合并页面内容
        article_text = "\n\n".join([f"Page {p['page']}:\n{p['text']}" for p in article_pages])
        codebook_text = "\n\n".join([f"Section {p['page']}:\n{p['text']}" for p in codebook_pages])

        # 构建提示
        prompt = self._build_prompt(codebook_text, article_text[:50000])

        # 调用API
        analysis_text = None
        error_message = None

        try:
            # 尝试使用新API
            response = self.client.responses.create(
                model=self.config.CLS_MODEL,
                input=prompt,
                reasoning={"effort": self.config.get_reasoning_effort()},
                text={"verbosity": self.config.get_text_verbosity()},
            )
            analysis_text = response.output_text
        except Exception as primary_error:
            # 回退到标准API
            fallback_error = None
            try:
                response = self.client.chat.completions.create(
                    model=self.config.CLS_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=30000,
                    temperature=self.config.TEMPERATURE
                )
                analysis_text = response.choices[0].message.content
            except Exception as secondary_error:
                fallback_error = secondary_error

            if analysis_text is None:
                if fallback_error is not None:
                    error_message = f"{primary_error}; fallback error: {fallback_error}"
                else:
                    error_message = str(primary_error)

        api_timestamp = self._get_timestamp()
        status = "success" if analysis_text else "error"

        # 保存原始响应
        self._save_raw_response(
            article_meta, run_index, prompt, analysis_text,
            api_timestamp, status, error_message
        )

        if analysis_text:
            return analysis_text, api_timestamp

        if error_message:
            print(f"  ⚠️ Error in analysis (run {run_index}): {error_message}")
        return None, api_timestamp

    def analyze_article_multiple_runs(
        self,
        article_pages: List[Dict],
        codebook_pages: List[Dict],
        article_meta: Dict
    ) -> List[Tuple[Optional[Dict], str]]:
        """
        多次分析单篇文章

        Args:
            article_pages: 文章页面列表
            codebook_pages: 编码手册页面列表
            article_meta: 文章元数据

        Returns:
            (answers, timestamp) 列表
        """
        ai_runs = self.config.get_ai_runs()

        if ai_runs <= 1:
            # 单次运行
            response, timestamp = self.analyze_single_article(
                article_pages, codebook_pages, article_meta, run_index=1
            )
            if response:
                answers = self.parser.parse_response(response)
                return [(answers, timestamp)] if answers else []
            return []

        # 多次独立运行
        print(f"    🔄 Running {ai_runs} independent iterations...")
        answer_sets = []

        for i in range(ai_runs):
            print(f"      Iteration {i+1}/{ai_runs}...")
            response, timestamp = self.analyze_single_article(
                article_pages, codebook_pages, article_meta, run_index=i+1
            )
            if response:
                answers = self.parser.parse_response(response)
                if answers:
                    answer_sets.append((answers, timestamp))
                else:
                    print(f"      ⚠️ Iteration {i+1} failed to parse")
                    answer_sets.append((None, timestamp))
            else:
                print(f"      ⚠️ Iteration {i+1} failed")
                answer_sets.append((None, timestamp))

        successful = sum(1 for x, _ in answer_sets if x is not None)
        print(f"    ✅ Completed {successful}/{ai_runs} successful runs")

        return answer_sets

    def process_batch(self, excel_path: str = None) -> pd.DataFrame:
        """
        批量处理Excel中的所有文章

        Args:
            excel_path: Excel文件路径，如果不提供则使用配置中的路径

        Returns:
            结果DataFrame
        """
        excel_path = excel_path or str(self.config.EXCEL_PATH)

        # 读取Excel
        print(f"Reading Excel from: {excel_path}")
        df_human = pd.read_excel(excel_path)
        print(f"Found {len(df_human)} articles to process")

        if self.config.DEBUG_MODE:
            print("⚙️ Debug mode active: limiting to first 2 articles")
            df_human = df_human.head(2).copy()
            print(f"Processing subset size: {len(df_human)}")

        # 确保新增问题列存在
        self._ensure_question_columns(df_human)

        # 获取列名映射
        column_mapping = self._get_column_mapping(df_human.columns)
        print(f"Found {len(column_mapping)} question mappings")

        # 加载codebook
        cb_pages = self.document_reader.read_markdown(str(self.config.CODEBOOK_MD))
        print(f"Codebook sections loaded: {len(cb_pages)}")

        # 处理每篇文章
        results = []
        for idx, row in df_human.iterrows():
            article_results = self._process_article(
                row, idx, len(df_human), cb_pages, column_mapping
            )
            results.extend(article_results)

        # 创建结果DataFrame
        df_results = pd.DataFrame(results)

        # 添加Decision Tree和Consensus列
        df_results = self._add_derived_columns(df_results, column_mapping)

        # 调整列顺序并保存
        df_results = self._finalize_dataframe(df_results, df_human, column_mapping)

        # 打印统计
        self._print_summary(df_results, df_human)

        return df_results

    def _process_article(
        self,
        row: pd.Series,
        idx: int,
        total: int,
        cb_pages: List[Dict],
        column_mapping: Dict[int, str]
    ) -> List[Dict]:
        """处理单篇文章，返回结果行列表"""
        article_id = row['#']
        title = row.get('Title of the Paper', 'Unknown')

        print(f"\n[{idx+1}/{total}] Processing article #{article_id}: {title[:50]}...")

        results = []

        # 添加human结果行
        human_row = row.to_dict()
        human_row['source'] = 'human'
        human_row['Analysis_Status'] = 'HUMAN_ORIGINAL'
        results.append(human_row)
        print(f"  ✓ Added human result row")

        # 查找并读取PDF
        pdf_path = self._find_pdf(article_id)
        if not pdf_path:
            print(f"  ⚠️ PDF not found for article #{article_id}")
            self.stats['pdf_not_found'] += 1
            results.extend(self._create_error_rows(row, 'PDF_NOT_FOUND', column_mapping))
            return results

        print(f"  📄 Found PDF: {os.path.basename(pdf_path)}")

        article_pages = self.document_reader.read_pdf(pdf_path)
        if not article_pages:
            print(f"  ⚠️ Failed to read PDF")
            self.stats['pdf_error'] += 1
            results.extend(self._create_error_rows(row, 'PDF_READ_ERROR', column_mapping))
            return results

        print(f"  📖 PDF loaded: {len(article_pages)} pages")

        # AI分析
        article_meta = {
            "article_id": article_id,
            "title": title,
            "index": idx,
            "total": total,
            "pdf_path": pdf_path,
            "ai_runs": self.config.get_ai_runs(),
        }

        print(f"  🤖 Running AI analysis...")
        ai_answer_sets = self.analyze_article_multiple_runs(
            article_pages, cb_pages, article_meta
        )

        if not ai_answer_sets:
            print(f"  ⚠️ All AI analysis runs failed")
            self.stats['analysis_error'] += 1
            results.extend(self._create_error_rows(row, 'ANALYSIS_ERROR', column_mapping))
            return results

        # 处理AI运行结果
        ai_success_count = 0
        for run_idx, (ai_answers, api_timestamp) in enumerate(ai_answer_sets):
            ai_row = self._create_ai_row(
                row, run_idx, ai_answers, api_timestamp, column_mapping
            )
            if ai_answers is not None:
                ai_success_count += 1
            results.append(ai_row)

        # 添加Majority Vote行
        if (self.config.ENABLE_MAJORITY_VOTE and
            self.config.get_ai_runs() > 1 and
            ai_success_count >= 2):
            majority_row = self._create_majority_vote_row(
                row, ai_answer_sets, column_mapping
            )
            if majority_row:
                results.append(majority_row)

        if ai_success_count > 0:
            self.stats['success'] += 1
        else:
            self.stats['analysis_error'] += 1

        return results

    def _build_prompt(self, codebook_text: str, article_text: str) -> str:
        """构建分析提示"""
        return f"""
You are an expert public policy analyst reviewing sustainability research articles.

**Instructions:**
- Answer ALL questions only based on the provided Codebook and Article
- Provide specific citations when requested
- Keep justifications concise and evidence-based
- For Yes/No questions, choose definitively based on evidence
- For Yes-or-No or multiple choice problems, answer from the given options only (the options are in parentheses)
- Format your entire response using the XML template below to ensure each answer stays inside its <Q#> tag. Do not include any text outside the template.

{self.config.STRUCTURED_RESPONSE_TEMPLATE}

**4PT Codebook:**
{codebook_text}

**Article to Analyze:**
{article_text}

{self.config.FOURPT_QUESTIONS}
        """.strip()

    def _save_raw_response(
        self,
        article_meta: Dict,
        run_index: int,
        prompt: str,
        response_text: Optional[str],
        api_timestamp: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """保存原始API响应"""
        try:
            article_id = str(article_meta.get('article_id', 'unknown'))
            safe_article_id = re.sub(r'[^A-Za-z0-9_-]+', '_', article_id)
            file_name = f"{safe_article_id}_run{run_index}_{api_timestamp}_{status}.json"
            file_path = self.config.RAW_OUTPUT_DIR / file_name

            record = {
                "timestamp": api_timestamp,
                "status": status,
                "error": error_message,
                "article_id": article_id,
                "article_title": article_meta.get('title'),
                "article_index": article_meta.get('index'),
                "excel_row_total": article_meta.get('total'),
                "pdf_path": article_meta.get('pdf_path'),
                "run_index": run_index,
                "ai_runs": article_meta.get('ai_runs'),
                "debug_mode": self.config.DEBUG_MODE,
                "model": self.config.CLS_MODEL,
                "temperature": self.config.TEMPERATURE,
                "reasoning_effort": self.config.get_reasoning_effort(),
                "text_verbosity": self.config.get_text_verbosity(),
                "prompt": prompt,
                "raw_response": response_text,
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️ Failed to save raw response: {e}")

    def _find_pdf(self, article_id) -> Optional[str]:
        """查找PDF文件"""
        pdf_path = self.config.PDF_FOLDER / f"{article_id}.pdf"
        return str(pdf_path) if pdf_path.exists() else None

    def _get_timestamp(self) -> str:
        """生成时间戳 (yymmddhhmmss)"""
        return datetime.now().strftime('%y%m%d%H%M%S')

    def _get_column_mapping(self, columns) -> Dict[int, str]:
        """获取问题编号到列名的映射"""
        mapping = {}
        for col in columns:
            match = re.search(r'\[Q(\d+)\]', col)
            if match:
                q_num = int(match.group(1))
                mapping[q_num] = col
        return mapping

    def _ensure_question_columns(self, df: pd.DataFrame):
        """确保所有问题列存在"""
        added = []
        for q_num, col_name in self.config.ADDITIONAL_QUESTION_COLUMNS.items():
            if col_name not in df.columns:
                df[col_name] = ''
                added.append(col_name)
        if added:
            print(f"Added {len(added)} missing question columns")

    def _create_error_rows(
        self,
        row: pd.Series,
        error_type: str,
        column_mapping: Dict[int, str]
    ) -> List[Dict]:
        """创建错误行"""
        ai_runs = self.config.get_ai_runs()
        rows = []
        for run_idx in range(ai_runs):
            ai_row = row.to_dict()
            run_source_id = self._get_run_source_id(run_idx)
            ai_row['source'] = run_source_id
            ai_row['Analysis_Status'] = f'{error_type}_{self._get_timestamp()}'
            # 清空答案
            for q_num in column_mapping.keys():
                ai_row[column_mapping[q_num]] = ''
            rows.append(ai_row)
        return rows

    def _create_ai_row(
        self,
        row: pd.Series,
        run_idx: int,
        ai_answers: Optional[Dict],
        api_timestamp: str,
        column_mapping: Dict[int, str]
    ) -> Dict:
        """创建AI结果行"""
        ai_row = row.to_dict()
        run_source_id = self._get_run_source_id(run_idx)
        ai_row['source'] = run_source_id

        if ai_answers is None:
            ai_row['Analysis_Status'] = f'ANALYSIS_ERROR_{api_timestamp}'
            for q_num in column_mapping.keys():
                ai_row[column_mapping[q_num]] = ''
        else:
            ai_row['Analysis_Status'] = f'SUCCESS_{api_timestamp}'
            for q_num in column_mapping.keys():
                ai_row[column_mapping[q_num]] = ''
            for q_num, col_name in column_mapping.items():
                if q_num in ai_answers:
                    ai_row[col_name] = ai_answers[q_num]

        return ai_row

    def _create_majority_vote_row(
        self,
        row: pd.Series,
        ai_answer_sets: List[Tuple],
        column_mapping: Dict[int, str]
    ) -> Optional[Dict]:
        """创建多数投票结果行"""
        print(f"  🗳️ Performing majority vote...")
        majority_results, vote_details, numeric_stats = self.voter.perform_vote(
            ai_answer_sets, column_mapping
        )

        if not majority_results and not numeric_stats:
            return None

        majority_row = row.to_dict()
        majority_source_id = f"{self.config.get_source_id()}-majority-vote"
        majority_row['source'] = majority_source_id
        majority_row['Analysis_Status'] = f'MAJORITY_VOTE_{self._get_timestamp()}'

        # 清空答案
        for q_num in column_mapping.keys():
            majority_row[column_mapping[q_num]] = ''

        # 填充投票结果
        for q_num, answer in majority_results.items():
            if q_num in column_mapping:
                majority_row[column_mapping[q_num]] = answer

        # 填充数值统计
        for q_num, stats in numeric_stats.items():
            if q_num not in column_mapping:
                continue
            avg_val = stats.get("average")
            count = stats.get("count")
            if avg_val is None or count is None:
                continue

            if q_num in self.config.TYPE_EXTENT_QUESTIONS:
                majority_row[column_mapping[q_num]] = f"{avg_val:.2f} (avg of {count} runs)"
            elif q_num in self.config.TYPE_LIKERT_QUESTIONS:
                rounded = int(round(avg_val))
                label = self.config.LIKERT_LABELS.get(rounded, "")
                label_suffix = f" ~ {label}" if label else ""
                majority_row[column_mapping[q_num]] = f"{avg_val:.2f}{label_suffix} (avg of {count} runs)"

        # 主观题标记
        for q_num in self.config.SUBJECTIVE_QUESTIONS:
            if q_num in column_mapping and q_num not in numeric_stats:
                majority_row[column_mapping[q_num]] = '[SUBJECTIVE - NO VOTE]'

        print(f"    ✅ Majority vote completed")
        return majority_row

    def _get_run_source_id(self, run_idx: int) -> str:
        """获取运行source ID"""
        base_id = self.config.get_source_id()
        if self.config.get_ai_runs() > 1:
            return f"{base_id}-run{run_idx+1}"
        return base_id

    def _add_derived_columns(
        self,
        df: pd.DataFrame,
        column_mapping: Dict[int, str]
    ) -> pd.DataFrame:
        """添加派生列（Decision Tree 和 Consensus）"""
        print("\n🌳 Calculating derived classifications...")

        decision_tree_col = 'Decision Tree 4PT'
        type_consensus_col = 'Type consensus (Q17-Q28 summary)'

        df[decision_tree_col] = df.apply(
            lambda row: DecisionTreeClassifier.calculate_4pt_type(row, column_mapping),
            axis=1
        )
        df[type_consensus_col] = df.apply(
            lambda row: self.consensus_analyzer.derive_consensus(row, column_mapping),
            axis=1
        )

        return df

    def _finalize_dataframe(
        self,
        df: pd.DataFrame,
        df_human: pd.DataFrame,
        column_mapping: Dict[int, str]
    ) -> pd.DataFrame:
        """整理DataFrame列顺序并保存"""
        # 调整列顺序
        base_cols = ['#', 'source', 'Analysis_Status']
        decision_tree_col = 'Decision Tree 4PT'
        type_consensus_col = 'Type consensus (Q17-Q28 summary)'

        q15_col = column_mapping.get(15)
        original_cols = list(df_human.columns)

        if q15_col and q15_col in original_cols:
            q15_index = original_cols.index(q15_col)
            new_cols = (base_cols +
                       [col for col in original_cols[:q15_index+1] if col not in base_cols] +
                       [decision_tree_col, type_consensus_col] +
                       [col for col in original_cols[q15_index+1:] if col not in base_cols])
        else:
            new_cols = base_cols + [col for col in original_cols if col not in base_cols] + [decision_tree_col, type_consensus_col]

        # 确保所有列存在
        for col in new_cols:
            if col not in df.columns:
                df[col] = ''

        final_cols = [col for col in new_cols if col in df.columns]
        df = df[final_cols]

        # 排序
        df = df.sort_values(['#', 'source'], ascending=[True, False])
        df = df.reset_index(drop=True)

        # 保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = self.config.RESULTS_DIR / f"analysis_results_{timestamp}.xlsx"
        df.to_excel(output_path, index=False)
        print(f"\n📊 Results saved to: {output_path}")

        return df

    def _print_summary(self, df_results: pd.DataFrame, df_human: pd.DataFrame):
        """打印分析汇总"""
        print("\n" + "=" * 60)
        print("ANALYSIS SUMMARY")
        print("=" * 60)
        print(f"Total articles processed: {len(df_human)}")
        print(f"✅ Successful analyses: {self.stats['success']}")
        print(f"⚠️ PDF not found: {self.stats['pdf_not_found']}")
        print(f"⚠️ PDF read errors: {self.stats['pdf_error']}")
        print(f"⚠️ Analysis errors: {self.stats['analysis_error']}")

        if 'source' in df_results.columns:
            print("\nSource distribution:")
            print(df_results['source'].value_counts())
