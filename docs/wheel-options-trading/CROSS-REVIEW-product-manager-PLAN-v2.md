# Cross-Review: product-manager — PLAN

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/PLAN-wheel-options-trading.md v0.2.0
**Date:** 2026-05-25
**Iteration:** 2

---

## Prior Findings Resolution

All four mandatory items from Iteration 1 are verified resolved:

| Prior ID | Severity | Resolution status | Evidence |
|----------|----------|-------------------|---------|
| F-01 | High | Resolved | PLAN PREREQUISITE GATE (§ top) explicitly requires REQ v0.3.0 before Batch 2–4. REQ v0.3.0 changelog confirms all four gaps patched: `near_the_money_pct` and `options_lookforward_days` in §7, `csp_open_date` and `prior_analyst_bias` in REQ-LIFE-02 schema, AC3a corrected to 33.21%. |
| F-02 | High | Resolved | DEC-PLAN-01 (PLAN §4) documents 28 DTE lower bound with full rationale. B3-T3 AC pointer explicitly references DEC-PLAN-01. REQ-TRADE-03 in REQ v0.3.0 updated to "28–45 DTE." |
| F-03 | Medium | Resolved | DEC-PLAN-02 (PLAN §4) documents all five automated phase transitions with a full agent-responsibility table. OI-02 and OI-03 are explicitly retired in PLAN §9. |
| F-04 | Medium | Resolved | B3-T6 added (`past_context` injection via `_build_options_context`). `tests/test_past_context_injection.py` added in B3-T-STUB and verified in B3-T-VERIFY. B3-T-VERIFY DoD and feature-level DoD both assert the multi-cycle injection test passes. |

Prior Low findings F-05 (near_the_money_pct REQ gap) and F-06 (CLI unknown-phase warning test) are also resolved: F-05 by REQ v0.3.0 formally including `near_the_money_pct` in §7; F-06 by explicit B4-T4 CLI test requirement and B4-T-VERIFY / B4 DoD checklist items.

---

## Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-01 | Low | Local | `cycle_complete` reset target diverges from REQ-LIFE-01. REQ-LIFE-01 description states `"cycle_complete"` → "emits cycle summary and resets phase to `'screening'`." B4-T1 implements `return {"wheel_phase": None}`, which means after a cycle completes the user must re-invoke with `wheel_phase="screening"` manually. This is consistent with Assumption A5 ("system produces recommendations only; human executes") and avoids an unprompted re-run, but it contradicts the literal REQ-LIFE-01 description text. The divergence creates ambiguity for PROPERTIES authors and testers: should PROP-ROUTE-X assert `wheel_phase == None` or `wheel_phase == "screening"` after `wheel_cycle_summary` runs? | REQ-LIFE-01 (description: "resets phase to 'screening'"); B4-T1 (returns `{"wheel_phase": None}`); A5 |
| F-02 | Low | Local | B1-T1 description contains an inline default value "(default 90)" for `options_lookforward_days` that conflicts with REQ §7 v0.3.0, which sets the default to `45`. The authoritative default is `45` from REQ §7 (aligned to `recommended_dte_high = 45` per the config validation warning in B2-T4). The "(default 90)" text in B1-T1 is a carry-forward from REQ-DATA-01 description text (which still reads "default: 90 days" in REQ v0.3.0). Implementers reading B1-T1 in isolation may code the function using 90 as the fallback, producing a mismatch with the config table. | REQ-DATA-01 (description: "default: 90 days"); REQ §7 config table v0.3.0 (`options_lookforward_days = 45`); B1-T1 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | After `wheel_cycle_summary` runs and the graph returns `{"wheel_phase": None}`, is the intended user experience that the CLI immediately prompts for a new cycle (i.e., the user re-invokes with `wheel_phase="screening"`)? Or should the graph automatically chain into `"screening"` to begin the next cycle without a second invocation? This affects whether B4-T1's `return {"wheel_phase": None}` is correct or whether it should return `{"wheel_phase": "screening"}`. |
| Q-02 | REQ-DATA-01 description still reads "default: 90 days" for the look-ahead window. Is this a REQ v0.3.0 authoring omission (the description was not updated when `options_lookforward_days = 45` was added to §7), or is there a deliberate product distinction between the chain-retrieval look-ahead and the CSP/CC candidate look-ahead? If the former, REQ-DATA-01 description text should be corrected to "default: 45 days" to match §7. |

---

## Positive Observations

- The PREREQUISITE GATE section is well-executed: it names the exact four gap items, explains the authority model (TSPEC authoritative until REQ v0.3.0 merges), and blocks Batch 2–4 implementation explicitly. This is exactly the right product safeguard for a known REQ-ahead-of-spec situation.
- DEC-PLAN-01 (CC DTE lower bound) is precisely documented with the quantitative rationale (gamma trap threshold, steepened gamma/theta curve below 28 DTE). The AC pointer update in B3-T3 gives the implementer an unambiguous implementation target.
- DEC-PLAN-02 (automated phase transitions) resolves the most product-material ambiguity from v1. The agent-responsibility table (which agent owns each transition, what the trigger condition is, how user confirmation interacts) is clear and complete. The "out-of-band mechanism" model (CLI prompts, user re-invokes with updated `wheel_phase`) is correctly aligned with A5.
- B3-T6 (`past_context` injection) is a well-scoped addition: it extends `_build_options_context` incrementally rather than requiring a new module, cites US-07 and REQ-LIFE-05 AC3 precisely, and the format string (`f"Prior cycle #{n}: P&L=..."`) gives implementers an unambiguous output format to test against.
- The B4-T4 fix for F-06 (CLI unknown-phase warning) correctly separates the routing assertion (`caplog`) from the user-visible assertion (`console.export_text()`), which is the right product testing model: `caplog` verifies internal behaviour; `console.export_text()` verifies what the user actually sees.
- All ten user stories remain fully traceable through the updated PLAN. US-07 (multi-cycle P&L) is now specifically covered by B3-T6 past-context injection and the B4-T1 `TradingMemoryLog` entry.
- The two new DEC-PLAN sections follow the same ADR structure as the DECISIONS document (context, decision, impact), making them straightforward for harvest-learnings to process.
- The feature-level Definition of Done (§12) is comprehensive: 15 checklist items each with a specific, testable outcome. No "done when tests pass" vagueness.

---

## Recommendation

**Approved**

Both remaining findings are Low severity. No High or Medium findings are present. The two open questions (Q-01, Q-02) are clarifying items that do not block implementation: B4-T1's `return {"wheel_phase": None}` is consistent with A5 and is a defensible product choice; the B1-T1 default value discrepancy is minor and implementers will read the config table (REQ §7) as the authoritative default regardless of the inline comment. Neither item poses a traceability gap that would cause a P0 or P1 requirement to be missed.

The PLAN is approved for implementation handoff. Recommended actions before or during Batch 1 implementation, not blocking:
1. (B1-T1 implementer) Use `options_lookforward_days` config value as the operative default; treat "(default 90)" in B1-T1 description as a stale copy of REQ-DATA-01 description text and use the §7 config table value (`45`) as authoritative.
2. (Product owner) Confirm post-cycle `wheel_phase` reset target (None vs "screening") so PROPERTIES authors can write an unambiguous assertion for the `wheel_cycle_summary` output state.
