# Cross-Review: software-engineer — FSPEC

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 3

---

## v2 Finding Resolution

All four v2 findings are resolved in v0.3.0:
- F-01 ✅ (High) FSPEC-BATCH-03 loop now iterates `ordered_tickers`; success path does lookup via `batch_results[ticker]`
- F-02 ✅ (Low) Redundant "Exit Rich Live context" removed from OSError handler
- F-03 ✅ (Low) `process_signal()` wrapped in non-fatal try/except with warning
- F-04 ✅ (Low) BatchTickerRecord/BatchTickerResult distinction noted in flow header

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | `batch_results` is defined as a `list` (`batch_results = [] ← list of BatchTickerRecord(...)`) in FSPEC-BATCH-02, but FSPEC-BATCH-03 accesses it as a dict (`batch_results[ticker].final_state`). A Python list does not support string-key lookup; this would raise `TypeError` at runtime. The FSPEC must resolve the access pattern: either (a) redefine `batch_results` as a dict keyed by ticker string (`batch_results: dict[str, BatchTickerRecord] = {}`), updating the append line to `batch_results[ticker] = BatchTickerRecord(...)`, or (b) keep it as a list and use a linear scan (`next(r for r in batch_results if r.ticker == ticker)`). Option (a) is O(1) and simpler. | FSPEC-BATCH-02 (input declaration); FSPEC-BATCH-03 (flow lookup) |
| F-02 | Low | Local | FSPEC-BATCH-02 Step 3a: the non-fatal `process_signal()` handler ends with `CONTINUE (ticker remains as Success; do not append to failed_tickers)`. In Python, `continue` inside a nested block advances the outer `for` loop — which would skip Steps 3b and 4 (the "✓ complete" line and the save). This is incorrect: the ticker is a success and both steps should still execute after a `process_signal()` warning. Remove the `CONTINUE`; execution should fall through to Step 3b naturally after the inner try/except. | FSPEC-BATCH-02, Step 3a |
| F-03 | Low | Local | FSPEC-BATCH-03 behavioral flow INPUT lists `N (total tickers)` but never uses `N` — the loop iterates `ordered_tickers` (which is not listed as an input). The standalone function signature in the extractability note is `build_batch_summary(batch_results, failed_tickers, selected_analyst_keys, n_total)` — replace `n_total` with `ordered_tickers` (the actual list). `N` can be derived as `len(ordered_tickers)` and does not need to be a separate parameter. | FSPEC-BATCH-03, behavioral flow INPUT; extractability note |

---

## Questions

None.

---

## Positive Observations

- The v0.3.0 FSPEC-BATCH-03 loop fix is structurally correct; iterating `ordered_tickers` with a dict lookup for successes is the right pattern.
- The non-fatal `process_signal()` handling (Step 3a) correctly preserves Success status for the ticker — the intent is right, only the `CONTINUE` keyword is wrong.
- The `BatchTickerRecord` type clarification note in the flow header cleanly separates the internal CLI type from the public `BatchTickerResult` API type.

---

## Recommendation

**Needs revision**

> F-01 is Medium: the `batch_results` list vs dict inconsistency would produce a runtime TypeError in FSPEC-BATCH-03. F-02 and F-03 are Low. All three should be addressed before TSPEC authoring.
