# Cross-Review: test-engineer — FSPEC

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 4

---

## v3 Finding Resolution

All three v3 findings are resolved in v0.4.0:
- F-01 ✅ `parse_tickers_input` extractability note added to FSPEC-BATCH-01
- F-02 ✅ SE v3 F-01 fixed (batch_results dict — AT2/AT5/AT8 now reach Failed rows)
- F-03 ✅ SE v3 F-02 fixed (CONTINUE removed from process_signal handler)

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | FSPEC-BATCH-03 flow still references `N == 1` and `N > 1` as gate conditions, but `N` was removed from the INPUT block (replaced by `ordered_tickers`). SE v4 already flagged this. From a testability perspective, a test calling `build_batch_summary` with `ordered_tickers=["AAPL"]` would not know what `N` refers to; the condition should be `len(ordered_tickers) == 1`. No separate TE change needed beyond SE v4 F-01. | FSPEC-BATCH-03, behavioral flow |

---

## Questions

None.

---

## Positive Observations

- v0.4.0 is in excellent testable shape. Every decision branch in all three FSPECs maps to a distinct, implementable test case.
- The `batch_results` dict pattern is fully consistent — `build_batch_summary` can now be unit tested with a simple dict fixture, no list iteration needed.
- Both extractability notes (`parse_tickers_input`, `build_batch_summary`) give TSPEC authors named function signatures with clear inputs — this is the minimum spec needed to write tests before implementation.
- FSPEC-BATCH-02 Step 3a process_signal fallthrough is correct and testable: inject a side_effect on `graph.process_signal` to raise, then assert that the ticker still appears as Success in the summary table and that its report was saved.
- AT2 in FSPEC-BATCH-02 (KI propagation via `pytest.raises`) is the correct test level; no higher-level test is needed for this specific property.

---

## Recommendation

**Approved with minor changes**

> Only F-01 remains (Low), which is the same as SE v4 F-01 — a one-line fix to replace `N == 1` / `N > 1` with `len(ordered_tickers) == 1` / `len(ordered_tickers) > 1`. Once SE v4 F-01 is addressed, this FSPEC requires no further TE iteration.
