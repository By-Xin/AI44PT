# Repository Guidelines

> **Last Updated**: November 23, 2025  
> **Current Version**: 3.0.0 (Modular Batch Analysis Architecture)  
> **Major Refactoring**: October 12, 2025 (Commit: cd98df1)

## Environment Setup

Activate the project environment and install dependencies:
```bash
conda activate NLP
pip install -r requirements.txt
```

Set up your environment with `.env` file containing `OPENAI_API_KEY`. Run `Config.validate()` to verify all paths and credentials.

## Core Commands

### Development Commands
```bash
# Full pipeline (generate + parse)
python code/pipeline_main.py --stage full

# Raw generation only 
python code/pipeline_main.py --stage raw --raw-path results/raw_responses

# Parse existing raw responses
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated/raw_responses_20240101_120000.json

# Debug mode (2 articles, low effort)
python code/pipeline_main.py --stage full --debug

# Skip malformed JSON during batch parsing
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated --skip-bad

# Parse all runs found in JSON (ignore configured ai_runs limit)
python code/pipeline_main.py --stage parse --raw-path results/raw_responses/aggregated --parse-all-runs
```

### Testing
No formal test suite exists. Use debug mode for smoke testing:
```bash
python code/pipeline_main.py --stage raw --debug
python code/pipeline_main.py --stage parse --raw-path [generated_path] --debug
```

## Architecture Overview

### Current Modular Structure (v3.0.0)

The system has been completely refactored from monolithic architecture to a clean modular design:

```
code/ (7 core modules, ~1763 lines)
├── config.py             (266行) - Unified configuration (merged from 2 files)
├── document_reader.py    (74行)  - PDF/markdown document reading
├── response_parser.py    (253行) - 28-question response parsing
├── voting.py             (436行) - Majority voting & consensus analysis
├── batch_analyzer.py     (606行) - Main workflow orchestrator
├── pipeline_main.py      (94行)  - CLI entry point
└── __init__.py           (37行)  - Package initialization
```

**Key Improvements from Refactoring**:
- ✅ Single Responsibility Principle - Each module has one clear purpose
- ✅ Loose Coupling - Minimal dependencies between modules
- ✅ High Testability - All components independently testable
- ✅ Unified Configuration - Single `config.py` (previously 2 files)
- ✅ Complete Audit Trail - All API responses saved as JSON
- ✅ Production Ready - Comprehensive error handling and logging

### Core Pipeline Flow
```
pipeline_main.py (CLI entry)
    └── BatchAnalyzer (orchestrates entire workflow)
        ├── Config (unified configuration)
        ├── DocumentReader (PDF/markdown reading)  
        ├── ResponseParser (28-question parsing)
        └── Voting (consensus analysis)
            ├── MajorityVoter
            ├── ConsensusAnalyzer  
            └── DecisionTreeClassifier
```

### Two-Stage Architecture
1. **Raw Generation** (`--stage raw`): Reads Excel metadata and PDFs, runs AI analysis, saves JSON responses
2. **Parsing** (`--stage parse`): Loads saved responses, applies majority voting, generates Excel reports

This staged approach enables resumable workflows - if generation fails, parsing can reconstruct outputs from saved JSON without re-querying APIs.

### Key Modules
- **`config.py`**: Unified configuration including 28-question template, AI parameters, paths (merged from previous `batch_config.py`)
- **`batch_analyzer.py`**: Main orchestrator coordinating document reading, AI calls, and parsing
- **`response_parser.py`**: Extracts structured answers from AI responses using XML-style tags
- **`voting.py`**: Implements majority voting and consensus analysis across multiple AI runs
- **`reporting.py`**: Generates rich Excel workbooks with multiple analysis sheets
- **`document_reader.py`**: Handles PDF and markdown document reading

### Configuration System

All settings unified in single file `code/config.py` (previously split across `config.py` and `batch_config.py`):

