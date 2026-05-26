# Cross-Review: test-engineer — Implementation

**Reviewer:** test-engineer
**Document reviewed:** `feat-wheel-options-trading` implementation + `tests/` (against `docs/wheel-options-trading/PROPERTIES-wheel-options-trading.md` v0.2.0)
**Date:** 2026-05-26
**Iteration:** 2

---

## Summary

512 tests pass across 41 test files. Five of six prior findings are fully or substantially resolved: F-01 (exact-value config assertions added, implementation corrected to 0.05/45), F-02 (second sequential PROP-LIFE-12 run added as a separate test method), F-05 (integration-level PROP-TRADE-08/09 tests now run the agents), F-06 (stale config comment removed). Two findings require further attention: F-03 (PROP-ROUTE-01/09 integration gap persists — the test class claims "full LangGraph integration" but only calls `route_wheel_phase()`), and F-04 (PROP-LIFE-10 vacuousness resolved but tests contradict the PROPERTIES spec assertion at `abs_delta=0.10`, and the required `abs_delta=0.09` test case is absent).

---

## Prior Finding Resolution Status

| Prior ID | Severity | Status | Notes |
|----------|----------|--------|-------|
| F-01 | High | Resolved | `test_properties_config.py` now asserts `near_the_money_pct == 0.05` and `options_lookforward_days == 45` exactly. `default_config.py` corrected to match. |
| F-02 | Medium | Resolved | `test_prior_analyst_bias_overwritten_on_second_run` added as a separate test method that starts from `prior_analyst_bias="bullish"`, runs with `"Sell"` plan, and asserts `prior_analyst_bias == "bearish"`. |
| F-03 | Medium | Partially resolved | Traceability label corrected (PROP-ROUTE-01 vs PROP-ROUTE-07). However, `TestEquityPassthroughIntegration` still does not compile or invoke the LangGraph; it only calls `route_wheel_phase()`. The test comment falsely claims "Full integration test using compiled LangGraph." Tool-call suppression and output field assertions remain absent. |
| F-04 | Medium | Partially resolved | Non-vacuous `earnings_within_cycle=True` test cases added. However, `test_rule4_boundary_exclusive_at_0_10_with_earnings_within_cycle` asserts `rule4 is False` at `abs_delta=0.10`, which contradicts PROP-LIFE-10's stated requirement that `abs_delta==0.10` must fire Rule 4. The required `abs_delta=0.09` test case is absent; implementation uses `abs_delta=0.05` instead. |
| F-05 | Medium | Resolved | `TestCspAgentStrikeBelowSpot` and `TestCcAgentStrikeAboveCostBasis` run the respective agents via `create_csp_agent`/`create_cc_agent` and assert strike constraints against injected spot/cost_basis values. |
| F-06 | Medium | Resolved | Stale "NOTE: not in REQ Section 7 — TSPEC addition per FSPEC-WHEEL-03 closure (PM-TSPEC-02)" comment removed. `default_config.py` now attributes both keys to REQ v0.3.0 §7. |

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|------------|
| F-01 | Medium | Local | **PROP-ROUTE-01/PROP-ROUTE-09 integration test remains at routing-method level only.** `TestEquityPassthroughIntegration` in `test_graph_routing.py` (lines 163–212) carries the docstring "Full integration test using compiled LangGraph" but contains no `StateGraph` compilation, no `app.invoke`, and no `graph.invoke`. Both test methods call only `logic.route_wheel_phase(state)`. PROP-ROUTE-01 and PROP-ROUTE-09 require: (a) invoking the full compiled graph, (b) asserting that none of the four options tools (`get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date`) are called (call count == 0), and (c) asserting output fields `market_report` and `fundamentals_report` are populated. None of these three assertions appear. The prior v1 review offered two resolution paths: (a) a full compiled-graph integration test, or (b) documentation as a known gap in PROPERTIES §10 with a PROP-ROUTE-01-INT entry. Neither path was followed — the test was relabelled correctly but not substantively upgraded, and no §10 gap entry was added. | PROP-ROUTE-01; PROP-ROUTE-09; ADR-WHEEL-03; REQ-NFR-01 |
| F-02 | Medium | Local | **PROP-LIFE-10: test contradicts PROPERTIES spec at the `abs_delta=0.10` boundary, and the `abs_delta=0.09` case is absent.** PROP-LIFE-10 explicitly states: "(a) `abs(current_delta) == 0.10` WITH earnings within DTE → Rule 4 must fire; (b) `abs(current_delta) == 0.09` → Rule 4 must NOT fire." The new test `test_rule4_boundary_exclusive_at_0_10_with_earnings_within_cycle` (line 167) asserts `rule4 is False` at `abs_delta=0.10, earnings_within_cycle=True` — the opposite of the PROPERTIES assertion. The required `abs_delta=0.09` test case is absent; the other new test uses `abs_delta=0.05`. The implementation (`rule4 = abs_delta < 0.10`) is consistent with FSPEC-WHEEL-06 ("Deep OTM is abs(delta) < 0.10, exclusive") and the tests correctly test the implementation. However, PROP-LIFE-10 appears to have an inversion error in its description that has been tacitly corrected in the tests without updating the PROPERTIES document. One of the following must happen: (a) update PROP-LIFE-10 to state `abs_delta < 0.10` fires Rule 4 (aligning with FSPEC and implementation), and add the `abs_delta=0.09` test that asserts Rule 4 fires; or (b) fix the implementation to fire at `abs_delta == 0.10`. The current state has a spec/test inconsistency that will confuse future reviewers. | PROP-LIFE-10; FSPEC-WHEEL-06 Rule 4 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | PROP-LIFE-10 states `abs_delta == 0.10` → Rule 4 fires. The implementation has `abs_delta < 0.10` (strictly less than). The FSPEC source says "Deep OTM is abs(delta) < 0.10, exclusive." Which is authoritative — the PROPERTIES description or the FSPEC/implementation? If FSPEC and implementation are correct, PROP-LIFE-10's description must be updated. |
| Q-02 | Will the PROP-ROUTE-01/09 full-graph integration test be added in v0.3.0, or should it be documented as GAP-06 in PROPERTIES §10? The current test class docstring claims "full LangGraph integration" which is misleading. Either the test must be substantively upgraded or the gap must be transparently documented. |

