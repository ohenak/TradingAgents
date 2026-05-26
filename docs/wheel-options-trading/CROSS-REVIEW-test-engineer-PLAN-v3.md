# Cross-Review: test-engineer — PLAN

**Reviewer:** test-engineer
**Document reviewed:** docs/wheel-options-trading/PLAN-wheel-options-trading.md
**Date:** 2026-05-26
**Iteration:** 3

---

## Prior Findings Resolution

### TE-v2-F-01 (Medium) — Negative test for empty/absent `cycle_history` in B3-T-STUB and B3-T-VERIFY

**Status: Resolved.**

B3-T-STUB now carries an explicit "(b) Negative test stub (TE-v2-F-01 — required)" block: when `WheelPosition.cycle_history` is empty OR `WheelPosition` is absent, `_build_options_context` must NOT inject any `Past Cycle Performance` section — the returned prompt string must be identical to a call with no `WheelPosition` at all. B3-T-VERIFY names this assertion explicitly. The Batch 3 DoD includes it as a standalone pass criterion. The feature-level DoD (Section 12) also carries the item. The boundary condition is now fully testably specified at four independent enforcement points.

### TE-v2-F-02 (Low) — `_position_loader` injectable requirement in `test_past_context_injection.py` stubs

**Status: Resolved.**

B3-T-STUB carries an explicit "(c) Injectable seam requirement (TE-v2-F-02 / ADR-WHEEL-05)" block: all stubs in `test_past_context_injection.py` MUST pass a `_position_loader` callable argument to `_build_options_context`; no test in this file may write to the real `positions_dir`. B3-T-VERIFY, the Batch 3 DoD, and the feature-level DoD all include corresponding enforcement items. Traceability from ADR-WHEEL-05 through to all four enforcement points is complete.

### TE-v2-F-03 (Low) — `wheel_phase="csp_open"` → `roll_check_agent` routing test stub in B4-T-STUB

**Status: Resolved.**

B4-T-STUB now names an explicit stub for `wheel_phase="csp_open"` → `roll_check_agent` (TE-v2-F-03 / DEC-PLAN-02), specifying that `route_wheel_phase` must return `"roll_check_agent"` for this input. B4-T-VERIFY carries a bold-annotated pass criterion for this case. The Batch 4 DoD and the feature-level DoD (Section 12) both include the item. The routing table in B4-T-STUB now covers all seven cases: `None`, `"cc_open"` (no-position guard), `"invalid_phase"`, `"screening"`, `"stock_owned"`, `"cycle_complete"`, and `"csp_open"` — matching the full DEC-PLAN-02 transition table.

---

## PM-v2-F-01 Fix — `wheel_phase=None` reset in `wheel_cycle_summary`: Testability Verification

B4-T-STUB names "wheel_phase=None` in returned state after `wheel_cycle_summary` runs" as an explicit stub requirement. B4-T1's task description contains a detailed authoritative note:

> "Return `{"wheel_phase": None}`. **Phase reset note (PM-v2-F-01):** The return value is `{"wheel_phase": None}`, NOT `{"wheel_phase": "screening"}`. ... PROPERTIES authors and testers must assert `wheel_phase == None` (not `"screening"`) in the `wheel_cycle_summary` output state."

B4-T-VERIFY makes this a named pass criterion: "`wheel_cycle_summary` returned state asserts `wheel_phase == None` (PM-v2-F-01)". The Batch 4 DoD and the feature-level DoD both include: "`wheel_cycle_summary` returned state has `wheel_phase == None`; next cycle re-enters via `wheel_router` on re-invocation (PM-v2-F-01)." The rationale (skip `wheel_router` guard logic bypass) is documented inline and is observable in tests. This fix is testably specified.

---

## Findings

No new findings.

---

## Questions

None.

---

## Positive Observations

- All three TE-v2 findings are addressed at every relevant enforcement point (stub description, verify assertion, batch DoD item, feature-level DoD item). The layered enforcement pattern — requiring each invariant to appear in at least the stub task, the verify task, and the DoD — is correct and makes it mechanically difficult for an implementer to skip a requirement.
- The v0.3.0 changelog entry is precise: each of the five changes (TE-v2-F-01, TE-v2-F-02, TE-v2-F-03, PM-v2-F-01, PM-v2-F-02) is identified by finding ID, mapped to the exact section changed, and described in testable terms. This makes the review diff unambiguous.
- The B4-T-STUB routing stub list now covers all seven routing inputs (six non-None phases plus `None`), matching the DEC-PLAN-02 table exactly. The prior gap (csp_open absent) is closed without introducing any new gaps.
- The `wheel_phase=None` rationale in B4-T1 is unusually thorough for a PLAN document: it explains why the node must NOT pre-set `"screening"` (to avoid bypassing `wheel_router` guard logic), giving PROPERTIES authors the correct assertion target and the reasoning to defend it in code review.
- The PM-v2-F-02 fix (stale "(default 90)" corrected to "(default 45)" in B1-T1) is a minor but important correction; the authoritative config table value is now consistently cited across B1-T1, the Batch 1 DoD, and the PREREQUISITE GATE note.

---

## Recommendation

**Approved**
