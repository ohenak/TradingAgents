# Cross-Review: test-engineer — Implementation

**Reviewer:** test-engineer
**Document reviewed:** `feat-wheel-options-trading` implementation + `tests/` (against `docs/wheel-options-trading/PROPERTIES-wheel-options-trading.md` v0.2.0)
**Date:** 2026-05-26
**Iteration:** 3

---

## Summary

521 tests pass (plus 1 skipped, 75 subtests) across 37 test files. Both v2 findings are fully resolved: F-01 (PROP-ROUTE-01/09 test class docstring corrected to accurately state scope limitation; GAP-06 added to PROPERTIES §10 documenting the compiled-graph integration deferral) and F-02 (PROP-LIFE-10 description corrected in PROPERTIES v0.2.0 to match FSPEC; `test_rule4_fires_at_0_09_boundary` added to `test_roll_agent.py` asserting `abs_delta=0.09` fires Rule 4). No new High or Medium findings.

---

## Prior Finding Resolution Status

| Prior ID | Severity | Status | Notes |
|----------|----------|--------|-------|
| F-01 (v2) | Medium | Resolved | `TestEquityPassthroughIntegration` docstring corrected: states "Scope limitation: these tests exercise `route_wheel_phase()` in isolation only. They do NOT compile or invoke a full LangGraph instance." GAP-06 added to PROPERTIES §10 with disposition "Add PROP-ROUTE-01-INT and PROP-ROUTE-09-INT when LangGraph integration harness is available." |
| F-02 (v2) | Medium | Resolved | PROP-LIFE-10 description updated in PROPERTIES v0.2.0 to state: `abs_delta == 0.10` must NOT fire Rule 4; `abs_delta == 0.09` must fire Rule 4 (TE-F-02 inversion correction noted in Source field). `test_rule4_fires_at_0_09_boundary` added at line 207 in `test_roll_agent.py`: asserts `rules["rule4"] is True` for `abs_delta=0.09, earnings_within_cycle=False`. Both required boundary cases are now present and non-vacuous. |

---

## Findings

No High or Medium findings. One Low finding noted for completeness.

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|------------|
| F-01 | Low | Local | **PROP-SCREEN-13 has no test.** PROP-SCREEN-13 requires: (a) building a graph with `selected_analysts` not containing `"wheel"`, (b) asserting `"wheel_analyst"` node is absent from `workflow.nodes`, and (c) asserting output `AgentState` has no `wheel_candidate_report` key set. No test in any test file covers this property. It shares the same underlying constraint as GAP-06 (requires a compiled LangGraph), but is not yet documented in PROPERTIES §10 as a gap. The absence is low-severity because the equity-passthrough routing is covered structurally via PROP-ROUTE-01/09 and the routing router tests, and PROP-SCREEN-13's node-exclusion assertion is a compile-time graph-structure check rather than a runtime invariant. | PROP-SCREEN-13; REQ-SCREEN-01 AC5; REQ-NFR-01 |

---

## Questions

No open questions.

---

## Positive Observations

- **F-01 (v2) fully resolved:** `TestEquityPassthroughIntegration` docstring now accurately states it exercises `route_wheel_phase()` in isolation only, with explicit acknowledgement that no compiled-graph invocation, tool-call count assertions, or output-field assertions are present. GAP-06 is documented in PROPERTIES §10 with the deferred property IDs (PROP-ROUTE-01-INT, PROP-ROUTE-09-INT) and a clear resolution trigger.
- **F-02 (v2) fully resolved:** PROP-LIFE-10 in PROPERTIES v0.2.0 now matches FSPEC-WHEEL-06 ("Deep OTM is abs(delta) < 0.10, exclusive"): `abs_delta == 0.10` does NOT fire, `abs_delta == 0.09` fires. The `test_rule4_fires_at_0_09_boundary` test at line 207 of `test_roll_agent.py` closes the gap. Combined with `test_rule4_boundary_exclusive_at_0_10_with_earnings_within_cycle` (line 167) asserting `abs_delta == 0.10` does not fire with `earnings_within_cycle=True`, all four required boundary sub-cases are present and non-vacuous.
- **PROP-LIFE-12 second-run guard is correct:** `test_prior_analyst_bias_overwritten_on_second_run` (line 394) starts from `prior_analyst_bias="bullish"`, runs with a `"Sell"` plan, and asserts `prior_analyst_bias == "bearish"`. The write-once regression guard is properly implemented.
- **GAP-06 correctly documents the integration harness gap** — including the TE-F-01 lineage, the three missing assertion types (compiled graph invocation, tool-call count == 0, output-field population), and the deferred resolution path.
- **Test isolation is maintained throughout:** all I/O-layer tests use `pytest tmp_path`; no agent test accesses `config["wheel"]["positions_dir"]` directly; `_position_loader` injectable seam is used correctly in all agent-level lifecycle tests.
- **PROP-CONFIG-02 exact-value assertions are sound:** `test_properties_config.py` asserts `near_the_money_pct == 0.05` (exact float) and `options_lookforward_days == 45` (exact int) against `DEFAULT_CONFIG["wheel"]`. Both match REQ v0.3.0 §7 and the corrected `default_config.py`.
- **All 13 PROP-FALLBACK properties covered** across four agent test files, with `STRUCTURED_OUTPUT_SENTINEL` imported (not hardcoded) in every relevant test and the `ast.parse`/`ast.walk` sentinel-enforcement test in `test_sentinel_enforcement.py` correctly parametrized.
- **521 tests pass with no regressions** introduced by the v2 remediation commits.

---

## Recommendation

**Approved**

> Both v2 findings (F-01 and F-02) are fully resolved. The one Low finding (PROP-SCREEN-13 untested) is consistent with the existing GAP-06 deferral posture and does not block approval. The implementation satisfies all P0 and covered P1 properties defined in PROPERTIES v0.2.0.
