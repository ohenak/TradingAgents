# Cross-Review: test-engineer — TSPEC

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/TSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 2

---

## v1 Finding Resolution

All six v1 findings are resolved in v0.2.0:
- F-01 ✅ `.value` removed from `_detect_asset_type()` call in batch_run_loop step 2
- F-02 ✅ `patch('cli.batch.Live', MagicMock())` added to §7.2 test doubles; headless note added to batch_run_loop test section
- F-03 ✅ 5 test cases added for `test_detect_asset_type_internal.py`
- F-04 ✅ `propagate_many([], date)` → `[]` test case added
- F-05 ✅ Precondition invariant note added to `build_batch_summary` algorithm
- F-06 ✅ Regression test baseline values specified with questionary call sequence, path pattern, and panel title set

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | `test_propagate_many.py` specifies `asset_types=["crypto"]` (single override) but not `asset_types=["stock","crypto"]` (mixed explicit list). The mixed case is the primary real-world use for `asset_types` — it verifies that each element is passed to the corresponding ticker in order. Add: `propagate_many(["AAPL","BTC-USD"], date, asset_types=["stock","crypto"])` → `propagate` called as `propagate("AAPL", date, asset_type="stock")` and `propagate("BTC-USD", date, asset_type="crypto")`. | §7.3 test_propagate_many.py |
| F-02 | Low | Local | The regression test baseline (§7.3) specifies questionary call sequence as `["text","select","select","select","text","checkbox","select"]` (7 calls). The CLI has 8 prompts in single-ticker mode: ticker (text), language (select), provider (select), deep model (select), quick model (select), date (text), analysts (checkbox), research depth (select). The sequence should be 8 elements: `["text","select","select","select","select","text","checkbox","select"]`. One `select` (quick model) appears to be missing. | §7.3 test_regression_single_ticker.py |

---

## Questions

None.

---

## Positive Observations

- The `Live` context mock addition (`patch('cli.batch.Live', MagicMock())`) is the right minimal approach — it prevents terminal I/O without affecting the rest of the batch loop logic.
- `build_batch_summary` precondition note cleanly scopes what the function promises vs. what the caller must guarantee — this prevents defensive guard-code in a pure function.
- The regression test parametrization over `["market","news"]` analyst set makes panel title assertions deterministic — a sound approach.
- All Medium findings from v1 are cleanly resolved with no introduced inconsistencies.
- The test double table is complete and directly usable by implementers.

---

## Recommendation

**Approved with minor changes**

> No High or Medium findings. F-01 (mixed explicit asset_types test) and F-02 (questionary sequence count) are Low and should be addressed before PLAN authoring.
