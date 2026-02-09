# Code Implementation Issue List

Last updated: 2026-02-09  
Scope: `code/` only (excludes `hf_demo/`, excludes doc inconsistency items)

## Priority Legend

- `P0`: Blocking / correctness-critical (can break runs or produce wrong conclusions)
- `P1`: High-risk implementation issue (stability/data quality/recovery risk)
- `P2`: Incomplete or consistency issue (non-blocking but should be fixed)

---

## 1) Configuration & Entry Flow

### [CFG-001] `parse` is blocked by online key validation (`P0`)
- **Evidence**: `code/pipeline_main.py:102`, `code/config.py:403`, `code/config.py:408`
- **Problem**: `parse` runs `Config.validate()` unconditionally, and validation requires provider API keys.
- **Impact**: Offline replay of existing raw JSON cannot run unless provider keys are present.
- **Suggested fix**: Stage-aware validation: `parse` should only validate parse-time dependencies (input paths/schema), not API keys.

### [CFG-002] `parse` is blocked by prompt-guide files (`P1`)
- **Evidence**: `code/config.py:424`, `code/config.py:428`, `code/config.py:432`
- **Problem**: Validation requires three markdown guide files even for parse-only runs.
- **Impact**: Parse-only environments fail even when raw artifacts are complete.
- **Suggested fix**: Validate those files only for `raw`/`full`.

### [CFG-003] Analyzer constructor eagerly initializes LLM clients (`P1`)
- **Evidence**: `code/batch_analyzer.py:68`, `code/batch_analyzer.py:75`
- **Problem**: `BatchAnalyzer` instantiates provider clients at construction time regardless of stage.
- **Impact**: Parse-only path still depends on client libs and key setup.
- **Suggested fix**: Lazy-init clients only when entering raw generation (or when a call is needed).

---

## 2) Prompt/Input Construction

### [PRM-001] Loaded reference materials are not actually injected (`P1`)
- **Evidence**: `code/batch_analyzer.py:172`, `code/prompts.py:65`, `code/prompts.py:59`
- **Problem**: `build_user_prompt(...)` accepts `coding_task_text/executive_summary_text/main_body_text`, but template body ignores them.
- **Impact**: Prompt content diverges from expected design; updates to reference files do not flow into model input.
- **Suggested fix**: Explicitly interpolate those three texts into the user prompt body.

### [PRM-002] Double truncation overrides config limit (`P1`)
- **Evidence**: `code/batch_analyzer.py:165`, `code/batch_analyzer.py:182`
- **Problem**: Text is truncated by `ARTICLE_TEXT_MAX_CHARS`, then hard-truncated again to `50000`.
- **Impact**: Configured upper bound is ineffective; large-context runs lose input unexpectedly.
- **Suggested fix**: Keep a single truncation source of truth.

---

## 3) Raw Generation & Concurrency

### [RAW-001] Race condition in callback registration/mapping (`P0`)
- **Evidence**: `code/batch_analyzer.py:827`, `code/batch_analyzer.py:829`
- **Problem**: `future.add_done_callback(...)` is called before `future_to_article[...]` mapping is written.
- **Impact**: Fast-finishing tasks can fire callback before mapping exists; article semaphore may not release correctly.
- **Suggested fix**: Assign `future_to_article` and related maps before callback registration.

### [RAW-002] PDF read exception can abort whole batch (`P1`)
- **Evidence**: `code/document_reader.py:24`, `code/batch_analyzer.py:763`
- **Problem**: `read_pdf` can raise, and call site does not wrap it in per-article exception handling.
- **Impact**: A single corrupt/problematic PDF may terminate the entire raw job.
- **Suggested fix**: Catch per-article PDF exceptions and convert to `PDF_READ_ERROR` records.

### [RAW-003] Per-call raw records are written to global root (`P1`)
- **Evidence**: `code/batch_analyzer.py:423`
- **Problem**: Single-call raw files are written into `RAW_OUTPUT_DIR` root, not current run directory.
- **Impact**: Historical artifacts accumulate and contaminate default parse discovery.
- **Suggested fix**: Write per-call artifacts under current batch run directory.

---

## 4) Parse Replay & Batch Control

### [PAR-001] CLI rejects `.jsonl` parse input (`P1`)
- **Evidence**: `code/pipeline_main.py:152`, `code/batch_analyzer.py:493`
- **Problem**: CLI accepts only `.json`, while loader supports `.jsonl`.
- **Impact**: Recovery workflows are constrained when only stream JSONL is available.
- **Suggested fix**: Accept `.jsonl` in CLI input routing.

