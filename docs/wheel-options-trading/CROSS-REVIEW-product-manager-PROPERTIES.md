# Cross-Review: product-manager — PROPERTIES

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/PROPERTIES-wheel-options-trading.md
**Date:** 2026-05-26
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-01 | High | Local | REQ-SCREEN-01 AC6, AC7, and AC8 have no corresponding properties. The FSPEC mandates exact rejection-reason substrings: `"Insufficient liquidity"` (AC6), `"Chain spread too wide"` (AC7), and `"Stock price exceeds cash management limit"` (AC8). These are product-critical acceptance criteria for the WheelAnalyst and are not covered anywhere in PROP-SCREEN. The coverage matrix maps REQ-SCREEN-01 only to PROP-SCREEN-01, PROP-SCREEN-05, and PROP-SCREEN-07, none of which test these criteria. | REQ-SCREEN-01 AC6, AC7, AC8; FSPEC-WHEEL-03 business rules |
| F-02 | High | Local | REQ-DATA-02 AC2 (shortened-lookback path) is not covered by any property. When fewer than `lookback_days` trading days are available, the FSPEC specifies that computation must proceed on available data and the report string must include the note `"Lookback shortened to {n} trading days"`. The coverage matrix maps REQ-DATA-02 to PROP-DATA-03 through PROP-DATA-07 and PROP-DATA-16, but none of these test this path. This is a user-visible behaviour for tickers with short history. | REQ-DATA-02 AC2; FSPEC-WHEEL-02 step 3a |
| F-03 | High | Local | PROP-SCREEN-02 has an incorrect source attribution that conceals a missing property. PROP-SCREEN-02 is described as testing that `recommended_strike_range` has correct values when `approved=True`, and it cites `REQ-SCREEN-02 AC2` as its source. However, REQ-SCREEN-02 AC2 states: "When `approved=True`, `rejection_reason` is `None`." The property tests the wrong thing against the wrong AC. A separate property for REQ-SCREEN-02 AC2 (asserting `rejection_reason is None` when `approved=True`) is missing. Strike-range validation is a valid property, but it should be sourced from FSPEC-WHEEL-03 step 8, not from REQ-SCREEN-02 AC2. | REQ-SCREEN-02 AC2; FSPEC-WHEEL-03 step 8 |
| F-04 | Medium | Local | REQ-TRADE-01 AC2 ("nearest available strike" note when no delta target match) is not covered by any property. The FSPEC specifies that `CspDecision.rationale` must contain `"No strike matches Delta target; nearest available: {delta}"` when Filter A eliminates all strikes and the nearest-Delta relaxation path activates. This is a distinct user-facing output path. The coverage matrix maps REQ-TRADE-01 to PROP-TRADE-08, PROP-TRADE-11, and PROP-TRADE-12, but none of these test the relaxation note. | REQ-TRADE-01 AC2; FSPEC-WHEEL-04 step 9c |
| F-05 | Medium | Local | FSPEC-WHEEL-04 steps 9a and 9b (progressive relaxation — yield filter relaxed, then earnings filter relaxed) have no corresponding properties despite being formally specified FSPEC acceptance tests. The coverage matrix for REQ-TRADE-01 does not include these paths. These are important safety behaviours: when the relaxation path activates, the agent must note it in the output so the user knows the recommendation was generated under relaxed constraints. | REQ-TRADE-01; FSPEC-WHEEL-04 steps 9a, 9b (FSPEC-TE-08 resolution ATs) |
| F-06 | Medium | Local | REQ-SCREEN-01 AC1 (all five criteria pass → `approved=True`) has no dedicated property. The coverage matrix maps REQ-SCREEN-01 to PROP-SCREEN-01, PROP-SCREEN-05, and PROP-SCREEN-07. PROP-SCREEN-01 tests schema validation (model_validate), not the WheelAnalyst's five-criterion approval logic. There is no property asserting that when all five criteria are satisfied, `WheelCandidateReport.approved == True`. | REQ-SCREEN-01 AC1; FSPEC-WHEEL-03 step 7a |
| F-07 | Medium | Local | The ADR-WHEEL-01 zero-variance disclosure at the CLI layer has no property. PROP-DATA-05 and PROP-DATA-06 cover the data-layer and WheelAnalyst-level disclosure. However, PROP-DATA-06 explicitly states "The CLI must not present a sentinel-generated `iv_environment = 'normal'` result without this disclosure," but there is no CLI-level property to enforce this. GAP-01 defers CLI properties entirely, but this disclosure is a product integrity requirement tied to ADR-WHEEL-01, not merely a display concern. Consider adding an integration property (or noting its deferral explicitly in GAP-01) that links the sentinel note propagation all the way to the `console.export_text()` assertion level. | ADR-WHEEL-01; REQ-SCREEN-03; PROP-DATA-06 |
| F-08 | Low | Local | PROP-CONFIG-01 description text says `"config['wheel'] must contain all 18+ required keys"` but the test method and body enumerate exactly 20 keys, and PROP-CONFIG-02 is titled with the note that the 20-key count comes from TSPEC §8.1. The `"18+"` in the description is stale (it was the count before `near_the_money_pct` and `options_lookforward_days` were added in REQ v0.3.0). This will cause confusion when the test is authored. | REQ §7 (v0.3.0 adds `near_the_money_pct` and `options_lookforward_days`); TSPEC §8.1 |
| F-09 | Low | Local | FSPEC-WHEEL-03 step 8d (price-based fallback for `recommended_strike_range` when Delta-anchored computation fails) has no property. The fallback formula is `[spot_price × (1 − target_csp_delta_high), spot_price × (1 − target_csp_delta_low)]`, rounded to nearest $0.50. This is a user-visible output path that requires a distinct test. | FSPEC-WHEEL-03 step 8d |
| F-10 | Low | Local | GAP-05 notes that the `cycle_pnl` formula is not separately verified and recommends a follow-on PROP-LIFE-13. However, REQ-LIFE-02 AC3 explicitly states the expected numeric value (`cycle_pnl = (145 − 140 + 4.30) × 100 = 930`), making this an AC-level verification gap, not merely a "nice to have." The gap is acknowledged, but it should be elevated to a Medium-priority gap or scheduled for inclusion in the next PROPERTIES iteration rather than a follow-on revision. | REQ-LIFE-02 AC3; GAP-05 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | PROP-SCREEN-07 tests that when `"wheel"` is not in `selected_analysts`, the WheelAnalyst node is absent and `wheel_candidate_report` is not set. This covers REQ-SCREEN-01 AC5. Is this intended to be the sole property for that AC, or is a separate property planned to assert the existing equity pipeline output fields are unmodified (i.e., a positive assertion on equity-mode behaviour when wheel is excluded)? PROP-ROUTE-01 and PROP-ROUTE-09 cover the routing-level equivalent, but PROP-SCREEN-07 is scoped to the SCREEN domain — there may be value in aligning these two. |
| Q-02 | GAP-01 defers all CLI properties (REQ-SCREEN-03) pending confirmation of the Rich `Console(file=StringIO())` harness. The FSPEC-WHEEL-08 already fully specifies the panel title, body strings, and exact `console.export_text()` assertions. Is the deferral because the harness is unconfirmed in the test infrastructure, or because the CLI code itself is not yet implemented? If the latter, the properties could be drafted now with the `@pytest.mark.skip(reason="CLI not yet implemented")` guard, so they are ready to activate when the code lands. |
| Q-03 | The PROPERTIES document has 50 properties across 7 domains. The domain table in §1 lists six domains (DATA, SCREEN, TRADE, LIFE, ROUTE, FALLBACK, CONFIG = 7 items) but the overview text says "six domains." Is the count in the prose intentionally omitting CONFIG, or is this a minor inconsistency to fix in the next revision? |

