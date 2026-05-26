# Cross-Review — Test Engineer — FSPEC (v2)
# Document: FSPEC-wheel-options-trading.md v0.2.0

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Iteration | 2 |
| Recommendation | Approved with minor changes |

---

## Resolution Status of Prior Findings

| Finding | Status | Notes |
|---|---|---|
| FSPEC-TE-01 | Resolved | A new unit AC is added (lines 382–383) that exercises Criterion 5 via an injectable `investment_plan` containing `recommendation=Underweight`. The exact extraction path (`investment_plan` → `ResearchPlan.recommendation` → Literal mapping) is now specified in Business Rules, making the seam deterministic. |
| FSPEC-TE-02 | Resolved | `WheelPosition.prior_analyst_bias: Optional[str]` is now defined in FSPEC-WHEEL-06 Business Rules. Rule 5's firing condition (`prior_analyst_bias == "bullish"` AND `current_analyst_bias == "bearish"`) is fully deterministic. The corresponding integration AC (lines 821–825) is now testable with a simple `WheelPosition` fixture. |
| FSPEC-TE-03 | Resolved | All three previously ambiguous "Who: Agent" ACs now include parenthetical fixture and mock annotations (`mocked LLM returning the first eligible candidate from the fixture`). The assertions on `strike` and `annualised_yield_pct` are explicitly justified by the mocked LLM returning the fixture's first eligible strike. |
| FSPEC-TE-04 | Resolved | Two new boundary unit ACs added (lines 213–222): `iv_rank == 25.0` → `"normal"` and `iv_rank == 50.0` → `"elevated"`. Both use the `iv_series` seam and are fully deterministic. |
| FSPEC-TE-05 | Partially resolved | The lower boundary for CSP Filter A (`abs(delta) == target_csp_delta_low`) now has an AC (lines 520–524). The upper boundary (`abs(delta) == target_csp_delta_high`) is still unaddressed for CSP, and neither boundary for CC Filter B has an AC. See FSPEC-TE2-01. |
| FSPEC-TE-06 | Partially resolved | The Rule 3 exact-boundary AC (`spot_price == csp_strike × 0.85` fires) is added (lines 827–831). The complementary "just above boundary does not fire" case (`spot_price == csp_strike × 0.851`) remains absent. Rule 4's deep-OTM boundary (`abs(delta) == 0.10` → Rule 4 fires; `abs(delta) == 0.09` → Rule 4 does not fire) is still unaddressed. See FSPEC-TE2-02. |
| FSPEC-TE-07 | Resolved | All ACs now carry `*Test level:*` annotations (`Unit`, `Integration`, `Smoke`). The mapping is consistent: deterministic rule assertions are `Unit`, full-agent-with-mocked-LLM flows are `Integration`, live-network ACs are `Smoke`. |
| FSPEC-TE-08 | Resolved | Two new unit ACs for relaxation branches 9a and 9b added (lines 532–542). Each specifies the fixture condition, the expected `tradeable` outcome, and the exact note string that must appear in `rationale` (`"yield_filter_relaxed"`, `"earnings_filter_relaxed"`). |
| FSPEC-TE-09 | Partially resolved | ACs for Rule 3+1 and Rule 2+1 simultaneous firing added (lines 833–843). The Rule 5+Rule 4 combination (priority: `"analyst_update"` > `"earnings_rule"`) and the Rule 3+Rule 2 combination (priority: breach > DTE) remain without ACs. See FSPEC-TE2-03. |
| FSPEC-TE-10 | Resolved | `rationale` schema-contract ACs added to all four agent sections (FSPEC-WHEEL-03, FSPEC-WHEEL-04, FSPEC-WHEEL-05, FSPEC-WHEEL-06). Each asserts: "any terminal output → `rationale` is a non-empty string." |
| FSPEC-TE-11 | Resolved | FSPEC-WHEEL-02 AC1 is now explicitly annotated `Smoke (requires live yfinance network call)`. This correctly places it outside the fast CI gate. |
| FSPEC-TE-12 | Resolved | The `approved=True` AC now asserts `recommended_strike_range` is a list of two positive floats, both greater than 0.0 (lines 333–335). |
| FSPEC-TE-13 | Not resolved | The Open Question for FSPEC-WHEEL-07 (whether CSP-to-stock_owned transition is manual or automated) remains explicitly unresolved. The AC at lines 993–997 still names no function to call and cannot be automated without knowing the transition mechanism. This finding is carried forward as FSPEC-TE2-04. |

