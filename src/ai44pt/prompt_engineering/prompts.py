from __future__ import annotations

from typing import Dict, List

from ..config import Config


def build_system_prompt(config: Config) -> str:
    template = config.PROMPTS["system_prompt"]
    structured = config.PROMPTS["structured_response_template"]
    return template.format(structured_response_template=structured).strip()

def build_user_prompt(
    config: Config,
    coding_task_text: str,
    executive_summary_text: str,
    main_body_text: str,
    article_text: str,
) -> str:
    template = config.PROMPTS["user_prompt"]
    return template.format(
        coding_task_text=coding_task_text,
        executive_summary_text=executive_summary_text,
        main_body_text=main_body_text,
        article_text=article_text,
    )

def format_questions_prompt(
    config: Config, question_order: List[int], question_texts: Dict[int, str], enable_shuffle: bool
) -> str:
    """根据指定顺序构建问题提示文本"""
    prompts = config.PROMPTS["questions_prompt"]

    header_lines = [prompts["header"]]
    header_lines.append(prompts["header_shuffle"] if enable_shuffle else prompts["header_ordered"])

    question_lines = [f"Q{q_num}. {question_texts[q_num]}" for q_num in question_order]
    return "\n\n".join(header_lines + question_lines + [prompts["footer"]])
