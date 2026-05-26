# Cross-Review: test-engineer — Implementation

**Reviewer:** test-engineer
**Document reviewed:** `feat-wheel-options-trading` implementation + `tests/` (against `docs/wheel-options-trading/PROPERTIES-wheel-options-trading.md` v0.2.0)
**Date:** 2026-05-26
**Iteration:** 1

---

## Summary

505 tests pass across 37 test files. The test suite is structurally sound: `STRUCTURED_OUTPUT_SENTINEL` is correctly imported (not hardcoded) in all agent test files, `test_sentinel_enforcement.py` uses `ast.parse` as specified, `load_latest_open_position` uses integer sort, `roll_agent.py` persists `prior_analyst_bias`, and the BSM numerical anchors (PROP-DATA-08/09) are tested in `test_options_data.py`. However, six findings require revision — one High and five Medium.

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|------------|
| F-01 | High | Local | **PROP-CONFIG-02 default-value assertion missing.** `test_properties_config.py` tests for key presence and type (`isinstance` checks) but does NOT assert the exact canonical values. `near_the_money_pct` is `0.10` in the implementation but PROP-CONFIG-02 requires `0.05`. `options_lookforward_days` is `90` in the implementation but PROP-CONFIG-02 requires `45`. The PROPERTIES doc (`PROP-CONFIG-02`) is the source of truth and derives from REQ v0.3.0 §7. This is a three-way conflict: PROPERTIES says `0.05`/`45`, REQ says `0.05`/`45`, but the implementation has `0.10`/`90`. Because the test was weakened (no exact-value assertion), the gap is invisible under CI. Either the test must be strengthened to assert exact values (and the implementation corrected) OR the PROPERTIES and REQ must be updated to accept `0.10`/`90`. The current state has a live contradiction between spec and implementation that is masked by a weak test. | PROP-CONFIG-02; REQ §7 (`near_the_money_pct=0.05`, `options_lookforward_days=45`) |
| F-02 | Medium | Local | **PROP-LIFE-12 single-run only; second sequential run missing.** The PROPERTIES test method explicitly requires two sequential invocations: first with `"Buy"` (→ `"bullish"`), then with `"Sell"` (→ `"bearish"`), to verify the field is overwritten and not just written once. The current test in `test_properties_life.py` (class `TestPriorAnalystBiasPersistence`) runs only one agent invocation and asserts `prior_analyst_bias is not None`. The second-run assertion (`prior_analyst_bias == "bearish"` after `"Sell"`) is absent. This means the test does not guard against an implementation that writes once and ignores subsequent updates. | PROP-LIFE-12 test method |
| F-03 | Medium | Local | **PROP-ROUTE-01/PROP-ROUTE-09 integration test does not verify tool-call suppression.** PROP-ROUTE-01 requires `@pytest.mark.integration` and asserts: (a) no options tools are called, (b) standard output fields (`market_report`, `fundamentals_report`) are populated. `test_graph_routing.py` marks `TestEquityPassthrough` with `@pytest.mark.integration` (satisfying the mark requirement), but only asserts the routing return value from `route_wheel_phase()`. It does not invoke the full compiled graph, does not track tool call counts, and does not assert on output state fields. This means the equity-passthrough invariant (REQ-NFR-01, ADR-WHEEL-03) is not actually verified end-to-end. PROP-ROUTE-09 has the same gap. Additionally, the test file labels what is PROP-ROUTE-07 behavior (unknown phase → warning) as "PROP-ROUTE-01", creating a traceability mismatch against the PROPERTIES doc. | PROP-ROUTE-01; PROP-ROUTE-09; REQ-NFR-01; ADR-WHEEL-03 |
| F-04 | Medium | Local | **PROP-LIFE-10 Rule 4 boundary test uses `earnings_within_cycle=False`.** PROP-LIFE-10 requires: (a) `abs(current_delta) == 0.10` WITH earnings within DTE → Rule 4 fires; (b) `abs(current_delta) == 0.09` WITH earnings within DTE → Rule 4 does NOT fire. The test `test_rule4_boundary_exclusive_at_0_10` in `test_roll_agent.py` uses `earnings_within_cycle=False` for the `abs_delta=0.10` case, so Rule 4 cannot fire regardless of delta. The boundary assertion (`assert rules["rule4"] is False`) passes vacuously — it would pass even if the deep-OTM boundary were implemented incorrectly. The boundary must be tested with `earnings_within_cycle=True` to be meaningful. | PROP-LIFE-10 test method; FSPEC-WHEEL-06 Rule 4 |
| F-05 | Medium | Local | **PROP-TRADE-08 and PROP-TRADE-09 integration-level assertions missing.** Both are classified as `Integration` / P0 in PROPERTIES. PROP-TRADE-08 requires asserting `CspDecision.strike < spot_price` through agent execution. PROP-TRADE-09 requires asserting `CcDecision.strike >= cost_basis` through agent execution. Neither has a test that runs the respective agent and checks the output field against the injected spot/cost_basis value. The schema-level tests in `test_properties_trade.py` only construct `CspDecision`/`CcDecision` objects directly (unit-level), which does not exercise the agent's strike-selection logic. The integration boundary is uncovered. | PROP-TRADE-08; PROP-TRADE-09 |
| F-06 | Medium | Cross-Feature | **PROP-CONFIG-02 discrepancy signals an undocumented TSPEC deviation.** The inline comment in `default_config.py` for `near_the_money_pct` states: "NOTE: not in REQ Section 7 — TSPEC addition per FSPEC-WHEEL-03 closure (PM-TSPEC-02)". However, REQ v0.3.0 §7 explicitly adds this key with default `0.05`. The TSPEC chose `0.10` without updating REQ or PROPERTIES, and this was not flagged in any prior cross-review. This pattern — TSPEC overriding REQ default without a bidirectional update — is a process gap. Future features should require a TSPEC deviation entry whenever implementation defaults differ from REQ-specified defaults. | PROP-CONFIG-02; REQ §7 v0.3.0; `default_config.py` comment |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | Is `near_the_money_pct=0.10` the intentional implementation default? The TSPEC comment describes it as a TSPEC extension, yet REQ v0.3.0 §7 explicitly specifies `0.05`. If `0.10` is deliberate (broader NTM window for better liquidity screening), REQ and PROPERTIES must be updated to `0.05 → 0.10`. If it is an accidental deviation, the implementation must change to `0.05`. The test must be fixed in either case to assert the exact value. |
| Q-02 | Is `options_lookforward_days=90` intentional? The TSPEC comment says "not in REQ Section 7" but REQ v0.3.0 §7 now explicitly includes it with default `45`. Same resolution path as Q-01. |
| Q-03 | The `PROP-LIFE-12` test comment says: "The current roll_agent.py implementation does NOT write prior_analyst_bias." This was written during test authoring. The implementation at `roll_agent.py` lines 267–274 *does* write it. Is the test comment stale, or was there a subsequent implementation fix that made it incorrect? If the implementation now persists the field, the comment should be removed to avoid confusion. |

