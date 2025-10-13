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

# (Optional) Stage 1: generate raw JSONL only
python code/pipeline_main.py --stage raw --raw-path results/raw_responses/my_run.jsonl

# (Optional) Stage 2: parse a previously generated JSON/JSONL file
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/my_run.jsonl

# Stage 2 in batch mode: parse every JSONL in a directory (or omit --raw-path to use the default)
python code/pipeline_main.py --stage parse --raw-path results/raw_responses

# (The parser also supports directories that contain only per-run *.json files)

# Allow batch parse to skip any JSON/JSONL inputs that fail to load/parse
python code/pipeline_main.py --stage parse --raw-path results/raw_responses --skip-bad

# Override the Excel source if needed
python code/pipeline_main.py --stage full --excel-path /path/to/custom.xlsx

# Toggle debug mode (limits to 2 articles, lowers effort)
python code/pipeline_main.py --stage raw --debug
```

## Configuration

All configuration is now in a single file: `config.py`

**Key parameters to adjust:**
- `DEBUG_MODE = True` - Limits to 2 articles for testing
- `DEFAULT_AI_RUNS = 3` - Number of independent AI runs per article
- `ENABLE_MAJORITY_VOTE = True` - Enable consensus analysis
- `EXCEL_PATH` - Path to input Excel file
- `PDF_FOLDER` - Path to PDF files directory
- `TEMPERATURE = 0.1` - AI randomness (0.0-1.0)
- `DEFAULT_REASONING_EFFORT` - "low", "medium", or "high"
- `DEFAULT_TEXT_VERBOSITY` - "low", "medium", or "high"
- `RAW_OUTPUT_DIR` - Base directory for raw `.json` and `.jsonl` records
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
   - Writes every request/response record to both individual `.json` files and an aggregated `.jsonl` stream

2. **Parsing (`--stage parse`)**
   - Loads the original Excel metadata
   - Replays answers from the saved `.jsonl`
   - Rebuilds AI rows, applies majority voting/consensus, and produces the final spreadsheet

The staged approach makes the process resumable: if generation is interrupted, simply re-run `--stage parse` with the saved JSONL to reconstruct outputs without re-querying the API.

## Output

Results are saved to `../results/`:
- `analysis_results_YYYYMMDD_HHMMSS.xlsx` - Full analysis results with human + AI + majority vote rows
- `raw_responses/*.json` - Per-run raw API responses for auditing
- `raw_responses/raw_responses_YYYYMMDD_HHMMSS.jsonl` - Stream of all raw interactions for resumable parsing

Each Excel row now includes additional review signals:
- `AI run agreement (Q15)` - summarizes how strongly the independent runs converged on a 4PT type.
- `Human vs AI (Q15)` - highlights whether the human-coded type matches the AI majority decision.
- `Human vs AI (consensus)` - compares the human-coded type with the Q17-Q28 consensus output.
- `Type summary (Q15, Decision Tree, Consensus)` - compact view of all type signals (direct answer, deprecated decision tree, Q17-Q28 consensus).