---

## Positive Observations

- F-01 fully resolved: `default_config.py` now uses `near_the_money_pct=0.05` and `options_lookforward_days=45`, both matching REQ v0.3.0 §7. The exact-value assertions in `test_properties_config.py` (`assert wheel["near_the_money_pct"] == 0.05` at line 83 and `assert wheel["options_lookforward_days"] == 45` at line 107) are correctly specified and will catch any future regression.
- F-02 fully resolved: `test_prior_analyst_bias_overwritten_on_second_run` starts from an already-persisted `"bullish"` position and asserts it is overwritten to `"bearish"` after a second invocation — exactly as the PROPERTIES test method specified. This guards against write-once implementation bugs.
- F-05 fully resolved at the agent-invocation level: `TestCspAgentStrikeBelowSpot` (PROP-TRADE-08) runs `create_csp_agent` and parses the returned `csp_decision` JSON to assert `stored_decision.strike < spot_price`. `TestCcAgentStrikeAboveCostBasis` (PROP-TRADE-09) runs `create_cc_agent` with `_position_loader` injecting a `WheelPosition` and asserts `stored_decision.strike >= stored_decision.cost_basis`.
- F-06 fully resolved: `default_config.py` comments now correctly attribute `near_the_money_pct` and `options_lookforward_days` to REQ v0.3.0 §7. The misleading "TSPEC extension" framing is gone.
- F-04 vacuousness resolved: both new tests use `earnings_within_cycle=True`, making the boundary assertion non-vacuous. The prior vacuous `earnings_within_cycle=False` test is retained as a complementary case.
- PROP-ROUTE-07 traceability corrected: the labelling mismatch (unknown phase test previously tagged PROP-ROUTE-01) has been fixed with a comment "Previously mislabelled as PROP-ROUTE-01 — corrected per TE-F-03".
- 512 tests pass with no new failures introduced.

---

## Recommendation

**Needs revision**

> F-01 (Medium) and F-02 (Medium) require revision before approval. The minimum changes are:
>
> 1. **F-01 (PROP-ROUTE-01/09 graph integration gap):** Either:
>    (a) Upgrade `TestEquityPassthroughIntegration` to compile and invoke the LangGraph with mocked LLM nodes, track tool-call counts, and assert `market_report`/`fundamentals_report` are populated; OR
>    (b) Remove the misleading docstring "full integration test using compiled LangGraph", add PROP-ROUTE-01 and PROP-ROUTE-09 to PROPERTIES §10 as a new known gap (GAP-06), and note the resolution path (add PROP-ROUTE-01-INT when LangGraph integration harness is available).
>
> 2. **F-02 (PROP-LIFE-10 spec/test inconsistency):** Either:
>    (a) Update PROP-LIFE-10 description to match FSPEC ("Rule 4 fires when `abs_delta < 0.10`; `abs_delta == 0.10` does NOT fire; `abs_delta == 0.09` fires") and add the `abs_delta=0.09` test case asserting Rule 4 fires; OR
>    (b) Fix the implementation to fire Rule 4 at `abs_delta <= 0.10` (inclusive boundary) per the PROPERTIES literal text, and update the test accordingly.
>    In either case, the `abs_delta=0.09` test case must be present so the boundary is tested at the specified value.
