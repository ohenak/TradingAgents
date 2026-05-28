# Cross-Review: test-engineer — REQ

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 2

---

## v1 Finding Resolution

All twelve v1 findings are resolved in v0.2.0:
- F-01 ✅ REQ-NFR-01 AC1 rewritten with concrete mock-based comparison (questionary call sequence, results path, Rich panel titles)
- F-02 ✅ REQ-BATCH-03 AC1 rewritten as `mock.assert_has_calls` ordering assertion
- F-03 ✅ `normalize_ticker_symbol()` explicitly referenced in REQ-BATCH-01 description and AC1
- F-04 ✅ Exit code `1` specified in REQ-BATCH-04 AC2
- F-05 ✅ Observable failure format `[FAILED] {TICKER}: {ExceptionClassName}` specified in REQ-BATCH-04 AC1
- F-06 ✅ REQ-BATCH-05 AC2 uses exception-injection test mechanism
- F-07 ✅ `final_trade_decision` source field, first non-empty line, 50-char truncation specified in REQ-BATCH-06
- F-08 ✅ `BatchTickerResult` dataclass with typed fields resolves return type ambiguity in REQ-API-01
- F-09 ✅ First-occurrence dedup order specified in REQ-BATCH-01
- F-10 ✅ Exact format string and regex pattern provided in REQ-NFR-02
- F-11 ✅ All-failure scenario added as REQ-BATCH-04 AC4
- F-12 ✅ §3 Assumptions documents message_buffer state clearing; cross-feature signal available for harvest

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | REQ-BATCH-01 AC6 "runs the stock/crypto pipeline" is not directly assertable. "AAPL runs the stock pipeline, BTC-USD runs the crypto pipeline" describes internal routing behaviour — there is no observable output the test can assert on without inspecting the `asset_type` argument passed to `propagate()`. Rewrite as: "`propagate('AAPL', …, asset_type='stock')` is called for AAPL and `propagate('BTC-USD', …, asset_type='crypto')` is called for BTC-USD." | REQ-BATCH-01 |
| F-02 | Medium | Local | REQ-BATCH-06 AC4 does not specify what happens when `wheel_candidate_report` JSON is malformed or unparseable. If `WheelCandidateReport.model_validate_json()` raises during summary table construction, the batch loop could crash after all tickers have successfully completed — a regression in the display path. The AC must specify the fallback: "if parsing fails, the Decision cell shows `N/A` and Status shows `Success`." | REQ-BATCH-06 |
| F-03 | Low | Local | REQ-BATCH-06 AC1 truncation is ambiguous. "the first non-empty line of `final_trade_decision` (≤ 50 chars)" could be read as a filter (only include lines already ≤ 50 chars) rather than a truncation rule. Rewrite as: "the first non-empty line of `final_trade_decision`, truncated to 50 characters if longer". | REQ-BATCH-06 |
| F-04 | Low | Local | REQ-NFR-01 AC1 references "the pre-feature baseline integration test" as if it already exists. It does not — it must be created as part of this feature's test work. The criterion is sound in principle, but the REQ should state "a baseline integration test is established as part of this feature's test suite" so the TSPEC author knows to create it. | REQ-NFR-01 |
| F-05 | Low | Local | REQ-BATCH-04 AC5 (`KeyboardInterrupt` propagation) does not specify the test mechanism. `typer.testing.CliRunner` does not propagate `KeyboardInterrupt` — it catches it internally. The AC must specify testing at the batch loop function level directly (unit test: `pytest.raises(KeyboardInterrupt)`) rather than via CliRunner. | REQ-BATCH-04 |
| F-06 | Low | Local | REQ-API-01 AC3 "result is equivalent to calling `propagate()` directly" does not specify which return value. `propagate()` returns `(final_state, decision)` — a 2-tuple. AC3 should read: "`result[0].decision == ta.propagate('AAPL', '2026-05-27')[1]`" to be unambiguous. | REQ-API-01 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For REQ-BATCH-06 AC4, should the wheel `Approved`/`Rejected` value take precedence even if `final_trade_decision` is also populated? SE v2 review (F-01) flags the same trigger ambiguity — resolving it will also clarify this AC. |

---

## Positive Observations

- The `BatchTickerResult` dataclass contract is now precise and directly testable — each field has a defined type and nullability rule.
- REQ-BATCH-04 AC5 (KeyboardInterrupt propagation) is a valuable addition that was missing from v0.1.0.
- REQ-BATCH-05 AC2 using exception injection is the correct test strategy — it makes the "interrupted batch" scenario deterministic and repeatable.
- REQ-BATCH-04 AC4 (all-tickers-fail) is a good edge case addition; exit code 1 and summary table still printing are both precisely testable.
- The progress format in REQ-NFR-02 now has both an exact template and a regex, which covers both human-readable specification and automated assertion.

---

## Recommendation

**Needs revision**

> F-01 (BATCH-01 AC6 unassertable pipeline routing) and F-02 (BATCH-06 AC4 malformed JSON fallback) are Medium findings that must be addressed. F-03 through F-06 are Low and should be addressed for precision before TSPEC authoring.
