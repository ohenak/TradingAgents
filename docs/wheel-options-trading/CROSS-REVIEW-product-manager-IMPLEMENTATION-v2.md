# Cross-Review: product-manager — Implementation (v2)

**Reviewer:** product-manager
**Document reviewed:** `tradingagents/` (full implementation, feat-wheel-options-trading branch)
**Date:** 2026-05-26
**Iteration:** 2

---

## Prior Findings Resolution Status

All four High and two Medium findings from the first iteration review (v1) were verified. Status for each:

| v1 ID | Severity | Status | Evidence |
|-------|----------|--------|---------|
| F-01 | High | **Resolved** | `default_config.py` line 178: `"near_the_money_pct": 0.05`; `wheel_analyst.py` line 67: fallback `0.05`; stale "not in REQ Section 7" comment removed |
| F-02 | High | **Resolved** | `default_config.py` line 193: `"options_lookforward_days": 45`; `y_finance_options.py` line 51 fallback: `45`; `setup.py` line 95 fallback: `45`; stale comment removed |
| F-03 | High | **Resolved** | `_evaluate_rules` splits Rule 3 into `rule3_roll` (value >= 50%) and `rule3_close` (value < 50%); `_resolve_priority` returns `("CLOSE", "breach_rule_close")` for `rule3_close` case at lines 107-108 |
| F-04 | High | **Resolved** | `setup.py` lines 219-231: `route_after_portfolio_manager()` conditional edge routes Portfolio Manager → `csp_agent` when `wheel_phase == "screening"`; `csp_agent` → END wired |
| F-05 | Medium | **Resolved** | `render_wheel_candidate_panel` (cli/main.py lines 1286-1352) renders `iv_assessment` as a dedicated field; deterministically surfaces `"IV range is flat"` sentinel from schema field (not LLM text); docstring references PM-F-05 |
| F-07 | Medium | **Resolved** | `default_config.py` comments at lines 179 and 194 now read `"REQ v0.3.0 §7 default: 0.05"` and `"REQ v0.3.0 §7 default: 45"` respectively; stale "not in REQ Section 7" language removed |
| F-08 | Low | **Resolved** | `cli/main.py` line 1443: `datetime.datetime.now().date()` is correctly qualified; `datetime.datetime.strptime` at line 1442 is also correct |
| F-06 | Medium | **Clarification only** | No defect; Rule 1 arithmetic is correct |
| F-09 | Low | **No change required** | `"IV Rank"` substring still present in rendered output; AC technically met |

---

## New Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-NEW-01 | High | Local | REQ-LIFE-03 AC4 requires `action="CLOSE"` with `trigger_reason="analyst_update"` when the analyst consensus changes from bullish/neutral to bearish. The deterministic logic in `_resolve_priority` (roll_agent.py line 115) returns `("ROLL", "analyst_update")`. The LLM prompt (line 224) also instructs `action: ROLL` for Rule 5. Two tests (`test_rule5_beats_rule2`, `test_rule5_beats_rule1`) assert `action == "ROLL"` — they were written to match the defective implementation, not the REQ. All 512 tests pass, but the Rule 5 acceptance criterion (AC4) is not met. | REQ-LIFE-03 AC4 |
| F-NEW-02 | Medium | Local | REQ-TRADE-05 (P1) requires that the Aggressive, Conservative, and Neutral risk debate agents receive `CspDecision` or `CcDecision` in their prompt context when the system is in wheel mode, with the prompt string containing `mid_premium` and `probability_of_profit` (AC1). A helper `_build_options_context` is implemented in `tradingagents/agents/utils/agent_utils.py` (lines 58-134) that correctly builds this context block, but none of the three risk debate agents (`aggressive_debator.py`, `conservative_debator.py`, `neutral_debator.py`) or the Portfolio Manager call this function. It is dead code. The Portfolio Manager also lacks wheel-mode options context injection. REQ-TRADE-05 AC1 and AC2 are unimplemented. | REQ-TRADE-05 AC1, AC2 |
| F-NEW-03 | Low | Local | The LLM prompt for Rule 3 in `roll_agent.py` (lines 217-218) only describes the `breach_rule_roll → ROLL` case. The `breach_rule_close → CLOSE` sub-case (AC3b: `current_value_pct < 50`) is absent from the prompt text. The deterministic `_evaluate_rules` / `_resolve_priority` logic is correct, but in the three-layer fallback architecture the LLM-guided structured-output path (Layer 1) and free-text JSON extraction (Layer 2b) may produce `breach_rule_roll / ROLL` for a deep-loss breach scenario because the prompt does not instruct the LLM about the two-sub-rule split. Only the deterministic override in `_evaluate_rules` would produce the correct answer, which is not called on the LLM output path. | REQ-LIFE-03 AC3b |