---

## New or Remaining Findings

### [FSPEC-TE2-01] Medium — Delta boundary completeness: upper CSP bound and both CC Filter B bounds lack ACs

**FSPEC section:** FSPEC-WHEEL-04, step 6 (Filter A); FSPEC-WHEEL-05, step 10 (Filter B)

**Finding:** The v0.2.0 AC for CSP Filter A (lines 520–524) tests only the lower boundary (`abs(delta) == target_csp_delta_low` is retained). The upper boundary (`abs(delta) == target_csp_delta_high` is retained) has no AC. For CC Filter B, neither the lower nor the upper boundary has any AC. All four boundary cases are specified as inclusive in the Business Rules (`target_csp_delta_low <= abs(delta) <= target_csp_delta_high`; `target_cc_delta_low <= delta <= target_cc_delta_high`).

**Impact:** An implementation using `abs(delta) < target_csp_delta_high` (strict upper) would pass all existing ACs but silently exclude boundary strikes. The CC filter boundary is entirely uncovered — any off-by-one in either direction passes all ACs.

**Suggested resolution:** Add unit ACs (mocked chain and Greeks):
- CSP Filter A upper: a strike with `abs(delta) == target_csp_delta_high` → retained in filtered set.
- CC Filter B lower: a call strike with `delta == target_cc_delta_low` → retained.
- CC Filter B upper: a call strike with `delta == target_cc_delta_high` → retained.

---

### [FSPEC-TE2-02] Medium — Rule 3 "does not fire" case and Rule 4 deep-OTM boundary are still missing

**FSPEC section:** FSPEC-WHEEL-06, Rule 3; Rule 4

**Finding:** The new AC (lines 827–831) confirms that `spot_price == csp_strike × 0.85` fires Rule 3 (inclusive boundary). The complementary negative case (`spot_price == csp_strike × 0.851` → Rule 3 does NOT fire) is absent. Without it, an implementation using `spot_price <= csp_strike × 0.851` (wrong constant) passes all ACs.

For Rule 4, the deep-OTM boundary from FSPEC-TE-06 remains entirely unaddressed in v0.2.0. The FSPEC specifies:
- `abs(current_delta) < 0.10` → deep OTM → Rule 4 does NOT fire.
- `abs(current_delta) == 0.10` → NOT deep OTM → Rule 4 FIRES (the boundary is exclusive on the deep-OTM side).

An implementation using `abs(delta) <= 0.10` (inclusive) for the deep-OTM guard would incorrectly suppress Rule 4 when `abs(delta) == 0.10`, and would pass all existing ACs.

**Suggested resolution:** Add two unit ACs:
- Rule 3 negative boundary: `spot_price = csp_strike × 0.851` → Rule 3 does not fire.
- Rule 4 deep-OTM boundary: (a) `abs(current_delta) == 0.10` with earnings within DTE → Rule 4 fires (`"earnings_rule"`). (b) `abs(current_delta) == 0.09` with earnings within DTE → Rule 4 does not fire.

---

### [FSPEC-TE2-03] Low — Two high-priority multi-rule combinations still lack ACs

**FSPEC section:** FSPEC-WHEEL-06, step 7 (priority order: Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1)

**Finding:** v0.2.0 adds ACs for Rule 3+Rule 1 and Rule 2+Rule 1. The following combinations remain without ACs despite being explicitly listed in the priority order:

1. **Rule 5 + Rule 4 fire simultaneously:** Priority says Rule 5 > Rule 4. Final `trigger_reason` must be `"analyst_update"`, not `"earnings_rule"`. No AC covers this.
2. **Rule 3 + Rule 2 fire simultaneously:** Priority says Rule 3 > Rule 2. Final action must come from Rule 3 (either `"breach_rule_roll"` or `"breach_rule_close"`), not from Rule 2 (`"dte_rule"`). No AC covers this.

These two combinations are the most operationally plausible multi-rule events: a stock can be deep enough in breach to trigger Rule 3 while simultaneously approaching DTE (Rule 2), and analyst sentiment can flip bearish (Rule 5) at the same time earnings are within the option window (Rule 4).

**Impact:** An implementation that evaluates rules in the wrong order or short-circuits on any CLOSE decision would incorrectly handle these combinations and pass all current ACs.

**Suggested resolution:** Add two unit ACs (mocked `WheelPosition` and rule inputs, no LLM required):
- Rule 3 fires (breach, `current_value_pct_of_premium >= 50`) AND Rule 2 fires (`current_dte <= dte_to_roll`) → final `trigger_reason == "breach_rule_roll"`, `action == "ROLL"`.
- Rule 5 fires (`prior_analyst_bias == "bullish"`, `current_analyst_bias == "bearish"`) AND Rule 4 fires (earnings within DTE, not deep OTM) → final `trigger_reason == "analyst_update"`, `action == "CLOSE"`.

---

### [FSPEC-TE2-04] Medium — FSPEC-WHEEL-07 phase-transition AC4 remains unautomatable (carry-forward from FSPEC-TE-13)

**FSPEC section:** FSPEC-WHEEL-07, AC4 (lines 993–997); Open Questions (line 1012)

**Finding:** The Open Question for the `"csp_open"` → `"stock_owned"` transition ("manual or automated?") is explicitly unresolved in v0.2.0. The AC states "Given: Phase transition occurs — When: State is updated — Then: `wheel_phase` changes." Neither the function that performs the write nor the automation boundary is named. Without this, the TE cannot determine whether to write a unit test (call a named function with a `WheelPosition` fixture), an integration test (run the graph with a mocked broker event), or mark the AC as manual-only.

**Impact:** PROPERTIES authoring will require an undocumented assumption about the automation boundary for this transition. If the assumption is wrong, the written property test will not match the implementation.

**Suggested resolution:** Either (a) resolve the Open Question before TSPEC authoring begins — if the trigger is always manual, mark the AC `[manual]` and exclude it from automated test plans; or (b) name the Python function that reads `WheelPosition.assignment_date` and updates `AgentState["wheel_phase"]` so it can be unit-tested directly.

---

### [FSPEC-TE2-05] Medium — FSPEC-WHEEL-08 AC1 asserts on `"WheelCandidateReport"` but the panel title is `"Wheel Suitability"` — assertion string is undefined

**FSPEC section:** FSPEC-WHEEL-08, AC1 (line 1075); Open Questions (line 1091)

**Finding:** AC1 asserts that `console.export_text()` contains `"Wheel Suitability"` (the panel title) and `"IV Rank"`. However, the FSPEC's own Open Question (line 1091) notes that REQ-SCREEN-03 AC1 checks for the string `"WheelCandidateReport"` in the output — a different string from the panel title `"Wheel Suitability"`. The FSPEC acknowledges: "If the AC asserts on that exact string, the panel title or a subtitle must include it." This conflict is not resolved in v0.2.0.

**Impact:** The test engineer cannot write a deterministic assertion for AC1 without knowing which string will actually appear in the exported terminal output. If the implementation uses `"Wheel Suitability"` as the panel title (as the Business Rules state), then asserting on `"WheelCandidateReport"` will fail. If the implementation includes `"WheelCandidateReport"` as a subtitle to satisfy the REQ, then asserting on `"Wheel Suitability"` may still pass but the test intent is ambiguous. Either the FSPEC must specify that both strings appear, or the REQ upstream string must be updated.