**Basic Parameters**:
- `DEBUG_MODE = False` - Set to `True` to limit to 2 articles with lower AI effort
- `DEFAULT_AI_RUNS = 3` - Number of independent runs per article  
- `ENABLE_MAJORITY_VOTE = True` - Enable consensus analysis across runs

**AI Model Settings**:
- `CLS_MODEL = "gpt-5-2025-08-07"` - OpenAI model for classification
- `TEMPERATURE = 1.0` - Sampling temperature
- `DEFAULT_REASONING_EFFORT = "high"` - Reasoning effort level

**Path Configuration**:
- `EXCEL_PATH` - Input Excel metadata file
- `PDF_FOLDER` - Directory containing PDF documents
- `RAW_OUTPUT_DIR` - Directory for saving raw JSON responses
- `RESULTS_DIR` - Directory for final Excel reports

**Configuration Structure**:
```python
from config import Config

# All configuration in one place:
class Config:
    # Project Paths
    PROJECT_ROOT, EXCEL_PATH, PDF_FOLDER, RESULTS_DIR, RAW_OUTPUT_DIR
    
    # OpenAI Settings  
    OPENAI_API_KEY, CLS_MODEL, TEMPERATURE, DEFAULT_REASONING_EFFORT
    
    # Batch Processing
    DEBUG_MODE, DEFAULT_AI_RUNS
    
    # Majority Voting
    ENABLE_MAJORITY_VOTE, OBJECTIVE_QUESTIONS, SUBJECTIVE_QUESTIONS
    
    # 28-Question Template
    FOURPT_QUESTIONS, STRUCTURED_RESPONSE_TEMPLATE
    
    # Utility Methods
    @classmethod get_ai_runs(), get_reasoning_effort(), validate(), display_config()
```

### Data Flow
- Input: Excel metadata (`data/processed/JRGsamples/JRG40.xlsx`) + PDFs (`data/processed/JRGsamples/`)
- Processing: 28-question AI analysis with configurable runs per article
- Output: 
  - Raw responses: `results/raw_responses/*.json` and aggregated bundles
  - Final reports: `results/analysis/analysis_results_YYYYMMDD_HHMMSS.xlsx`

### Excel Report Structure
The reporting system generates comprehensive workbooks with:
- **Summary**: Headline metrics, status breakdowns, glossary
- **All_Results**: Human rows, AI runs, majority votes  
- **Article_Summary**: One row per article with agreement scores
- **Confusion_Matrix**: Four-type accuracy analysis
- **Status sheets**: Pass_Strong, Pass_Weak, Contradiction, Ambiguous_Tie, etc.

### 4PT Framework
This is an academic analysis framework with 4 policy theory types. The system:
- Processes 28 structured questions per article (Q1-Q28)
- Questions 17-28 assess alignment with each of the 4 types
- Uses majority voting across multiple AI runs for reliability
- Compares AI judgments against human-coded ground truth

## Refactoring History

### Major Refactoring v3.0.0 (October 12, 2025)

**Commit**: `cd98df1670479f3e7d3aecb2a7e548335de69e31`

**Changes**: 73 files changed, 4557 insertions(+), 789 deletions(-)

**Key Achievements**:
- ✅ Refactored from monolithic pipeline to modular architecture
- ✅ Merged configuration files (`batch_config.py` + `config.py` → single `config.py`)
- ✅ Reduced code files from 10 to 7 (-30%)
- ✅ Reduced maximum file size from 1375 to 606 lines (-56%)
- ✅ Deleted 9 legacy/redundant files
- ✅ Archived 4 notebook files
- ✅ Created comprehensive documentation

**Architecture Improvements**:
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Code Files | 10 | 7 | -30% |
| Max File Lines | 1375 | 606 | -56% |
| Config Files | 2 | 1 | -50% |
| Modularity | Low | High | ✅ |
| Testability | Low | High | ✅ |
| Code Duplication | Yes | No | ✅ |

