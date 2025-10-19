"""Utilities for exporting formatted Excel reports."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

import pandas as pd
from openpyxl.styles import Alignment, Border, PatternFill, Side
from openpyxl.utils import get_column_letter


STATUS_COLORS = {
    "Correct_All": PatternFill("solid", fgColor="C6EFCE"),  # green
    "Error_Ambiguous": PatternFill("solid", fgColor="F9CB9C"),  # orange
    "Error_Mismatch": PatternFill("solid", fgColor="F4CCCC"),  # red
    "Error_Technical": PatternFill("solid", fgColor="D9D9D9"),  # gray
}


def export_excel(
    df: pd.DataFrame,
    output_path: Path,
    *,
    article_id_column: str = "#",
    source_column: str = "source",
    title_column: str = "Title of the Paper",
    article_status_column: str = "Article_Status",
    ai_agreement_column: str = "AI run agreement (Q15)",
    human_vs_ai_column: str = "Human vs AI (Q15)",
    human_vs_consensus_column: str = "Human vs AI (consensus)",
    type_summary_column: str = "Type summary (Q15, Decision Tree, Consensus)",
) -> pd.DataFrame:
    """Export analysis results to a richly formatted Excel workbook."""
    if df.empty:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="All_Results", index=False)
        return pd.DataFrame(columns=[article_id_column, article_status_column])

    df_all = df.copy()
    summary_df, status_map, run_stats = _build_article_summary(
        df_all,
        article_id_column,
        source_column,
        title_column,
        article_status_column,
        ai_agreement_column,
        human_vs_ai_column,
        human_vs_consensus_column,
        type_summary_column,
    )

    status_series = df_all[article_id_column].apply(lambda value: status_map.get(str(value), ""))
    if article_status_column in df_all.columns:
        df_all[article_status_column] = status_series
    else:
        insert_at = 2 if "Analysis_Status" in df_all.columns else 1
        df_all.insert(insert_at, article_status_column, status_series)

    output_path = Path(output_path)
    if output_path.suffix.lower() != ".xlsx":
        output_path = output_path.with_suffix(".xlsx")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    status_order = ["Correct_All", "Error_Mismatch", "Error_Ambiguous", "Error_Technical"]
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="All_Results", index=False)
        summary_df.to_excel(writer, sheet_name="Article_Summary", index=False)

        for status in status_order:
            status_df = summary_df[summary_df[article_status_column] == status]
            if status_df.empty:
                # Write headers only to keep sheet visible.
                pd.DataFrame(columns=summary_df.columns).to_excel(
                    writer, sheet_name=status, index=False
                )
                continue
            status_df.to_excel(writer, sheet_name=status, index=False)

        sheets = writer.sheets

        _format_all_results_sheet(
            sheets.get("All_Results"),
            article_id_column,
            article_status_column,
        )
        _format_summary_sheet(
            sheets.get("Article_Summary"),
            article_status_column,
        )
        for status in status_order:
            _format_summary_sheet(
                sheets.get(status),
                article_status_column,
            )

    _print_status_report(status_map, run_stats)
    return summary_df


def _build_article_summary(
    df: pd.DataFrame,
    article_id_column: str,
    source_column: str,
    title_column: str,
    article_status_column: str,
    ai_agreement_column: str,
    human_vs_ai_column: str,
    human_vs_consensus_column: str,
    type_summary_column: str,
) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, Counter]]:
    summary_rows: List[Dict[str, object]] = []
    status_map: Dict[str, str] = {}
    run_stats: Dict[str, Counter] = {}

    for article_id, group in df.groupby(article_id_column, sort=True):
        human_rows = group[group[source_column] == "human"]
        human_row = human_rows.iloc[0] if not human_rows.empty else group.iloc[0]

        ai_rows = group[group[source_column] != "human"].copy()
        ai_base_rows = ai_rows[~ai_rows[source_column].astype(str).str.contains("majority-vote", na=False)]
        success_count = ai_base_rows["Analysis_Status"].astype(str).str.startswith("SUCCESS_").sum()
        total_ai_runs = len(ai_base_rows)
        has_success = success_count > 0
        has_majority = ai_rows[source_column].astype(str).str.contains("majority-vote", na=False).any()

        human_vs_ai = str(human_row.get(human_vs_ai_column, "") or "")
        human_vs_consensus = str(human_row.get(human_vs_consensus_column, "") or "")

        status = _determine_article_status(human_vs_ai, human_vs_consensus, has_success)
        status_map[str(article_id)] = status

        summary_row = {
            article_id_column: article_id,
            article_status_column: status,
            ai_agreement_column: human_row.get(ai_agreement_column, ""),
            human_vs_ai_column: human_vs_ai,
            human_vs_consensus_column: human_vs_consensus,
            type_summary_column: human_row.get(type_summary_column, ""),
            title_column: human_row.get(title_column, human_row.get("Title", "")),
            "Successful AI Runs": int(success_count),
            "Total AI Runs": int(total_ai_runs),
            "Majority Vote Available": "Yes" if has_majority else "No",
        }
        summary_rows.append(summary_row)

        outcome_counter = Counter()
        for status_value in ai_base_rows["Analysis_Status"].astype(str):
            key = status_value.split("_")[0] if status_value else "UNKNOWN"
            outcome_counter[key] += 1
        run_stats[str(article_id)] = outcome_counter

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(article_id_column).reset_index(drop=True)

    desired_order = [
        article_id_column,
        title_column,
        article_status_column,
        "Successful AI Runs",
        "Total AI Runs",
        "Majority Vote Available",
        ai_agreement_column,
        human_vs_ai_column,
        human_vs_consensus_column,
        type_summary_column,
    ]
    existing_columns = [col for col in desired_order if col in summary_df.columns]
    remaining_columns = [col for col in summary_df.columns if col not in existing_columns]
    summary_df = summary_df[existing_columns + remaining_columns]
    return summary_df, status_map, run_stats


def _determine_article_status(
    human_vs_ai: str,
    human_vs_consensus: str,
    has_success: bool,
) -> str:
    normalized_ai = (human_vs_ai or "").strip().lower()
    normalized_consensus = (human_vs_consensus or "").strip().lower()

    if not has_success:
        return "Error_Technical"

    if "mismatch" in normalized_ai or "mismatch" in normalized_consensus:
        return "Error_Mismatch"

    ai_match = normalized_ai.startswith("match") and "missing" not in normalized_ai
    consensus_match = normalized_consensus.startswith("match") and "missing" not in normalized_consensus

    ambiguous_tokens = [
        "missing",
        "unclassified",
        "unclear",
        "no ai majority",
        "no q15 data",
        "insufficient data",
        "consensus unavailable",
        "consensus missing",
        "consensus unclear",
        "majority vote disabled",
        "majority vote not applicable",
        "majority vote unavailable",
        "ai majority missing",
    ]

    if ai_match and consensus_match:
        return "Correct_All"

    if any(token in normalized_ai for token in ambiguous_tokens) or any(
        token in normalized_consensus for token in ambiguous_tokens
    ):
        return "Error_Ambiguous"

    if ai_match or consensus_match:
        # Only one side confident; treat as ambiguous.
        return "Error_Ambiguous"

    if not normalized_ai and not normalized_consensus:
        return "Error_Ambiguous"

    return "Error_Ambiguous"


def _format_all_results_sheet(ws, article_id_column: str, article_status_column: str) -> None:
    if ws is None:
        return

    _apply_common_sheet_formatting(ws, freeze_cell="D2", article_status_column=article_status_column)
    _apply_article_separators(ws, article_id_column)


def _format_summary_sheet(ws, article_status_column: str) -> None:
    if ws is None:
        return

    _apply_common_sheet_formatting(ws, freeze_cell="C2", article_status_column=article_status_column)


def _apply_common_sheet_formatting(
    ws,
    *,
    freeze_cell: str,
    article_status_column: str,
) -> None:
    if ws.max_row >= 1 and ws.max_column >= 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"

    ws.freeze_panes = freeze_cell

    header_alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    for cell in ws[1]:
        cell.alignment = header_alignment

    wrap_alignment = Alignment(wrap_text=True, vertical="top")
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.alignment = wrap_alignment

    for column_index, column_cells in enumerate(ws.columns, start=1):
        max_length = 0
        for cell in column_cells:
            value = cell.value
            if value is None:
                continue
            text = str(value)
            if "\n" in text:
                text = max(text.splitlines(), key=len)
            max_length = max(max_length, len(text))
        adjusted_width = max(10, min(max_length + 2, 80))
        ws.column_dimensions[get_column_letter(column_index)].width = adjusted_width

    status_col_idx = _find_column_index(ws, article_status_column)
    if status_col_idx is None:
        return

    for row_idx in range(2, ws.max_row + 1):
        cell = ws.cell(row=row_idx, column=status_col_idx)
        fill = STATUS_COLORS.get(str(cell.value))
        if fill:
            cell.fill = fill


def _apply_article_separators(ws, article_id_column: str) -> None:
    id_col_idx = _find_column_index(ws, article_id_column)
    if id_col_idx is None:
        return

    thick_side = Side(style="medium", color="000000")
    previous_value = None
    for row_idx in range(2, ws.max_row + 1):
        current_value = ws.cell(row=row_idx, column=id_col_idx).value
        if row_idx == 2 or current_value != previous_value:
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                existing_border = cell.border or Border()
                cell.border = Border(
                    left=existing_border.left,
                    right=existing_border.right,
                    top=thick_side,
                    bottom=existing_border.bottom,
                )
        previous_value = current_value


def _find_column_index(ws, column_name: str) -> Optional[int]:
    for idx, cell in enumerate(ws[1], start=1):
        if cell.value == column_name:
            return idx
    return None


def _print_status_report(status_map: Mapping[str, str], run_stats: Mapping[str, Counter]) -> None:
    if not status_map:
        return

    print("\n📌 Article status breakdown:")
    status_counter = Counter(status_map.values())
    for status, count in status_counter.most_common():
        print(f"  - {status}: {count}")

    technical_articles = [key for key, value in status_map.items() if value == "Error_Technical"]
    if not technical_articles:
        return

    print("\n  Technical issues by article:")
    for article_id in technical_articles:
        counter = run_stats.get(article_id, Counter())
        issues = ", ".join(f"{label}:{count}" for label, count in counter.items()) or "No AI runs recorded"
        print(f"    • Article {article_id}: {issues}")