**Suggested resolution:** Resolve the Open Question in FSPEC-WHEEL-08 before PROPERTIES authoring: either (a) update REQ-SCREEN-03 AC1 to assert on `"Wheel Suitability"`, or (b) add a business rule requiring a subtitle or section label containing `"WheelCandidateReport"` so both strings are present and both assertions are valid. The AC must then specify exactly which string(s) are asserted.

---

### [FSPEC-TE2-06] Low — "No rule fired" and "Rule 1 fired" are aliased to the same output — the no-trigger path has no dedicated test

**FSPEC section:** FSPEC-WHEEL-06, step 7 (lines 737–738); Business Rules (line 757)

**Finding:** The FSPEC explicitly states: "No rule fired → `action = 'HOLD'`, `trigger_reason = 'profit_capture'`" and "This aliases both 'Rule 1 fired — profit target hit' and 'no rule fired — position within normal parameters.'" The aliasing is documented as intentional. However, no AC tests the "no rule fired" path specifically. The existing AC for Rule 1 (lines 797–801) covers the case where `current_value_pct_of_premium == 50.0` (Rule 1 fires), but there is no AC for a position where `current_value_pct_of_premium == 30.0` (well below 50%) AND `current_dte == 30` (well above `dte_to_roll`) AND no breach AND no earnings — i.e., a genuinely quiescent position where no rule should fire.

**Impact:** Without a "no rule fires" AC, an implementation that unconditionally sets `trigger_reason = "profit_capture"` regardless of rule evaluation (and never evaluates rules) would pass all current ACs. The "no rule fires" path is the steady-state for most option positions and represents the most frequently executed code path in production.

**Suggested resolution:** Add a unit AC: "Given: `current_value_pct_of_premium = 30.0`, `current_dte = 30`, no breach, no upcoming earnings, `prior_analyst_bias = None` — When: RollCheckAgent rule evaluation runs — Then: `action == 'HOLD'`, `trigger_reason == 'profit_capture'`, and all five rule evaluations return False (verifiable via instrumentation or by asserting no rule-specific trigger strings appear in `rationale`)."

---

### [FSPEC-TE2-07] Low — FSPEC-WHEEL-09 prompt-content ACs do not specify the exact field label format, making string assertions implementation-dependent

**FSPEC section:** FSPEC-WHEEL-09, AC1 (lines 1153–1157); Business Rules (line 1132)

**Finding:** The Business Rules state: "The injected context is formatted as a structured text block (not raw JSON) for LLM readability. Field names and values are written as `'Field: value'` pairs, one per line." AC1 asserts that the prompt contains `"mid_premium"` and `"probability_of_profit"` as substring matches. However, the Business Rules only say fields appear as `"Field: value"` pairs — they do not specify whether the key is `"mid_premium"` (snake_case), `"Mid Premium"` (title case), or `"Mid-Premium"` (hyphenated). An implementation using `"Mid Premium: 1.50"` would not contain the substring `"mid_premium"` and would fail AC1, even though it satisfies the Business Rule.

**Impact:** The AC could fail against a correct implementation, or pass against an incorrect one, depending purely on formatting choices made by the implementer.

**Suggested resolution:** Either (a) specify in the Business Rules that keys must use snake_case matching the schema field name (e.g., `"mid_premium: 1.50"`), making the AC assertion unambiguous; or (b) change the AC assertions to match the exact format specified (e.g., assert on `"Mid Premium"` if title case is the chosen format). The Business Rules and ACs must agree on the key format.

---

## Summary

v0.2.0 resolves the three High findings from iteration 1 and most of the Medium/Low findings. The document has materially improved: all ACs now carry test level annotations, the `iv_series` boundary ACs are exemplary, the Criterion 5 and Rule 5 seams are properly specified via structured field extraction, the relaxation branch ACs provide actionable fixture specifications, and the `rationale` schema contract is now universally asserted. Seven findings from iteration 1 are fully resolved.

