# Cross-Review: software-engineer — FSPEC

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 2

---

## v1 Finding Resolution

All five v1 findings are resolved in v0.2.0:
- F-01 ✅ (High) Interactive prompts suppressed in batch mode; BR-07 added; "✓ {ticker} complete" condensed line specified
- F-02 ✅ (High) Rich Live context entered/exited per ticker; BR-08 added; flow updated
- F-03 ✅ (Medium) `graph.process_signal(decision)` added as Step 3a in behavioral flow
- F-04 ✅ (Low) `batch_results = [] ← list of BatchTickerRecord(ticker, final_state, decision)` defined in flow header
- F-05 ✅ (Low) AT3 wording changed to "may be partially populated"

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | High | Local | FSPEC-BATCH-03 iterates `batch_results` but `batch_results` only contains successful tickers — failed tickers are never appended to it (FSPEC-BATCH-02 only appends to `failed_tickers` on failure). The `IF ticker in failed_tickers` branch inside the loop can therefore never be reached, and failed tickers will produce **no row in the table**. The loop must iterate over `ordered_tickers` (the original input list), then for each ticker check: if it is in `failed_tickers` → Failed row; else look up its `BatchTickerRecord` in `batch_results` → Success row. Fix: change `FOR EACH ticker result in batch_results` to `FOR EACH ticker in ordered_tickers` with a lookup by ticker name into `batch_results`. | FSPEC-BATCH-03, Behavioral Flow |
| F-02 | Low | Local | FSPEC-BATCH-02: the OSError handler says "Exit Rich Live context (if not already exited)", but the Live context was already exited on the success path immediately after `propagate()` returned. At the point OSError is raised (inside the inner TRY for save), the Live context is no longer active. The "if not already exited" qualifier is therefore never applicable here and could mislead the implementer into writing dead-code guards. Remove the Live context exit from the OSError handler; it is not needed. | FSPEC-BATCH-02, Step 4 |
| F-03 | Low | Local | `graph.process_signal(decision)` in Step 3a has no specified failure handling. If `process_signal()` raises an `Exception` (e.g., file I/O error writing the memory log), the outer `EXCEPT Exception as e` will catch it and mark the ticker as FAILED — even though the analysis succeeded and the save may have completed. The FSPEC should specify whether `process_signal()` failures are fatal (fail the ticker) or non-fatal (log a warning, continue). | FSPEC-BATCH-02, Step 3a |
| F-04 | Low | Local | `BatchTickerRecord` in FSPEC-BATCH-02 uses `final_state` as a field name, but the existing dataclass defined in REQ-API-01 is `BatchTickerResult` with a `state` field (not `final_state`). The FSPEC introduces a new name `BatchTickerRecord` that is not defined in the REQ. The TSPEC will need to reconcile these; the FSPEC should clarify whether `BatchTickerRecord` is the same as `BatchTickerResult` (used by `propagate_many`) or a distinct internal type. | FSPEC-BATCH-02; REQ-API-01 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For F-03: should `process_signal()` failures silently log a warning (preserving ticker as Success) or propagate to the ticker failure handler? The memory log is a best-effort feature — silent failure seems appropriate but must be specified. |

---

## Positive Observations

- All three v1 High/Medium findings are cleanly resolved. The behavioral flow is now substantially more implementable than v0.1.0.
- BR-07 and BR-08 are crisp, testable rules that prevent two significant implementation ambiguities (prompt suppression and Live context lifetime).
- FSPEC-BATCH-03 extractability note (standalone `build_batch_summary` function) is correctly positioned to improve testability without prescribing implementation.
- The OQ-F-01 resolution (exit code 2 for blank `--tickers`) is precise and adds AT6 as the corresponding test.

---

## Recommendation

**Needs revision**

> F-01 is High: the FSPEC-BATCH-03 loop iterates the wrong list and would produce a table with no rows for failed tickers. This is a correctness bug in the flow that must be fixed before TSPEC authoring. F-02, F-03, and F-04 are Low and should be addressed for precision.