---

## Summary of P0 and P1 Requirement Coverage (updated)

| Requirement | Priority | Status | Notes |
|-------------|----------|--------|-------|
| REQ-DATA-01 | P0 | Satisfied | AC1–AC6 covered; `options_lookforward_days = 45` correct |
| REQ-DATA-02 | P0 | Satisfied | IV Rank/Percentile; zero-variance sentinel; `iv_series` test seam |
| REQ-DATA-03 | P0 | Satisfied | BSM Greeks; DTE=0 guard; IV=0 guard; `^IRX` fallback |
| REQ-DATA-04 | P0 | Satisfied | `get_next_earnings_date` with `within_options_cycle`; graceful no-earnings return |
| REQ-DATA-05 | P0 | Satisfied | All four tools registered; Alpha Vantage stubs; vendor routing |
| REQ-SCREEN-01 | P0 | Satisfied | `WheelAnalyst` evaluates all five criteria; `selected_analysts` guard |
| REQ-SCREEN-02 | P0 | Satisfied | `WheelCandidateReport` schema; all fields present; `iv_assessment` explicit |
| REQ-SCREEN-03 | P1 | Satisfied | CLI renders `WheelCandidateReport` panel with IV Rank; rejection reason displayed |
| REQ-TRADE-01 | P0 | Satisfied | `CspAgent` with deterministic delta filter; reachable via screening path (F-04 resolved) |
| REQ-TRADE-02 | P0 | Satisfied | `CspDecision` schema with all fields; `annualised_yield_pct` formula correct |
| REQ-TRADE-03 | P0 | Satisfied | `CcAgent`; 28–45 DTE; cost-basis filter |
| REQ-TRADE-04 | P0 | Satisfied | `CcDecision` schema; `strike_above_cost_basis`; `upside_to_strike_pct` |
| REQ-TRADE-05 | P1 | **Not satisfied** | `_build_options_context` is dead code; risk debaters receive no `CspDecision`/`CcDecision` context (F-NEW-02) |
| REQ-LIFE-01 | P0 | Satisfied | `WheelPhase` as `str, Enum`; all phases routed; `WheelStateError` on missing position; unknown phase falls back with warning |
| REQ-LIFE-02 | P0 | Satisfied | `WheelPosition` with `csp_open_date` and `prior_analyst_bias`; atomic write; formula correct |
| REQ-LIFE-03 | P0 | **Partially satisfied** | Rules 1, 2, 3 (breach split), 4 implemented correctly. Rule 5 returns `ROLL` instead of `CLOSE` (F-NEW-01 — AC4 not met) |
| REQ-LIFE-04 | P0 | Satisfied | `RollDecision` schema; all six `trigger_reason` Literals defined |
| REQ-LIFE-05 | P1 | Satisfied | Cycle outcome written to `TradingMemoryLog`; `past_context` injected in subsequent runs |
| REQ-LIFE-06 | P1 | Satisfied | `tradingagents wheel-status` command; open positions table; completed cycles table; `"No open wheel positions"` string |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For F-NEW-01: REQ-LIFE-03 explicitly states `action="CLOSE"` for AC4. Is the `ROLL` return a deliberate product decision (i.e., rolling out of a bearish position rather than closing outright) that was not reflected in the REQ, or is it an implementation oversight? If deliberate, the REQ and PROPERTIES need updating. |
| Q-02 | For F-NEW-02: `_build_options_context` in `agent_utils.py` is fully implemented. Was REQ-TRADE-05 deferred intentionally (perhaps pending F-04 resolution), or was the call-site wiring simply missed? The fix is to call `_build_options_context(state)` in each risk debate agent's prompt assembly. |

