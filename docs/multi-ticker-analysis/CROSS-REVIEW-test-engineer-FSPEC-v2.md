# Cross-Review: test-engineer — FSPEC

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 2

---

## v1 Finding Resolution

All six v1 findings are resolved in v0.2.0:
- F-01 ✅ CliRunner test mechanism note added under FSPEC-BATCH-01
- F-02 ✅ `message_buffer.reset()` added as BR-04 with test isolation note
- F-03 ✅ AT1 specifies `graph.propagate` mocked to raise ValueError for BADTICKER
- F-04 ✅ AT3 specifies `save_report_to_disk` mocked with `side_effect`
- F-05 ✅ Extractability note added to FSPEC-BATCH-03 (standalone `build_batch_summary` function)
- F-06 ✅ OQ-F-01 resolved to exit-code-2 usage error; AT6 added

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | FSPEC-BATCH-02 AT2 ("propagate raises KeyboardInterrupt; batch aborts") does not specify how "batch aborts" is verified in a test. Since `CliRunner` suppresses `KeyboardInterrupt`, the AT must clarify: "verified via `pytest.raises(KeyboardInterrupt)` on the batch loop function directly, not via CliRunner". Without this, a test author may use CliRunner and get a false pass (KI is swallowed, batch appears to succeed). | FSPEC-BATCH-02, AT2 |
| F-02 | Low | Local | FSPEC-BATCH-01 AT1 asserts `ordered_tickers == ["AAPL", "MSFT"]`, but `ordered_tickers` is an internal variable not observable via CliRunner output. The assertion should be on an observable: e.g., "the batch runs analyses for AAPL and MSFT (verified by mock call list) and the ticker prompt is not shown (CliRunner input not consumed)". | FSPEC-BATCH-01, AT1 |
| F-03 | Low | Local | FSPEC-BATCH-02 Step 2 says "Re-initialise message_buffer for this ticker's analyst selection" without naming the method. The existing `MessageBuffer.init_for_analysis(selected_analyst_keys)` method is what performs this — naming it removes ambiguity and enables tests to assert the call was made. | FSPEC-BATCH-02, Step 2 |
| F-04 | Low | Local | SE v2 review (F-01 High) identifies that FSPEC-BATCH-03 iterates `batch_results` (successes only) instead of `ordered_tickers`, meaning failed-ticker rows are never built. This also breaks AT2, AT5, and AT8 in FSPEC-BATCH-03 which assert on Failed rows. Once SE-F-01 is resolved (loop changed to iterate `ordered_tickers`), these ATs will become testable. No TE change needed beyond noting the dependency. | FSPEC-BATCH-03, AT2, AT5, AT8 |

---

## Questions

None.

---

## Positive Observations

- BR-07 (interactive prompt suppression) and BR-08 (Live context per ticker) are both clearly stated and directly testable.
- The `build_batch_summary` extractability note enables all FSPEC-BATCH-03 ATs (AT1–AT9) to be implemented as unit tests without CLI invocation — this is the right test pyramid pressure.
- AT6 (blank `--tickers` → exit code 2) is immediately testable via `CliRunner.invoke(app, ["analyze", "--tickers", "   "])` with `assert result.exit_code == 2`.
- message_buffer `reset()` as BR-04 gives a clean isolation mechanism that will produce reliable test results across all batch loop tests.
- The OQ-F-01 resolution (exit code 2) is consistent with Typer's standard error handling for usage errors — a test can assert both on `exit_code` and on the error message string.

---

## Recommendation

**Approved with minor changes**

> No High or Medium testability findings from the TE perspective. F-01 through F-03 are Low and should be addressed before TSPEC authoring. F-04 is a consequence of SE v2 F-01 (High) — once the loop is fixed there, AT2/AT5/AT8 will be testable without further FSPEC changes. The SE High finding must be resolved before this FSPEC can be fully approved.
