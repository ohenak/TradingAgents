# Cross-Review: software-engineer — PROPERTIES

**Reviewer:** software-engineer
**Document reviewed:** `docs/wheel-options-trading/PROPERTIES-wheel-options-trading.md`
**Date:** 2026-05-26
**Iteration:** 2

---

## Prior-Finding Resolution Status

All 8 findings from the v1 SE cross-review have been addressed in v0.2.0.

| Prior ID | Severity | Resolution |
|----------|----------|------------|
| F-01 | High | PROP-LIFE-07 test method rewritten to use `CspDecision` fields (`mid_premium`, `probability_of_profit`, `delta`, `max_loss`, `earnings_clear`). References to `cycle_pnl` and `cycle_annualised_return_pct` removed. Resolved. |
| F-02 | High | PROP-DATA-08 Delta tolerance corrected from ±0.001 to ±0.0005, matching TSPEC §2.1.3. Resolved. |
| F-03 | High | PROP-ROUTE-10 added: `csp_open` guard raises `WheelStateError` when no `WheelPosition` with `csp_strike` set exists. Symmetric with PROP-ROUTE-08. Resolved. |
| F-04 | Medium | PROP-SCREEN-12 (renumbered from PROP-SCREEN-06) test method now uses only `mock.assert_called_once_with(llm, WheelCandidateReport, "wheel_analyst")`. Misleading `inspect.signature` alternative removed. Resolved. |
| F-05 | Medium | PROP-DATA-13 precondition now explicitly sets `config["wheel"]["risk_free_rate_source"] = "yfinance_irx"` to ensure the `^IRX` fetch path is exercised. Resolved. |
| F-06 | Medium | PROP-LIFE-03 test method now specifies the `wheel_cycle_summary` node directly with a full `AgentState` dict injection containing `WheelPosition` fixture via `tmp_path`. Resolved. |
| F-07 | Medium | PROP-FALLBACK-13 test method now specifies `ast.parse()` + `ast.walk()` scanning of all four wheel agent source files. Resolved. |
| F-08 | Medium | PROP-LIFE-12 added: `prior_analyst_bias` round-trip persistence with two sequential `RollCheckAgent` invocations, `tmp_path` isolation, and `_position_loader` injection. Resolved. |

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | **PROP-SCREEN-10 and PROP-SCREEN-11 test method targets the wrong agent.** Both properties are classified under `PROP-SCREEN` (WheelAnalyst domain) and their descriptions correctly identify the WheelAnalyst progressive-relaxation behaviour. However, both test methods say "Run `CspAgent`" and assert on `CspDecision.tradeable` and `CspDecision.rationale`. The relaxation logic (yield_filter_relaxed, earnings_filter_relaxed) in FSPEC-WHEEL-04 §9a/§9b is part of `CspAgent`'s filter pipeline — it is not a property of `WheelAnalyst` or `WheelCandidateReport`. The property descriptions ("the WheelAnalyst yield filter", "the WheelAnalyst earnings filter") are misleading: the filter is executed inside `CspAgent`, not `WheelAnalyst`. Either (a) rename / re-domain these properties to `PROP-TRADE-15` and `PROP-TRADE-16` to reflect their true home in the CspAgent pipeline, or (b) update the description to correctly attribute the relaxation to `CspAgent` while keeping the PROP-SCREEN number. As written, the description / test method mismatch will cause confusion when implementers look for the relaxation logic in `WheelAnalyst` and do not find it. This is a documentation clarity issue only — the test assertion itself is correct. | PROP-SCREEN-10, PROP-SCREEN-11 |
| F-02 | Low | Local | **PROP-DATA-17 assertion on `iv_rank` / `iv_percentile` presence in the returned string is underspecified.** The test method says "Assert the returned string also contains `iv_rank` and `iv_percentile` values that are numeric and in `[0, 100]`." The word "contains" is ambiguous — a pytest test cannot assert a string "contains a numeric value in [0, 100]" without parsing it. The prior v0.1.0 version of PROP-DATA-17 (PM-F-03) did not specify how to extract the numeric values from the returned string. Recommend specifying the extraction approach: either (a) assert that the returned string contains the substring `"iv_rank:"` and parse the adjacent float, asserting it is in `[0, 100]`; or (b) assert that `get_iv_metrics` returns a structured object (not just a string) in this path, and check the numeric fields directly. If the function contract is "returns a formatted string", option (a) is the pragmatic approach. | PROP-DATA-17 |
| F-03 | Low | Local | **GAP-04 (`cycle_pnl` formula verification) disposition note is aspirational but the property is not present in v0.2.0.** GAP-04 states "Add PROP-LIFE-13 in v0.3.0: verify `cycle_pnl` against REQ-LIFE-02 AC3 numeric example (expected: 930)." REQ-LIFE-02 AC3 explicitly states the expected numeric value, which makes this a straightforward P0 property. Deferring a directly-specified numeric contract to v0.3.0 is reasonable but increases the risk that it ships without a regression test. This is a low-severity observation only — the gap is acknowledged and has a concrete resolution plan. | §10 Known Gaps, GAP-04 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | PROP-LIFE-12 test method invokes `RollCheckAgent` with `recommendation="Buy"` mapping to bias `"bullish"`, and `recommendation="Sell"` mapping to bias `"bearish"`. Is this `recommendation → bias` mapping documented in the TSPEC or FSPEC? If it lives only in the agent implementation, the test is implicitly coupling to an undocumented convention. Consider adding a one-line note in the test method citing the TSPEC section that defines this mapping. |
| Q-02 | PROP-SCREEN-10 and PROP-SCREEN-11 assert `CspDecision.rationale` contains `"yield_filter_relaxed"` and `"earnings_filter_relaxed"`. Are these string literals defined as constants in the implementation, or are they free-text LLM-generated values? If they are LLM-generated, the assertion will be non-deterministic. The test method should clarify that the LLM is mocked to return these exact strings in `rationale`, not that the agent generates them autonomously. |

