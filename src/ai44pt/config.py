"""
配置模块 - 4PT批量分析系统的完整配置（YAML 单一真源）
"""

from __future__ import annotations

import logging
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from dotenv import load_dotenv

load_dotenv()

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], Mapping)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_with_extends(path: Path) -> Dict[str, Any]:
    if yaml is None:  # pragma: no cover
        raise RuntimeError("Missing dependency: pyyaml. Install it to use YAML configs.")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    extends = raw.pop("extends", None)
    if not extends:
        return raw

    merged: Dict[str, Any] = {}
    extend_list = extends if isinstance(extends, list) else [extends]
    for item in extend_list:
        parent_path = (path.parent / str(item)).resolve()
        merged = _deep_merge(merged, _load_yaml_with_extends(parent_path))
    return _deep_merge(merged, raw)


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def _as_int_keyed_map(mapping: Mapping[Any, Any]) -> Dict[int, Any]:
    converted: Dict[int, Any] = {}
    for key, value in mapping.items():
        converted[int(key)] = value
    return converted


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
            for key, value in self.human.items():
                merged.setdefault(key, value)
        return merged


class Config:
    """4PT分析系统配置类（由 YAML 驱动）。"""

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "base.yaml"

    _loaded: bool = False
    _config_path: Optional[Path] = None
    _raw_config: Dict[str, Any] = {}

    # Regex helpers (logic, not config)
    QUESTION_COLUMN_PATTERN = re.compile(r"\[Q(\d+)\]")

    # -------------------- YAML-driven fields (populated by load_from_yaml) --------------------
    CODINGTASK_MD: Path
    EXECUTIVESUMMARY_MD: Path
    MAINBODY_MD: Path
    EXCEL_PATH: Path
    PDF_FOLDER: Path
    RESULTS_DIR: Path
    RAW_OUTPUT_DIR: Path

    OPENAI_API_KEY: Optional[str]
    CLS_MODEL: str
    TEMPERATURE: float
    DEFAULT_REASONING_EFFORT: str
    DEFAULT_TEXT_VERBOSITY: str

    GEMINI_API_KEY: Optional[str]
    GEMINI_MODEL: str

    LLM_PROVIDER: str
    ENABLED_PROVIDERS: List[str]

    DEBUG_MODE: bool
    DEFAULT_AI_RUNS: int
    ENABLE_SHUFFLE: bool

    ENABLE_CONCURRENT_CALLS: bool
    MAX_PARALLEL_ARTICLES: int
    MAX_TOTAL_CONCURRENT_CALLS: int
    MAX_CONCURRENT_OPENAI: int
    MAX_CONCURRENT_GEMINI: int
    JSONL_FLUSH_EACH_WRITE: bool

    ENABLE_MAJORITY_VOTE: bool
    OBJECTIVE_QUESTIONS: List[int]
    SUBJECTIVE_QUESTIONS: List[int]
    TOTAL_QUESTIONS: int

    Q_ID_UNCERTAINTY: int
    Q_ID_CLASSIFICATION: int
    Q_ID_CONFIDENCE: int

    TYPE_CLASS_YN_QUESTIONS: List[int]
    TYPE_CONFIDENCE_QUESTIONS: List[int]
    CONFIDENCE_LABELS: Dict[int, str]

    P_KEYS: Dict[str, str]
    HUMAN_QNUM_TO_PKEY: Dict[int, str]
    AI_QNUM_TO_PKEY: Dict[int, str]
    ADDITIONAL_QUESTION_COLUMNS: Dict[int, str]
    AI_ONLY_PKEY_COLUMNS: Dict[str, str]
    LEGACY_AI_FINAL_TYPE_COLUMN: str
    TYPE_QUESTION_GROUPS: Dict[int, Dict[str, int]]

    QUESTION_TEXTS: Dict[int, str]
    SUPPORT_QUESTION_GROUPS: List[List[int]]

    PROMPTS: Dict[str, Any]

    # ----------------------------------------------------------------------------------------

    def __init__(self, *, config_path: Optional[Path] = None):
        if config_path is not None:
            self.load_from_yaml(config_path)
        else:
            self.ensure_loaded()

    @classmethod
    def ensure_loaded(cls) -> None:
        if not cls._loaded:
            cls.load_from_yaml(cls.DEFAULT_CONFIG_PATH)

    @classmethod
    def load_from_yaml(cls, config_path: Path) -> None:
        config_path = Path(config_path).expanduser().resolve()
        cls._raw_config = _load_yaml_with_extends(config_path)
        cls._config_path = config_path

        paths = cls._raw_config.get("paths", {})
        instructions = paths.get("instructions", {})
        outputs = paths.get("outputs", {})

        cls.CODINGTASK_MD = _resolve_path(cls.PROJECT_ROOT, instructions["codingtask_md"])
        cls.EXECUTIVESUMMARY_MD = _resolve_path(cls.PROJECT_ROOT, instructions["executive_summary_md"])
        cls.MAINBODY_MD = _resolve_path(cls.PROJECT_ROOT, instructions["mainbody_md"])

        cls.EXCEL_PATH = _resolve_path(cls.PROJECT_ROOT, paths["excel_path"])
        cls.PDF_FOLDER = _resolve_path(cls.PROJECT_ROOT, paths["pdf_folder"])

        cls.RESULTS_DIR = _resolve_path(cls.PROJECT_ROOT, outputs["output_dir"])
        cls.RAW_OUTPUT_DIR = _resolve_path(cls.PROJECT_ROOT, outputs["raw_output_dir"])

        cls.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        cls.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

        openai_cfg = cls._raw_config.get("openai", {})
        cls.CLS_MODEL = str(openai_cfg.get("model", "")).strip()
        cls.TEMPERATURE = float(openai_cfg.get("temperature", 0.0))
        cls.DEFAULT_REASONING_EFFORT = str(openai_cfg.get("default_reasoning_effort", "medium"))
        cls.DEFAULT_TEXT_VERBOSITY = str(openai_cfg.get("default_text_verbosity", "low"))

        gemini_cfg = cls._raw_config.get("gemini", {})
        cls.GEMINI_MODEL = str(gemini_cfg.get("model", "")).strip()

        llm_cfg = cls._raw_config.get("llm", {})
        cls.LLM_PROVIDER = str(llm_cfg.get("provider", "openai")).lower().strip()
        cls.ENABLED_PROVIDERS = [str(p).lower().strip() for p in llm_cfg.get("enabled_providers", [])]

        batch_cfg = cls._raw_config.get("batch", {})
        cls.DEBUG_MODE = bool(batch_cfg.get("debug_mode", False))
        cls.DEFAULT_AI_RUNS = int(batch_cfg.get("default_ai_runs", 3))
        cls.ENABLE_SHUFFLE = bool(batch_cfg.get("enable_shuffle", False))

        concurrency_cfg = batch_cfg.get("concurrency", {})
        cls.ENABLE_CONCURRENT_CALLS = bool(concurrency_cfg.get("enable_concurrent_calls", True))
        cls.MAX_PARALLEL_ARTICLES = int(concurrency_cfg.get("max_parallel_articles", 0))
        cls.MAX_TOTAL_CONCURRENT_CALLS = int(concurrency_cfg.get("max_total_concurrent_calls", 0))
        cls.MAX_CONCURRENT_OPENAI = int(concurrency_cfg.get("max_concurrent_openai", 0))
        cls.MAX_CONCURRENT_GEMINI = int(concurrency_cfg.get("max_concurrent_gemini", 0))
        cls.JSONL_FLUSH_EACH_WRITE = bool(concurrency_cfg.get("jsonl_flush_each_write", True))

        voting_cfg = cls._raw_config.get("voting", {})
        cls.ENABLE_MAJORITY_VOTE = bool(voting_cfg.get("enable_majority_vote", True))
        cls.OBJECTIVE_QUESTIONS = [int(x) for x in voting_cfg.get("objective_questions", [])]
        cls.SUBJECTIVE_QUESTIONS = [int(x) for x in voting_cfg.get("subjective_questions", [])]
        cls.TOTAL_QUESTIONS = int(voting_cfg.get("total_questions", 25))

        cls.Q_ID_UNCERTAINTY = int(voting_cfg.get("q_id_uncertainty", 15))
        cls.Q_ID_CLASSIFICATION = int(voting_cfg.get("q_id_classification", 16))
        cls.Q_ID_CONFIDENCE = int(voting_cfg.get("q_id_confidence", 17))

        cls.TYPE_CLASS_YN_QUESTIONS = [int(x) for x in voting_cfg.get("type_class_yn_questions", [])]
        cls.TYPE_CONFIDENCE_QUESTIONS = [int(x) for x in voting_cfg.get("type_confidence_questions", [])]
        cls.CONFIDENCE_LABELS = {int(k): str(v) for k, v in (voting_cfg.get("confidence_labels", {}) or {}).items()}

        schema_cfg = cls._raw_config.get("schema", {})
        cls.P_KEYS = {str(k): str(v) for k, v in (schema_cfg.get("p_keys", {}) or {}).items()}
        cls.HUMAN_QNUM_TO_PKEY = _as_int_keyed_map(schema_cfg.get("human_qnum_to_pkey", {}) or {})
        cls.AI_QNUM_TO_PKEY = _as_int_keyed_map(schema_cfg.get("ai_qnum_to_pkey", {}) or {})
        cls.ADDITIONAL_QUESTION_COLUMNS = _as_int_keyed_map(schema_cfg.get("additional_question_columns", {}) or {})
        cls.AI_ONLY_PKEY_COLUMNS = {str(k): str(v) for k, v in (schema_cfg.get("ai_only_pkey_columns", {}) or {}).items()}
        cls.LEGACY_AI_FINAL_TYPE_COLUMN = str(schema_cfg.get("legacy_ai_final_type_column", ""))
        cls.TYPE_QUESTION_GROUPS = {int(k): dict(v) for k, v in (schema_cfg.get("type_question_groups", {}) or {}).items()}

        cls.QUESTION_TEXTS = _as_int_keyed_map(schema_cfg.get("question_texts", {}) or {})
        cls.SUPPORT_QUESTION_GROUPS = [
            [int(x) for x in group]
            for group in (schema_cfg.get("support_question_groups", []) or [])
        ]

        cls.PROMPTS = dict(cls._raw_config.get("prompts", {}) or {})

        cls._loaded = True

    @classmethod
    def get_required_ai_columns(cls) -> List[str]:
        """返回需要自动追加的AI专属列"""
        cls.ensure_loaded()
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
        cls.ensure_loaded()
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

    @classmethod
    def get_ai_runs(cls) -> int:
        cls.ensure_loaded()
        return 2 if cls.DEBUG_MODE else cls.DEFAULT_AI_RUNS

    @classmethod
    def get_reasoning_effort(cls) -> str:
        cls.ensure_loaded()
        return "low" if cls.DEBUG_MODE else cls.DEFAULT_REASONING_EFFORT

    @classmethod
    def get_text_verbosity(cls) -> str:
        cls.ensure_loaded()
        return "low" if cls.DEBUG_MODE else cls.DEFAULT_TEXT_VERBOSITY

    @classmethod
    def get_source_id(cls) -> str:
        cls.ensure_loaded()
        reasoning = cls.get_reasoning_effort()
        verbosity = cls.get_text_verbosity()
        model = cls.GEMINI_MODEL if cls.LLM_PROVIDER == "gemini" else cls.CLS_MODEL
        return f"{model}-temp{cls.TEMPERATURE}-reasoning_{reasoning}-verbosity_{verbosity}"

    @classmethod
    def generate_question_order(cls) -> List[int]:
        cls.ensure_loaded()
        units = []
        used_numbers = set()

        for group in cls.SUPPORT_QUESTION_GROUPS:
            units.append(list(group))
            used_numbers.update(group)

        for q_num in sorted(cls.QUESTION_TEXTS.keys()):
            if q_num in used_numbers:
                continue
            units.append([q_num])

        if cls.ENABLE_SHUFFLE:
            random.shuffle(units)
        else:
            units.sort(key=lambda x: x[0])

        ordered_questions: List[int] = []
        for unit in units:
            ordered_questions.extend(unit)
        return ordered_questions

    @classmethod
    def setup_directories(cls) -> None:
        cls.ensure_loaded()
        cls.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.RAW_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> bool:
        cls.ensure_loaded()
        logger = logging.getLogger(__name__)

        if "openai" in cls.ENABLED_PROVIDERS and not cls.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not found in environment. Please set it in .env file.")
            return False
        if "gemini" in cls.ENABLED_PROVIDERS and not cls.GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not found in environment. Please set it in .env file.")
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

        if not cls.EXCEL_PATH.exists():
            logger.error("Excel file not found at %s", cls.EXCEL_PATH)
            return False
        if not cls.PDF_FOLDER.exists():
            logger.error("PDF folder not found at %s", cls.PDF_FOLDER)
            return False

        return True

    @classmethod
    def display_config(cls) -> None:
        cls.ensure_loaded()
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("CONFIGURATION")
        logger.info("=" * 60)
        logger.info("Config YAML: %s", cls._config_path)
        logger.info("Project Root: %s", cls.PROJECT_ROOT)
        logger.info("Coding Task: %s", cls.CODINGTASK_MD)
        logger.info("Exec Summary: %s", cls.EXECUTIVESUMMARY_MD)
        logger.info("Main Body: %s", cls.MAINBODY_MD)
        logger.info("Excel Path: %s", cls.EXCEL_PATH)
        logger.info("PDF Folder: %s", cls.PDF_FOLDER)
        logger.info("Output Dir: %s", cls.RESULTS_DIR)
        logger.info("Enabled Providers: %s", cls.ENABLED_PROVIDERS)
        logger.info("OpenAI Model: %s", cls.CLS_MODEL)
        logger.info("Gemini Model: %s", cls.GEMINI_MODEL)
        logger.info("Temperature: %s", cls.TEMPERATURE)
        logger.info("AI Runs: %s", cls.get_ai_runs())
        logger.info("Reasoning Effort: %s", cls.get_reasoning_effort())
        logger.info("Text Verbosity: %s", cls.get_text_verbosity())
        logger.info("Majority Vote: %s", cls.ENABLE_MAJORITY_VOTE)
        logger.info("Shuffle Questions: %s", cls.ENABLE_SHUFFLE)
        logger.info("Debug Mode: %s", cls.DEBUG_MODE)
        logger.info("=" * 60)

