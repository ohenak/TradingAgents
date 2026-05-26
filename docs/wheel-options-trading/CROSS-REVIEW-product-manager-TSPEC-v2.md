# Cross-Review — Product Manager — TSPEC (v2)
# Document: TSPEC-wheel-options-trading.md v0.2.0

| Field | Value |
|---|---|
| Reviewer | Product Manager (PM-Review) |
| Date | 2026-05-25 |
| Iteration | 2 |
| Recommendation | Approved with minor changes |

---

## Resolution Status of Prior Findings

| Finding | Status | Notes |
|---|---|---|
| PM-TSPEC-01 — `get_next_earnings_date` did not return `within_options_cycle` | Resolved | Section 2.1.4 now computes `within_options_cycle` against the front-month expiry using a yfinance options fetch and includes the flag in the output string. REQ-DATA-04 AC1 and AC2 are now satisfiable at the function level. |
| PM-TSPEC-02 — `near_the_money_pct` and `options_lookforward_days` absent from REQ Section 7 | Partially resolved | Section 8.1 now carries explicit "NOTE: not in REQ Section 7 — TSPEC addition" inline comments for both keys, and Section 10.8 lists both in the Traceability Gap Summary table. The gap remains open by design (pending REQ v0.3.0 patch), but PROPERTIES authors have a clear citation path. This is acceptable for PLAN handoff, with the understanding that REQ v0.3.0 is produced before implementation begins. |
| PM-TSPEC-03 — `WheelPosition` adds undocumented fields (`csp_open_date`, `prior_analyst_bias`) | Resolved | Section 9.1 now carries explicit "NOTE: not in REQ-LIFE-02 schema table — TSPEC extension" annotations on both fields with functional justifications. Section 10.8 lists both in the Traceability Gap Summary. PROPERTIES has a clear citation path. |
| PM-TSPEC-04 — `cycle_annualised_return_pct` example diverges from REQ-LIFE-02 AC3a | Resolved | Section 9.4 explicitly states the TSPEC value (~33.21%) is authoritative and the REQ value (~33.25%) is a rounding error, to be corrected in REQ v0.3.0. Section 10.8 lists this in the Traceability Gap Summary. |
| PM-TSPEC-05 — Risk debate options context injection lacked file/injection-point specification | Resolved | Section 5.5 (new in v0.2.0) fully specifies the files modified, the `_build_options_context()` helper, the exact injection point (after `{market_context}`, before role-assignment instruction), the equity-only no-op path, and maps to each of the three REQ-TRADE-05 ACs. |
| PM-TSPEC-06 — `CspDecision` sentinel `delta=0.0` ambiguous against AC1 boundary | Resolved | Section 3.4 now carries an explicit note that REQ-TRADE-02 AC1 field-range constraints apply only when `tradeable=True`. The sentinel is formally documented as a failure-mode value exempt from field-range constraints. PROPERTIES test authors have clear guidance. |
| PM-TSPEC-07 — CC DTE lower bound deferred with no resolution path | Partially resolved | Section 10.1 item 5 still defers this to PLAN/PROPERTIES; Section 10.8 lists it as a Traceability Gap. The deferral is now explicitly documented and the shared `recommended_dte_low = 28` is the specified behaviour. This is acceptable but the ambiguity between REQ-TRADE-03 text ("21–45 DTE") and the config table ("28") must be resolved before implementation begins (see new finding PM-TSPEC-v2-01 below). |

---

## New or Remaining Findings

### [PM-TSPEC-v2-01] Low — REQ-TRADE-03 CC DTE lower-bound ambiguity remains unresolved and will block PROPERTIES authoring

**Requirement(s):** REQ-TRADE-03 (Description: "default 21–45 DTE"), REQ Section 7 (`recommended_dte_low` default `28`)

