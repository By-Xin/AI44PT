# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **4PT Framework Analysis System** for academic research. It uses AI (GPT models) to classify sustainability policy and governance articles according to Cashore's Four Problem Types framework based on two key dimensions:

1. **Utility orientation**: Does the analysis treat entities as self-interested, utility-maximizing agents?
2. **Problem contingency**: Is the analysis focused on solving a specific "on the ground" problem, or does it apply universal theories?

The system processes academic papers (PDFs) using a detailed codebook and generates classifications with supporting evidence.

## Development Commands

### Environment Setup
```bash
# Activate the conda environment
conda activate NLP

# Install dependencies
pip install -r requirements.txt
```

### Running the System

**Batch analysis pipeline** now supports a resumable two-stage workflow.

```bash
# Full run: generate raw JSON bundle + parse into Excel
python code/pipeline_main.py --stage full

# Stage 1 only: produce raw `.json` bundle (plus per-run `.json`) without parsing
python code/pipeline_main.py --stage raw --raw-path results/raw_responses/aggregated/raw_responses_my_run.json

# Stage 2 only: parse a previously generated raw file or directory
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated/raw_responses_my_run.json
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated

# Optionally skip broken raw batches during parsing
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated --skip-bad

# Parse using every run found in the raw JSON bundle
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated --parse-all-runs

# Optional: override the Excel source file
python code/pipeline_main.py --stage full --excel-path /path/to/custom.xlsx

# Enable debug mode (limits to 2 articles, reduced effort)
python code/pipeline_main.py --stage raw --debug
```

If processing is interrupted, you can resume by rerunning the `parse` stage against the saved aggregated JSON file (or the directory of per-run JSONs)—no need to regenerate model outputs.

### Configuration

**All configuration** is in [code/config.py](code/config.py):
- Set `OPENAI_API_KEY` in `.env` file
- `CLS_MODEL`: AI model to use (default: `gpt-5-2025-08-07`)
- `DEBUG_MODE = True`: Limits to 2 articles with reduced AI effort for testing
- `DEFAULT_AI_RUNS`: Number of independent AI runs per article (default: 3; parse stage uses this unless `--parse-all-runs` is supplied)
- `TEMPERATURE`: Randomness in AI responses (0.1 for slight randomness)
- `DEFAULT_REASONING_EFFORT`, `DEFAULT_TEXT_VERBOSITY`: AI behavior parameters
- `ENABLE_MAJORITY_VOTE`: Enable consensus analysis across multiple runs (default: True)
- `EXCEL_PATH`, `PDF_FOLDER`: Input data paths
- `CODEBOOK_MD`, `RESULTS_DIR`, `RAW_OUTPUT_DIR`: File paths for codebook and outputs

## Architecture

### Core Modules (`code/`)

The system is organized into specialized modules following single-responsibility principles:

1. **[config.py](code/config.py)**: Unified configuration management
   - All project paths, API keys, model settings in one place
   - Batch processing parameters (AI runs, voting, debug mode)
   - 28-question templates and structured response templates
   - Configuration validation and display methods
   - Class methods: `validate()`, `setup_directories()`, `display_config()`

2. **[document_reader.py](code/document_reader.py)**: Document ingestion
   - `DocumentReader.read_pdf()`: Extracts text from PDF pages using PyMuPDF
   - `DocumentReader.read_markdown()`: Parses codebook markdown by sections
   - Used by `BatchAnalyzer` for loading papers and codebook

3. **[response_parser.py](code/response_parser.py)**: AI response parsing
   - `ResponseParser`: Extracts and validates 28 answers from AI responses
   - Handles XML-style structured response templates
   - Normalizes Yes/No, Type classifications, Likert scales, difficulty levels
   - Static methods for extracting numeric values from text

4. **[voting.py](code/voting.py)**: Consensus and voting logic
   - `MajorityVoter`: Performs majority voting across multiple AI runs
   - `ConsensusAnalyzer`: Derives type consensus from Q17-Q28 responses
   - `DecisionTreeClassifier`: Calculates 4PT type from Q3 + Q9 (simple decision tree)
   - Handles tie detection and numeric statistics (averages)

5. **[batch_analyzer.py](code/batch_analyzer.py)**: Batch processing orchestration
   - `BatchAnalyzer`: Main coordinator for batch analysis workflow
   - Manages article processing, PDF reading, multi-run analysis
   - Creates human/AI/majority-vote result rows
   - Persists per-run JSON and aggregated JSON bundles for resumable parsing
   - Adds derived columns (Decision Tree, Type Consensus)
   - Handles OpenAI API compatibility (new vs. legacy API)

6. **[pipeline_main.py](code/pipeline_main.py)**: Pipeline entry point
   - Command-line interface with `--stage` (`raw|parse|full`), `--raw-path`, `--excel-path`
   - Optional `--skip-bad` flag lets batch parses continue when individual raw files are malformed
   - Configuration validation and display
   - Error handling and progress reporting between stages

7. **[__init__.py](code/__init__.py)**: Package initialization
   - Exports all main classes for easy importing
   - Version information

