# Repository Guidelines

## Project Structure & Module Organization
`code/` contains production modules: `pipeline_main.py` runs the CLI stages, `batch_analyzer.py` coordinates article processing, `response_parser.py` normalizes the 28-question template, and `voting.py` aggregates per-run judgments. `code/config.py` centralizes paths, models, and defaults. Place training data and manuals in `data/processed/`, keep exploratory work in `notebooks/`, and treat `results/` as write-only output (aggregated Excel files, per-run JSON).

## Build, Test, and Development Commands
Activate the project environment with `conda activate NLP`, then install dependencies via `pip install -r requirements.txt`. Run a full batch with `python code/pipeline_main.py --stage full`. For resumable workflows, pair `python code/pipeline_main.py --stage raw --raw-path <json>` with a later `--stage parse` using the same path. Use `--debug` during development to limit processing to two papers and shorten API calls. Regenerate Excel outputs by re-running the parse stage rather than editing spreadsheets manually.

## Coding Style & Naming Conventions
Follow PEP 8 (4-space indentation, 100-character soft wrap) and prefer expressive snake_case identifiers; reserve UpperCamelCase for classes such as `BatchAnalyzer` and `MajorityVoter`. Keep configuration constants and default parameters in `config.py` or a dedicated dataclass to avoid scattering literals. Expand public methods with docstrings and type hints that mirror existing module patterns, and maintain clear separation between I/O helpers and AI orchestration logic.

## Testing Guidelines
The repository lacks a formal test suite, so treat staged pipeline runs as smoke tests. For new logic, add targeted `pytest` cases under `tests/` that load sample PDFs from `data/processed/JRGsamples` and exercise response parsing or voting. Before opening a PR, run the debug raw stage, inspect the generated per-run JSON in `results/raw_responses/`, and ensure `--stage parse` rebuilds majority-vote rows without validation errors.

## Commit & Pull Request Guidelines
Adopt concise imperative messages similar to `Fix human-vs-consensus comparison`. Prefer a `type: short-action` prefix when feasible (e.g., `feat: add consensus diagnostics`). Each PR should include: a high-level summary, the commands/tests executed, notes on data dependencies or migrations, and screenshots only if output formats change. Reference related issues, request reviewers familiar with the touched modules, and highlight any backward-incompatible config adjustments.

## Configuration & Secrets
Store credentials like `OPENAI_API_KEY` in `.env` and keep that file out of version control. Adjust models, directory paths, and AI run counts in `code/config.py` or via CLI flags so jobs remain reproducible. Run `Config.validate()` (invoked automatically at pipeline start) after modifying configuration to catch missing folders or keys before launching long analyses.

## Agent Notes (2024-10-20)
- Enriched Excel reporting: `Article_Summary` now includes human/AI Q15 labels, vote counts, run success metrics, and per-type extent/Likert averages; majority rows in `All_Results` carry the same stats.
- Added per-status detail sheets（错题本） that list the human row, majority vote, and every run for each article, including `Detail Note` and `Mismatch Pair (Human→AI)` columns.
- Introduced a `Summary` sheet with headline metrics (coverage, accuracy, ambiguous rate), status/consensus breakdowns, glossary entries, and a colour legend.
- Added analytics sheets: `Confusion_Matrix`, `Agreement_Distribution`, optional `Ambiguity_Patterns`, and `Majority_Margin` for single-run diagnostics.
- Refined `Article_Status` taxonomy (`Pass_Strong`, `Pass_Weak`, `Contradiction`, `Ambiguous_Tie`, `Ambiguous_PoorCoverage`, `Technical_Failure`) with updated colour mapping and per-status sheets.
- Updated `README.md` 和 `code/README.md` 以说明新增摘要字段和报表内容。
- Smoke test：`conda activate NLP && python code/pipeline_main.py --stage parse --raw-path results/raw_responses/filtered_251013 --debug` ✅（解析通过，Excel 导出成功）。