---

## Positive Observations

- The zero-variance sentinel (ADR-WHEEL-01) is excellently covered across the data layer (PROP-DATA-05, unit), agent integration (PROP-DATA-06, PROP-SCREEN-05), and the sentinel constant enforcement rule (PROP-FALLBACK-13). The three-layer coverage model is exactly right.
- The fallback domain (PROP-FALLBACK-01 through PROP-FALLBACK-13) is comprehensive and correctly uses the 4-agents × 3-scenarios structure. The import-not-hardcode rule in PROP-FALLBACK-13 is a strong process invariant that will catch sentinel string drift.
- The coverage matrix in §9 is detailed and honest — gaps are listed explicitly with dispositions rather than hidden. This transparency is exactly what a reviewer needs.
- PROP-LIFE-04 (integer-sort regression guard for `load_latest_open_position`) and PROP-LIFE-05 (atomic write test) both map cleanly to named ADRs (ADR-WHEEL-05), making them easy to maintain.
- PROP-TRADE-11 correctly tests delta filter boundary inclusivity with five test cases (0.15, 0.20, 0.25, 0.30, 0.35), including explicit in/out assertions at both boundaries. This matches the FSPEC-TE2-01 resolution requirement.
- The known gaps (§10) are well-reasoned: GAP-01 (CLI), GAP-02 (wheel-status), and GAP-03 (performance) are all correctly deferred with clear rationale. GAP-04 (prior_analyst_bias persistence) is honest about partial coverage.
- PROP-CONFIG-05 (options_lookforward_days >= recommended_dte_high guard) is a product-important invariant from TSPEC §8.3 that is often overlooked in configuration validation. Its inclusion at P1 level is appropriate.

---

## Recommendation

**Needs revision**

The following items must be addressed before this PROPERTIES document is approved:

1. **F-01 (High):** Add properties for REQ-SCREEN-01 AC6, AC7, and AC8 — the three rejection-reason string properties for WheelAnalyst's liquidity, spread, and price-affordability criteria.
2. **F-02 (High):** Add a property for REQ-DATA-02 AC2 — the shortened-lookback path (`iv_series` with fewer days than `lookback_days`, assert the report string note).
3. **F-03 (High):** Fix PROP-SCREEN-02's source attribution (change from `REQ-SCREEN-02 AC2` to `FSPEC-WHEEL-03 step 8`). Add a new property for REQ-SCREEN-02 AC2 asserting `rejection_reason is None` when `approved=True` and vice versa.
4. **F-04 (Medium):** Add a property for REQ-TRADE-01 AC2 — the nearest-delta relaxation path note (`"No strike matches Delta target; nearest available: {delta}"` in rationale).
5. **F-05 (Medium):** Add properties for FSPEC-WHEEL-04 steps 9a and 9b — yield-filter-relaxed and earnings-filter-relaxed candidate set paths.
6. **F-06 (Medium):** Add a property asserting the positive-approval path for REQ-SCREEN-01 AC1 — when all five WheelAnalyst criteria are satisfied, `WheelCandidateReport.approved == True`.
