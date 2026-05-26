# Cross-Review: product-manager — PLAN

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/PLAN-wheel-options-trading.md v0.3.0
**Date:** 2026-05-26
**Iteration:** 3

---

## Context

This is a focused re-review confirming that v0.3.0 remains clean from a product perspective after TE-driven changes. PM approved v0.2.0. TE issued "Needs revision" on v0.2.0 with three findings (TE-v2-F-01, TE-v2-F-02, TE-v2-F-03). All three are addressed in v0.3.0. This review confirms:

1. All prior PM findings (from Iterations 1 and 2) remain resolved.
2. The TE-driven v0.3.0 additions are product-coherent.

---

## Prior PM Findings Resolution Confirmation

All prior PM findings from Iterations 1 and 2 remain resolved in v0.3.0. No regression observed.

| Prior ID | Iter | Severity | Prior resolution (v0.2.0) | Status in v0.3.0 |
|----------|------|----------|--------------------------|-----------------|
| F-01 | 1 | High | PREREQUISITE GATE blocks Batch 2–4 until REQ v0.3.0 merges | Unchanged. PREREQUISITE GATE (top of PLAN) still present and unmodified. Resolved. |
| F-02 | 1 | High | DEC-PLAN-01 documents 28 DTE lower bound; B3-T3 AC pointer references DEC-PLAN-01 | Unchanged. DEC-PLAN-01 retained in §4. B3-T3 task description still references DEC-PLAN-01 explicitly. Resolved. |
| F-03 | 1 | Medium | DEC-PLAN-02 documents all five automated phase transitions; OI-02/OI-03 retired | Unchanged. DEC-PLAN-02 retained in §4. A sixth transition (`"csp_open" → roll_check_agent`) is now explicitly addressed by TE-v2-F-03 additions — DEC-PLAN-02 product intent is preserved and strengthened. Resolved. |
| F-04 | 1 | Medium | B3-T6 added for past-context injection; `test_past_context_injection.py` in B3-T-STUB and B3-T-VERIFY | Still present. B3-T6 task text unchanged. v0.3.0 adds the negative test requirement on top of the positive test. Resolution intact. |
| F-05 | 1 | Low | REQ v0.3.0 formally includes `near_the_money_pct` in §7 | Unchanged. Resolution carried forward from v0.2.0. Resolved. |
| F-06 | 1 | Low | B4-T4 CLI test + B4-T-VERIFY / Batch 4 DoD require CLI unknown-phase warning in `console.export_text()` | Still present and strengthened in v0.3.0: B4-T-STUB now also lists this requirement, and B4-T-VERIFY explicitly calls it out as a pass criterion. Resolved. |
| F-01 | 2 | Low | B4-T1 documents `return {"wheel_phase": None}` and explains the product rationale (A5 / re-entry via wheel_router) | v0.3.0 adds a dedicated "Phase reset note (PM-v2-F-01)" block to B4-T1, provides the product rationale in detail, and adds an explicit `wheel_phase == None` (not `"screening"`) assertion to B4-T-VERIFY and the Batch 4 DoD. Resolved and clarified. |
| F-02 | 2 | Low | "(default 90)" stale text in B1-T1 noted; authoritative default is 45 from §7 | v0.3.0 fixes the B1-T1 description to read "(default 45 per REQ §7 config table v0.3.0)" and explicitly notes that the REQ-DATA-01 description text still reads "default: 90 days" but the §7 config table is authoritative (PM-v2-F-02). Resolved. |

---

## TE-Driven v0.3.0 Additions — Product Coherence Check

The five TE-v2 changes are:

### 1. Negative `past_context` test stub (TE-v2-F-01)

**Change:** B3-T-STUB description now names an explicit negative test: when `WheelPosition.cycle_history` is empty or `WheelPosition` is absent, `_build_options_context` must return a prompt identical to a call with no `WheelPosition` at all. B3-T-VERIFY and the Batch 3 DoD both carry the corresponding pass criterion.

**Product coherence:** The negative test directly protects a product guarantee that matters to users: the first-cycle experience (US-01 through US-06) must be identical to a standard equity analysis run when no prior cycle exists. Accidentally injecting a `Past Cycle Performance` section containing zero or empty values on the first cycle would confuse users and violate REQ-NFR-01 (equity pass-through). The negative test boundary is product-correct and closes a real regression gap. No product scope change introduced.

### 2. `_position_loader` injectable seam in B3-T-STUB and B3-T6 (TE-v2-F-02)

**Change:** B3-T-STUB now explicitly requires all `test_past_context_injection.py` stubs to pass a `_position_loader` callable rather than relying on the real filesystem loader. The Batch 3 DoD adds a corresponding item.