The remaining issues are bounded: two are partial resolutions of prior findings (delta upper bound, Rule 4 deep-OTM boundary, and two priority-order combinations); two are unresolved open questions that were already acknowledged in the document (FSPEC-WHEEL-07 assignment trigger, FSPEC-WHEEL-08 panel title conflict); and three are new issues introduced by the v0.2.0 additions (Rule 1/no-rule aliasing path, FSPEC-WHEEL-09 label format, and FSPEC-TE2-01 CC Filter B coverage). None of the remaining findings are blockers for TSPEC authoring, provided the PROPERTIES author is aware of the open questions and marks the affected properties as "pending resolution." FSPEC-TE2-04 (phase transition automation boundary) and FSPEC-TE2-05 (panel title string conflict) should be resolved before the PROPERTIES document is finalised, as they affect two specific automated test assertions directly.

**Recommendation:** Approved with minor changes. TSPEC and PROPERTIES authoring may proceed in parallel with resolution of FSPEC-TE2-04 and FSPEC-TE2-05. The remaining five findings (FSPEC-TE2-01 through FSPEC-TE2-03, FSPEC-TE2-06, FSPEC-TE2-07) should be addressed as AC additions before implementation begins, as they represent coverage gaps in deterministic rule boundaries.

---

## Approved Items

The following items are well-specified and require no further changes:

- **Criterion 5 and Rule 5 seams (FSPEC-WHEEL-03, FSPEC-WHEEL-06):** The `investment_plan` → `ResearchPlan.recommendation` → Literal extraction path is now unambiguous, deterministic, and exercisable with a dict fixture. The corresponding ACs are correctly annotated and use injectable state.
- **IV rank boundary ACs (FSPEC-WHEEL-02):** The `iv_rank == 25.0` → `"normal"` and `iv_rank == 50.0` → `"elevated"` ACs are exemplary: they use the `iv_series` seam, specify an exact crafted series, and assert on a Literal output field. These are the model for all boundary-condition tests in this feature.
- **Relaxation branch ACs (FSPEC-WHEEL-04, steps 9a and 9b):** Both ACs specify the fixture condition precisely (which filters pass/fail), assert on `tradeable == True`, and check for exact note strings in `rationale`. This is the correct test structure for state-machine branch coverage.
- **Rule 3 firing boundary AC (FSPEC-WHEEL-06):** The `spot_price == csp_strike × 0.85` AC correctly captures the inclusive boundary intent.
- **Multi-rule priority ACs (Rule 3+1, Rule 2+1) (FSPEC-WHEEL-06):** Both are clean unit tests on the rule-evaluation function. Rule 3+1 correctly specifies both sub-cases (`breach_rule_roll` and `breach_rule_close`).
- **`rationale` schema-contract ACs (all four agent sections):** The universal assertion ("any terminal output → `rationale` is a non-empty string") fills the gap identified in FSPEC-TE-10 consistently across all schemas.
- **`structured.py` LLM call contract (FSPEC-WHEEL-04, FSPEC-WHEEL-05, FSPEC-WHEEL-06):** The requirement to use `bind_structured(llm, Schema)` from `structured.py` and the fallback behaviour on schema validation failure are now clearly specified in all three agent sections. Agents do not add outer retry loops beyond `structured.py`'s internal fallback.
- **`route_to_vendor()` call contract (FSPEC-WHEEL-01):** The corrected signature (method name first, no category argument), the category registration requirement in `TOOLS_CATEGORIES`, and the error-catching responsibility at the tool-wrapper layer are all precisely specified.
- **`WheelPosition.prior_analyst_bias` field definition (FSPEC-WHEEL-06):** The field is named, typed (`Optional[str]`), and its update lifecycle (written at end of every `RollCheckAgent` run) is unambiguously specified. This is sufficient for PROPERTIES authoring.
- **CLI display Business Rules (FSPEC-WHEEL-08):** The test harness (`Rich Console(file=StringIO())` with `console.export_text()`) and the approved/rejected styling rules are fully specified and deterministically testable.
- **FSPEC-WHEEL-09 injection suppression (equity-only mode):** The `wheel_phase is None` → no injection path is clearly defined and the corresponding AC (Integration, mocked debate agents) is testable with `MagicMock`.
