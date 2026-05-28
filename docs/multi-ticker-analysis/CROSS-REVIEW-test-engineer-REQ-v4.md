# Cross-Review: test-engineer — REQ

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 4

---

## v3 Finding Resolution

All three v3 findings are resolved in v0.4.0:
- F-01 ✅ API-01 AC3 Given clause: "with `propagate()` mocked to return a deterministic `(state, decision)` tuple"
- F-02 ✅ BATCH-04 AC2: failure summary explicitly references REQ-BATCH-06 table, no separate output
- F-03 ✅ Resolved by SE-F-02: BATCH-06 description now covers `None`/absent `wheel_candidate_report`

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | REQ-API-01 AC2 Given clause reads "`propagate('BADTICKER', …)` raises `ValueError` inside `propagate_many`" — this describes the behaviour rather than the test setup. AC1, AC3, AC4, and AC5 all say "with `propagate()` mocked …" explicitly. AC2 should be rewritten to match: "with `propagate('BADTICKER', …)` mocked to raise `ValueError` and `propagate('AAPL', …)` mocked to succeed" to make the test double setup unambiguous. | REQ-API-01 |
| F-02 | Low | Local | REQ-BATCH-02 AC1 still says "asset type is determined per ticker by `detect_asset_type()`". After the v0.4.0 boundary resolution, the CLI uses the library-internal function (not `cli.utils.detect_asset_type`). A test asserting on BATCH-02 that mocks `detect_asset_type` from the CLI layer will not intercept the right call. The AC should say "library-internal asset type detection" (consistent with SE v4 F-01). | REQ-BATCH-02 |

---

## Questions

None — all open questions remain appropriately deferred to the user.

---

## Positive Observations

- v0.4.0 is in excellent testable shape. All High and Medium findings across four iterations have been resolved.
- The `propagate_many` signature with `asset_types=None` is a clean, testable contract: AC4 verifies auto-detection, AC5 verifies explicit override — both via mock call inspection with no real LLM calls needed.
- BATCH-06's complete decision-extraction logic (standard, wheel approved/rejected, None fallback, malformed-JSON fallback) gives the TSPEC author exactly four test branches to implement.
- BATCH-04 AC5's `pytest.raises(KeyboardInterrupt)` on the batch loop function directly is the correct isolation approach and will be straightforward to implement.
- The `BatchTickerResult` dataclass contract (all fields typed, nullability rules explicit) means AC1/AC2 assertions can be written as single-line field checks with no parsing ambiguity.

---

## Recommendation

**Approved with minor changes**

> No High or Medium findings. F-01 and F-02 are Low. F-01 (AC2 mock setup wording) ensures the test double is set up correctly for both the failing and succeeding ticker. F-02 (BATCH-02 AC1 function name) prevents a wrong mock target in tests. Both are one-sentence fixes. SE v4 F-02 (asset_types length mismatch raises ValueError) also needs a test once the TSPEC adds the validation AC — no REQ change required from the TE side.