### [PAR-002] Default directory parse can merge unrelated history (`P0`)
- **Evidence**: `code/pipeline_main.py:138`, `code/pipeline_main.py:140`
- **Problem**: Fallback behavior loads all `*.json` in directory and “merge during parse”.
- **Impact**: Cross-run data contamination, wrong run counts, misleading agreement metrics.
- **Suggested fix**: Parse explicit run directories or explicit aggregated file only by default.

### [PAR-003] Loader prefers `*.json` and ignores `*.jsonl` if both exist (`P1`)
- **Evidence**: `code/batch_analyzer.py:479`, `code/batch_analyzer.py:482`
- **Problem**: Directory load path uses `if json_files ... elif jsonl_files ...`.
- **Impact**: Potentially newer/complete JSONL stream is ignored.
- **Suggested fix**: Merge both sets deterministically or choose latest by timestamp rule.

### [PAR-004] Multi-target parse may return success even with empty batches (`P1`)
- **Evidence**: `code/pipeline_main.py:261`, `code/pipeline_main.py:284`
- **Problem**: In multi-file parse mode, empty parse result becomes warning (unless `--skip-bad`), but command still exits `0`.
- **Impact**: CI/automation can treat partial/empty outputs as success.
- **Suggested fix**: Track hard failures/empty batches and return non-zero unless explicitly skipped.

### [PAR-005] RAW-not-found placeholders ignore multi-provider cardinality (`P2`)
- **Evidence**: `code/batch_analyzer.py:1006`, `code/batch_analyzer.py:1239`
- **Problem**: Missing-raw placeholders are generated by `ai_runs` only, not provider × run.
- **Impact**: Parse output shape is inconsistent with configured multi-provider generation.
- **Suggested fix**: Generate placeholders by expected provider-run combinations.

---

## 5) Voting & Consensus Semantics

### [VOT-001] `AI run agreement` is overwritten with different semantics (`P0`)
- **Evidence**: `code/batch_analyzer.py:1108`, `code/batch_analyzer.py:1665`
- **Problem**: Field first stores run-consensus labels (`Unanimous/Strong/...`), then is overwritten by intra-row signal agreement (`Agree/Disagree`).
- **Impact**: Downstream status logic reads wrong semantics.
- **Suggested fix**: Split into two explicit columns (e.g., `Run_Consensus_Label` and `Signal_Consistency_Label`).

### [VOT-002] `Human vs Consensus` path is effectively unimplemented (`P0`)
- **Evidence**: `code/batch_analyzer.py:115`, `code/batch_analyzer.py:1000`, `code/voting.py:264`
- **Problem**: `ConsensusAnalyzer` exists but is never applied to populate `Human vs Consensus`.
- **Impact**: Consensus comparison remains blank/invalid; related status logic loses signal.
- **Suggested fix**: Compute consensus per article row and fill comparison columns before reporting.

---

## 6) Reporting & Metrics

### [REP-001] Vote-count format mismatch breaks margin/pattern analytics (`P0`)
- **Evidence**: `code/batch_analyzer.py:1446`, `code/reporting.py:947`, `code/reporting.py:751`
- **Problem**: Upstream writes `2*Type 1`, parser expects mainly `Type 1:2` style.
- **Impact**: `Majority_Margin` and ambiguity pattern summaries can be incorrect.
- **Suggested fix**: Standardize one canonical format and support backward-compatible parse.

### [REP-002] Status classification consumes overwritten agreement field (`P1`)
- **Evidence**: `code/reporting.py:1168`, `code/batch_analyzer.py:1665`
- **Problem**: Status rule expects “unanimous/strong/simple majority” semantics, but upstream may have overwritten the column.
- **Impact**: Misclassification into `Ambiguous_*` / wrong status breakdown.
- **Suggested fix**: Status engine should read a dedicated immutable run-consensus column.

### [REP-003] `extent_avgs` is declared but never computed (`P2`)
- **Evidence**: `code/reporting.py:1076`, `code/reporting.py:1088`, `code/reporting.py:1103`
- **Problem**: `_collect_type_metrics()` returns `extent_avgs`, but only confidence averages are populated.
- **Impact**: Incomplete metric layer and potential confusion for consumers.
- **Suggested fix**: Either implement extent aggregation or remove dead metric contract.

---

## Suggested Fix Order

1. **P0 batch 1**: `CFG-001`, `RAW-001`, `PAR-002`, `VOT-001`, `VOT-002`, `REP-001`  
2. **P1 batch 2**: `CFG-002`, `CFG-003`, `PRM-001`, `PRM-002`, `RAW-002`, `RAW-003`, `PAR-001`, `PAR-003`, `PAR-004`, `REP-002`  
3. **P2 batch 3**: `PAR-005`, `REP-003`

