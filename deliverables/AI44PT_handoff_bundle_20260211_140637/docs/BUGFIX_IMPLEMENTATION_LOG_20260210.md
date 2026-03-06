# Bugfix Implementation Log (2026-02-10)

Branch: `bugfix/p0-implementation-fixes`

## Scope

Independent re-audit across the repository with implementation-first fixes, then staged commits.

## Commit Batches

### Batch A (core pipeline)

- Commit: `f689de6`
- Message: `fix: harden parse verification and confusion matrix stability`
- Files:
  - `code/pipeline_main.py`
  - `code/batch_analyzer.py`
  - `code/reporting.py`

Implemented fixes:
- Corrected final verification row-count expectation logic to avoid false-positive warnings when majority rows are legitimately absent (e.g., insufficient successful runs).
- Fixed raw directory loader control flow to avoid erroneous "Unsupported raw data format" errors after valid directory ingestion.
- Corrected raw-generation progress stats key (`pdf_read_error`) so progress logs match real counters.
- Hardened confusion-matrix generation against mixed label types (`int`/`str`) and normalized labels before matrix construction.
- Removed pandas `FutureWarning` trigger in row/column normalization by replacing `pd.NA` with numeric NaN for division denominators.

### Batch B (HF demo)

- Commit: `d8ba514`
- Message: `fix: repair hf demo single-paper pipeline wiring`
- Files:
  - `hf_demo/app.py`
  - `hf_demo/code/reporting.py`

Implemented fixes:
- Fixed runtime crash in demo upload flow (`read_pdf` result is list, not string; removed invalid `.strip()` call).
- Ensured uploaded PDF is actually the analyzed file by routing `Config.PDF_FOLDER` to a temporary folder containing the uploaded file as `1.pdf` during run.
- Added robust cleanup/restoration in `finally` (temporary files and runtime config rollback).
- Switched demo result extraction to regex-based `Q` column discovery (`[Q15]`, `[Q16]`) instead of stale hardcoded column names.
- Applied same confusion-matrix mixed-type and normalization hardening in `hf_demo/code/reporting.py`.

## Validation Evidence

### Static compilation

Command:
- `rg --files -g '*.py' code hf_demo -0 | xargs -0 python3 -m py_compile`

Result:
- Pass.

### Regression smoke test (core parse)

Command:
- `uv run python code/pipeline_main.py --stage parse --raw-path results/archive/raw_batch_20251027_120243/raw_responses_20251027_120243.json --debug`

Result:
- Exit code `0`.
- Previous false warnings (`Expected 3 AI rows, found 2`) no longer present.
- Previous pandas normalization `FutureWarning` no longer present.

### Targeted reproduction for confusion-matrix crash

Command:
- `uv run python - <<'PY' ... from reporting import _build_confusion_matrix_tables ... PY`

Result:
- Previously raised `TypeError: '<' not supported between instances of 'str' and 'int'`.
- Now executes successfully and returns table outputs.

## Notes

- `uv` is available and usable in this environment (`uv 0.8.4`).
- HF demo end-to-end API analysis was not executed in this session due external-key/runtime dependency constraints, but compile-level and logic-path fixes were applied.
