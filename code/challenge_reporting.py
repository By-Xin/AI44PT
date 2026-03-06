"""Utilities for exporting dynamic challenge reports."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


DEFAULT_COLUMNS = [
    "article_id",
    "article_title",
    "provider",
    "run_index",
    "analysis_timestamp",
    "analysis_status",
    "analysis_error_type",
    "analysis_error",
    "human_label",
    "human_label_normalized",
    "ai_label",
    "ai_label_normalized",
    "comparison_status",
    "probe_triggered",
    "probe_status",
    "probe_timestamp",
    "probe_summary",
    "root_cause",
    "prompt_risk_sentence",
    "minimal_prompt_fix",
    "expert_review_checklist",
]


def export_challenge_report_bundle(
    challenge_rows: List[Dict],
    output_dir: Path,
    timestamp: str,
    report_markdown_path: Optional[Path] = None,
) -> Dict[str, Path]:
    """Export challenge report files and return generated paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(challenge_rows or [])
    for column in DEFAULT_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    df = df[DEFAULT_COLUMNS]
    if not df.empty:
        df = df.sort_values(["article_id", "provider", "run_index"], na_position="last").reset_index(drop=True)

    json_path = output_dir / f"challenge_events_{timestamp}.json"
    csv_path = output_dir / f"challenge_events_{timestamp}.csv"
    xlsx_path = output_dir / f"challenge_events_{timestamp}.xlsx"
    markdown_path = report_markdown_path or (output_dir / f"challenge_report_{timestamp}.md")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(df.to_dict(orient="records"), json_file, ensure_ascii=False, indent=2)

    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_excel(xlsx_path, index=False)

    markdown_path.write_text(_build_markdown_report(df, timestamp), encoding="utf-8")

    return {
        "report_markdown": markdown_path,
        "report_json": json_path,
        "report_csv": csv_path,
        "report_xlsx": xlsx_path,
    }


def _build_markdown_report(df: pd.DataFrame, timestamp: str) -> str:
    """Render a human-review challenge report in markdown."""
    lines: List[str] = []
    lines.append("# Dynamic Challenge Report")
    lines.append("")
    lines.append(f"- Generated at: `{timestamp}`")

    if df.empty:
        lines.append("- No challenge rows were produced.")
        return "\n".join(lines) + "\n"

    issue_mask = df["comparison_status"].isin(["mismatch", "ai_unclassified"])
    probe_success_mask = df["probe_status"] == "success"
    lines.extend(
        [
            f"- Total run rows: **{len(df)}**",
            f"- Issue rows (mismatch / ai_unclassified): **{int(issue_mask.sum())}**",
            f"- Probe triggered rows: **{int(df['probe_triggered'].astype(bool).sum())}**",
            f"- Probe success rows: **{int(probe_success_mask.sum())}**",
            f"- Articles covered: **{df['article_id'].nunique()}**",
            "",
        ]
    )

    lines.append("## Comparison Status Breakdown")
    lines.append("")
    status_counts = df["comparison_status"].fillna("unknown").astype(str).value_counts()
    for status, count in status_counts.items():
        lines.append(f"- `{status}`: {int(count)}")
    lines.append("")

    lines.append("## Recurring Prompt Gaps (From Probe Root Cause)")
    lines.append("")
    root_causes = [
        _normalize_bucket_text(text)
        for text in df.loc[issue_mask & probe_success_mask, "root_cause"].fillna("").astype(str).tolist()
        if str(text).strip()
    ]
    if root_causes:
        for item, count in Counter(root_causes).most_common(10):
            lines.append(f"- ({count}) {item}")
    else:
        lines.append("- No successful probe root-cause text captured.")
    lines.append("")

    lines.append("## Article-by-Article Review")
    lines.append("")
    for article_id, group in df.groupby("article_id", sort=True):
        title = str(group["article_title"].iloc[0] or "")
        human_label = str(group["human_label"].iloc[0] or "")
        human_norm = str(group["human_label_normalized"].iloc[0] or "")

        lines.append(f"### Article `{article_id}`")
        if title:
            lines.append(f"- Title: {title}")
        lines.append(f"- Human label: `{human_label or '[missing]'}`")
        lines.append(f"- Human normalized: `{human_norm or '[missing]'}`")
        lines.append("")
        lines.append("| Provider | Run | AI label | Comparison | Probe |")
        lines.append("|---|---:|---|---|---|")

        sorted_group = group.sort_values(["provider", "run_index"], na_position="last")
        for _, row in sorted_group.iterrows():
            provider = str(row.get("provider", "") or "")
            run_index = row.get("run_index", "")
            ai_label = str(row.get("ai_label", "") or "")
            comparison_status = str(row.get("comparison_status", "") or "")
            probe_status = str(row.get("probe_status", "") or "")
            lines.append(
                f"| {provider} | {run_index} | {_escape_pipe(ai_label)} "
                f"| {comparison_status} | {probe_status} |"
            )
        lines.append("")

        issue_rows = sorted_group[sorted_group["comparison_status"].isin(["mismatch", "ai_unclassified"])]
        if issue_rows.empty:
            lines.append("- No mismatch challenge entries for this article.")
            lines.append("")
            continue

        for _, issue in issue_rows.iterrows():
            run_index = issue.get("run_index", "")
            provider = str(issue.get("provider", "") or "")
            lines.append(f"#### Mismatch Detail: `{provider}` run `{run_index}`")
            lines.append(f"- Comparison status: `{issue.get('comparison_status', '')}`")
            lines.append(f"- AI label: `{issue.get('ai_label', '')}`")
            lines.append(f"- Probe status: `{issue.get('probe_status', '')}`")
            lines.append(f"- Probe summary: {_safe_markdown(issue.get('probe_summary', ''))}")
            lines.append(f"- Root cause: {_safe_markdown(issue.get('root_cause', ''))}")
            lines.append(
                f"- Prompt risk sentence: {_safe_markdown(issue.get('prompt_risk_sentence', ''))}"
            )
            lines.append(f"- Minimal prompt fix: {_safe_markdown(issue.get('minimal_prompt_fix', ''))}")
            lines.append(
                f"- Expert review checklist: {_safe_markdown(issue.get('expert_review_checklist', ''))}"
            )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _normalize_bucket_text(text: str) -> str:
    """Normalize probe text into a compact bucket string."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return ""
    if len(cleaned) > 180:
        cleaned = f"{cleaned[:180].rstrip()}..."
    return cleaned


def _safe_markdown(value: object) -> str:
    """Collapse whitespace for markdown list readability."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if text else "[empty]"


def _escape_pipe(value: str) -> str:
    """Escape markdown pipe characters in table cells."""
    return str(value or "").replace("|", r"\|")
