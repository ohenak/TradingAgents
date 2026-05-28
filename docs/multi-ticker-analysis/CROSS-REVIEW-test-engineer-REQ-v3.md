# Cross-Review: test-engineer — REQ

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 3

---

## v2 Finding Resolution

All six v2 findings are resolved in v0.3.0:
- F-01 ✅ BATCH-01 AC6 rewritten: `propagate('AAPL', …, asset_type='stock')` / `propagate('BTC-USD', …, asset_type='crypto')` — mock-assertable
- F-02 ✅ BATCH-06 AC4 malformed-JSON fallback: `N/A` / `Success` on `model_validate_json()` raise
- F-03 ✅ BATCH-06 AC1: "truncated to 50 characters if longer"
- F-04 ✅ NFR-01: baseline test creation explicitly required as part of this feature's test suite
- F-05 ✅ BATCH-04 AC5: `pytest.raises(KeyboardInterrupt)` on batch loop function, not CliRunner
- F-06 ✅ API-01 AC3: `result[0].decision == ta.propagate("AAPL", "2026-05-27")[1]`

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | REQ-API-01 AC3 does not specify that `propagate()` is mocked. The criterion calls `ta.propagate("AAPL", "2026-05-27")` as the reference value — without mocking, this triggers a real LLM call and produces a non-deterministic result that can't be asserted against reliably. Add "with `propagate()` mocked to return a deterministic `(state, decision)` tuple" to the Given clause. | REQ-API-01 |
| F-02 | Low | Local | REQ-BATCH-04 AC2 says "prints a failure summary listing all failed tickers" — it is unclear whether this is (a) the summary table already defined in REQ-BATCH-06 (which shows `Failed` per row), or (b) a separate printed list before the table. If it is the summary table, say so explicitly. If it is a separate output, specify its format. The ambiguity means a test cannot assert on the right observable. | REQ-BATCH-04 |
| F-03 | Low | Local | REQ-BATCH-06 AC4 covers the malformed-JSON fallback but not the `None`/absent `wheel_candidate_report` case. SE v3 review (F-02) flags this at Medium. From a testability angle, there is no AC that exercises `wheel_candidate_report is None` — a test for that case cannot be written to a specific AC. Addressing SE v3 F-02 will also close this testability gap, so no separate REQ change is needed beyond what SE already requires. | REQ-BATCH-06 |

---

## Questions

None — open questions OQ-01 through OQ-03 are appropriately deferred to the user.

---

## Positive Observations

- v0.3.0 is in strong shape from a testability standpoint. Every High and Medium testability finding from v1 and v2 has been resolved.
- The `call_args_list` strict-equality assertion in BATCH-03 AC1 is the correct approach for sequential ordering verification.
- The `pytest.raises(KeyboardInterrupt)` specification in BATCH-04 AC5 correctly identifies the test harness constraint (CliRunner suppresses KI) without leaving it ambiguous.
- BATCH-05 AC1 call-count assertion is a clean, synchronous verification approach that avoids timing dependencies.
- NFR-01 explicitly noting that the baseline test is created as part of this feature prevents a "missing test" gap at delivery time.
- The `BatchTickerResult` dataclass, `[FAILED] TICKER: ExceptionClass` format, and `[N/TOTAL]` progress pattern are all precisely assertable.

---

## Recommendation

**Approved with minor changes**

> No High or Medium findings from the testing perspective. F-01 and F-02 are Low and should be addressed before TSPEC authoring. F-03 will be resolved by the SE v3 Medium finding (no separate change needed). The SE v3 High finding (import boundary on `detect_asset_type`) must be resolved before this REQ can be considered fully approved — once that architectural decision is made, a final pass may be needed if the resolution changes any AC.
