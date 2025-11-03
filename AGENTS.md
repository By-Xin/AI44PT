# Repository Guidelines

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

### Core Pipeline Flow
```
pipeline_main.py (CLI entry)
    └── BatchAnalyzer (orchestrates entire workflow)
        ├── Config (centralized configuration)
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
- **`config.py`**: Complete configuration including 28-question template, AI parameters, paths
- **`batch_analyzer.py`**: Main orchestrator coordinating document reading, AI calls, and parsing
- **`response_parser.py`**: Extracts structured answers from AI responses using XML-style tags
- **`voting.py`**: Implements majority voting and consensus analysis across multiple AI runs
- **`reporting.py`**: Generates rich Excel workbooks with multiple analysis sheets
- **`document_reader.py`**: Handles PDF and markdown document reading

### Configuration System
All settings centralized in `code/config.py`:
- `DEBUG_MODE = True` limits to 2 articles with lower AI effort
- `DEFAULT_AI_RUNS = 3` sets independent runs per article  
- `ENABLE_MAJORITY_VOTE = True` enables consensus analysis
- Model settings: `CLS_MODEL`, `TEMPERATURE`, `DEFAULT_REASONING_EFFORT`
- Paths: `EXCEL_PATH`, `PDF_FOLDER`, `RAW_OUTPUT_DIR`

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

## Coding Style & Naming Conventions
Follow PEP 8 (4-space indentation, 100-character soft wrap) and prefer expressive snake_case identifiers; reserve UpperCamelCase for classes such as `BatchAnalyzer` and `MajorityVoter`. Keep configuration constants and default parameters in `config.py` or a dedicated dataclass to avoid scattering literals. Expand public methods with docstrings and type hints that mirror existing module patterns, and maintain clear separation between I/O helpers and AI orchestration logic.

## Commit & Pull Request Guidelines
Adopt concise imperative messages similar to `Fix human-vs-consensus comparison`. Prefer a `type: short-action` prefix when feasible (e.g., `feat: add consensus diagnostics`). Each PR should include: a high-level summary, the commands/tests executed, notes on data dependencies or migrations, and screenshots only if output formats change. Reference related issues, request reviewers familiar with the touched modules, and highlight any backward-incompatible config adjustments.

## Configuration & Secrets
Store credentials like `OPENAI_API_KEY` in `.env` and keep that file out of version control. Adjust models, directory paths, and AI run counts in `code/config.py` or via CLI flags so jobs remain reproducible. Run `Config.validate()` (invoked automatically at pipeline start) after modifying configuration to catch missing folders or keys before launching long analyses.

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

## Agent Notes (2024-10-20)
- Enriched Excel reporting: `Article_Summary` now includes human/AI Q15 labels, vote counts, run success metrics, and per-type extent/Likert averages; majority rows in `All_Results` carry the same stats.
- Added per-status detail sheets（错题本） that list the human row, majority vote, and every run for each article, including `Detail Note` and `Mismatch Pair (Human→AI)` columns.
- Introduced a `Summary` sheet with headline metrics (coverage, accuracy, ambiguous rate), status/consensus breakdowns, glossary entries, and a colour legend.
- Added analytics sheets: `Confusion_Matrix`, `Agreement_Distribution`, optional `Ambiguity_Patterns`, and `Majority_Margin` for single-run diagnostics.
- Refined `Article_Status` taxonomy (`Pass_Strong`, `Pass_Weak`, `Contradiction`, `Ambiguous_Tie`, `Ambiguous_PoorCoverage`, `Technical_Failure`) with updated colour mapping and per-status sheets.
- Updated `README.md` 和 `code/README.md` 以说明新增摘要字段和报表内容。
- Smoke test：`conda activate NLP && python code/pipeline_main.py --stage parse --raw-path results/raw_responses/filtered_251013 --debug` ✅（解析通过，Excel 导出成功）。
