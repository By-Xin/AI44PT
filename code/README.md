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
# Run batch analysis pipeline
python code/pipeline_main.py
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

## Output

Results are saved to `../results/`:
- `analysis_results_YYYYMMDD_HHMMSS.xlsx` - Full analysis results with human + AI + majority vote rows
- `raw_responses/*.json` - Raw API responses for full auditing
