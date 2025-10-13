"""
批量分析器模块 - 协调批量文章的4PT分析流程
"""
import os
import json
import re
from collections import defaultdict
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

    AI_AGREEMENT_COL = 'AI run agreement (Q15)'
    HUMAN_VS_AI_COL = 'Human vs AI (Q15)'
    TYPE_SUMMARY_COL = 'Type summary (Q15, Decision Tree, Consensus)'
    HUMAN_VS_CONSENSUS_COL = 'Human vs AI (consensus)'

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
        self.last_raw_source_path: Optional[Path] = None

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
        error_type = None if analysis_text else "api_error"

        # 保存原始响应
        record = self._save_raw_response(
            article_meta, run_index, prompt, analysis_text,
            api_timestamp, status, error_message, error_type=error_type
        )

        if analysis_text:
            return analysis_text, api_timestamp, record

        if error_message:
            print(f"  ⚠️ Error in analysis (run {run_index}): {error_message}")
        return None, api_timestamp, record

    def analyze_article_multiple_runs(
        self,
        article_pages: List[Dict],
        codebook_pages: List[Dict],
        article_meta: Dict,
        collect_records: bool = False
    ):
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

        raw_records = [] if collect_records else None

        if ai_runs <= 1:
            # 单次运行
            response, timestamp, record = self.analyze_single_article(
                article_pages, codebook_pages, article_meta, run_index=1
            )
            if collect_records and record:
                raw_records.append(record)
            if response:
                answers = self.parser.parse_response(response)
                results = [(answers, timestamp)] if answers else []
            else:
                results = []

            if collect_records:
                return results, raw_records
            return results

        # 多次独立运行
        print(f"    🔄 Running {ai_runs} independent iterations...")
        answer_sets = []

        for i in range(ai_runs):
            print(f"      Iteration {i+1}/{ai_runs}...")
            response, timestamp, record = self.analyze_single_article(
                article_pages, codebook_pages, article_meta, run_index=i+1
            )
            if collect_records and record:
                raw_records.append(record)
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

        if collect_records:
            return answer_sets, raw_records
        return answer_sets

    def process_batch(
        self,
        excel_path: str = None,
        raw_data_path: str = None,
        stage: str = "full"
    ):
        """
        批量处理入口（支持生成raw或从raw解析）

        Args:
            excel_path: Excel文件路径
            raw_data_path: 原始JSON文件路径或目录（解析阶段使用）
            stage: 处理阶段，可选 "raw"、"parse"、"full"

        Returns:
            当stage为"raw"时返回JSON路径，其余情况返回结果DataFrame
        """
        stage = (stage or "full").lower()

        if stage == "raw":
            return self.generate_raw_responses(excel_path=excel_path, output_path=raw_data_path)

        if stage == "parse":
            if not raw_data_path:
                raise ValueError("parse stage requires raw data path")
            return self.parse_raw_responses(json_path=raw_data_path, excel_path=excel_path)

        if stage == "full":
            generated_path = self.generate_raw_responses(excel_path=excel_path, output_path=raw_data_path)
            return self.parse_raw_responses(json_path=str(generated_path), excel_path=excel_path)

        raise ValueError(f"Unsupported processing stage: {stage}")

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

    def _build_raw_record(
        self,
        article_meta: Dict,
        run_index: int,
        prompt: Optional[str],
        response_text: Optional[str],
        api_timestamp: str,
        status: str,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None
    ) -> Dict:
        """构建原始响应记录"""
        article_id = str(article_meta.get('article_id', 'unknown'))
        return {
            "timestamp": api_timestamp,
            "status": status,
            "error_type": error_type,
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
            "stage": "raw_generation",
        }

    def _save_raw_response(
        self,
        article_meta: Dict,
        run_index: int,
        prompt: str,
        response_text: Optional[str],
        api_timestamp: str,
        status: str,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None
    ) -> Dict:
        """保存原始API响应"""
        record = self._build_raw_record(
            article_meta,
            run_index,
            prompt,
            response_text,
            api_timestamp,
            status,
            error_message,
            error_type
        )

        try:
            article_id = record["article_id"]
            safe_article_id = re.sub(r'[^A-Za-z0-9_-]+', '_', article_id)
            file_name = f"{safe_article_id}_run{run_index}_{api_timestamp}_{status}.json"
            file_path = self.config.RAW_OUTPUT_DIR / file_name
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠️ Failed to save raw response: {e}")
        return record

    def _load_raw_records(self, source_path: Path) -> List[Dict]:
        """从JSON文件或目录读取原始记录"""
        records: List[Dict] = []

        def load_json_file(path: Path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                records.append(item)
                            else:
                                print(f"  ⚠️ Skipping non-dict entry in {path.name}")
                    elif isinstance(data, dict):
                        records.append(data)
                    else:
                        print(f"  ⚠️ Unsupported JSON structure in {path.name}")
            except FileNotFoundError:
                print(f"❌ Raw JSON file not found: {path}")
            except json.JSONDecodeError as exc:
                print(f"  ⚠️ Skipping malformed JSON file {path.name}: {exc}")

        if source_path.is_dir():
            json_files = sorted(source_path.glob("*.json"))

            if json_files:
                for json_file in json_files:
                    load_json_file(json_file)

            if not json_files:
                print(f"❌ No JSON files found in directory: {source_path}")

            return records

        suffix = source_path.suffix.lower()
        if suffix == ".json":
            load_json_file(source_path)
        else:
            print(f"❌ Unsupported raw data format: {source_path}")
        return records

    def generate_raw_responses(
        self,
        excel_path: str = None,
        output_path: Optional[str] = None
    ) -> Path:
        """生成原始响应并保存为JSON数组"""
        excel_path = excel_path or str(self.config.EXCEL_PATH)
        print(f"\n📥 Loading Excel for raw generation: {excel_path}")
        df_human = pd.read_excel(excel_path)
        article_count = len(df_human)
        print(f"Found {article_count} articles to process for raw generation")

        if self.config.DEBUG_MODE:
            print("⚙️ Debug mode active: limiting to first 2 articles")
            df_human = df_human.head(2).copy()
            article_count = len(df_human)
            print(f"Processing subset size: {article_count}")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if output_path:
            output_path = Path(output_path)
            if output_path.suffix:
                base_dir = output_path.parent
                run_dir_name = output_path.stem
                final_filename = output_path.name
            else:
                base_dir = output_path
                run_dir_name = f"raw_batch_{timestamp}"
                final_filename = f"raw_responses_{timestamp}.json"
        else:
            base_dir = self.config.RAW_OUTPUT_DIR
            run_dir_name = f"raw_batch_{timestamp}"
            final_filename = f"raw_responses_{timestamp}.json"

        run_dir = base_dir / run_dir_name
        run_dir.mkdir(parents=True, exist_ok=True)
        final_output_path = run_dir / final_filename

        print(f"\n📝 Writing aggregated raw responses to JSON: {final_output_path}")

        # 预加载Codebook
        cb_pages = self.document_reader.read_markdown(str(self.config.CODEBOOK_MD))
        print(f"Codebook sections loaded: {len(cb_pages)}")

        generation_stats = defaultdict(int)
        ai_runs = self.config.get_ai_runs()

        aggregated_records: List[Dict] = []

        for idx, row in df_human.iterrows():
            article_id = row['#']
            title = row.get('Title of the Paper', 'Unknown')

            print(f"\n[{idx+1}/{article_count}] Generating raw for article #{article_id}: {title[:50]}...")

            article_meta = {
                "article_id": article_id,
                "title": title,
                "index": idx,
                "total": article_count,
                "pdf_path": None,
                "ai_runs": ai_runs,
            }

            pdf_path = self._find_pdf(article_id)
            if not pdf_path:
                print("  ⚠️ PDF not found; recording error runs")
                generation_stats['pdf_not_found'] += 1
                article_meta['pdf_path'] = None
                for run_idx in range(ai_runs):
                    err_record = self._build_raw_record(
                        article_meta,
                        run_index=run_idx + 1,
                        prompt=None,
                        response_text=None,
                        api_timestamp=self._get_timestamp(),
                        status="error",
                        error_message="PDF not found",
                        error_type="PDF_NOT_FOUND",
                    )
                        aggregated_records.append(err_record)
                continue

            article_meta['pdf_path'] = pdf_path
            generation_stats['pdf_found'] += 1
            print(f"  📄 Using PDF: {os.path.basename(pdf_path)}")

            article_pages = self.document_reader.read_pdf(pdf_path)
            if not article_pages:
                print("  ⚠️ Failed to read PDF; recording error runs")
                generation_stats['pdf_read_error'] += 1
                for run_idx in range(ai_runs):
                    err_record = self._build_raw_record(
                        article_meta,
                        run_index=run_idx + 1,
                        prompt=None,
                        response_text=None,
                        api_timestamp=self._get_timestamp(),
                        status="error",
                        error_message="PDF read error",
                        error_type="PDF_READ_ERROR",
                    )
                    aggregated_records.append(err_record)
                continue

            print(f"  📖 PDF loaded: {len(article_pages)} pages")
            print(f"  🤖 Requesting {ai_runs} raw AI runs...")

            for run_idx in range(ai_runs):
                response, api_timestamp, record = self.analyze_single_article(
                    article_pages, cb_pages, article_meta, run_index=run_idx + 1
                )
                if record:
                    aggregated_records.append(record)

                if response:
                    generation_stats['success'] += 1
                else:
                    generation_stats['analysis_error'] += 1

        with open(final_output_path, 'w', encoding='utf-8') as json_file:
            json.dump(aggregated_records, json_file, ensure_ascii=False, indent=2)

        print("\n📦 Raw generation complete")
        print(f"  ✅ Successful API responses: {generation_stats['success']}")
        print(f"  ⚠️ API/analysis errors: {generation_stats['analysis_error']}")
        print(f"  ⚠️ PDF not found: {generation_stats['pdf_not_found']}")
        print(f"  ⚠️ PDF read errors: {generation_stats['pdf_read_error']}")

        self.last_raw_source_path = final_output_path
        return final_output_path

    def parse_raw_responses(
        self,
        json_path: str,
        excel_path: str = None
    ) -> pd.DataFrame:
        """从原始JSON记录解析并生成结果"""
        excel_path = excel_path or str(self.config.EXCEL_PATH)
        raw_source = Path(json_path)
        self.last_raw_source_path = raw_source

        print(f"\n📥 Loading Excel for parsing: {excel_path}")
        df_human = pd.read_excel(excel_path)
        total_articles = len(df_human)
        print(f"Found {total_articles} articles to parse")

        if self.config.DEBUG_MODE:
            print("⚙️ Debug mode active: limiting to first 2 articles")
            df_human = df_human.head(2).copy()
            total_articles = len(df_human)
            print(f"Parsing subset size: {total_articles}")

        # 确保新增问题列存在
        self._ensure_question_columns(df_human)

        # 获取列名映射
        column_mapping = self._get_column_mapping(df_human.columns)
        print(f"Found {len(column_mapping)} question mappings")

        # 读取原始记录
        if raw_source.is_dir():
            print(f"\n📂 Reading raw responses from directory: {raw_source}")
        elif raw_source.suffix.lower() == ".json":
            print(f"\n📂 Reading raw JSON file: {raw_source}")
        else:
            print(f"\n📂 Reading raw responses from: {raw_source}")

        raw_records = self._load_raw_records(raw_source)
        if not raw_records:
            print("❌ No raw records found; aborting parse stage")
            return pd.DataFrame()

        records_by_article = defaultdict(list)
        for record in raw_records:
            article_id = str(record.get('article_id', ''))
            records_by_article[article_id].append(record)

        # 对记录排序
        for record_list in records_by_article.values():
            record_list.sort(key=lambda r: (
                r.get('run_index') or 0,
                r.get('timestamp') or ''
            ))

        print(f"Grouped raw records for {len(records_by_article)} articles")

        # 重置统计
        self.stats = {
            'success': 0,
            'pdf_not_found': 0,
            'pdf_error': 0,
            'analysis_error': 0
        }

        results = []

        for idx, row in df_human.iterrows():
            article_id = str(row['#'])
            title = row.get('Title of the Paper', 'Unknown')

            print(f"\n[{idx+1}/{total_articles}] Parsing article #{article_id}: {title[:50]}...")
            q15_col = column_mapping.get(15)

            # 添加human结果行
            human_row = row.to_dict()
            human_row['source'] = 'human'
            human_row['Analysis_Status'] = 'HUMAN_ORIGINAL'
            human_row[self.AI_AGREEMENT_COL] = ''
            human_row[self.HUMAN_VS_AI_COL] = ''
            human_row[self.HUMAN_VS_CONSENSUS_COL] = ''
            results.append(human_row)

            article_records = records_by_article.get(article_id, [])
            if not article_records:
                print("  ⚠️ No raw records found; adding RAW_NOT_FOUND rows")
                results.extend(self._create_error_rows(row, 'RAW_NOT_FOUND', column_mapping))
                self.stats['analysis_error'] += 1
                continue

            ai_runs = self.config.get_ai_runs()
            run_record_map = {}
            for record in article_records:
                run_idx = record.get('run_index')
                if run_idx is not None and run_idx not in run_record_map:
                    run_record_map[run_idx] = record

            ai_answer_sets = []
            ai_success_count = 0

            for run_idx in range(ai_runs):
                record = run_record_map.get(run_idx + 1)
                if not record:
                    print(f"  ⚠️ Missing raw record for run {run_idx+1}; inserting placeholder")
                    placeholder_ts = self._get_timestamp()
                    ai_row = self._create_ai_row(row, run_idx, None, placeholder_ts, column_mapping)
                    ai_row['Analysis_Status'] = f'RAW_MISSING_{placeholder_ts}'
                    results.append(ai_row)
                    self.stats['analysis_error'] += 1
                    continue

                status = record.get('status')
                error_type = record.get('error_type')
                raw_text = record.get('raw_response')
                api_timestamp = record.get('timestamp') or self._get_timestamp()

                if status == 'success' and raw_text:
                    answers = self.parser.parse_response(raw_text)
                    if answers:
                        ai_row = self._create_ai_row(row, run_idx, answers, api_timestamp, column_mapping)
                        ai_answer_sets.append((answers, api_timestamp))
                        ai_success_count += 1
                    else:
                        print(f"  ⚠️ Parse error for run {run_idx+1}")
                        ai_row = self._create_ai_row(row, run_idx, None, api_timestamp, column_mapping)
                        ai_row['Analysis_Status'] = f'PARSE_ERROR_{api_timestamp}'
                        self.stats['analysis_error'] += 1
                else:
                    ai_row = self._create_ai_row(row, run_idx, None, api_timestamp, column_mapping)
                    label = error_type or status or 'ANALYSIS_ERROR'
                    ai_row['Analysis_Status'] = f'{label.upper()}_{api_timestamp}'

                    if error_type == 'PDF_NOT_FOUND':
                        self.stats['pdf_not_found'] += 1
                    elif error_type == 'PDF_READ_ERROR':
                        self.stats['pdf_error'] += 1
                    else:
                        self.stats['analysis_error'] += 1

                results.append(ai_row)

            # 计算投票细节以评估一致性
            majority_results = {}
            vote_details = {}
            numeric_stats = {}
            if ai_success_count > 0:
                majority_results, vote_details, numeric_stats = self.voter.perform_vote(
                    ai_answer_sets, column_mapping
                )

            ai_agreement_label = self._summarize_q15_agreement(vote_details, ai_success_count)
            if ai_agreement_label:
                human_row[self.AI_AGREEMENT_COL] = ai_agreement_label

            # 多数票
            if (self.config.ENABLE_MAJORITY_VOTE and
                self.config.get_ai_runs() > 1 and
                ai_success_count >= 2):
                vote_output = self._create_majority_vote_row(
                    row, ai_answer_sets, column_mapping,
                    majority_results, vote_details, numeric_stats
                )
                if vote_output:
                    majority_row, majority_metadata = vote_output
                    majority_row[self.AI_AGREEMENT_COL] = ai_agreement_label
                    results.append(majority_row)

                    human_value = human_row.get(q15_col, '') if q15_col else ''
                    ai_value = majority_row.get(q15_col, '') if q15_col else ''
                    human_vs_ai = self._compare_human_vs_ai_q15(human_value, ai_value)
                    human_row[self.HUMAN_VS_AI_COL] = human_vs_ai
                    majority_row[self.HUMAN_VS_AI_COL] = human_vs_ai
                else:
                    human_row[self.HUMAN_VS_AI_COL] = 'No AI majority'
            else:
                if not self.config.ENABLE_MAJORITY_VOTE:
                    human_row[self.HUMAN_VS_AI_COL] = 'Majority vote disabled'
                elif self.config.get_ai_runs() <= 1:
                    human_row[self.HUMAN_VS_AI_COL] = 'Majority vote not applicable (single run)'
                elif ai_success_count < 2:
                    human_row[self.HUMAN_VS_AI_COL] = 'Majority vote unavailable (insufficient runs)'
                else:
                    human_row[self.HUMAN_VS_AI_COL] = 'No AI majority'

            if ai_success_count > 0:
                self.stats['success'] += 1

        if not results:
            print("❌ No results generated from raw parsing")
            return pd.DataFrame()

        df_results = pd.DataFrame(results)
        df_results = self._add_derived_columns(df_results, column_mapping)
        df_results = self._finalize_dataframe(df_results, df_human, column_mapping)
        self._print_summary(df_results, df_human)
        return df_results

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
            ai_row[self.AI_AGREEMENT_COL] = ''
            ai_row[self.HUMAN_VS_AI_COL] = ''
            ai_row[self.HUMAN_VS_CONSENSUS_COL] = ''
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

        ai_row[self.AI_AGREEMENT_COL] = ''
        ai_row[self.HUMAN_VS_AI_COL] = ''
        ai_row[self.HUMAN_VS_CONSENSUS_COL] = ''
        return ai_row

    def _create_majority_vote_row(
        self,
        row: pd.Series,
        ai_answer_sets: List[Tuple],
        column_mapping: Dict[int, str],
        majority_results: Dict[int, str],
        vote_details: Dict[int, Dict],
        numeric_stats: Dict[int, Dict]
    ) -> Optional[Tuple[Dict, Dict]]:
        """创建多数投票结果行"""
        print(f"  🗳️ Performing majority vote...")
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
        majority_row[self.AI_AGREEMENT_COL] = ''
        majority_row[self.HUMAN_VS_AI_COL] = ''
        majority_row[self.HUMAN_VS_CONSENSUS_COL] = ''
        metadata = {
            "majority_results": majority_results,
            "vote_details": vote_details,
            "numeric_stats": numeric_stats,
        }
        return majority_row, metadata

    def _summarize_q15_agreement(
        self,
        vote_details: Dict[int, Dict],
        total_runs: int
    ) -> str:
        """汇总Q15的AI一致性情况"""
        detail = vote_details.get(15)
        if detail is None or not detail.get('vote_counts'):
            if total_runs <= 1:
                return 'Insufficient data'
            return 'No Q15 data'

        counts = detail['vote_counts']
        sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        top_answer, top_count = sorted_counts[0]
        total_votes = sum(counts.values())
        if total_votes == 0:
            return 'No Q15 data'

        tie_count = sum(1 for _, cnt in counts.items() if cnt == top_count)
        if tie_count > 1:
            detail_text = ", ".join(f"{ans}:{cnt}" for ans, cnt in sorted_counts)
            return f"Split consensus ({detail_text})"

        ratio = top_count / total_votes
        if ratio == 1.0:
            label = "Unanimous"
        elif ratio >= 0.75:
            label = "Strong majority"
        elif ratio > 0.5:
            label = "Simple majority"
        else:
            label = "Plurality"

        detail_text = ", ".join(f"{ans}:{cnt}" for ans, cnt in sorted_counts)
        return f"{label} ({detail_text})"

    def _compare_human_vs_ai_q15(self, human_value: str, ai_value: str) -> str:
        """比较人类与多数投票在Q15上的一致性"""
        human_value = human_value or ''
        ai_value = ai_value or ''

        if not ai_value:
            return 'AI majority missing'

        normalized_human = self.voter._normalize_type_for_vote(human_value) if human_value else ''
        normalized_ai = self.voter._normalize_type_for_vote(ai_value) if ai_value else ''

        if not human_value:
            return f"Human missing (AI={normalized_ai or ai_value})"

        if not normalized_ai:
            return "AI majority missing"

        if not normalized_human:
            return f"Human unclassified (AI={normalized_ai})"

        if normalized_human == normalized_ai:
            return f"Match ({normalized_ai})"

        return f"Mismatch (Human={normalized_human}, AI={normalized_ai})"

    def _compare_human_vs_consensus(
        self,
        row: pd.Series,
        column_mapping: Dict[int, str],
        consensus_col: str
    ) -> str:
        """比较人类与共识列在Q15上的一致性"""
        consensus_value = str(row.get(consensus_col, '') or '').strip()
        if not consensus_value:
            return 'Consensus missing'

        lower_val = consensus_value.lower()
        if 'no data' in lower_val:
            return 'Consensus unavailable (no data)'
        if 'no clear' in lower_val:
            return 'Consensus unclear'

        q15_col = column_mapping.get(15)
        human_raw = str(row.get(q15_col, '') or '').strip() if q15_col else ''
        if not human_raw:
            return f"Human missing (Consensus={consensus_value})"

        normalized_human = self.voter._normalize_type_for_vote(human_raw)
        if not normalized_human:
            return f"Human unclassified (Consensus={consensus_value})"

        type_matches = re.findall(r'Type\s*([1-4])', consensus_value, flags=re.IGNORECASE)
        if not type_matches:
            return f"Consensus text: {consensus_value}"

        consensus_types = sorted({f"Type {match}" for match in type_matches})
        if normalized_human in consensus_types:
            if len(consensus_types) == 1:
                return f"Match ({normalized_human})"
            return f"Match within tie ({normalized_human}; Consensus={', '.join(consensus_types)})"

        return f"Mismatch (Human={normalized_human}, Consensus={', '.join(consensus_types)})"

    def _compose_type_summary(
        self,
        row: pd.Series,
        column_mapping: Dict[int, str],
        decision_tree_col: str,
        consensus_col: str
    ) -> str:
        """整合Q15、决策树和共识结果"""
        parts = []
        q15_col = column_mapping.get(15)
        if q15_col:
            q15_val = str(row.get(q15_col, '') or '').strip()
            if q15_val:
                parts.append(f"Q15={q15_val}")

        decision_val = str(row.get(decision_tree_col, '') or '').strip()
        if decision_val:
            parts.append(f"DecisionTree={decision_val}")

        consensus_val = str(row.get(consensus_col, '') or '').strip()
        if consensus_val:
            parts.append(f"Consensus={consensus_val}")

        return " | ".join(parts)

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
        summary_col = self.TYPE_SUMMARY_COL
        df[summary_col] = df.apply(
            lambda row: self._compose_type_summary(
                row, column_mapping, decision_tree_col, type_consensus_col
            ),
            axis=1
        )
        df[self.HUMAN_VS_CONSENSUS_COL] = df.apply(
            lambda row: self._compare_human_vs_consensus(
                row, column_mapping, type_consensus_col
            ),
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
        extra_cols = [
            decision_tree_col,
            type_consensus_col,
            self.AI_AGREEMENT_COL,
            self.HUMAN_VS_AI_COL,
            self.HUMAN_VS_CONSENSUS_COL,
            self.TYPE_SUMMARY_COL,
        ]

        q15_col = column_mapping.get(15)
        original_cols = list(df_human.columns)

        if q15_col and q15_col in original_cols:
            q15_index = original_cols.index(q15_col)
            prefix = [col for col in original_cols[:q15_index+1] if col not in base_cols]
            suffix = [col for col in original_cols[q15_index+1:] if col not in base_cols]
            new_cols = base_cols + prefix + extra_cols + [col for col in suffix if col not in extra_cols]
        else:
            remaining = [col for col in original_cols if col not in base_cols]
            new_cols = base_cols + remaining + extra_cols

        # 去重同时保持顺序
        seen = set()
        ordered_cols = []
        for col in new_cols:
            if col not in seen:
                ordered_cols.append(col)
                seen.add(col)

        # 确保所有列存在
        for col in ordered_cols:
            if col not in df.columns:
                df[col] = ''

        final_cols = [col for col in ordered_cols if col in df.columns]
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
