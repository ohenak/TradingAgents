# Cross-Review: software-engineer — REQ

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 2

---

## v1 Finding Resolution

All ten v1 findings are resolved in v0.2.0:
- F-01 ✅ message_buffer rebinding explicitly required in §3 Assumptions
- F-02 ✅ run_analysis() refactoring scope stated in §3 Assumptions
- F-03 ✅ Per-ticker asset type detection specified; AC6 added to REQ-BATCH-01
- F-04 ✅ AC3 removed from REQ-BATCH-03; design constraint note added
- F-05 ✅ BatchTickerResult dataclass defined in REQ-API-01
- F-06 ✅ Exception-only isolation with KeyboardInterrupt/SystemExit propagation stated
- F-07 ✅ REQ-NFR-01 AC1 rewritten with concrete mock-based comparison
- F-08 ✅ StatsCallbackHandler per-ticker scope stated in §3 Assumptions
- F-09 ✅ Graph initialised-once constraint stated in §3 Assumptions
- F-10 ✅ _processed_message_ids cleared on buffer reset stated in §3 Assumptions

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | REQ-BATCH-06 wheel decision trigger is state-presence, not analyst-selection, which creates an ambiguity. The description says "where `wheel_candidate_report` is present in state" — but when wheel mode is selected, both `wheel_candidate_report` AND `final_trade_decision` are always present (wheel_analyst runs after Trader, so both fields are populated in every wheel-mode run). The trigger should be "wheel analyst was selected for this batch" (i.e., `"wheel" in selected_analyst_keys`), not state key presence. Using state-presence risks showing stale `Approved`/`Rejected` if cached state bleeds between runs. | REQ-BATCH-06 |
| F-02 | Medium | Local | REQ-API-01 `propagate_many` does not specify asset_type handling. The existing `propagate(ticker, date, asset_type)` signature accepts `asset_type` explicitly; its docstring says "programmatic callers pass it explicitly". `propagate_many(tickers, date)` has no `asset_type` parameter and no statement that `detect_asset_type()` is called per ticker. Without this, API callers passing crypto tickers (e.g. `BTC-USD`) will silently run the stock pipeline. Specify that `propagate_many` calls `detect_asset_type(ticker)` per ticker before calling `propagate()`, matching CLI behaviour. | REQ-API-01 |
| F-03 | Low | Local | REQ-BATCH-03 AC1 uses `mock.assert_has_calls(...)` which does **not** guarantee strict ordering with no interleaved calls — it only checks that the listed calls appear somewhere in call history in order. A concurrent or interleaved implementation could pass this assertion. For a strict sequential ordering guarantee, the AC should specify `mock.call_args_list == [call("AAPL", …), call("MSFT", …)]` (exact equality on the full call list). | REQ-BATCH-03 |
| F-04 | Low | Local | REQ-BATCH-02 AC1 says "each ticker's graph is initialised with the same provider, model, date, and analyst set" — but §3 Assumptions states the graph is initialised **once** before the loop. The AC wording contradicts the assumption. Should read: "the single TradingAgentsGraph instance (initialised once) is called with the same provider, model, and analyst set for all tickers; only asset_type varies per ticker." | REQ-BATCH-02 |
| F-05 | Low | Local | REQ-BATCH-05 AC1 phrase "at the moment of save" is timing-dependent wording that could imply a race condition in an asynchronous context. Since the implementation is single-threaded and synchronous, restate as: "when `save_report_to_disk()` is invoked for AAPL, `propagate.call_count` for 'MSFT' is 0." | REQ-BATCH-05 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For `propagate_many`, should the caller be able to override asset_type per ticker (e.g. pass `asset_types: list[str] | None = None`), or is auto-detection always sufficient? |

---

## Positive Observations

- All three High findings from v1 are cleanly resolved; the §3 Assumptions block is now a valuable implementation guide.
- The `BatchTickerResult` dataclass contract is precise and directly testable.
- REQ-BATCH-04 AC5 (KeyboardInterrupt propagation) is a good addition that prevents a class of uninterruptible-batch bugs.
- The design constraint note on REQ-BATCH-03 correctly separates the architectural invariant from the AC, making the requirement both testable and readable.

---

## Recommendation

**Needs revision**

> F-01 and F-02 are Medium findings. F-01 (BATCH-06 trigger) could cause incorrect decision display for wheel-mode batches. F-02 (API-01 asset_type) would silently mis-route crypto tickers through the wrong pipeline for API callers. Both must be addressed. F-03 through F-05 are Low and should be addressed for precision.
