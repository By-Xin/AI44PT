"""
批量分析器模块 - 协调批量文章的4PT分析流程
"""
import os
import json
import re
import threading
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from config import Config, QuestionMaps
from prompts import SYSTEM_PROMPT, build_user_prompt, format_questions_prompt
from document_reader import DocumentReader
from response_parser import ResponseParser
from voting import MajorityVoter, ConsensusAnalyzer, DecisionTreeClassifier
from reporting import (
    export_excel,
    AI_SUCCESS_COUNT_COLUMN,
    AI_TOTAL_COUNT_COLUMN,
    AI_SUCCESS_RATE_COLUMN,
    Q15_VOTE_COUNTS_COLUMN,
)


class BatchAnalyzer:
    """批量分析协调器"""

    AI_AGREEMENT_COL = 'AI run agreement'
    RUN_CONSENSUS_COL = AI_AGREEMENT_COL
    SIGNAL_CONSISTENCY_COL = 'Signal consistency'
    HUMAN_VS_AI_COL = 'Human vs AI Match'
    TYPE_SUMMARY_COL = 'Type summary'
    HUMAN_VS_CONSENSUS_COL = 'Human vs Consensus'
    AI_SUCCESS_COUNT_COL = AI_SUCCESS_COUNT_COLUMN
    AI_TOTAL_COUNT_COL = AI_TOTAL_COUNT_COLUMN
    AI_SUCCESS_RATE_COL = AI_SUCCESS_RATE_COLUMN
    Q15_VOTE_COUNTS_COL = Q15_VOTE_COUNTS_COLUMN
    DECISION_TREE_COL = 'Decision Tree 4PT'
    SUPPORT_TYPES_COL = 'Type support (Q18/20/22/24)'
    FINAL_AI_DECISION_COL = 'Final AI decision'

    def __init__(self, config: Config = None):
        """
        初始化批量分析器

        Args:
            config: 批处理配置对象
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or Config()
        self.config.setup_directories()

        # 运行时组件（LLM 客户端按需初始化，避免 parse 阶段依赖在线配置）
        self.clients = {}
        self.available_providers: List[str] = []
        self.client = None
        self.current_raw_run_dir: Optional[Path] = None
            
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
        self.last_parse_run_counts: Dict[str, int] = {}

    def _initialize_clients(self):
        """按需初始化已启用的 LLM 客户端。"""
        if self.clients:
            return

        enabled_providers = list(self.config.ENABLED_PROVIDERS or [])
        if not enabled_providers:
            enabled_providers = [self.config.LLM_PROVIDER]

        for provider in enabled_providers:
            provider = (provider or "").strip().lower()
            if provider == "openai":
                if not self.config.OPENAI_API_KEY:
                    self.logger.warning("OpenAI provider skipped: OPENAI_API_KEY is missing.")
                    continue
                from llm_clients.openai_client import OpenAIClient
                self.clients["openai"] = OpenAIClient(
                    api_key=self.config.OPENAI_API_KEY,
                    model=self.config.CLS_MODEL
                )
                self.available_providers.append("openai")
                continue

            if provider == "gemini":
                if not self.config.GEMINI_API_KEY:
                    self.logger.warning("Gemini provider skipped: GEMINI_API_KEY is missing.")
                    continue
                try:
                    from llm_clients.gemini_client import GeminiClient
                    self.clients["gemini"] = GeminiClient(
                        api_key=self.config.GEMINI_API_KEY,
                        model=self.config.GEMINI_MODEL
                    )
                    self.available_providers.append("gemini")
                except ImportError as exc:
                    self.logger.warning(
                        "Gemini provider disabled (dependency missing): %s. "
                        "Install google-generativeai or remove 'gemini' from ENABLED_PROVIDERS.",
                        exc
                    )
                continue

            self.logger.warning("Unsupported provider '%s'; skipping.", provider)

        if not self.clients:
            raise RuntimeError(
                "No LLM clients initialized. Check provider keys/dependencies or ENABLED_PROVIDERS."
            )

        self.client = self.clients.get(self.config.LLM_PROVIDER) or list(self.clients.values())[0]

    def _ensure_clients_initialized(self):
        if not self.clients:
            self._initialize_clients()
        if self.client is None and self.clients:
            self.client = self.clients.get(self.config.LLM_PROVIDER) or list(self.clients.values())[0]

    def analyze_single_article(
        self,
        article_pages: List[Dict],
        coding_task_pages: List[Dict],
        executive_summary_pages: List[Dict],
        main_body_pages: List[Dict],
        article_meta: Dict,
        run_index: int,
        client=None,
        model_name: str = None,
        provider: Optional[str] = None
    ) -> Tuple[Optional[str], str, Dict]:
        """
        分析单篇文章（单次运行）

        Args:
            article_pages: 文章页面列表
            coding_task_pages: 编码任务说明页面列表
            executive_summary_pages: 执行摘要页面列表
            main_body_pages: 主体内容页面列表
            article_meta: 文章元数据
            run_index: 运行索引
            client: LLM客户端实例 (optional, defaults to self.client)
        model_name: 模型名称 (optional)
        provider: 提供商名称 (optional)

        Returns:
            (answers_dict, timestamp) 元组
        """
        if not article_pages:
            return None, self._get_timestamp()
            
        # Use provided client or lazy-initialized default client
        current_client = client
        if current_client is None:
            self._ensure_clients_initialized()
            current_client = self.client
        current_model = model_name or (self.config.GEMINI_MODEL if self.config.LLM_PROVIDER == "gemini" else self.config.CLS_MODEL)

        # 合并页面内容并截断防止超长
        article_text = "\n\n".join([f"Page {p['page']}:\n{p['text']}" for p in article_pages])
        max_chars = getattr(self.config, "ARTICLE_TEXT_MAX_CHARS", None)
        if max_chars and len(article_text) > max_chars:
            self.logger.warning(
                "Article text length %s exceeds limit %s; truncating",
                len(article_text), max_chars
            )
            article_text = article_text[:max_chars]
        coding_task_text = "\n\n".join([f"Section {p['page']}:\n{p['text']}" for p in coding_task_pages])
        executive_summary_text = "\n\n".join([f"Section {p['page']}:\n{p['text']}" for p in executive_summary_pages])
        main_body_text = "\n\n".join([f"Section {p['page']}:\n{p['text']}" for p in main_body_pages])

        # 构建提示
        question_order = self.config.generate_question_order()
        system_prompt, user_prompt = self._build_prompt(
            coding_task_text, 
            executive_summary_text, 
            main_body_text, 
            article_text,
            question_order
        )
        
        # For recording and single-input API
        full_prompt_for_record = f"{system_prompt}\n\n{user_prompt}"

        # 调用API
        analysis_text = None
        error_message = None

        try:
            analysis_text = current_client.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=self.config.TEMPERATURE,
                reasoning_effort=self.config.get_reasoning_effort(),
                text_verbosity=self.config.get_text_verbosity()
            )
        except Exception as e:
            error_message = str(e)

        api_timestamp = self._get_timestamp()
        status = "success" if analysis_text else "error"
        error_type = None if analysis_text else "api_error"

        # 保存原始响应
        record = self._save_raw_response(
            article_meta, run_index, full_prompt_for_record, analysis_text,
            api_timestamp, status, error_message, error_type=error_type,
            model_name=current_model, provider=provider
        )

        if analysis_text:
            return analysis_text, api_timestamp, record

        if error_message:
            self.logger.warning("  ⚠️ Error in analysis (run %s): %s", run_index, error_message)
        return None, api_timestamp, record

    def analyze_article_multiple_runs(
        self,
        article_pages: List[Dict],
        coding_task_pages: List[Dict],
        executive_summary_pages: List[Dict],
        main_body_pages: List[Dict],
        article_meta: Dict,
        collect_records: bool = False
    ):
        """
        多次分析单篇文章

        Args:
            article_pages: 文章页面列表
            coding_task_pages: 编码任务说明页面列表
            executive_summary_pages: 执行摘要页面列表
            main_body_pages: 主体内容页面列表
            article_meta: 文章元数据

        Returns:
            (answers, timestamp) 列表
        """
        ai_runs = self.config.get_ai_runs()

        raw_records = [] if collect_records else None

        if ai_runs <= 1:
            # 单次运行
            response, timestamp, record = self.analyze_single_article(
                article_pages, coding_task_pages, executive_summary_pages, main_body_pages, article_meta, run_index=1
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
        self.logger.info("    🔄 Running %s independent iterations...", ai_runs)
        answer_sets = []

        for i in range(ai_runs):
            self.logger.info("      Iteration %s/%s...", i + 1, ai_runs)
            response, timestamp, record = self.analyze_single_article(
                article_pages, coding_task_pages, executive_summary_pages, main_body_pages, article_meta, run_index=i+1
            )
            if collect_records and record:
                raw_records.append(record)
            if response:
                answers = self.parser.parse_response(response)
                if answers:
                    answer_sets.append((answers, timestamp))
                else:
                    self.logger.warning("      ⚠️ Iteration %s failed to parse", i + 1)
                    answer_sets.append((None, timestamp))
            else:
                self.logger.warning("      ⚠️ Iteration %s failed", i + 1)
                answer_sets.append((None, timestamp))

        successful = sum(1 for x, _ in answer_sets if x is not None)
        self.logger.info("    ✅ Completed %s/%s successful runs", successful, ai_runs)

        if collect_records:
            return answer_sets, raw_records
        return answer_sets

    def process_batch(
        self,
        excel_path: str = None,
        raw_data_path: str = None,
        stage: str = "full",
        use_all_runs: bool = False
    ):
        """
        批量处理入口（支持生成raw或从raw解析）

        Args:
            excel_path: Excel文件路径
            raw_data_path: 原始JSON文件路径或目录（解析阶段使用）
            stage: 处理阶段，可选 "raw"、"parse"、"full"
            use_all_runs: 解析阶段是否使用所有可用run（忽略配置的ai_runs限制）

        Returns:
            当stage为"raw"时返回JSON路径，其余情况返回结果DataFrame
        """
        stage = (stage or "full").lower()

        if stage == "raw":
            return self.generate_raw_responses(excel_path=excel_path, output_path=raw_data_path)

        if stage == "parse":
            if not raw_data_path:
                raise ValueError("parse stage requires raw data path")
            return self.parse_raw_responses(
                json_path=raw_data_path,
                excel_path=excel_path,
                use_all_runs=use_all_runs
            )

        if stage == "full":
            generated_path = self.generate_raw_responses(excel_path=excel_path, output_path=raw_data_path)
            return self.parse_raw_responses(
                json_path=str(generated_path),
                excel_path=excel_path,
                use_all_runs=use_all_runs
            )

        raise ValueError(f"Unsupported processing stage: {stage}")

    def _build_prompt(self, coding_task_text: str, executive_summary_text: str, main_body_text: str, article_text: str, question_order: List[int]) -> Tuple[str, str]:
        """构建分析提示（支持随机问题顺序）"""
        system_prompt = SYSTEM_PROMPT
        
        user_prompt_base = build_user_prompt(coding_task_text, executive_summary_text, main_body_text, article_text)
        questions_prompt = format_questions_prompt(question_order, self.config.QUESTION_TEXTS, self.config.ENABLE_SHUFFLE)
        
        user_prompt = f"{user_prompt_base}\n\n{questions_prompt}".strip()
        
        return system_prompt, user_prompt

    def _build_raw_record(
        self,
        article_meta: Dict,
        run_index: int,
        prompt: Optional[str],
        response_text: Optional[str],
        api_timestamp: str,
        status: str,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict:
        """构建原始响应记录"""
        article_id = str(article_meta.get('article_id', 'unknown'))
        if not model_name:
            model_name = self.config.GEMINI_MODEL if self.config.LLM_PROVIDER == "gemini" else self.config.CLS_MODEL
            
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
            "provider": provider,
            "ai_runs": article_meta.get('ai_runs'),
            "debug_mode": self.config.DEBUG_MODE,
            "model": model_name,
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
        error_type: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None
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
            error_type,
            model_name,
            provider
        )

        try:
            article_id = record["article_id"]
            safe_article_id = re.sub(r'[^A-Za-z0-9_-]+', '_', article_id)
            # Include model name in filename to avoid collisions when running multiple models
            safe_model = re.sub(r'[^A-Za-z0-9_-]+', '', model_name or "unknown")
            safe_provider = re.sub(r'[^A-Za-z0-9_-]+', '', provider or "provider")
            file_name = f"{safe_article_id}_{safe_provider}_{safe_model}_run{run_index}_{api_timestamp}_{status}.json"
            run_dir = self.current_raw_run_dir or self.config.RAW_OUTPUT_DIR
            run_dir.mkdir(parents=True, exist_ok=True)
            file_path = run_dir / file_name
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning("  ⚠️ Failed to save raw response: %s", e)
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
                                self.logger.warning("  ⚠️ Skipping non-dict entry in %s", path.name)
                    elif isinstance(data, dict):
                        records.append(data)
                    else:
                        self.logger.warning("  ⚠️ Unsupported JSON structure in %s", path.name)
            except FileNotFoundError:
                self.logger.error("❌ Raw JSON file not found: %s", path)
            except json.JSONDecodeError as exc:
                self.logger.warning("  ⚠️ Skipping malformed JSON file %s: %s", path.name, exc)

        def load_jsonl_file(path: Path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                records.append(obj)
                            else:
                                self.logger.warning(
                                    "  ⚠️ Skipping non-dict entry in %s line %s", path.name, line_num
                                )
                        except json.JSONDecodeError as exc:
                            self.logger.warning(
                                "  ⚠️ Skipping malformed JSONL line %s in %s: %s", line_num, path.name, exc
                            )
            except FileNotFoundError:
                self.logger.error("❌ Raw JSONL file not found: %s", path)

        if source_path.is_dir():
            json_files = sorted(source_path.glob("*.json"))
            jsonl_files = sorted(source_path.glob("*.jsonl"))

            if not json_files and not jsonl_files:
                self.logger.error("❌ No JSON/JSONL files found in directory: %s", source_path)
            else:
                for json_file in json_files:
                    load_json_file(json_file)
                for jsonl_file in jsonl_files:
                    load_jsonl_file(jsonl_file)
        else:
            suffix = source_path.suffix.lower()
            if suffix == ".json":
                load_json_file(source_path)
            elif suffix == ".jsonl":
                load_jsonl_file(source_path)
            else:
                self.logger.error("❌ Unsupported raw data format: %s", source_path)

        if not records:
            return records

        deduped_records: List[Dict] = []
        seen = set()
        for record in records:
            try:
                key = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                key = repr(record)
            if key in seen:
                continue
            seen.add(key)
            deduped_records.append(record)

        duplicates_removed = len(records) - len(deduped_records)
        if duplicates_removed > 0:
            self.logger.info("Deduplicated raw records: removed %s duplicate entries", duplicates_removed)

        return deduped_records

    def generate_raw_responses(
        self,
        excel_path: str = None,
        output_path: Optional[str] = None
    ) -> Path:
        """生成原始响应并保存为JSON数组（并发 + JSONL流式写入）"""
        excel_path = excel_path or str(self.config.EXCEL_PATH)
        self.logger.info("📥 Loading Excel for raw generation: %s", excel_path)
        df_human = pd.read_excel(excel_path)
        article_count = len(df_human)
        self.logger.info("Found %s articles to process for raw generation", article_count)

        if self.config.DEBUG_MODE:
            self.logger.info("⚙️ Debug mode active: limiting to first 2 articles")
            df_human = df_human.head(2).copy()
            article_count = len(df_human)
            self.logger.info("Processing subset size: %s", article_count)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if output_path:
            output_path = Path(output_path)
            if output_path.suffix:
                base_dir = output_path.parent
                run_dir_name = output_path.stem
                # Enforce aggregated file to be .json to avoid clobbering JSONL stream
                if output_path.suffix.lower() == ".jsonl":
                    self.logger.warning(
                        "Output path uses .jsonl; switching aggregated output to .json to prevent overwrite"
                    )
                    final_filename = output_path.with_suffix(".json").name
                elif output_path.suffix.lower() != ".json":
                    self.logger.warning(
                        "Output path suffix %s is not .json; using .json for aggregated output", output_path.suffix
                    )
                    final_filename = output_path.with_suffix(".json").name
                else:
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
        self.current_raw_run_dir = run_dir
        final_output_path = run_dir / final_filename
        streaming_output_path = final_output_path.with_suffix(".jsonl")

        self.logger.info("📝 Aggregated raw (array) will be written to: %s", final_output_path)
        self.logger.info("🧮 Streaming JSONL (append per call) will be written to: %s", streaming_output_path)
        streaming_output_path.write_text("", encoding="utf-8")

        # raw/full 阶段才需要客户端；这里按需初始化
        self._ensure_clients_initialized()

        # 预加载Codebook
        coding_task_pages = self.document_reader.read_markdown(str(self.config.CODINGTASK_MD))
        executive_summary_pages = self.document_reader.read_markdown(str(self.config.EXECUTIVESUMMARY_MD))
        main_body_pages = self.document_reader.read_markdown(str(self.config.MAINBODY_MD))
        
        self.logger.info("Reference documents loaded:")
        self.logger.info("  - Coding Task: %s sections", len(coding_task_pages))
        self.logger.info("  - Executive Summary: %s sections", len(executive_summary_pages))
        self.logger.info("  - Main Body: %s sections", len(main_body_pages))

        generation_stats = defaultdict(int)
        ai_runs = self.config.get_ai_runs()

        aggregated_records: List[Dict] = []
        records_lock = threading.Lock()
        stats_lock = threading.Lock()
        jsonl_lock = threading.Lock()
        article_lock = threading.Lock()

        concurrency_enabled = bool(self.config.ENABLE_CONCURRENT_CALLS)

        # 并发控制
        article_semaphore = threading.Semaphore(self.config.MAX_PARALLEL_ARTICLES) if concurrency_enabled and self.config.MAX_PARALLEL_ARTICLES else None
        global_semaphore = threading.Semaphore(self.config.MAX_TOTAL_CONCURRENT_CALLS) if concurrency_enabled and self.config.MAX_TOTAL_CONCURRENT_CALLS else None
        provider_semaphores = {
            "openai": threading.Semaphore(self.config.MAX_CONCURRENT_OPENAI) if concurrency_enabled and self.config.MAX_CONCURRENT_OPENAI else None,
            "gemini": threading.Semaphore(self.config.MAX_CONCURRENT_GEMINI) if concurrency_enabled and self.config.MAX_CONCURRENT_GEMINI else None,
        }

        # 每篇文章在飞的任务计数，用于释放 article_semaphore
        article_pending_tasks: Dict[str, int] = defaultdict(int)

        def append_record(record: Dict):
            with records_lock:
                aggregated_records.append(record)
            with jsonl_lock:
                with open(streaming_output_path, "a", encoding="utf-8") as jf:
                    jf.write(json.dumps(record, ensure_ascii=False))
                    jf.write("\n")
                    if self.config.JSONL_FLUSH_EACH_WRITE:
                        jf.flush()
                        try:
                            os.fsync(jf.fileno())
                        except OSError:
                            pass

        def update_stats_from_record(record: Dict):
            status = record.get("status")
            error_type = record.get("error_type")
            with stats_lock:
                if status == "success" and record.get("raw_response"):
                    generation_stats["success"] += 1
                elif error_type in {"PDF_NOT_FOUND", "PDF_READ_ERROR"}:
                    # 这些错误在文章层面已经计数，避免重复累计
                    pass
                else:
                    generation_stats["analysis_error"] += 1

        def execute_single_call(
            article_pages: List[Dict],
            coding_pages: List[Dict],
            exec_pages: List[Dict],
            main_pages: List[Dict],
            article_meta: Dict,
            run_idx: int,
            provider: str,
            client,
            model_name: str
        ) -> Dict:
            provider_sem = provider_semaphores.get(provider)
            acquired_global = False
            acquired_provider = False

            try:
                if global_semaphore:
                    global_semaphore.acquire()
                    acquired_global = True
                if provider_sem:
                    provider_sem.acquire()
                    acquired_provider = True

                response, api_timestamp, record = self.analyze_single_article(
                    article_pages,
                    coding_pages,
                    exec_pages,
                    main_pages,
                    article_meta,
                    run_index=run_idx,
                    client=client,
                    model_name=model_name,
                    provider=provider
                )
                return record
            except Exception as exc:
                ts = self._get_timestamp()
                err_record = self._save_raw_response(
                    article_meta,
                    run_idx,
                    prompt=None,
                    response_text=None,
                    api_timestamp=ts,
                    status="error",
                    error_message=str(exc),
                    error_type="api_error",
                    model_name=model_name,
                    provider=provider
                )
                return err_record
            finally:
                if acquired_provider:
                    provider_sem.release()
                if acquired_global:
                    global_semaphore.release()

        rows_iter = df_human.iterrows()
        # 并发模式下 tqdm 输出会混乱，这里禁用；串行模式继续使用 tqdm
        if not concurrency_enabled and tqdm:
            rows_iter = tqdm(rows_iter, total=article_count, desc="Raw generation", unit="article")

        futures = []
        future_to_article: Dict = {}
        future_to_provider: Dict = {}
        total_tasks = 0
        done_calls = 0
        done_lock = threading.Lock()
        progress_step = None

        def handle_future_completion(future):
            nonlocal done_calls, progress_step
            record = None
            try:
                record = future.result()
            except Exception as exc:
                article_id = future_to_article.get(future, "unknown")
                provider = future_to_provider.get(future, "unknown")
                ts = self._get_timestamp()
                article_meta = {
                    "article_id": article_id,
                    "title": "",
                    "index": None,
                    "total": article_count,
                    "pdf_path": None,
                    "ai_runs": ai_runs,
                    "provider": provider,
                }
                record = self._build_raw_record(
                    article_meta,
                    run_index=1,
                    prompt=None,
                    response_text=None,
                    api_timestamp=ts,
                    status="error",
                    error_message=str(exc),
                    error_type="api_error",
                    model_name=self.config.CLS_MODEL if provider == "openai" else self.config.GEMINI_MODEL,
                    provider=provider
                )

            append_record(record)
            update_stats_from_record(record)

            article_id = future_to_article.get(future)
            if article_id is not None:
                with article_lock:
                    article_pending_tasks[article_id] -= 1
                    if article_pending_tasks[article_id] <= 0:
                        article_pending_tasks.pop(article_id, None)
                        if article_semaphore:
                            article_semaphore.release()
                        self.logger.info("  ✅ Completed article #%s", article_id)

            with done_lock:
                done_calls += 1
                if total_tasks:
                    if progress_step is None:
                        progress_step = max(1, total_tasks // 10)
                    if done_calls % progress_step == 0 or done_calls == total_tasks:
                        with stats_lock:
                            s_success = generation_stats.get('success', 0)
                            s_err = generation_stats.get('analysis_error', 0)
                            s_pdf_missing = generation_stats.get('pdf_not_found', 0)
                            s_pdf_err = generation_stats.get('pdf_read_error', 0)
                        self.logger.info(
                            "  ↪️ Progress: %s/%s calls | success %s, errors %s, pdf_missing %s, pdf_read_err %s",
                            done_calls,
                            total_tasks,
                            s_success,
                            s_err,
                            s_pdf_missing,
                            s_pdf_err
                        )

        default_workers = max(4, (os.cpu_count() or 2) * 2)
        if concurrency_enabled:
            max_workers = self.config.MAX_TOTAL_CONCURRENT_CALLS or default_workers
        else:
            max_workers = 1
            # 禁用并发时确保信号量不生效
            global_semaphore = threading.Semaphore(1)
            provider_semaphores = {"openai": threading.Semaphore(1), "gemini": threading.Semaphore(1)}
        executor = ThreadPoolExecutor(max_workers=max_workers)

        for seq_idx, (df_index, row) in enumerate(rows_iter, start=1):
            article_id = row['#']
            title = row.get('Title of the Paper', 'Unknown')

            if article_semaphore:
                article_semaphore.acquire()

            self.logger.info(
                "[%s/%s] Scheduling raw generation for article #%s: %s...",
                seq_idx,
                article_count,
                article_id,
                title[:50]
            )

            article_meta = {
                "article_id": article_id,
                "title": title,
                "index": df_index,
                "total": article_count,
                "pdf_path": None,
                "ai_runs": ai_runs,
            }

            pdf_path = self._find_pdf(article_id)
            if not pdf_path:
                self.logger.warning("  ⚠️ PDF not found; recording error runs")
                generation_stats['pdf_not_found'] += 1
                article_meta['pdf_path'] = None
                
                providers = self.config.ENABLED_PROVIDERS or [self.config.LLM_PROVIDER]
                for provider in providers:
                    model_name = self.config.GEMINI_MODEL if provider == "gemini" else self.config.CLS_MODEL
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
                            model_name=model_name,
                            provider=provider
                        )
                        append_record(err_record)
                        update_stats_from_record(err_record)
                if article_semaphore:
                    article_semaphore.release()
                continue

            article_meta['pdf_path'] = pdf_path
            generation_stats['pdf_found'] += 1
            self.logger.info("  📄 Using PDF: %s", os.path.basename(pdf_path))

            try:
                article_pages = self.document_reader.read_pdf(pdf_path)
            except Exception as exc:
                self.logger.warning("  ⚠️ Exception while reading PDF: %s; recording error runs", exc)
                article_pages = []

            if not article_pages:
                self.logger.warning("  ⚠️ Failed to read PDF; recording error runs")
                generation_stats['pdf_read_error'] += 1
                
                providers = self.config.ENABLED_PROVIDERS or [self.config.LLM_PROVIDER]
                for provider in providers:
                    model_name = self.config.GEMINI_MODEL if provider == "gemini" else self.config.CLS_MODEL
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
                            model_name=model_name,
                            provider=provider
                        )
                        append_record(err_record)
                        update_stats_from_record(err_record)
                if article_semaphore:
                    article_semaphore.release()
                continue

            self.logger.info("  📖 PDF loaded: %s pages", len(article_pages))
            
            providers = self.available_providers or self.config.ENABLED_PROVIDERS
            if not providers:
                providers = [self.config.LLM_PROVIDER]
                
            self.logger.info(
                "  🤖 Scheduling %s run(s) for each of %s providers: %s...",
                ai_runs,
                len(providers),
                providers
            )

            for provider in providers:
                client = self.clients.get(provider)
                if not client:
                    self.logger.warning("  ⚠️ Client for provider '%s' not initialized. Skipping.", provider)
                    continue
                    
                model_name = self.config.GEMINI_MODEL if provider == "gemini" else self.config.CLS_MODEL
                for run_idx in range(ai_runs):
                    meta_copy = dict(article_meta)
                    meta_copy["provider"] = provider
                    with article_lock:
                        article_pending_tasks[str(article_id)] += 1
                    future = executor.submit(
                        execute_single_call,
                        article_pages,
                        coding_task_pages,
                        executive_summary_pages,
                        main_body_pages,
                        meta_copy,
                        run_idx + 1,
                        provider,
                        client,
                        model_name
                    )
                    futures.append(future)
                    future_to_article[future] = str(article_id)
                    future_to_provider[future] = provider
                    future.add_done_callback(handle_future_completion)
                    total_tasks += 1

            # 如果没有任何任务被提交，需要释放文章并发槽位
            with article_lock:
                pending = article_pending_tasks.get(str(article_id), 0)
            if pending == 0 and article_semaphore:
                article_semaphore.release()

        executor.shutdown(wait=True)

        with open(final_output_path, 'w', encoding='utf-8') as json_file:
            json.dump(aggregated_records, json_file, ensure_ascii=False, indent=2)

        self.logger.info("📦 Raw generation complete")
        self.logger.info("  ✅ Successful API responses: %s", generation_stats['success'])
        self.logger.info("  ⚠️ API/analysis errors: %s", generation_stats['analysis_error'])
        self.logger.info("  ⚠️ PDF not found: %s", generation_stats['pdf_not_found'])
        self.logger.info("  ⚠️ PDF read errors: %s", generation_stats['pdf_read_error'])
        self.logger.info("  📄 Streaming JSONL: %s", streaming_output_path)

        self.last_raw_source_path = final_output_path
        self.current_raw_run_dir = None
        return final_output_path

    def parse_raw_responses(
        self,
        json_path: str,
        excel_path: str = None,
        use_all_runs: bool = False,
        csv_output_path: Optional[str] = None,
        json_output_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """从原始JSON记录解析并生成结果并导出报表"""
        excel_path = excel_path or str(self.config.EXCEL_PATH)
        raw_source = Path(json_path)
        self.last_raw_source_path = raw_source

        self.logger.info("📥 Loading Excel for parsing: %s", excel_path)
        df_human = pd.read_excel(excel_path)
        total_articles = len(df_human)
        self.logger.info("Found %s articles to parse", total_articles)

        if self.config.DEBUG_MODE:
            self.logger.info("⚙️ Debug mode active: limiting to first 2 articles")
            df_human = df_human.head(2).copy()
            total_articles = len(df_human)
            self.logger.info("Parsing subset size: %s", total_articles)

        # 确保新增问题列存在
        self._ensure_question_columns(df_human)

        # 获取列名映射（人类/AI/概念层）
        question_maps: QuestionMaps = self.config.build_question_maps(df_human.columns)
        qnum_map = question_maps.as_qnum_map(prefer_human=True)
        self.logger.info(
            "Found %s human question columns, %s AI question columns",
            len(question_maps.human),
            len(question_maps.ai),
        )

        self.last_parse_run_counts = {}

        # 读取原始记录
        if raw_source.is_dir():
            self.logger.info("📂 Reading raw responses from directory: %s", raw_source)
        elif raw_source.suffix.lower() == ".json":
            self.logger.info("📂 Reading raw JSON file: %s", raw_source)
        else:
            self.logger.info("📂 Reading raw responses from: %s", raw_source)

        raw_records = self._load_raw_records(raw_source)
        if not raw_records:
            self.logger.error("❌ No raw records found; aborting parse stage")
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

        self.logger.info("Grouped raw records for %s articles", len(records_by_article))

        # 重置统计
        self.stats = {
            'success': 0,
            'pdf_not_found': 0,
            'pdf_error': 0,
            'analysis_error': 0
        }

        results = []

        parse_iter = df_human.iterrows()
        if tqdm:
            parse_iter = tqdm(parse_iter, total=total_articles, desc="Parsing articles", unit="article")

        for seq_idx, (_, row) in enumerate(parse_iter, start=1):
            article_id = str(row['#'])
            title = row.get('Title of the Paper', 'Unknown')

            self.logger.info("[%s/%s] Parsing article #%s: %s...", seq_idx, total_articles, article_id, title[:50])
            q_human_col = question_maps.human.get(15)
            q_ai_col = question_maps.ai.get(self.config.Q_ID_CLASSIFICATION)

            # 添加human结果行
            human_row = row.to_dict()
            human_row['source'] = 'human'
            human_row['Analysis_Status'] = 'HUMAN_ORIGINAL'
            human_row[self.AI_AGREEMENT_COL] = ''
            human_row[self.SIGNAL_CONSISTENCY_COL] = ''
            human_row[self.HUMAN_VS_AI_COL] = ''
            human_row[self.HUMAN_VS_CONSENSUS_COL] = ''
            results.append(human_row)

            article_records = records_by_article.get(article_id, [])
            if not article_records:
                self.logger.warning("  ⚠️ No raw records found; adding RAW_NOT_FOUND rows")
                results.extend(self._create_error_rows(row, 'RAW_NOT_FOUND', question_maps, providers=None))
                self.stats['analysis_error'] += 1
                continue

            configured_runs = self.config.get_ai_runs()
            run_entries, expected_providers = self._build_run_entries(
                article_records=article_records,
                configured_runs=configured_runs,
                use_all_runs=use_all_runs
            )
            if not run_entries:
                run_entries = [
                    (run_number, provider, None)
                    for run_number in range(1, configured_runs + 1)
                    for provider in expected_providers
                ]

            actual_run_count = len(run_entries)
            self.last_parse_run_counts[article_id] = actual_run_count

            ai_answer_sets = []
            ai_success_count = 0
            ai_rows_for_article: List[Dict] = []
            successful_ai_rows: List[Dict] = []

            for run_number, expected_provider, record in run_entries:
                if not record:
                    self.logger.warning(
                        "  ⚠️ Missing raw record for provider=%s run=%s; inserting placeholder",
                        expected_provider,
                        run_number
                    )
                    placeholder_ts = self._get_timestamp()
                    model_name = self.config.GEMINI_MODEL if expected_provider == "gemini" else self.config.CLS_MODEL
                    ai_row = self._create_ai_row(
                        row,
                        run_number,
                        None,
                        placeholder_ts,
                        question_maps,
                        model_name=model_name,
                        provider=expected_provider
                    )
                    ai_row['Analysis_Status'] = (
                        f'RAW_MISSING_{expected_provider.upper()}_RUN{run_number}_{placeholder_ts}'
                    )
                    ai_rows_for_article.append(ai_row)
                    results.append(ai_row)
                    self.stats['analysis_error'] += 1
                    continue

                status = record.get('status')
                error_type = record.get('error_type')
                raw_text = record.get('raw_response')
                api_timestamp = record.get('timestamp') or self._get_timestamp()
                model_name = record.get('model')
                provider = record.get('provider')

                if status == 'success' and raw_text:
                    answers = self.parser.parse_response(raw_text)
                    if answers:
                        ai_row = self._create_ai_row(row, run_number, answers, api_timestamp, question_maps, model_name=model_name, provider=provider)
                        ai_answer_sets.append((answers, api_timestamp))
                        ai_success_count += 1
                        successful_ai_rows.append(ai_row)
                    else:
                        self.logger.warning("  ⚠️ Parse error for provider=%s run=%s", provider, run_number)
                        ai_row = self._create_ai_row(row, run_number, None, api_timestamp, question_maps, model_name=model_name, provider=provider)
                        ai_row['Analysis_Status'] = f'PARSE_ERROR_{str(provider or "unknown").upper()}_RUN{run_number}_{api_timestamp}'
                        self.stats['analysis_error'] += 1
                else:
                    ai_row = self._create_ai_row(row, run_number, None, api_timestamp, question_maps, model_name=model_name, provider=provider)
                    label = error_type or status or 'ANALYSIS_ERROR'
                    ai_row['Analysis_Status'] = (
                        f'{label.upper()}_{str(provider or expected_provider or "unknown").upper()}_RUN{run_number}_{api_timestamp}'
                    )

                    if error_type == 'PDF_NOT_FOUND':
                        self.stats['pdf_not_found'] += 1
                    elif error_type == 'PDF_READ_ERROR':
                        self.stats['pdf_error'] += 1
                    else:
                        self.stats['analysis_error'] += 1

                ai_rows_for_article.append(ai_row)
                results.append(ai_row)

            # 计算投票细节以评估一致性
            majority_results = {}
            vote_details = {}
            numeric_stats = {}
            if ai_success_count > 0:
                majority_results, vote_details, numeric_stats = self.voter.perform_vote(
                    ai_answer_sets, question_maps.ai
                )

            ai_agreement_label = self._summarize_classification_agreement(vote_details, ai_success_count)
            if ai_agreement_label:
                human_row[self.AI_AGREEMENT_COL] = ai_agreement_label
                for ai_row in ai_rows_for_article:
                    ai_row[self.AI_AGREEMENT_COL] = ai_agreement_label

            is_classification_tie = self._is_classification_tie(vote_details)
            vote_counts_text = self._format_classification_vote_counts(vote_details, is_tie=is_classification_tie)
            success_rate_value: Optional[float]
            if actual_run_count:
                success_rate_value = round(ai_success_count / actual_run_count, 3)
            else:
                success_rate_value = ''

            human_row[self.AI_SUCCESS_COUNT_COL] = ai_success_count
            human_row[self.AI_TOTAL_COUNT_COL] = actual_run_count
            human_row[self.AI_SUCCESS_RATE_COL] = success_rate_value
            human_row[self.Q15_VOTE_COUNTS_COL] = vote_counts_text

            majority_row = None
            # 多数票逻辑 (Modified to always generate row even on tie)
            if (self.config.ENABLE_MAJORITY_VOTE and
                actual_run_count > 1 and
                ai_success_count >= 2):
                
                vote_output = self._create_majority_vote_row(
                    row, ai_answer_sets, question_maps,
                    majority_results, vote_details, numeric_stats
                )
                
                if vote_output:
                    majority_row, majority_metadata = vote_output
                    majority_row[self.AI_AGREEMENT_COL] = ai_agreement_label
                    majority_row[self.AI_SUCCESS_COUNT_COL] = ai_success_count
                    majority_row[self.AI_TOTAL_COUNT_COL] = actual_run_count
                    majority_row[self.AI_SUCCESS_RATE_COL] = success_rate_value
                    majority_row[self.Q15_VOTE_COUNTS_COL] = vote_counts_text
                    results.append(majority_row)

                    # Handle Human vs AI comparison
                    if is_classification_tie:
                        tie_msg = 'Tie (no AI majority)'
                        human_row[self.HUMAN_VS_AI_COL] = tie_msg
                        majority_row[self.HUMAN_VS_AI_COL] = tie_msg
                    else:
                        human_value = human_row.get(q_human_col, '') if q_human_col else ''
                        ai_value = majority_row.get(q_ai_col, '') if q_ai_col else ''
                        human_vs_ai = self._compare_human_vs_ai_classification(human_value, ai_value)
                        human_row[self.HUMAN_VS_AI_COL] = human_vs_ai
                        majority_row[self.HUMAN_VS_AI_COL] = human_vs_ai
                else:
                    human_row[self.HUMAN_VS_AI_COL] = 'No AI majority'
            else:
                # Fallback logic for insufficient runs or disabled voting
                if is_classification_tie:
                     human_row[self.HUMAN_VS_AI_COL] = 'Tie (no AI majority)'
                elif not self.config.ENABLE_MAJORITY_VOTE:
                    human_row[self.HUMAN_VS_AI_COL] = 'Majority vote disabled'
                elif actual_run_count <= 1:
                    human_row[self.HUMAN_VS_AI_COL] = 'Majority vote not applicable (single run)'
                elif ai_success_count < 2:
                    human_row[self.HUMAN_VS_AI_COL] = 'Majority vote unavailable (insufficient runs)'
                else:
                    human_row[self.HUMAN_VS_AI_COL] = 'No AI majority'

            human_value_for_consensus = human_row.get(q_human_col, '') if q_human_col else ''
            consensus_vote_text, consensus_majority_type = self._summarize_consensus_across_rows(
                successful_ai_rows,
                qnum_map
            )
            human_vs_consensus = self._compare_human_vs_consensus_classification(
                human_value_for_consensus,
                consensus_majority_type,
                consensus_vote_text
            )
            human_row[self.HUMAN_VS_CONSENSUS_COL] = human_vs_consensus
            for ai_row in ai_rows_for_article:
                ai_row[self.HUMAN_VS_CONSENSUS_COL] = human_vs_consensus
            if majority_row is not None:
                majority_row[self.HUMAN_VS_CONSENSUS_COL] = human_vs_consensus

            if ai_success_count > 0:
                self.stats['success'] += 1

        if not results:
            self.logger.error("❌ No results generated from raw parsing")
            return pd.DataFrame()

        df_results = pd.DataFrame(results)
        df_results = self._add_derived_columns(df_results, qnum_map)
        df_results, excel_output_path = self._finalize_dataframe(df_results, df_human, qnum_map)

        _ = export_excel(
            df_results,
            excel_output_path,
            article_id_column='#',
            source_column='source',
            title_column='Title of the Paper',
            article_status_column='Article_Status',
            ai_agreement_column=self.AI_AGREEMENT_COL,
            human_vs_ai_column=self.HUMAN_VS_AI_COL,
            human_vs_consensus_column=self.HUMAN_VS_CONSENSUS_COL,
            type_summary_column=self.TYPE_SUMMARY_COL,
        )

        self.logger.info("📊 Results saved to: %s", excel_output_path)

        if csv_output_path:
            csv_path = Path(csv_output_path).expanduser()
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            df_results.to_csv(csv_path, index=False)
            self.logger.info("📝 CSV export saved to: %s", csv_path)

        if json_output_path:
            json_path_out = Path(json_output_path).expanduser()
            json_path_out.parent.mkdir(parents=True, exist_ok=True)
            df_results.to_json(json_path_out, orient='records', force_ascii=False, indent=2)
            self.logger.info("📝 JSON export saved to: %s", json_path_out)

        self._print_summary(df_results, df_human)
        return df_results

    def _find_pdf(self, article_id) -> Optional[str]:
        """查找PDF文件"""
        pdf_path = self.config.PDF_FOLDER / f"{article_id}.pdf"
        return str(pdf_path) if pdf_path.exists() else None

    def _get_timestamp(self) -> str:
        """生成时间戳 (yymmddhhmmss)"""
        return datetime.now().strftime('%y%m%d%H%M%S')

    def _ensure_question_columns(self, df: pd.DataFrame):
        """确保所有问题列存在"""
        added = []
        for col_name in self.config.get_required_ai_columns():
            if col_name not in df.columns:
                df[col_name] = ''
                added.append(col_name)
        if added:
            self.logger.info("Added %s missing question columns", len(added))

    def _create_error_rows(
        self,
        row: pd.Series,
        error_type: str,
        question_maps: QuestionMaps,
        providers: Optional[List[str]] = None,
    ) -> List[Dict]:
        """创建错误行"""
        ai_runs = self.config.get_ai_runs()
        if not providers:
            providers = [p.strip().lower() for p in (self.config.ENABLED_PROVIDERS or []) if p]
        if not providers:
            providers = [(self.config.LLM_PROVIDER or "openai").strip().lower()]

        rows = []
        for provider in providers:
            model_name = self.config.GEMINI_MODEL if provider == "gemini" else self.config.CLS_MODEL
            for run_idx in range(ai_runs):
                run_number = run_idx + 1
                ts = self._get_timestamp()
                ai_row = self._create_ai_row(
                    row=row,
                    run_number=run_number,
                    ai_answers=None,
                    api_timestamp=ts,
                    question_maps=question_maps,
                    model_name=model_name,
                    provider=provider,
                )
                ai_row['Analysis_Status'] = f'{error_type}_{provider.upper()}_RUN{run_number}_{ts}'
                rows.append(ai_row)
        return rows

    def _create_ai_row(
        self,
        row: pd.Series,
        run_number: int,
        ai_answers: Optional[Dict],
        api_timestamp: str,
        question_maps: QuestionMaps,
        model_name: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict:
        """创建AI结果行"""
        ai_row = row.to_dict()
        
        if model_name:
            # Use specific model name if available
            # Reconstruct source ID format: model-temp-reasoning-verbosity-runX
            reasoning = self.config.get_reasoning_effort()
            verbosity = self.config.get_text_verbosity()
            provider_prefix = f"{provider}-" if provider else ""
            base_source = f"{provider_prefix}{model_name}-temp{self.config.TEMPERATURE}-reasoning_{reasoning}-verbosity_{verbosity}"
            run_source_id = f"{base_source}-run{run_number}"
        else:
            if provider:
                default_model = self.config.GEMINI_MODEL if provider == "gemini" else self.config.CLS_MODEL
                reasoning = self.config.get_reasoning_effort()
                verbosity = self.config.get_text_verbosity()
                run_source_id = (
                    f"{provider}-{default_model}-temp{self.config.TEMPERATURE}"
                    f"-reasoning_{reasoning}-verbosity_{verbosity}-run{run_number}"
                )
            else:
                run_source_id = self._get_run_source_id(run_number - 1)

        ai_row['source'] = run_source_id

        target_columns = set(question_maps.pkey.values()).union(question_maps.ai.values())
        if ai_answers is None:
            ai_row['Analysis_Status'] = f'ANALYSIS_ERROR_{api_timestamp}'
            for col_name in target_columns:
                ai_row[col_name] = ''
        else:
            ai_row['Analysis_Status'] = f'SUCCESS_{api_timestamp}'
            for col_name in target_columns:
                ai_row[col_name] = ''
            for q_num, answer in ai_answers.items():
                pkey = self.config.AI_QNUM_TO_PKEY.get(q_num)
                if not pkey:
                    continue
                col_name = question_maps.pkey.get(pkey)
                if col_name:
                    ai_row[col_name] = answer

        ai_row[self.AI_AGREEMENT_COL] = ''
        ai_row[self.SIGNAL_CONSISTENCY_COL] = ''
        ai_row[self.HUMAN_VS_AI_COL] = ''
        ai_row[self.HUMAN_VS_CONSENSUS_COL] = ''
        ai_row[self.AI_SUCCESS_COUNT_COL] = ''
        ai_row[self.AI_TOTAL_COUNT_COL] = ''
        ai_row[self.AI_SUCCESS_RATE_COL] = ''
        ai_row[self.Q15_VOTE_COUNTS_COL] = ''
        return ai_row

    def _create_majority_vote_row(
        self,
        row: pd.Series,
        ai_answer_sets: List[Tuple],
        question_maps: QuestionMaps,
        majority_results: Dict[int, str],
        vote_details: Dict[int, Dict],
        numeric_stats: Dict[int, Dict]
    ) -> Optional[Tuple[Dict, Dict]]:
        """创建多数投票结果行"""
        self.logger.info("  🗳️ Performing majority vote...")
        if not majority_results and not numeric_stats:
            return None

        majority_row = row.to_dict()
        
        # Determine source ID for majority vote row
        providers = self.config.ENABLED_PROVIDERS
        if len(providers) > 1:
            # If multiple providers, use a generic ensemble name
            majority_source_id = f"ensemble-majority-vote"
        else:
            # If single provider, keep model info but ensure it's clear
            majority_source_id = f"{self.config.get_source_id()}-majority-vote"
            
        majority_row['source'] = majority_source_id
        majority_row['Analysis_Status'] = f'MAJORITY_VOTE_{self._get_timestamp()}'

        # 清空答案
        for col_name in set(question_maps.pkey.values()).union(question_maps.ai.values()):
            majority_row[col_name] = ''

        qnum_map = question_maps.as_qnum_map(prefer_human=True)

        # 填充投票结果
        for q_num, answer in majority_results.items():
            col_name = question_maps.ai.get(q_num) or qnum_map.get(q_num)
            if col_name:
                majority_row[col_name] = answer

        # 填充数值统计
        for q_num, stats in numeric_stats.items():
            col_name = question_maps.ai.get(q_num) or qnum_map.get(q_num)
            if not col_name:
                continue
            avg_val = stats.get("average")
            count = stats.get("count")
            if avg_val is None or count is None:
                continue

            if q_num in self.config.TYPE_CONFIDENCE_QUESTIONS:
                rounded = int(round(avg_val))
                label = self.config.CONFIDENCE_LABELS.get(rounded, "")
                label_suffix = f" ~ {label}" if label else ""
                majority_row[col_name] = f"{avg_val:.2f}{label_suffix} (avg of {count} runs)"

        # 主观题标记
        for q_num in self.config.SUBJECTIVE_QUESTIONS:
            col_name = qnum_map.get(q_num)
            if col_name and q_num not in numeric_stats:
                majority_row[col_name] = '[SUBJECTIVE - NO VOTE]'

        self.logger.info("    ✅ Majority vote completed")
        majority_row[self.AI_AGREEMENT_COL] = ''
        majority_row[self.SIGNAL_CONSISTENCY_COL] = ''
        majority_row[self.HUMAN_VS_AI_COL] = ''
        majority_row[self.HUMAN_VS_CONSENSUS_COL] = ''
        majority_row[self.AI_SUCCESS_COUNT_COL] = ''
        majority_row[self.AI_TOTAL_COUNT_COL] = ''
        majority_row[self.AI_SUCCESS_RATE_COL] = ''
        majority_row[self.Q15_VOTE_COUNTS_COL] = ''
        metadata = {
            "majority_results": majority_results,
            "vote_details": vote_details,
            "numeric_stats": numeric_stats,
        }
        return majority_row, metadata

    def _summarize_classification_agreement(
        self,
        vote_details: Dict[int, Dict],
        total_runs: int
    ) -> str:
        """汇总分类问题(Q16)的AI一致性情况"""
        detail = vote_details.get(self.config.Q_ID_CLASSIFICATION)
        if detail is None or not detail.get('vote_counts'):
            if total_runs <= 1:
                return 'Insufficient data'
            return 'No Classification data'

        counts = detail['vote_counts']
        sorted_counts = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        top_answer, top_count = sorted_counts[0]
        total_votes = sum(counts.values())
        if total_votes == 0:
            return 'No Classification data'

        tie_count = sum(1 for _, cnt in counts.items() if cnt == top_count)
        if tie_count > 1:
            detail_text = ", ".join(f"{cnt}*{ans}" for ans, cnt in sorted_counts)
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

        detail_text = ", ".join(f"{cnt}*{ans}" for ans, cnt in sorted_counts)
        return f"{label} ({detail_text})"

    def _format_classification_vote_counts(
        self,
        vote_details: Dict[int, Dict],
        *,
        is_tie: bool = False
    ) -> str:
        """格式化分类问题(Q16)投票计数字符串"""
        detail = vote_details.get(self.config.Q_ID_CLASSIFICATION) if vote_details else None
        if not detail:
            return ''
        vote_counts = detail.get('vote_counts') or {}
        if not vote_counts:
            return ''
        sorted_counts = sorted(vote_counts.items(), key=lambda item: (-item[1], item[0]))
        formatted_counts = []
        for answer, count in sorted_counts:
            normalized_answer = self.voter._normalize_type_for_vote(str(answer))
            label = normalized_answer or str(answer)
            formatted_counts.append(f"{label}:{count}")
        counts_text = ", ".join(formatted_counts)
        if is_tie:
            return f"Tie ({counts_text})"
        return counts_text

    def _compare_human_vs_ai_classification(self, human_value: str, ai_value: str) -> str:
        """比较人类与多数投票在分类问题(Q16)上的一致性"""
        if human_value is None or (isinstance(human_value, float) and pd.isna(human_value)):
            human_value = ''
        if ai_value is None or (isinstance(ai_value, float) and pd.isna(ai_value)):
            ai_value = ''
        human_value = str(human_value).strip()
        ai_value = str(ai_value).strip()

        if not ai_value:
            return 'AI majority missing'

        ai_lower = ai_value.lower()
        if ai_lower.startswith('tie'):
            return 'AI tie (no majority)'

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

    def _is_classification_tie(self, vote_details: Dict[int, Dict]) -> bool:
        """判断分类问题(Q16)是否出现平票"""
        if not vote_details:
            return False
        detail = vote_details.get(self.config.Q_ID_CLASSIFICATION)
        if not detail:
            return False
        counts = detail.get('vote_counts')
        if not counts:
            return False
        max_count = max(counts.values())
        if max_count == 0:
            return False
        tied = sum(1 for value in counts.values() if value == max_count)
        return tied > 1

    @staticmethod
    def _normalize_run_index(run_idx) -> Optional[int]:
        if run_idx is None:
            return None
        if isinstance(run_idx, str):
            if run_idx.isdigit():
                run_idx = int(run_idx)
            else:
                return None
        if isinstance(run_idx, (int, float)):
            try:
                run_idx = int(run_idx)
            except (TypeError, ValueError):
                return None
        if not isinstance(run_idx, int) or run_idx <= 0:
            return None
        return run_idx

    @staticmethod
    def _normalize_provider_name(provider_value: Optional[str]) -> str:
        normalized = str(provider_value or "").strip().lower()
        return normalized if normalized else "unknown"

    def _extract_expected_providers(self, article_records: List[Dict]) -> List[str]:
        known_providers = set()
        has_unknown = False
        for record in article_records:
            provider = self._normalize_provider_name(record.get("provider"))
            if provider == "unknown":
                has_unknown = True
            else:
                known_providers.add(provider)

        if known_providers:
            providers = sorted(known_providers)
            if has_unknown and len(providers) > 1:
                providers.append("unknown")
            return providers

        configured_providers = [p.strip().lower() for p in (self.config.ENABLED_PROVIDERS or []) if p]
        if configured_providers:
            return configured_providers

        fallback = (self.config.LLM_PROVIDER or "openai").strip().lower()
        return [fallback]

    def _build_run_entries(
        self,
        article_records: List[Dict],
        configured_runs: int,
        use_all_runs: bool
    ) -> Tuple[List[Tuple[int, str, Optional[Dict]]], List[str]]:
        expected_providers = self._extract_expected_providers(article_records)
        record_by_key: Dict[Tuple[int, str], Dict] = {}
        discovered_runs = set()

        for record in article_records:
            run_idx = self._normalize_run_index(record.get("run_index"))
            if run_idx is None:
                continue

            provider = self._normalize_provider_name(record.get("provider"))
            if provider == "unknown" and len(expected_providers) == 1:
                provider = expected_providers[0]

            key = (run_idx, provider)
            existing = record_by_key.get(key)
            if existing is None or (record.get("timestamp") or "") >= (existing.get("timestamp") or ""):
                record_by_key[key] = record
            discovered_runs.add(run_idx)

        entries: List[Tuple[int, str, Optional[Dict]]] = []
        if use_all_runs and discovered_runs:
            for run_idx in sorted(discovered_runs):
                providers_for_run = sorted({
                    provider for (record_run, provider) in record_by_key.keys() if record_run == run_idx
                })
                if not providers_for_run:
                    providers_for_run = expected_providers
                for provider in providers_for_run:
                    entries.append((run_idx, provider, record_by_key.get((run_idx, provider))))
            return entries, expected_providers

        for run_idx in range(1, configured_runs + 1):
            for provider in expected_providers:
                entries.append((run_idx, provider, record_by_key.get((run_idx, provider))))

        return entries, expected_providers

    def _extract_consensus_type(self, consensus_text: str) -> str:
        if not consensus_text:
            return ''
        normalized = str(consensus_text).strip().lower()
        if not normalized:
            return ''
        if normalized.startswith("tie between"):
            return ''
        if normalized in {"no data", "no clear consensus"}:
            return ''
        match = re.search(r'\btype\s*([1-4])\b', consensus_text, re.IGNORECASE)
        if not match:
            return ''
        return f"Type {match.group(1)}"

    def _summarize_consensus_across_rows(
        self,
        successful_ai_rows: List[Dict],
        column_mapping: Dict[int, str]
    ) -> Tuple[str, str]:
        if not successful_ai_rows:
            return "No successful runs", ''

        consensus_counter = defaultdict(int)
        for ai_row in successful_ai_rows:
            consensus_text = self.consensus_analyzer.derive_consensus(pd.Series(ai_row), column_mapping)
            consensus_type = self._extract_consensus_type(consensus_text)
            if consensus_type:
                consensus_counter[consensus_type] += 1

        if not consensus_counter:
            return "No clear consensus", ''

        sorted_counts = sorted(consensus_counter.items(), key=lambda item: (-item[1], item[0]))
        vote_text = ", ".join(f"{label}:{count}" for label, count in sorted_counts)
        top_count = sorted_counts[0][1]
        tied_winners = [item for item in sorted_counts if item[1] == top_count]
        if len(tied_winners) > 1:
            return f"Tie ({vote_text})", ''

        return vote_text, sorted_counts[0][0]

    def _compare_human_vs_consensus_classification(
        self,
        human_value: str,
        consensus_type: str,
        consensus_vote_text: str
    ) -> str:
        consensus_vote_text = consensus_vote_text or ''
        if not consensus_vote_text:
            return "Consensus unavailable"
        if consensus_vote_text.lower().startswith("tie"):
            return "Consensus tie (no majority)"
        if not consensus_type:
            return "Consensus unavailable"

        if human_value is None or (isinstance(human_value, float) and pd.isna(human_value)):
            human_value = ''
        human_value = str(human_value).strip()

        if not human_value:
            return f"Human missing (Consensus={consensus_type})"
        normalized_human = self.voter._normalize_type_for_vote(human_value)
        if not normalized_human:
            return f"Human unclassified (Consensus={consensus_type})"
        if normalized_human == consensus_type:
            return f"Match ({consensus_type})"
        return f"Mismatch (Human={normalized_human}, Consensus={consensus_type})"

    def _compose_type_summary(
        self,
        row: pd.Series,
        column_mapping: Dict[int, str],
        decision_tree_col: str,
        support_types_col: str,
        final_decision_col: str,
    ) -> str:
        """整合Q15/Q16、决策树、支持信号与最终决策"""
        parts = []
        
        source = str(row.get('source', '')).lower()
        if source == 'human':
            q_col = column_mapping.get(15)
            label = "Q15"
        else:
            q_col = column_mapping.get(self.config.Q_ID_CLASSIFICATION)
            label = f"Q{self.config.Q_ID_CLASSIFICATION}"

        if q_col:
            val = str(row.get(q_col, '') or '').strip()
            if val:
                parts.append(f"{label}={val}")

        decision_val = str(row.get(decision_tree_col, '') or '').strip()
        if decision_val:
            parts.append(f"DecisionTree={decision_val}")

        support_val = str(row.get(support_types_col, '') or '').strip()
        if support_val:
            parts.append(f"Support={support_val}")

        final_val = str(row.get(final_decision_col, '') or '').strip()
        if final_val:
            parts.append(f"Final={final_val}")

        return " | ".join(parts)

    def _normalize_type_label(self, value) -> str:
        """标准化类型标签，处理缺失/平票文本"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ''
        text = str(value).strip()
        if not text:
            return ''
        lower = text.lower()
        if lower.startswith('tie'):
            return ''
        normalized = self.voter._normalize_type_for_vote(text)
        return normalized or text

    def _derive_support_types(self, row: pd.Series, column_mapping: Dict[int, str]) -> str:
        """从Q18/20/22/24提取支持的Type列表"""
        yes_types: List[str] = []
        saw_any = False

        for type_id, q_map in self.config.TYPE_QUESTION_GROUPS.items():
            support_col = column_mapping.get(q_map["support"])
            if not support_col:
                continue
            raw = row.get(support_col)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                continue
            saw_any = True
            normalized = self.voter._normalize_yes_no_for_vote(str(raw))
            if normalized == 'Yes':
                yes_types.append(f"Type {type_id}")

        if not saw_any:
            return ''
        if not yes_types:
            return 'None'
        if len(yes_types) == 1:
            return yes_types[0]
        return "+".join(sorted(yes_types))

    def _select_support_primary(self, support_value: str) -> str:
        """提取单一支持类型，若多选/缺失则返回空"""
        if not support_value:
            return ''
        if support_value.lower() == 'none':
            return ''
        parts = [p.strip() for p in support_value.split('+') if p.strip()]
        if len(parts) == 1 and parts[0].lower().startswith('type'):
            return parts[0]
        return ''

    def _summarize_run_agreement(
        self,
        row: pd.Series,
        column_mapping: Dict[int, str],
        decision_tree_col: str,
        support_types_col: str
    ) -> str:
        """汇总单次运行的三路信号一致性（Q16、决策树、Q18-24支持）"""
        q16_col = column_mapping.get(self.config.Q_ID_CLASSIFICATION)
        q16_type = self._normalize_type_label(row.get(q16_col)) if q16_col else ''
        tree_type = self._normalize_type_label(row.get(decision_tree_col))
        support_value = str(row.get(support_types_col, '') or '').strip()
        support_type = self._select_support_primary(support_value)

        signals = {}
        if q16_type:
            signals["Q16"] = q16_type
        if tree_type:
            signals["DecisionTree"] = tree_type
        if support_type:
            signals["Support"] = support_type

        if not signals:
            return "Insufficient data"

        unique_types = set(signals.values())
        if len(unique_types) == 1:
            agreed_type = unique_types.pop()
            return f"Agree ({agreed_type})"

        parts = [f"{k}={v}" for k, v in signals.items()]
        return "Disagree (" + " | ".join(parts) + ")"

    def _choose_final_ai_decision(
        self,
        row: pd.Series,
        column_mapping: Dict[int, str],
        decision_tree_col: str,
        support_types_col: str
    ) -> str:
        """确定最终AI决策，优先Q16，其次决策树，最后单一支持类型"""
        q16_col = column_mapping.get(self.config.Q_ID_CLASSIFICATION)
        q16_type = self._normalize_type_label(row.get(q16_col)) if q16_col else ''
        if q16_type:
            return q16_type

        tree_type = self._normalize_type_label(row.get(decision_tree_col))
        if tree_type:
            return tree_type

        support_value = str(row.get(support_types_col, '') or '').strip()
        support_type = self._select_support_primary(support_value)
        return support_type

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
        """添加派生列（Decision Tree、Q18-24支持、AI内部一致性、最终决策）"""
        self.logger.info("🌳 Calculating derived classifications...")

        decision_tree_col = self.DECISION_TREE_COL
        support_types_col = self.SUPPORT_TYPES_COL
        final_decision_col = self.FINAL_AI_DECISION_COL

        df[decision_tree_col] = df.apply(
            lambda row: DecisionTreeClassifier.calculate_4pt_type(row, column_mapping),
            axis=1
        )

        df[support_types_col] = df.apply(
            lambda row: self._derive_support_types(row, column_mapping),
            axis=1
        )

        df[self.SIGNAL_CONSISTENCY_COL] = df.apply(
            lambda row: self._summarize_run_agreement(
                row, column_mapping, decision_tree_col, support_types_col
            ),
            axis=1
        )

        df[final_decision_col] = df.apply(
            lambda row: self._choose_final_ai_decision(
                row, column_mapping, decision_tree_col, support_types_col
            ),
            axis=1
        )

        summary_col = self.TYPE_SUMMARY_COL
        df[summary_col] = df.apply(
            lambda row: self._compose_type_summary(
                row, column_mapping, decision_tree_col, support_types_col, final_decision_col
            ),
            axis=1
        )
        return df

    def _finalize_dataframe(
        self,
        df: pd.DataFrame,
        df_human: pd.DataFrame,
        column_mapping: Dict[int, str]
    ) -> Tuple[pd.DataFrame, Path]:
        """整理DataFrame列顺序并返回结果及输出路径"""
        # 调整列顺序
        base_cols = ['#', 'source', 'Analysis_Status']
        decision_tree_col = self.DECISION_TREE_COL
        extra_cols = [
            decision_tree_col,
            self.SUPPORT_TYPES_COL,
            self.AI_AGREEMENT_COL,
            self.SIGNAL_CONSISTENCY_COL,
            self.HUMAN_VS_AI_COL,
            self.HUMAN_VS_CONSENSUS_COL,
            self.TYPE_SUMMARY_COL,
            self.FINAL_AI_DECISION_COL,
            self.AI_SUCCESS_COUNT_COL,
            self.AI_TOTAL_COUNT_COL,
            self.AI_SUCCESS_RATE_COL,
            self.Q15_VOTE_COUNTS_COL,
        ]

        q15_col = column_mapping.get(15)
        original_cols = [col for col in df_human.columns if col != self.config.LEGACY_AI_FINAL_TYPE_COLUMN]

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

        # 删除已废弃的AI最终类型列
        if self.config.LEGACY_AI_FINAL_TYPE_COLUMN in df.columns:
            df = df.drop(columns=[self.config.LEGACY_AI_FINAL_TYPE_COLUMN])

        # 确保所有列存在
        for col in ordered_cols:
            if col not in df.columns:
                df[col] = ''

        final_cols = [col for col in ordered_cols if col in df.columns]
        df = df[final_cols]

        # 排序
        df = df.sort_values(['#', 'source'], ascending=[True, False])
        df = df.reset_index(drop=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = self.config.RESULTS_DIR / f"analysis_results_{timestamp}.xlsx"
        return df, output_path

    def _print_summary(self, df_results: pd.DataFrame, df_human: pd.DataFrame):
        """打印分析汇总"""
        self.logger.info("=" * 60)
        self.logger.info("ANALYSIS SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info("Total articles processed: %s", len(df_human))
        self.logger.info("✅ Successful analyses: %s", self.stats['success'])
        self.logger.info("⚠️ PDF not found: %s", self.stats['pdf_not_found'])
        self.logger.info("⚠️ PDF read errors: %s", self.stats['pdf_error'])
        self.logger.info("⚠️ Analysis errors: %s", self.stats['analysis_error'])

        if 'source' in df_results.columns:
            self.logger.info("Source distribution:\n%s", df_results['source'].value_counts())