---

## Positive Observations

- All 8 prior high/medium findings are correctly resolved. The v0.2.0 changelog entry is accurate and traceable.
- PROP-LIFE-07 fix is precise: the test method now references exactly the fields that `_build_options_context` reads from `CspDecision` per TSPEC §5.5, and the "no prior cycle" path (both decisions `None`) is correctly specified.
- PROP-DATA-13 precondition addition is exactly what was requested: the `risk_free_rate_source = "yfinance_irx"` guard prevents the test from passing for the wrong reason.
- PROP-LIFE-12 test method is well-structured: two sequential invocations with different `recommendation` values, `_position_loader` injection, `tmp_path` isolation, and explicit round-trip file assertions. This is the correct pattern for persistence testing without fixture coupling.
- PROP-FALLBACK-13 test method is now a properly specified `ast`-based pytest test, including the assertion that the sentinel import appears in each agent file.
- PROP-ROUTE-10 is a correct and complete addition: symmetric with PROP-ROUTE-08, correct error message assertion (`"csp_open"` substring in the raised exception), and the `ConditionalLogic` mock pattern is consistent with PROP-ROUTE-08.
- The renumbering of former PROP-SCREEN-06/07/08 to PROP-SCREEN-12/13/14 (to make room for new PROP-SCREEN-06 through PROP-SCREEN-11) is internally consistent throughout the document and coverage matrix.
- Coverage matrix (§9) is correctly updated to include all new properties (PROP-ROUTE-10, PROP-LIFE-12, PROP-SCREEN-06 through PROP-SCREEN-11) and their source traceability.

---

## Recommendation

**Approved**

All 3 new findings are Low severity. Per approval rules, Low-only findings permit approval without requiring another revision cycle.

The three Low findings are informational:
- F-01: description/domain attribution mismatch in PROP-SCREEN-10/11 — the test assertion is correct, only the naming is confusing.
- F-02: PROP-DATA-17 string-parsing assertion could be more specific — does not block implementation.
- F-03: GAP-04 deferral acknowledged with a resolution plan.

These may be addressed opportunistically in v0.3.0 alongside the planned GAP additions (PROP-LIFE-13, PROP-SCREEN-15), or inline during implementation if the implementer encounters them.