---

## Positive Observations

- All four v1 High findings (F-01 through F-04) are cleanly resolved with accurate defaults, correct breach-rule split logic, and proper graph wiring.
- `default_config.py` comment header (lines 170-172) now explicitly states "All defaults below match REQ v0.3.0 §7 config table (authoritative)" — a durable improvement for future maintainers.
- The `render_wheel_candidate_panel` refactor (F-05 fix) is a material quality improvement: the panel now renders a structured Rich table from schema fields rather than a raw JSON blob, and deterministically surfaces the flat-IV sentinel regardless of LLM output.
- The `route_after_portfolio_manager()` implementation is clean: single conditional on `wheel_phase == "screening"`, minimal surface area, clearly documented with REQ traceability in the code comment.
- `_build_options_context` in `agent_utils.py` is well-structured and correctly implements all REQ-TRADE-05 context fields — it just needs to be called.
- The `breach_rule_close` deterministic path is correctly implemented in `_evaluate_rules` and `_resolve_priority`; the code comments reference AC3a/AC3b and REQ-LIFE-03 explicitly.

---

## What Must Change Before Approval

**Blocking (High):**

1. **F-NEW-01 — Rule 5 must return CLOSE, not ROLL:**
   - `_resolve_priority` line 115: change `return ("ROLL", "analyst_update")` to `return ("CLOSE", "analyst_update")`.
   - LLM prompt line 224: change `action: ROLL` to `action: CLOSE` for Rule 5.
   - Update tests `test_rule5_beats_rule2` and `test_rule5_beats_rule1` to assert `action == "CLOSE"`.

**Recommended (Medium — P1 requirement gap):**

2. **F-NEW-02 — Wire `_build_options_context` into risk debate agents:**
   - In `aggressive_debator.py`, `conservative_debator.py`, `neutral_debator.py`: import `_build_options_context` from `agent_utils` and append `_build_options_context(state)` to each agent's prompt string before LLM invocation, guarded by `wheel_phase` being non-None.
   - In `portfolio_manager.py`: inject the same context block when `wheel_phase` is non-None.
   - Add prompt-content assertions per REQ-TRADE-05 AC1 verifying that when `wheel_phase` is set and a `CspDecision` is present, the assembled prompt string contains `mid_premium` and `probability_of_profit`.

**Advisory (Low):**

3. **F-NEW-03 — Update Rule 3 prompt description to include the CLOSE sub-case:**
   - In the `roll_check_agent` prompt (lines 217-218), extend Rule 3 to describe both sub-cases: `breach_rule_roll → ROLL` when `current_value_pct >= 50`, and `breach_rule_close → CLOSE` when `current_value_pct < 50`. This aligns the LLM guidance with the deterministic logic and REQ-LIFE-03 AC3b.

---

## Recommendation

**Needs revision**

> One High finding (F-NEW-01) is present: Rule 5 in `_resolve_priority` and the LLM prompt returns `ROLL` instead of `CLOSE` for analyst-update scenarios, contradicting REQ-LIFE-03 AC4. The supporting tests assert the wrong behavior and pass because they mirror the defective implementation. This is a single-line fix with test updates. One Medium finding (F-NEW-02) covers a P1 requirement (REQ-TRADE-05) where the options context injection function is implemented but never called. Both items are narrow and well-scoped. Once F-NEW-01 is fixed and tests corrected, and F-NEW-02 is wired in, the implementation will be approvable.