**Deleted Legacy Files**:
- `code/4pt_noRAG.py` - Old entry point
- `code/analyzer.py` - Old analyzer
- `code/main.py` - Old system class
- `code/result_saver.py` - Old saver
- `code/batch_config.py` - Merged into `config.py`
- `README_modular.md` - Replaced by better docs
- `notebooks/pipeline.py` - Replaced by `code/` modules

**Design Principles Followed**:
- SOLID principles (Single Responsibility, Open/Closed, etc.)
- DRY (Don't Repeat Yourself)
- KISS (Keep It Simple, Stupid)
- Occam's Razor (Simplest solution is often best)

### Configuration Migration

**Before** (2 files):
```python
from batch_config import BatchConfig
config = BatchConfig()
```

**After** (1 unified file):
```python
from config import Config
config = Config()  # All settings in one place
```

**Benefits**:
- Single source of truth for all configuration
- No inheritance complexity
- Easier to modify and maintain
- Clear section organization with comment separators

## Coding Style & Naming Conventions
Follow PEP 8 (4-space indentation, 100-character soft wrap) and prefer expressive snake_case identifiers; reserve UpperCamelCase for classes such as `BatchAnalyzer` and `MajorityVoter`. Keep configuration constants and default parameters in `config.py` to avoid scattering literals. Expand public methods with docstrings and type hints that mirror existing module patterns, and maintain clear separation between I/O helpers and AI orchestration logic.

## Commit & Pull Request Guidelines
Adopt concise imperative messages similar to `Fix human-vs-consensus comparison`. Prefer a `type: short-action` prefix when feasible (e.g., `feat: add consensus diagnostics`, `refactor: merge config files`). Each PR should include: a high-level summary, the commands/tests executed, notes on data dependencies or migrations, and screenshots only if output formats change. Reference related issues, request reviewers familiar with the touched modules, and highlight any backward-incompatible config adjustments.

## Configuration & Secrets
Store credentials like `OPENAI_API_KEY` in `.env` and keep that file out of version control. All configuration is now unified in `code/config.py` - adjust models, directory paths, and AI run counts there or via CLI flags so jobs remain reproducible. Run `Config.validate()` (invoked automatically at pipeline start) after modifying configuration to catch missing folders or keys before launching long analyses.

### Quick Configuration Examples

**Enable Debug Mode** (limit to 2 articles, low effort):
```python
# Edit code/config.py
DEBUG_MODE = True  # Change from False to True
```

**Adjust AI Runs**:
```python
# Edit code/config.py
DEFAULT_AI_RUNS = 5  # Change from 3 to 5 for more consensus
```

**Change Model**:
```python
# Edit code/config.py
CLS_MODEL = "gpt-4"  # Use different model
TEMPERATURE = 0.0  # More deterministic results
DEFAULT_REASONING_EFFORT = "medium"  # Lower cost
```

## Hugging Face Deployment (2025-11-03)

### 🚀 Interactive Web Platform Deployment
Successfully created and deployed an interactive 4PT analysis platform to Hugging Face Spaces:

**Live Demo**: https://huggingface.co/spaces/BYLEON/4PT

### Key Achievements
- ✅ **Core Q&A Architecture**: Simplified analyzer focused on single-paper analysis + follow-up questions
- ✅ **Web Interface**: Gradio-based interface with upload, analysis, and chat capabilities
- ✅ **Quality Preservation**: Full 28-question framework maintained without compromise
- ✅ **Interactive Features**: Real-time analysis + conversational Q&A about results
- ✅ **Deployment Success**: Resolved multiple technical challenges (dependencies, API integration)

### Technical Implementation
```
HF Space Structure:
├── app.py              # Main Gradio interface
├── core_analyzer.py    # Simplified 4PT analysis engine
├── requirements.txt    # Dependencies (Gradio 4.26.0, OpenAI, PyMuPDF)
└── README.md          # HF Space configuration + documentation
```

### Architecture Decisions
- **Single Paper Focus**: Upload PDF → Analyze → Interactive Q&A (vs. batch Excel processing)
- **Core Quality Maintained**: Complete 28-question framework, same AI model (`gpt-5-2025-08-07`)
- **Interactive Enhancement**: Users can ask follow-up questions about analysis results
- **Simplified Deployment**: Removed Excel dependencies, direct JSON storage for web compatibility

### Resolved Technical Challenges
1. **Gradio Version Issues**: Fixed compatibility with stable version 4.26.0
2. **PyMuPDF Import**: Resolved package naming inconsistencies across environments  
3. **API Key Detection**: Enhanced environment variable detection with debugging
4. **Model Consistency**: Maintained original `gpt-5-2025-08-07` model configuration

### User Experience Flow
```
1. Upload PDF → 2. Click "Analyze Paper" → 3. View Classification Results → 4. Ask Follow-up Questions
```

### Example Interactions
- "Why was this classified as Type 2?"
- "What evidence supports this classification?" 
- "How confident are you in this result?"
- "What would make this paper a different type?"

### Current Status
- **Deployment**: ✅ Live on HF Spaces
- **Core Analysis**: ✅ Full 28-question framework operational
- **Interactive Q&A**: ✅ Follow-up question system working
- **API Integration**: ⚠️ Requires OPENAI_API_KEY configuration in HF Space settings

### Next Steps for Enhancement
1. **User Testing**: Gather feedback from academic users
2. **Performance Optimization**: Improve analysis speed and reliability
3. **Feature Expansion**: Add comparison tools, batch upload, citation generation
4. **Community Building**: Promote adoption in policy research community

### Legacy Commands (Still Available)
Original batch processing pipeline remains fully functional:
```bash
# Local batch analysis (original system)
python code/pipeline_main.py --stage full

# Web interactive analysis (new HF deployment)  
Visit: https://huggingface.co/spaces/BYLEON/4PT
```

## Documentation Resources

The repository includes comprehensive documentation for different purposes:

- **[AGENTS.md](AGENTS.md)** (this file) - Complete repository guidelines for AI agents and developers
- **[REFACTORING_COMPLETE.md](REFACTORING_COMPLETE.md)** - Detailed refactoring report and statistics (Oct 12, 2025)
- **[CONFIG_MERGE_SUMMARY.md](CONFIG_MERGE_SUMMARY.md)** - Configuration merge details and migration guide
- **[code/README.md](code/README.md)** - Quick module reference and usage examples
- **[MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md)** - Architecture migration report
- **[CLEANUP_NOTES.md](CLEANUP_NOTES.md)** - Code cleanup documentation

## Agent Notes (2024-10-20)
- Enriched Excel reporting: `Article_Summary` now includes human/AI Q15 labels, vote counts, run success metrics, and per-type extent/Likert averages; majority rows in `All_Results` carry the same stats.
- Added per-status detail sheets（错题本） that list the human row, majority vote, and every run for each article, including `Detail Note` and `Mismatch Pair (Human→AI)` columns.
- Introduced a `Summary` sheet with headline metrics (coverage, accuracy, ambiguous rate), status/consensus breakdowns, glossary entries, and a colour legend.
- Added analytics sheets: `Confusion_Matrix`, `Agreement_Distribution`, optional `Ambiguity_Patterns`, and `Majority_Margin` for single-run diagnostics.
- Refined `Article_Status` taxonomy (`Pass_Strong`, `Pass_Weak`, `Contradiction`, `Ambiguous_Tie`, `Ambiguous_PoorCoverage`, `Technical_Failure`) with updated colour mapping and per-status sheets.
- Updated `README.md` 和 `code/README.md` 以说明新增摘要字段和报表内容。
- Smoke test：`conda activate NLP && python code/pipeline_main.py --stage parse --raw-path results/raw_responses/filtered_251013 --debug` ✅（解析通过，Excel 导出成功）。

---

**Document Version**: 2.0  
**Last Updated**: November 23, 2025  
**System Version**: 3.0.0 (Modular Architecture)  
**Status**: ✅ Production Ready