**Finding:** This item was PM-TSPEC-07 in v1 and remains open in v0.2.0 with an explicit deferral to PLAN (Section 10.1 item 5 and Section 10.8). The TSPEC correctly documents the conflict — REQ-TRADE-03 description says "default 21–45 DTE" for CC; the REQ Section 7 config table has a single shared `recommended_dte_low = 28` — but defers resolution.

The consequence for PROPERTIES authoring is concrete: there is no authoritative DTE lower bound for the CC filter pipeline (Filter B in `_filter_cc_candidates`). If PROPERTIES asserts "CC DTE >= 21" and the implementation uses 28, the test will either pass spuriously (all test inputs have DTE >= 28) or fail on edge-case inputs with DTE in [21, 27].

**Impact:** Low severity because the config is overridable. However, leaving this unresolved into PLAN authoring means the PLAN will carry a "TBD" on a concrete threshold, which can result in an implementation choice made ad-hoc at code-writing time with no PROPERTIES coverage.

**Suggested resolution:** Choose one of two paths before PLAN authoring begins:

Option A — Keep a single shared `recommended_dte_low = 28` for both CSP and CC. Update REQ-TRADE-03 description to read "default 28–45 DTE" (REQ v0.3.0 patch). Update the TSPEC Section 10.1 deferral to mark this as "resolved: 28 for both".

Option B — Add a distinct `cc_recommended_dte_low = 21` key to REQ Section 7 and the TSPEC config block (Section 8.1). This adds one config key and one env var entry but fully aligns with the REQ description text.

Either option takes fewer than 15 minutes to implement; the PM should decide before the PLAN authoring sprint begins.

---

### [PM-TSPEC-v2-02] Low — `within_options_cycle` now uses front-month expiry but REQ-DATA-04 AC2 specifies a user-supplied expiration date

**Requirement(s):** REQ-DATA-04 (AC1, AC2)

**Finding:** PM-TSPEC-01 in v1 identified that `within_options_cycle` was absent from the function output. TSPEC v0.2.0 addresses this by computing `within_options_cycle` against the **front-month expiry** fetched from yfinance: `within_options_cycle = (earnings_date <= front_month_expiry_date)`.

REQ-DATA-04 AC2 states: "`within_options_cycle` is `True` because the earnings event falls within the option's remaining life (earnings date < expiry date)." The REQ AC2 scenario gives "Earnings is 10 days away and the next expiration is 30 days away" — in this scenario the front-month expiry IS the 30-day expiration, so the TSPEC's approach produces the correct answer.

However, for CspAgent and CcAgent use cases the relevant expiry is the specific trade expiration being evaluated, not the generic front-month. The TSPEC's `get_next_earnings_date` now returns a fixed flag anchored to the front-month, which may differ from the expiry the calling agent is working with (e.g., CspAgent may be evaluating a 40-DTE expiry while the front-month is 25 days away). In that case, `within_options_cycle` would be `True` (earnings falls before the front-month) even though the specific 40-DTE expiry being evaluated clears earnings.

**Impact:** Low — The CspAgent deterministic filter (Section 5.2 Filter B) applies an independent hard earnings check: `earnings_date > expiration_date` using the candidate expiration. The `within_options_cycle` flag from the raw tool is advisory context for the LLM prompt, not the gate used by the filter. The filter's independent check is more specific and correct. The flag from the tool output may be misleading in multi-expiry scenarios, but will not cause incorrect trade decisions.

**Suggested resolution:** Add a brief note in TSPEC Section 2.1.4 clarifying that `within_options_cycle` in the tool output uses the front-month as proxy, and that the authoritative earnings gate for trade decisions is performed independently in each agent's filter function (CspAgent Filter B, CcAgent Filter C). This ensures PROPERTIES authors understand that REQ-DATA-04 AC2 is verified at the function level using front-month, while trade-level earnings clearance is verified separately in agent-level tests. No code change required.

---

### [PM-TSPEC-v2-03] Low — `WheelAnalyst` graph insertion point (between Trader and Aggressive Analyst) may conflict with REQ-LIFE-01 AC2 routing

