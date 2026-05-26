# Cross-Review: product-manager — PLAN

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/PLAN-wheel-options-trading.md
**Date:** 2026-05-25
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-01 | High | Local | REQ v0.3.0 patch was listed as a prerequisite before PLAN authoring in the TSPEC v2 PM cross-review (PM-TSPEC-v2-01, PM-TSPEC-02, PM-TSPEC-03, PM-TSPEC-04), but REQ is still at v0.2.0. Four unresolved gaps from the TSPEC review remain open: (a) `near_the_money_pct` and `options_lookforward_days` are absent from REQ Section 7 config table; (b) `csp_open_date` and `prior_analyst_bias` are absent from the REQ-LIFE-02 `WheelPosition` schema; (c) `cycle_annualised_return_pct` is stated as ~33.25% in REQ-LIFE-02 AC3a but the PLAN asserts 33.21% as authoritative. The PLAN's B2-T4 and B2-T5 implement these TSPEC-only additions without a corresponding REQ update, creating a gap between the approved requirements and the implementation contract. Implementers reading the REQ will not find authoritative definitions for these four items. | REQ-LIFE-02 AC3a; REQ §7 config table; TSPEC §8.1, §9.1, §9.4, §10.8 |
| F-02 | High | Local | The CC DTE lower-bound ambiguity (PM-TSPEC-v2-01) was explicitly flagged as a product decision required "before PLAN authoring begins" in the TSPEC v2 PM cross-review. The PLAN does not contain a resolution. B3-T3 (CcAgent) references "same shared defaults" for DTE bounds, silently inheriting `recommended_dte_low = 28`, but REQ-TRADE-03 description says "default 21–45 DTE." The PLAN has no open issue entry for this item and no AC pointer that resolves the conflict. An implementer implementing `_filter_cc_candidates` has no authoritative lower-DTE bound to implement against. | REQ-TRADE-03 (description: "21–45 DTE"); REQ §7 (`recommended_dte_low = 28`); TSPEC §10.1 item 5 |
| F-03 | Medium | Local | Open issues OI-02 and OI-03 (Phase transition trigger for `csp_open` → `stock_owned` and `cc_open` → `stock_owned`) are product-scope questions about whether phase transitions are manual or automated. The PLAN states "confirm with product owner before B4-T2" but does not record a resolution. B4-T2 (conditional_logic.py) implements `route_wheel_phase()` including the routing logic for `"csp_open"` and `"cc_open"` — and B4-T6 tests these branches. If the product owner decides automated detection is required, the B4-T2 routing logic and B4-T6 tests will need to change. The PLAN should not leave product-scope decisions to implementer discovery at B4-T2 coding time. | REQ-LIFE-01 AC4 ("Phase transition occurs (CSP assigned)"); FSPEC-WHEEL-07 transition table ("CSP expires worthless OR assignment is detected") |
| F-04 | Medium | Local | US-05 ("Track open wheel positions and their cost basis") and US-07 ("See a running P&L and annualised yield") both require the `wheel-status` CLI command. B4-T5 specifies the `wheel-status` sub-command correctly. However, the AC pointer for B4-T5 cites only REQ-LIFE-06 AC1–AC3 and TSPEC §7.2. REQ-LIFE-05 AC3 requires that `past_context` (injected into WheelAnalyst and CspAgent on subsequent runs) contains `cycle_pnl` and `cycle_annualised_return_pct`. No task in any batch explicitly implements or tests this `past_context` injection path. B4-T1 handles the `wheel_cycle_summary` node (which writes the TradingMemoryLog entry), but no task specifies where the `past_context` string is assembled and injected into WheelAnalyst/CspAgent prompts on the next run. REQ-LIFE-05 AC3 is untraced to any task. | REQ-LIFE-05 AC3; US-07 |
| F-05 | Low | Local | The `near_the_money_pct` config key (added by TSPEC, noted as pending REQ v0.3.0) is part of the 18-key `config["wheel"]` sub-dict in B2-T4, but the PLAN's AC pointer for B2-T4 cites only REQ-NFR-03 and REQ-NFR-07. Because `near_the_money_pct` has no REQ ID, PROPERTIES authors have no REQ-level acceptance criterion to cite for this key's coverage. The TSPEC §10.8 "NOTE: not in REQ Section 7" annotation is the only reference chain. This is manageable given the TSPEC note, but the PLAN should explicitly acknowledge the gap in B2-T4's task description or AC pointer. | REQ-NFR-03; REQ-NFR-07; TSPEC §8.1 (near_the_money_pct NOTE) |
| F-06 | Low | Local | B4-T4 (CLI panel display) has an AC pointer of "REQ-SCREEN-03 AC1–AC3; FSPEC-WHEEL-08; TSPEC §7.1" and contains a correct display guard, style specification, and ADR-WHEEL-02 unknown-phase warning requirement. The ADR-WHEEL-02 requirement to "surface to the CLI user" (not just log) is correctly noted in B4-T4's description. However, B4-T6 CLI tests do not include an explicit test assertion for the unknown-phase warning appearing in CLI output (as distinct from a `caplog` assertion). The B4-T6 routing test for `wheel_phase="invalid_phase"` asserts the warning is logged (PROP-ROUTE-01, ADR-WHEEL-02 `caplog`), but REQ-LIFE-01 AC6 says "logs a warning" — it does not require CLI output. The FSPEC-WHEEL-07 business rule and ADR-WHEEL-02 require CLI surfacing. B4-T4 mentions it but no test in B4-T6 validates CLI output for the unknown-phase warning path. | REQ-LIFE-01 AC6; ADR-WHEEL-02; FSPEC-WHEEL-07 Business Rules |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | Has a decision been made on the CC DTE lower bound (21 vs 28)? If the resolution is "28 for both CSP and CC," should REQ-TRADE-03 be patched to read "28–45 DTE" before implementation begins, so that implementers and PROPERTIES authors have an unambiguous requirement to test against? |
| Q-02 | Has a decision been made on OI-02/OI-03 (manual vs. automated assignment detection for phase transitions)? This affects B4-T2 routing logic and the transition tests in B4-T6. If automated detection is deferred to Phase 5 (as the PLAN's OI-02 note suggests), this should be recorded as a confirmed decision rather than "confirm with product owner." |
| Q-03 | The REQ is still at v0.2.0. The TSPEC v2 PM cross-review approved TSPEC "for PLAN handoff provided REQ v0.3.0 is produced before implementation begins." Will REQ v0.3.0 be produced before Batch 2–3 implementation starts, or are implementers expected to rely solely on TSPEC §10.8 annotations for the four unpatched items? |
| Q-04 | REQ-LIFE-05 AC3 (`past_context` injection into WheelAnalyst/CspAgent on subsequent runs) is untraced to any PLAN task. Should this be added to Batch 3 (as an extension to B3-T1 WheelAnalyst task) or is it intentionally deferred? |

---

## Positive Observations

- Batch ordering maps cleanly to the four REQ delivery phases. Each batch delivers a meaningfully incrementally useful capability: data tools alone (B1) are usable for any options-aware agent; schemas + config (B2) are prerequisite but isolated; agent layer (B3) delivers actual trade recommendations; graph wiring (B4) delivers the full lifecycle product. A user could run Phase 1 tools via existing agent plumbing even before Batch 3 ships.
- All ten user stories (US-01 through US-10) are traceable to tasks. US-01, US-02 map to B3-T1; US-03 to B3-T2; US-04 to B3-T3; US-05 to B2-T5 and B4-T5; US-06 to B3-T4; US-07 to B4-T1 and B4-T5; US-08 to B1-T4, B3-T1, B3-T2; US-09 to B4-T4 and B4-T5; US-10 to B2-T4.
- All P0 requirements are covered. REQ-DATA-01 through REQ-DATA-05 (all P0) are in Batch 1. REQ-SCREEN-01, REQ-SCREEN-02 (P0) are in Batches 2–3. REQ-TRADE-01 through REQ-TRADE-04 (all P0) are in Batch 3. REQ-LIFE-01 through REQ-LIFE-04 (all P0) are in Batches 2–4. No P0 requirement is deferred beyond Batch 4.
- P1 requirements are correctly placed after P0: REQ-SCREEN-03 (P1) in B4-T4; REQ-TRADE-05 (P1) in B3-T5; REQ-LIFE-05 (P1) in B4-T1; REQ-LIFE-06 (P1) in B4-T5.
- The AC pointers in task tables are specific and actionable. Each task cites the REQ IDs and TSPEC/FSPEC section numbers rather than generic cross-references. This level of precision is well above baseline for PLAN documents.
- The DECISIONS carry-forward table (Section 3) is an excellent addition. Surfacing ADR constraints directly in the PLAN (with exact string values like `STRUCTURED_OUTPUT_SENTINEL` and sorting behaviour) reduces the risk of implementers making inconsistent local decisions.
- The canonical test fixture in Section 4 and the per-batch Definition of Done checklists provide clear, checkable exit criteria that avoid ambiguous "done when tests pass" language.
- OI-04 (CLI module location) is pragmatically handled by deferring file identification to the implementer with a specific grep command, avoiding a hard-coded assumption that could be wrong. This is appropriate.
- The `cycle_annualised_return_pct` discrepancy (Section 9) is handled transparently: the PLAN asserts the arithmetically correct value (33.21%), records the REQ's stated value (33.25%), and provides the comment template implementers must include. This is the correct product handling for a known REQ arithmetic error.
- REQ-NFR-01 (backwards compatibility) is explicitly addressed throughout: the equity-passthrough integration test is in Batch 4 DoD, and the `wheel_phase is None` no-op path is woven into every task description that touches the graph.

---

## Items That Must Change Before Approval

The following must be resolved before the PLAN is approved for implementation handoff:

1. **F-01 — REQ v0.3.0 patch:** Either (a) produce REQ v0.3.0 that adds `near_the_money_pct`, `options_lookforward_days`, `csp_open_date`, `prior_analyst_bias` to the schema/config tables, and corrects AC3a to 33.21%, before Batch 2 implementation begins; OR (b) add an explicit Open Issue entry to Section 8 that formally records these as TSPEC-authoritative additions with the understanding that REQ v0.3.0 will follow. The PLAN currently neither patches REQ nor formally defers the gap — it simply inherits the TSPEC's "NOTE" annotations without acknowledging them at the PLAN level.

2. **F-02 — CC DTE resolution:** The PLAN must record a product decision on the CC DTE lower bound. Add to OI table: either "CC uses same `recommended_dte_low = 28` as CSP — REQ-TRADE-03 description is being corrected in REQ v0.3.0" OR "a new `cc_recommended_dte_low = 21` key is added to config." B3-T3's AC pointer must reference whichever decision is made so the CcAgent implementer knows which bound to implement and which PROPERTIES test to expect.

3. **F-03 — OI-02/OI-03 resolution:** Replace "confirm with product owner before B4-T2" with the confirmed decision. If the decision is "manual state update only in Phase 1, automated detection deferred to Phase 5," record that as a confirmed decision in the OI table and in the B4-T2 task description. This removes ambiguity from B4-T2/B4-T6 implementers.

4. **F-04 — REQ-LIFE-05 AC3 task gap:** Add a task or sub-task covering `past_context` injection into WheelAnalyst/CspAgent prompts on subsequent wheel cycles. Without this, REQ-LIFE-05 AC3 is unimplemented and US-07's "running P&L" intent is incomplete for the multi-cycle scenario.

---

## Recommendation

**Needs revision**

Two High findings (F-01, F-02) and two Medium findings (F-03, F-04) require resolution before implementation begins. The PLAN is structurally sound and product coverage is thorough — all ten user stories and all P0 requirements trace to tasks. The revisions required are focused product decisions and a single missing task, not architectural replanning.