**Key capabilities:**
- Reads article metadata from Excel with human annotations
- Processes PDFs in batch with detailed progress tracking
- Runs multiple independent AI analyses per article (configurable)
- **Majority voting**: Aggregates objective questions across AI runs
- **Decision Tree 4PT**: Auto-calculates from Q3 (problem contingency) + Q9 (utility)
- **Type consensus**: Derives best-fit type from Q17-Q28 (per-type confidence scores)
- Saves raw API responses as per-run JSON + aggregated JSON bundles for full auditing and replay
- Outputs comprehensive Excel with human + AI results + consensus side-by-side

**Analysis questions** (28 total):
- Q1-Q14: Core 4PT analysis questions
- Q15: Final Type classification (Type 1/2/3/4)
- Q16: Difficulty level (1-5 scale)
- Q17-Q28: Per-type validation (Yes/No + 0-1 extent + 1-5 Likert for each of 4 types)

**Output structure:**
- Each article produces multiple rows: 1 human + N AI runs + 1 majority vote row
- `source` column distinguishes rows (e.g., "human", "gpt-5-...-run1", "...-majority-vote")
- `Analysis_Status` tracks success/failure with timestamps
- Decision Tree 4PT and Type Consensus columns appear next to Q15 for easy comparison
- Additional review columns:
  - `AI run agreement (Q15)` shows how strongly independent runs converged on a single type.
  - `Human vs AI (Q15)` highlights alignment (or conflict) between the majority vote and the human-coded answer.
  - `Human vs AI (consensus)` compares the human-coded type to the Q17-Q28 consensus result.
  - `Type summary (Q15, Decision Tree, Consensus)` collates the three main type signals for quick inspection.

**Running the pipeline:**
```bash
# Standard run (processes all articles in Excel)
python code/pipeline_main.py

# For debugging (set DEBUG_MODE = True in code/config.py)
# This limits to 2 articles with reduced AI effort
```

## Key Design Patterns

### Modular Components
- Each module has a single responsibility
- Loose coupling between modules
- Components can be used independently

### API Compatibility
The analyzer tries the new OpenAI API format first, falls back to legacy format:
```python
try:
    # New API (supports reasoning effort)
    response = client.responses.create(...)
except AttributeError:
    # Legacy API
    response = client.chat.completions.create(...)
```

### Error Handling
- Configuration validation before execution
- Graceful fallback for missing files
- Detailed error messages preserved in output

### Structured Output Parsing
AI responses use XML-style templates:
```xml
<BEGIN_4PT_RESPONSE>
<Q1>[Answer]</Q1>
...
</END_4PT_RESPONSE>
```

This ensures reliable extraction of 28 answers per article.

## Data Flow

1. **Input**:
   - Excel file with article metadata (from `data/processed/JRGsamples/`)
   - PDF papers in batch
   - Codebook markdown (`TheCodingTask.md`)

2. **Processing**:
   - **Raw generation stage** (`--stage raw` / `--stage full` first phase)
     - `BatchAnalyzer` reads Excel metadata and locates PDFs
     - `DocumentReader` parses PDFs and codebook into page/section structures
     - Prompts built with codebook + article + 28 questions
     - Multiple API calls per article (configurable runs)
     - Every request/response saved as both per-run JSON and captured in an aggregated JSON bundle
   - **Parsing stage** (`--stage parse` / `--stage full` second phase)
     - Loads raw JSON records (single aggregated file or directory of per-run JSONs) and rebuilds AI answer rows without re-calling the API; use `--parse-all-runs` to include every run discovered in the raw data
     - `ResponseParser` extracts structured 28-answer responses
     - `MajorityVoter` aggregates across runs
     - `DecisionTreeClassifier` and `ConsensusAnalyzer` derive additional classifications

3. **Output**:
   - Comprehensive Excel file in `results/` with:
     - Human annotations (original row)
     - Multiple AI run results (N rows per article)
     - Majority vote consensus (1 row per article)
     - Decision Tree and Type Consensus columns
     - New agreement diagnostics (`AI run agreement`, `Human vs AI`, `Human vs AI (consensus)`, `Type summary`)
   - Raw API responses saved in `results/raw_responses/` as individual JSON files and aggregated JSON bundles

## Important Files

- **`data/processed/TheCodingTask.md`**: The definitive 4PT coding manual (essential for understanding classifications)
- **`data/processed/JRGsamples/`**: Sample PDFs and Excel file for batch processing
- **`results/`**: All analysis outputs (Excel, per-run JSON, aggregated JSON)
- **`.env`**: Must contain `OPENAI_API_KEY`

## Notes on the 4PT Framework

The Four Problem Types based on two binary dimensions:

|                          | **Utility Focus** | **Not Utility Focus** |
|--------------------------|-------------------|-----------------------|
| **Problem Contingent**   | Type 1            | Type 4                |
| **Not Problem Contingent**| Type 2           | Type 3                |

- **Type 1**: Utility-seeking, problem-specific (e.g., tragedy of the commons)
- **Type 2**: Utility-seeking, universal theories (e.g., cost-benefit analysis, IR realism)
- **Type 3**: Non-utility, universal theories (e.g., alternative dispute resolution, ethics frameworks)
- **Type 4**: Non-utility, problem-specific (e.g., species conservation, anti-slavery)

The codebook provides extensive examples and guidance for classification edge cases.

## Development Principles

Per the README, this codebase follows **Occam's Razor**: maximize simplicity and minimize unnecessary complexity. Maintain:
- Clear module boundaries
- Minimal dependencies between components
- Self-documenting code with docstrings
- Backward compatibility where possible