---

## Positive Observations

- BSM numerical anchors (PROP-DATA-08, PROP-DATA-09: `Delta_put ≈ -0.4602`, `Theta_put_daily ≈ -0.0314`) are tested correctly in `test_options_data.py` with the prescribed test seam parameters (`_spot_price`, `_risk_free_rate`, `_sigma`).
- `test_sentinel_enforcement.py` correctly uses `ast.parse()` + `ast.walk()` and parametrizes across all four wheel agent modules. `STRUCTURED_OUTPUT_SENTINEL` is imported (not hardcoded) in every relevant test file.
- `load_latest_open_position` uses integer sort (`key=_cycle_number`) with the regression test in `test_wheel_position.py` (`test_integer_sort_regression_cycle_10_over_cycle_9`). Both PROP-LIFE-04 requirements (cycle-10 returned, cycle-9 excluded) are asserted.
- `roll_agent.py` persists `prior_analyst_bias` to `WheelPosition` (lines 267–274). The `save_wheel_position` call with the updated position satisfies TSPEC §5.4.
- PROP-SCREEN-10/11 (`yield_filter_relaxed`, `earnings_filter_relaxed`) are tested in `test_properties_screen.py` via direct calls to `_filter_csp_candidates`. The relaxation notes are checked in the returned candidate dicts.
- All 13 PROP-FALLBACK tests are present and correctly categorized across four agent test files (`test_wheel_analyst.py`, `test_csp_agent.py`, `test_cc_agent.py`, `test_roll_agent.py`).
- Known gaps from PROPERTIES §10 (GAP-01 through GAP-05) are correctly documented. GAP-04 (`cycle_pnl` formula) has been escalated to Medium priority with a resolution path (PROP-LIFE-13 in v0.3.0).
- PROP-CONFIG-04 (inline comments for all wheel config keys) is satisfied: every key in `default_config.py["wheel"]` has an inline `#` comment.
- Test isolation is correct: all I/O layer tests use `tmp_path`; no agent test writes directly to `config["wheel"]["positions_dir"]`. The `_position_loader` injectable seam is used throughout `test_past_context_injection.py`.
- PROP-LIFE-04, PROP-LIFE-05, PROP-LIFE-07 are all covered with `tmp_path` in `test_properties_life.py`.

---

## Recommendation

**Needs revision**

> F-01 (High) and F-02 through F-05 (Medium) require revision before approval. The minimum changes required are:
>
> 1. **F-01**: Either (a) update `default_config.py` to `near_the_money_pct=0.05` and `options_lookforward_days=45` and add exact-value assertions to `test_properties_config.py`, OR (b) update PROPERTIES §PROP-CONFIG-02 and REQ §7 defaults to `0.10`/`90` and add exact-value assertions to match the implementation. Both paths require exact-value assertions — the current range-only assertion is insufficient regardless.
>
> 2. **F-02**: Add a second sequential run to `TestPriorAnalystBiasPersistence.test_prior_analyst_bias_persisted_after_agent_run` with `"Sell"` → assert `prior_analyst_bias == "bearish"`.
>
> 3. **F-03**: Either (a) add a full graph integration test for equity passthrough that tracks tool calls and asserts on output state, OR (b) document as a known gap (alongside GAP-01 through GAP-05) with a PROP-ROUTE-01-INT property to be activated when the integration harness is available. Retag the existing routing tests with the correct PROP IDs.
>
> 4. **F-04**: Add a test case to `TestRollRule4` with `earnings_within_cycle=True, abs_delta=0.10` (assert fires) and `earnings_within_cycle=True, abs_delta=0.09` (assert does NOT fire).
>
> 5. **F-05**: Add integration-level tests for PROP-TRADE-08 and PROP-TRADE-09 that run the agents and check the output strike against injected spot/cost_basis values.