**Product coherence:** This is a test isolation mechanism consistent with the ADR-WHEEL-05 convention already established for CcAgent and RollCheckAgent. The injectable seam has no impact on production behaviour: the default `_position_loader` is `load_latest_open_position`, unchanged. No user-facing functionality is altered. No product scope change introduced.

### 3. `wheel_phase="csp_open"` routing stub in B4-T-STUB, B4-T-VERIFY, and Batch 4 DoD (TE-v2-F-03)

**Change:** B4-T-STUB now names an explicit test stub: `wheel_phase="csp_open"` → `route_wheel_phase` returns `"roll_check_agent"`. B4-T-VERIFY and the Batch 4 DoD carry the corresponding pass criterion.

**Product coherence:** This test closing is product-critical. DEC-PLAN-02 already established that the `csp_open` phase routes to `RollCheckAgent` (the agent responsible for monitoring the open CSP position and detecting assignment). Without a routing test for `"csp_open"`, the automated transition `csp_open → stock_owned` — a core lifecycle step for US-06 and REQ-LIFE-03 — would be untested at the graph level. The addition is product-correct and improves assurance on a P0 lifecycle path. No scope change introduced.

### 4. `wheel_phase=None` reset note in B4-T1 and B4-T-VERIFY (PM-v2-F-01 clarification)

**Change:** B4-T1 now contains a dedicated "Phase reset note" block explaining that `return {"wheel_phase": None}` is intentional, not an error. B4-T-VERIFY explicitly asserts `wheel_phase == None` (not `"screening"`) in the `wheel_cycle_summary` output state. The Batch 4 DoD echoes this assertion.

**Product coherence:** This change resolves the v0.2.0 PM Q-01 question definitively, in favour of the product-consistent choice: the node returns `None`, and the next execution re-enters via `wheel_router`, which evaluates the state fresh. This preserves Assumption A5 ("system produces recommendations; human executes") — the system does not automatically initiate the next cycle. The product rationale ("bypass any inter-cycle state validation") is correctly stated. The addition is product-correct and improves clarity for PROPERTIES authors and testers. No scope change introduced.

### 5. `options_lookforward_days` default correction in B1-T1 (PM-v2-F-02 fix)

**Change:** B1-T1 description updated from "(default 90)" to "(default 45 per REQ §7 config table v0.3.0)". An inline note acknowledges the REQ-DATA-01 description text still reads "default: 90 days" and designates §7 as authoritative.

**Product coherence:** The authoritative default is 45, aligned to `recommended_dte_high = 45` in the config table and the config validation warning in B2-T4. The corrected text removes a genuine implementer confusion risk identified in PM v2 review. No scope change introduced.

---

## Findings

No new findings. The five TE-driven changes are product-coherent, do not introduce scope creep, do not alter any P0 or P1 requirement's acceptance criterion, and do not create traceability gaps. All changes either close previously identified test gaps or clarify existing product decisions.

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|

*(No findings)*

---

## Questions

*(No new questions. PM v2 Q-01 — post-cycle phase reset target — is now definitively answered by the B4-T1 "Phase reset note" block. PM v2 Q-02 — REQ-DATA-01 description text — is now resolved by the B1-T1 inline note.)*

---

## Positive Observations

- The PM-v2-F-01 "Phase reset note" block in B4-T1 is the most complete product-rationale documentation in the entire PLAN. It names the REQ description text ("resets phase to 'screening'"), explains the logical vs. literal interpretation, and articulates the guard-logic consequence of pre-setting `"screening"`. Future PROPERTIES authors will have no ambiguity about the correct assertion.
- The TE-v2-F-03 `"csp_open"` routing test addition correctly closes the last gap in the DEC-PLAN-02 routing coverage. The Batch 4 routing stub list now covers all seven routing cases (None + six non-None phases), which is exactly the complete test matrix for `route_wheel_phase`.
- v0.3.0 changelog is accurate and complete: all five addressed items (TE-v2-F-01, TE-v2-F-02, TE-v2-F-03, PM-v2-F-01, PM-v2-F-02) are listed with precise descriptions. This makes audit tracing straightforward.
- The feature-level Definition of Done (§12) now contains 19 checkable items, each with a specific, testable outcome. The three new DoD items added in v0.3.0 (negative past-context test, `_position_loader` injectable isolation, `csp_open` routing) are all product-observable criteria, not just implementation constraints.

---

## Recommendation

**Approved**

No findings. All prior PM findings from Iterations 1 and 2 remain resolved. All five TE-driven v0.3.0 additions are product-coherent: they close real test gaps, clarify existing product decisions, and introduce no scope creep or acceptance-criteria divergence. The PLAN is approved for implementation handoff.