**Requirement(s):** REQ-LIFE-01 (AC2: "screening → analyst pipeline + WheelAnalyst + CspAgent nodes are visited"), REQ-SCREEN-01 (AC5)

**Finding:** TSPEC Section 6.1 specifies that `WheelAnalyst` is inserted between the Trader node and the Aggressive Analyst node: `workflow.add_edge("Trader", "wheel_analyst"); workflow.add_edge("wheel_analyst", "Aggressive Analyst")`.

REQ-LIFE-01 AC2 says `wheel_phase="screening"` routes to "analyst pipeline + WheelAnalyst + CspAgent." The TSPEC graph topology has `route_wheel_phase` routing `"screening"` to `first_analyst_node` (the first standard analyst), which then flows through the full pipeline to WheelAnalyst. This is correct for the AC2 intent.

However, CspAgent is not in the linear edge chain after WheelAnalyst. The `route_wheel_phase` mapping (Section 6.1) shows `first_analyst_node`, `roll_check_agent`, `cc_agent`, and `wheel_cycle_summary` as possible routes from START — but `csp_agent` is not a direct START target. The flow from WheelAnalyst to CspAgent is implicit: WheelAnalyst ends and presumably CspAgent runs next in the "screening" flow, but the exact edge connecting them is not specified in TSPEC Section 6.1.

**Impact:** Low — the TSPEC Section 10.1 item 4 defers the `tools_options` ToolNode wiring to PLAN. The CspAgent → graph edge from WheelAnalyst is similarly implicit. A PLAN author reading only Section 6.1 may miss that CspAgent needs to be placed after WheelAnalyst in the "screening" path.

**Suggested resolution:** Add a note to Section 6.1 or a new row in the route table showing the `screening` path: `first_analyst_node → ... → Trader → wheel_analyst → Aggressive Analyst → ... → csp_agent`. The explicit edge from WheelAnalyst to the next node in the "screening" flow (either CspAgent directly, or Aggressive Analyst, after which CspAgent must be triggered) should be identified so the PLAN author has a clear edge specification to implement.

---

## Summary

TSPEC v0.2.0 successfully resolves all seven findings from the v1 PM cross-review. The resolutions are substantive and accurate:

- `within_options_cycle` is now computed and returned by `get_next_earnings_date` (PM-TSPEC-01 resolved).
- Both TSPEC-only config keys have proper inline annotations and a traceability gap table (PM-TSPEC-02 partially resolved; gap acknowledged and managed).
- Both extra `WheelPosition` fields have functional justifications and annotations (PM-TSPEC-03 resolved).
- The 33.21% formula discrepancy is explicitly documented with TSPEC authority asserted (PM-TSPEC-04 resolved).
- Section 5.5 provides a complete Risk Debate injection specification meeting all three REQ-TRADE-05 ACs (PM-TSPEC-05 resolved).
- The `CspDecision` sentinel is now formally scoped to the `tradeable=False` path (PM-TSPEC-06 resolved).
- The CC DTE deferral is documented in the traceability gap table (PM-TSPEC-07 partially resolved).

Three new minor findings are raised. Two are documentation clarifications (PM-TSPEC-v2-02 on the `within_options_cycle` proxy vs. per-trade use, and PM-TSPEC-v2-03 on the CspAgent edge from WheelAnalyst in the screening path). One (PM-TSPEC-v2-01) is the CC DTE lower-bound ambiguity that was already PM-TSPEC-07 in v1 and remains genuinely open — it requires a product decision before PLAN authoring begins, but does not require further TSPEC revision. All three are Low severity.

Traceability across all 26 REQ items is complete. All 10 user stories (US-01 through US-10) are addressed. All 17 REQ Section 7 config keys are covered by the TSPEC (two additional TSPEC-only keys are documented with annotations). All 7 NFR items are addressed. The TSPEC is approved for PLAN handoff provided the CC DTE lower-bound decision (PM-TSPEC-v2-01) is resolved as a pre-PLAN PM decision.

