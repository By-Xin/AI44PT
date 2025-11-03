# Code Module Overview

This directory contains the modular 4PT analysis system, organized into specialized modules following data science best practices.

## Module Structure (7 files)

### Core Modules
- **`config.py`** (12K) - Complete configuration including paths, API keys, model settings, and all batch parameters
- **`document_reader.py`** (2.2K) - PDF and Markdown document reading
- **`__init__.py`** (909B) - Package initialization

### Analysis Pipeline Modules
- **`response_parser.py`** (7.7K) - AI response parsing and normalization
- **`voting.py`** (13K) - Majority voting, consensus analysis, decision tree classification
- **`batch_analyzer.py`** (21K) - Main batch processing orchestrator
- **`pipeline_main.py`** (3.0K) - Command-line entry point for batch analysis

## Quick Start

```bash
# Run the complete two-stage pipeline (raw generation + parsing)
python code/pipeline_main.py --stage full

# (Optional) Stage 1: generate raw JSON bundle (per-run JSON + aggregated JSON)
python code/pipeline_main.py --stage raw --raw-path results/raw_responses/aggregated/raw_responses_my_run.json

# (Optional) Stage 2: parse a previously generated aggregated JSON file
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated/raw_responses_my_run.json

# Stage 2 in batch mode: parse every aggregated JSON in a directory (or omit --raw-path to use the default)
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated

# (The parser also supports directories that contain only per-run *.json files)

# Allow batch parse to skip any JSON inputs that fail to load/parse
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated --skip-bad

# Parse using every run found in the raw JSON (ignore configured ai_runs)
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated --parse-all-runs

# Override the Excel source if needed
python code/pipeline_main.py --stage full --excel-path /path/to/custom.xlsx

# Toggle debug mode (limits to 2 articles, lowers effort)
python code/pipeline_main.py --stage raw --debug
```

## Configuration

All configuration is now in a single file: `config.py`

**Key parameters to adjust:**
- `DEBUG_MODE = True` - Limits to 2 articles for testing
- `DEFAULT_AI_RUNS = 3` - Number of independent AI runs per article (parse stage uses this unless you pass `--parse-all-runs`)
- `ENABLE_MAJORITY_VOTE = True` - Enable consensus analysis
- `EXCEL_PATH` - Path to input Excel file
- `PDF_FOLDER` - Path to PDF files directory
- `TEMPERATURE = 0.1` - AI randomness (0.0-1.0)
- `DEFAULT_REASONING_EFFORT` - "low", "medium", or "high"
- `DEFAULT_TEXT_VERBOSITY` - "low", "medium", or "high"
- `RAW_OUTPUT_DIR` - Base directory for raw `.json` records (per-run files + aggregated exports)
- `--debug` (CLI flag) - Forces debug mode without editing `config.py`

## Module Dependencies

```
pipeline_main.py
    └── BatchAnalyzer (batch_analyzer.py)
            ├── Config (config.py)
            ├── DocumentReader (document_reader.py)
            ├── ResponseParser (response_parser.py)
            └── Voting modules (voting.py)
                    ├── MajorityVoter
                    ├── ConsensusAnalyzer
                    └── DecisionTreeClassifier
```

## Design Principles

- **Single Responsibility**: Each module has one clear purpose
- **Loose Coupling**: Modules interact through well-defined interfaces
- **High Cohesion**: Related functionality grouped together
- **Testability**: All components can be tested independently
- **Occam's Razor**: Simplicity over unnecessary complexity

## Two-Stage Workflow

1. **Raw generation (`--stage raw`)**
   - Reads the Excel input and source PDFs
   - Submits independent AI runs per article
   - Writes every request/response record to both individual `.json` files and an aggregated `.json` bundle

2. **Parsing (`--stage parse`)**
   - Loads the original Excel metadata
   - Replays answers from the saved aggregated `.json`
   - Rebuilds AI rows, applies majority voting/consensus, and produces the final spreadsheet (pass `--parse-all-runs` to include every run found in the raw JSON bundle)

The staged approach makes the process resumable: if generation is interrupted, simply re-run `--stage parse` with the saved aggregated JSON to reconstruct outputs without re-querying the API.

## Output

Results are written beneath `../results/`:

- `analysis/analysis_results_YYYYMMDD_HHMMSS.xlsx` – main Excel workbook.
- `raw_responses/*.jsonl` – per-run raw API responses for auditing.
- `raw_responses/aggregated/raw_responses_YYYYMMDD_HHMMSS.json` – aggregated raw interactions for resumable parsing.

The Excel exporter in [`reporting.py`](reporting.py) builds several sheets automatically:

- **Summary** – high-level metrics (coverage, accuracy, ambiguous rate, averages), status/consensus breakdowns, a terminology glossary, and a colour legend for the status taxonomy.
- **Confusion_Matrix** – four-type confusion tables (raw and normalised) with per-class precision/recall/F1 and the top error pairs.
- **Agreement_Distribution** – distribution of the “AI run agreement (Q15)” labels.
- **Ambiguity_Patterns** *(only when ambiguous cases exist)* – aggregated vote-shape patterns and article-level detail for ambiguous outcomes.
- **Majority_Margin** – article-level majority margins and accuracy-by-bucket summaries.
- **All_Results** – full table with human rows, AI runs, and majority-vote summaries.
- **Article_Summary** – one row per article with status, agreement scores, and run counts.
- **Pass_Strong**, **Pass_Weak**, **Contradiction**, **Ambiguous_Tie**, **Ambiguous_PoorCoverage**, **Technical_Failure** – per-status “错题本” tabs that duplicate the relevant rows from `All_Results` (human, majority, each run) while adding diagnostics such as `Detail Note` and `Mismatch Pair (Human→AI)`.

Status glossary:

- `Pass_Strong` – human label matches the AI majority and the runs are Unanimous / Strong majority.
- `Pass_Weak` – human label matches the AI majority, but agreement strength is only Simple majority (or weaker).
- `Contradiction` – human label conflicts with the AI majority decision.
- `Ambiguous_Tie` – AI runs produce a tie / split consensus, so no decisive majority.
- `Ambiguous_PoorCoverage` – insufficient evidence (plurality, missing data, single run, or majority voting disabled).
- `Technical_Failure` – no successful AI runs (PDF/read/API errors).

`Article_Summary` enriches each article row with the human/majority Q15 labels, Q15 vote breakdown, success/total run counts (and success rate), plus per-type averages for extent (Q18/21/24/27) and Likert (Q19/22/25/28) scores. The majority rows in `All_Results` carry the same run statistics for quick reference.

Formatting highlights include:

- Bold separators between articles and frozen headers for quick scanning.
- Conditional fill colours on `Article_Status` (two shades of green for passes, orange variants for ambiguous cases, red for contradictions, grey for technical failures) plus thick separators between articles on both overview and detail sheets.
- Auto-fitted column widths, enabled filters, and wrapped text to prevent truncated content, with the Summary sheet titles/legend styled for rapid scanning.

Each summary row tracks additional review signals produced during parsing:

- `AI run agreement (Q15)` – summarizes how strongly the independent runs converged on a 4PT type.
- `Human vs AI (Q15)` – highlights whether the human-coded type matches the AI majority decision.
- `Human vs AI (consensus)` – compares the human-coded type with the Q17-Q28 consensus output.
- `Type summary (Q15, Decision Tree, Consensus)` – compact view of all type signals (direct answer, deprecated decision tree, Q17-Q28 consensus).
