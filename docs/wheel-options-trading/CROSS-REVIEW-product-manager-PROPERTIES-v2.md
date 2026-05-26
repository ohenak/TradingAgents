# Cross-Review: product-manager — PROPERTIES

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/PROPERTIES-wheel-options-trading.md
**Date:** 2026-05-26
**Iteration:** 2

---

## Prior Findings Disposition (v1 → v2)

The following table summarises how each finding from the v1 review was resolved in v0.2.0.

| Prior ID | Severity | Status | Resolution |
|----------|----------|--------|-----------|
| F-01 | High | Resolved | PROP-SCREEN-07 (liquidity), PROP-SCREEN-08 (spread), PROP-SCREEN-09 (affordability) added with correct substring assertions against REQ-SCREEN-01 AC6/AC7/AC8. |
| F-02 | High | Resolved | PROP-DATA-17 added; shortened-lookback path covered with substring check and valid-range assertion. |
| F-03 | High | Resolved | PROP-SCREEN-02 now cites `FSPEC-WHEEL-03 step 8c` (not REQ-SCREEN-02 AC2). PROP-SCREEN-03 now explicitly tests `rejection_reason=None` when `approved=True` and `rejection_reason` non-empty when `approved=False`. |
| F-04 | Medium | Resolved | PROP-TRADE-14 added; nearest-delta fallback annotation `"No strike matches Delta target; nearest available:"` tested. |
| F-05 | Medium | Resolved | PROP-SCREEN-10 (yield-filter-relaxed) and PROP-SCREEN-11 (earnings-filter-relaxed) added with `tradeable=True` and rationale substring assertions. |
| F-06 | Medium | Resolved | PROP-SCREEN-06 added; all-five-criteria positive-approval path (`approved=True`) tested. |
| F-07 | Medium | Resolved (acknowledged deferral) | GAP-01 updated to explicitly include ADR-WHEEL-01 CLI-layer disclosure deferral with rationale: `iv_assessment` propagation covered at integration layer (PROP-DATA-06, PROP-SCREEN-05); CLI assertion deferred pending CLI implementation. Disposition is acceptable. |
| F-08 | Low | Resolved | PROP-CONFIG-01 description now reads "20 required keys" (stale "18+" appeared only in the changelog line documenting the fix). |
| F-09 | Low | Acknowledged | GAP-05 added; PROP-SCREEN-15 scheduled for v0.3.0. |
| F-10 | Low | Acknowledged | GAP-04 elevated to Medium priority; PROP-LIFE-13 scheduled for v0.3.0. |

---

## Findings

No new findings were raised during this iteration.

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|

*(Table left intentionally empty — no findings.)*

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | PROP-SCREEN-10 and PROP-SCREEN-11 test the relaxation path at the `CspAgent` level (not `WheelAnalyst`). This is consistent with the FSPEC-WHEEL-04 §9a/§9b specification, but it means `WheelCandidateReport.approved` is not directly asserted in these two properties. Is the intent that a `WheelCandidateReport.approved=True` for a relaxed candidate is confirmed transitively through `CspDecision.tradeable=True`, or is a direct assertion on `WheelCandidateReport.approved` expected? No action required — flagging for implementation team awareness only. |
| Q-02 | GAP-04 (PROP-LIFE-13 for `cycle_pnl` formula verification) is scheduled for v0.3.0. Given that `cycle_pnl` feeds directly into the `cycle_annualised_return_pct` formula tested by PROP-LIFE-03, the sequencing is sound. Confirmed: no gap in coverage chain for the numeric AC3 / AC3a values. |

---

## Positive Observations

- All six High and Medium findings from v1 are fully and correctly resolved. The properties added in v0.2.0 are well-formed: they cite the correct REQ and FSPEC sources, specify deterministic test methods, and use the correct assertion patterns (substring checks, equality checks, schema validation calls).
- PROP-SCREEN-03 is now the cleanest coverage of REQ-SCREEN-02 AC2/AC3: four sub-cases covering all combinations of `approved` and `rejection_reason` validity.
- PROP-DATA-17 correctly uses the injectable `iv_series` test seam and avoids hardcoding the substring — the "contains at least one of `days`, `lookback`, or `available`" pattern accommodates the FSPEC's note template without over-specifying the exact string format.
- PROP-TRADE-14's test method is precise: it constrains the fixture so Filter A eliminates all strikes, forcing the relaxation path, and then asserts on `rationale` content rather than free-text.
- GAP-01 now explicitly names PM-F-07 (the CLI-level ADR-WHEEL-01 disclosure finding) and provides a clear deferral rationale. This is the correct handling — acknowledging the gap explicitly with a pending disposition is far preferable to leaving it undocumented.
- The coverage matrix (§9) has been correctly updated: REQ-SCREEN-01 now maps to PROP-SCREEN-06, PROP-SCREEN-07, PROP-SCREEN-08, PROP-SCREEN-09, PROP-SCREEN-10, and PROP-SCREEN-11, in addition to the prior entries.
- The renaming of old PROP-SCREEN-06/07/08 to PROP-SCREEN-12/13/14 was handled cleanly; no dangling references were left in the coverage matrix.

---

## Recommendation

**Approved**

All High and Medium findings from the v1 review have been resolved. No new High or Medium findings were identified in this iteration. The two Low-severity gaps (GAP-04 and GAP-05) are acknowledged with explicit follow-on dispositions (v0.3.0 entries). The PROPERTIES document v0.2.0 is approved to proceed to implementation.