---

## Approved Items

The following areas were reviewed and are approved without findings in this iteration:

- **All seven v1 finding resolutions** are accepted as described in the Resolution Status table above.
- **Section 5.5 Risk Debate injection** — `_build_options_context()` correctly gates on `csp_decision`/`cc_decision` non-None presence, correctly falls back to the raw string on parse failure, and correctly returns `""` in equity-only mode. The three REQ-TRADE-05 ACs are directly traceable to the specified behaviour.
- **`within_options_cycle` implementation (Section 2.1.4)** — the front-month proxy approach satisfies REQ-DATA-04 AC1 and AC2 at the function level. The advisory caveat in PM-TSPEC-v2-02 is documentation-only and does not affect correctness.
- **`WheelCandidateReport` `model_validator` (Section 3.3)** — enforces `approved=True → positive strike range` and `approved=False → non-empty rejection_reason`. Correctly allows `[0.0, 0.0]` sentinel under `approved=False`. Satisfies REQ-SCREEN-02 AC2 and AC3.
- **`load_latest_open_position` integer sort fix (Section 9.3)** — the `_cycle_number()` extractor with `int()` parse and `reverse=True` correctly handles cycle numbers ≥ 10. The comment "String sort MUST NOT be used" is appropriate and will prevent regression.
- **Traceability Gap Summary (Section 10.8)** — all five open gaps are documented with resolution paths. PROPERTIES authors have unambiguous citation guidance.
- **Config section (Section 8.1)** — all 18 keys have inline comments satisfying REQ-NFR-07. The two TSPEC-only keys have explicit "NOTE: not in REQ Section 7" annotations. The `_WHEEL_ENV_OVERRIDES` dict (Section 8.2) covers all 18 keys plus the two TSPEC additions (20 env vars total). REQ-NFR-03 is satisfied for all 17 REQ-specified keys.
- **Requirements traceability — all 26 REQ items covered:**
  - REQ-DATA-01 through REQ-DATA-05: Sections 2.1.1–2.2 and interface.py spec — complete.
  - REQ-SCREEN-01 through REQ-SCREEN-03: Sections 5.1, 3.3, 7.1 — complete.
  - REQ-TRADE-01 through REQ-TRADE-05: Sections 5.2, 3.4, 5.3, 3.5, 5.5 — complete.
  - REQ-LIFE-01 through REQ-LIFE-06: Sections 3.1, 6.1–6.3, 9, 7.2 — complete.
  - REQ-NFR-01 through REQ-NFR-07: covered across Sections 2–9 — complete.
- **User story coverage — all 10 US items addressed:**
  - US-01 (screening): WheelAnalyst (Section 5.1) — covered.
  - US-02 (IV environment): `get_iv_metrics` (Section 2.1.2), WheelAnalyst Criterion 1 — covered.
  - US-03 (CSP recommendation): CspAgent (Section 5.2), CspDecision (Section 3.4) — covered.
  - US-04 (CC recommendation): CcAgent (Section 5.3), CcDecision (Section 3.5) — covered.
  - US-05 (position tracking): WheelPosition (Section 9), `wheel-status` CLI (Section 7.2) — covered.
  - US-06 (roll/hold/close): RollCheckAgent (Section 5.4), RollDecision (Section 3.6) — covered.
  - US-07 (P&L and annualised yield): `wheel_cycle_summary` (Section 6.3), `wheel-status` CLI (Section 7.2) — covered.
  - US-08 (earnings avoidance): earnings check in CspAgent Filter B, CcAgent Filter C, WheelAnalyst Criterion 3, `get_next_earnings_date` (Section 2.1.4) — covered.
  - US-09 (familiar CLI): `MessageBuffer` section key, `wheel-status` sub-command (Sections 7.1–7.2) — covered.
  - US-10 (env var config): `_WHEEL_ENV_OVERRIDES` and `_apply_nested_env_overrides` (Section 8.2) — covered.
