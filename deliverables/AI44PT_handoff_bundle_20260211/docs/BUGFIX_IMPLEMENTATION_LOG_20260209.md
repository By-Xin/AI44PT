# Bugfix Implementation Log (2026-02-09)

Branch: `bugfix/p0-implementation-fixes`

## Scope

- Canonical tracker: `CODE_IMPLEMENTATION_ISSUES.md`
- Target area: `code/` pipeline and reporting implementation
- Objective: close P0/P1/P2 implementation issues with reproducible, stage-safe behavior

## Commit Batches

### Batch 1 (code fixes)

- Commit: `c91531b`
- Message: `fix: harden parse/raw pipeline and consensus reporting semantics`
- Key files:
  - `code/config.py`
  - `code/pipeline_main.py`
  - `code/batch_analyzer.py`
  - `code/reporting.py`

## Implemented Changes by Area

### 1) Stage-aware validation and parse entry safety

- `Config.validate(stage=...)` now validates dependencies by stage:
  - `raw/full`: provider keys + prompt guides + PDF folder + Excel
  - `parse`: Excel only (no provider key or prompt guide requirement)
- `pipeline_main.py` now calls `config.validate(stage=stage)`.
- Multi-target parse now returns non-zero for hard/empty failures unless `--skip-bad` is enabled.

### 2) Parse target discovery and replay control

- Parse CLI now accepts `.jsonl` input files.
- Directory parse target collection now prefers aggregated artifacts only.
- Unsafe fallback that merged arbitrary loose `*.json` files by default was removed.
- Nested run directories are scanned for aggregated artifacts.
- Raw loader now reads both `.json` and `.jsonl` when a directory is provided, then deduplicates records deterministically.

### 3) Raw generation robustness

- LLM clients are now lazy-initialized (only when raw generation/calls are needed).
- Per-call raw records are written into the active run directory instead of global root.
- PDF read exceptions are caught per article and converted into error records; one corrupt PDF no longer crashes whole raw batch.

### 4) Voting/consensus semantics and reporting consistency

- `AI run agreement` semantics are preserved as run-level consensus.
- Added dedicated `Signal consistency` column for intra-row signal agreement.
- Implemented article-level consensus aggregation via `ConsensusAnalyzer` and populated `Human vs Consensus`.
- Vote count text standardized to `Type N:count`.
- Reporting parser now supports both canonical format and legacy `count*Type N` format.

### 5) Multi-provider run cardinality and metrics

- Parse replay now builds expected run entries by provider × run (not run only).
- RAW-missing placeholders now honor provider-run combinations.
- Implemented `extent_avgs` in reporting as per-type support averages (`Yes=1.0`, `No=0.0`).

## Issue Tracker Outcome

- Updated `CODE_IMPLEMENTATION_ISSUES.md` with resolution status table.
- Statuses include:
  - `✅ Resolved` for implemented fixes
  - `✅ Verified already fixed` for items that were already correct in current branch baseline (`RAW-001`, `PRM-001`)

## Validation Evidence

### Static checks completed

- Command:
  - `python3 -m py_compile code/__init__.py code/batch_analyzer.py code/config.py code/document_reader.py code/logging_utils.py code/pipeline_main.py code/prompts.py code/reporting.py code/response_parser.py code/voting.py code/llm_clients/base_client.py code/llm_clients/openai_client.py code/llm_clients/gemini_client.py`
- Result: pass

### Runtime smoke test constraints

- Runtime pipeline smoke tests could not be executed in this shell due missing runtime dependencies in current environment (`pandas`, `python-dotenv`, etc.).
- Observed errors while attempting runtime execution:
  - `ModuleNotFoundError: No module named 'dotenv'`
  - `ModuleNotFoundError: No module named 'pandas'`

## Recommended Follow-up Verification (when env is ready)

1. `conda activate NLP && pip install -r requirements.txt`
2. Parse-only offline replay:
   - `OPENAI_API_KEY= GEMINI_API_KEY= python code/pipeline_main.py --stage parse --raw-path <aggregated_raw.json|jsonl> --debug`
3. Raw generation sanity:
   - `python code/pipeline_main.py --stage raw --debug`
4. Multi-target parse exit code behavior:
   - `python code/pipeline_main.py --stage parse --raw-path results/raw_responses --skip-bad`

