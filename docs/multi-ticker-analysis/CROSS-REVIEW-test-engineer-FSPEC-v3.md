# Cross-Review: test-engineer — FSPEC

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 3

---

## v2 Finding Resolution

All four v2 findings are resolved in v0.3.0:
- F-01 ✅ AT2 specifies `pytest.raises(KeyboardInterrupt)` on batch loop function directly
- F-02 ✅ AT1 uses observable mock-call-list assertion
- F-03 ✅ Step 2 names `message_buffer.init_for_analysis(selected_analyst_keys)` explicitly
- F-04 ✅ SE v2 F-01 (batch_results loop) fixed — AT2/AT5/AT8 now reach the `failed_tickers` branch

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | FSPEC-BATCH-01 AT2 still asserts on the internal variable `ordered_tickers == ["NVDA", "AAPL"]`, which is not observable via CliRunner. This AT is testing normalization and dedup logic — that logic is testable at the unit level only if it is extracted as a pure function (e.g. `parse_tickers_input(csv_string) → list[str]`). The FSPEC should add an extractability note for the normalisation/dedup step (similar to the FSPEC-BATCH-03 note), so the AT can be implemented as a unit test on that function. Without extraction, the AT requires inspecting internal state. | FSPEC-BATCH-01, AT2 |
| F-02 | Low | Local | SE v3 F-01 (Medium) identifies a list-vs-dict inconsistency in `batch_results` that would cause a TypeError at runtime in FSPEC-BATCH-03. Until resolved, FSPEC-BATCH-03 ATs (AT2, AT5, AT8) that exercise failed tickers cannot be implemented. No TE change needed; noting dependency on SE v3 F-01 fix. | FSPEC-BATCH-03, AT2, AT5, AT8 |
| F-03 | Low | Local | SE v3 F-02 identifies a `CONTINUE` in Step 3a that would skip Steps 3b and 4 (the completion line and save). If kept, a test for "process_signal fails but ticker still saves" would fail incorrectly. No TE change needed; noting dependency on SE v3 F-02 fix. | FSPEC-BATCH-02, Step 3a |

---

## Questions

None.

---

## Positive Observations

- The `build_batch_summary` extractability note makes AT1–AT9 fully unit testable — this is the right level for decision-logic tests.
- The `batch_results: dict[str, BatchTickerRecord]` fix (once SE v3 F-01 is applied) will make the lookup in FSPEC-BATCH-03 deterministic and O(1) — correct for a table-building function.
- AT2 in FSPEC-BATCH-02 now correctly calls out `pytest.raises(KeyboardInterrupt)` — this is the only reliable way to test KI propagation without CliRunner interference.
- AT6 in FSPEC-BATCH-01 (blank `--tickers` → exit code 2) is immediately testable: `CliRunner.invoke(app, ["analyze", "--tickers", "   "])` with `assert result.exit_code == 2`.

---

## Recommendation

**Approved with minor changes**

> No High or Medium testability findings. F-01 (normalisation/dedup extractability note) is Low and should be addressed. F-02 and F-03 are Low and will be resolved by SE v3 F-01 and F-02 fixes respectively. The SE v3 Medium finding must be resolved before this FSPEC can be fully approved — once that fix lands, no further TE iteration should be needed.
