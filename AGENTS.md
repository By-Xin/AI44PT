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
