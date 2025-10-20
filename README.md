# 4PT Batch Analysis Pipeline

This repository contains a two-stage workflow for running large batches of 4PT article evaluations. It reads human-labelled metadata from Excel, replays saved AI responses, and produces a richly formatted workbook that highlights agreement across runs.

## Environment setup

1. Create/activate the project environment (the team standard uses Conda):
   ```bash
   conda activate NLP
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Provide credentials and paths in `.env` (at least `OPENAI_API_KEY`). See `code/config.py` for all configurable values.

## Quick start

The pipeline is controlled through `code/pipeline_main.py`. Three modes are available:

```bash
# 1) Generate raw API responses and parse them immediately (default)
python code/pipeline_main.py --stage full

# 2) Generate raw responses only (JSON + JSONL bundle)
python code/pipeline_main.py --stage raw --raw-path results/raw_responses

# 3) Parse an existing raw JSON bundle into Excel outputs
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated/raw_responses_20240101_120000.json
```

Key optional flags:

- `--excel-path /path/to/input.xlsx` – override the Excel metadata source.
- `--debug` – limit processing to two articles with lighter LLM settings.
- `--skip-bad` – ignore malformed JSON files during batch parsing.
- `--parse-all-runs` – when parsing, include every AI run found in the raw JSON instead of truncating to the configured `ai_runs`.

> 💡 When running `--stage raw` or `--stage full`, omit `--raw-path` to use the timestamped default output directory from `config.py`.

## Output files

Parsing always emits a timestamped Excel workbook under `results/analysis/`. The new Excel reporter (powered by `code/reporting.py`) generates:

- **Summary** – headline metrics (coverage, accuracy, ambiguous rate, averages) alongside status/consensus breakdowns, a terminology glossary, and a colour legend.
- **All_Results** – every row from the parser (human, individual AI runs, majority vote).
- **Article_Summary** – one row per article with human vs AI/consensus alignment and run statistics.
- **Pass_Strong**, **Pass_Weak**, **Contradiction**, **Ambiguous_Tie**, **Ambiguous_PoorCoverage**, **Technical_Failure** – “错题本” style sheets that copy the matching rows from `All_Results` (human, majority vote, and every run) with extra diagnostics like `Detail Note` and `Mismatch Pair (Human→AI)`.

Status definitions:

- `Pass_Strong`: human label matches the AI majority and the AI runs are Unanimous or Strong majority.
- `Pass_Weak`: human label matches the AI majority, but the internal consensus is only a Simple majority (or weaker).
- `Contradiction`: AI majority Q15 classification conflicts with the human label.
- `Ambiguous_Tie`: the AI runs end in a tie or split consensus, so no clear majority is available.
- `Ambiguous_PoorCoverage`: insufficient evidence for a reliable conclusion (single run, plurality, missing data, or majority vote disabled).
- `Technical_Failure`: every AI run failed (PDF/read/API errors), leaving no usable output.

Article-level summary rows now include:

- Human/majority Q15 types, majority vote counts, and run success rates.
- Automatically computed averages for each type’s extent (Q18/21/24/27) and Likert (Q19/22/25/28) signals.

Each sheet includes the following formatting:

- Article boundaries separated by bold top borders.
- `Article_Status` cells coloured to distinguish strong/weak passes (greens), ambiguous outcomes (oranges), contradictions (red), and technical failures (grey), with thick separators between articles on every detail sheet.
- “Summary” sheet titles and legend rows are styled for quick scanning, with status chips reusing the same colour palette.
- Auto-sized columns, frozen headers, filters, and wrapped text for readability.

CSV and JSON exports remain available: pass `--stage parse --raw-path ... --debug` (or any other flag combination) and the pipeline will write companion files beside the Excel workbook when `BatchAnalyzer.parse_raw_responses` is invoked programmatically with `csv_output_path` or `json_output_path`.

## Configuration tips

- Adjust default paths, AI settings, and toggles inside `code/config.py`.
- `Config.DEBUG_MODE = True` limits the run to two articles and drops reasoning effort for cheaper iterations.
- The parser expects the Excel workbook columns used in the original template (`#`, `source`, `Title of the Paper`, etc.).
- PDFs referenced in the Excel sheet should live under `data/processed/` unless you override `PDF_FOLDER`.

For a deeper look at module responsibilities and data flow, read [`code/README.md`](code/README.md).
