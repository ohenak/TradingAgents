# Cross-Review: product-manager — Implementation

**Reviewer:** product-manager
**Document reviewed:** `tradingagents/` (full implementation, feat-wheel-options-trading branch)
**Date:** 2026-05-26
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-01 | High | Local | `near_the_money_pct` default is `0.10` in `default_config.py` (line 179) and hardcoded as `0.10` in `wheel_analyst.py` (line 67). REQ v0.3.0 §7 config table specifies the default as `0.05`. The PROPERTIES doc (PROP-CFG-02) asserts `DEFAULT_CONFIG["wheel"]["near_the_money_pct"] == 0.05`. The implementation contradicts the REQ-authorised default; the PROPERTIES test for this assertion will fail. | REQ §7 (`near_the_money_pct`) |
| F-02 | High | Local | `options_lookforward_days` default is `90` in `default_config.py` (line 194), in `y_finance_options.py` (line 51 fallback), in `setup.py` (line 95 fallback), and in `TSPEC`. REQ v0.3.0 §7 specifies the default as `45`. The PROPERTIES doc asserts `DEFAULT_CONFIG["wheel"]["options_lookforward_days"] == 45`. The implementation contradicts the REQ-authorised default; the PROPERTIES test will fail. | REQ §7 (`options_lookforward_days`) |
| F-03 | High | Local | REQ-LIFE-03 AC3b requires: when stock drops ≥15% below CSP strike **and** `current_value_pct_of_premium < 50` (deep loss), return `action="CLOSE"` with `trigger_reason="breach_rule_close"`. The implementation's `_evaluate_rules` / `_resolve_priority` in `roll_agent.py` collapses both AC3a and AC3b into a single `Rule3` that **always** returns `action="ROLL", trigger_reason="breach_rule_roll"` regardless of `current_value_pct_of_premium`. The `"breach_rule_close"` trigger is defined in `TriggerReason` (schemas.py) but is never emitted. AC3b is unimplemented. | REQ-LIFE-03 AC3b |
| F-04 | High | Local | `csp_agent` node is registered in the graph but has no outgoing edge connecting it into the "screening" path. After `Portfolio Manager` → `END` in the screening flow, `csp_agent` is an orphan node. REQ-LIFE-01 AC2 states that `wheel_phase="screening"` must visit CspAgent after analyst + WheelAnalyst. The `route_wheel_phase` mapping also excludes `"csp_agent"` from the routing map. The CSP trade recommendation can never be reached in the screening flow. | REQ-LIFE-01 AC2, REQ-TRADE-01 AC1 |
| F-05 | Medium | Local | The `WheelCandidateReport.iv_assessment` field is described in REQ-SCREEN-02 and REQ-DATA-02 AC5 as required to surface the zero-variance sentinel `"IV range is flat — rank set to neutral 50"` when `max_vol == min_vol`. The `wheel_analyst.py` prompt instructs the LLM to include this note (line 109), but the `render_wheel_candidate_report` helper and the CLI `render_wheel_candidate_panel` do not explicitly display `iv_assessment` text in isolation — the panel renders the raw JSON blob rather than a structured Rich table showing `iv_assessment` separately. For a flat-IV edge case the disclosure depends entirely on LLM faithfulness. There is no deterministic, code-level guarantee the sentinel surfaces in the CLI output. | REQ-DATA-02 AC5, REQ-SCREEN-02 |
| F-06 | Medium | Local | REQ-LIFE-03 AC1 states: when `current_value_pct_of_premium == 50` (profit at exactly 50%), return `action="HOLD"` with `trigger_reason="profit_capture"`. The implementation uses `current_value_pct <= (100 - take_profit_pct)` (line 83 of `roll_agent.py`), i.e. `current_value_pct <= 50`. This fires HOLD when value is at or below 50% of premium. AC1 specifies "Premium at 50% of received value, DTE = 30 → action=HOLD trigger_reason=profit_capture", which the code does satisfy. However, the REQ description of Rule 1 states "declined to ≤ `take_profit_pct`" while the code tests `current_value_pct <= (100 - take_profit_pct)`. When `take_profit_pct=50`, `100 - 50 = 50`, and `current_value_pct <= 50` means the position has lost half its value — meaning "50% of premium remains". This logic is arithmetically correct. **No defect** — clarification note only. | REQ-LIFE-03 AC1 |
| F-07 | Medium | Cross-Feature | `default_config.py` comment at line 179–180 reads: `"NOTE: not in REQ Section 7 — TSPEC addition per FSPEC-WHEEL-03 closure (PM-TSPEC-02)"`. This comment is stale: REQ v0.3.0 explicitly added `near_the_money_pct` to §7. The comment misleads future maintainers about the authoritative source. Similarly, line 195 for `options_lookforward_days` says "not in REQ Section 7 — TSPEC addition". Both are now in REQ §7. Stale comments that misrepresent the authoritative source of a configuration default are a cross-feature risk pattern. | REQ §7, REQ-NFR-07 |
| F-08 | Low | Local | REQ-LIFE-06 AC1 requires that when two open positions exist, `console.export_text()` contains both tickers with current DTE and P&L. The `wheel-status` command computes DTE via `datetime.now().date()` (live wall clock), but `datetime` in scope at that line (cli/main.py line 1405) is imported as `import datetime` — so the call `datetime.strptime(...)` is valid but `datetime.now()` refers to the module, not the class. The correct call would be `datetime.datetime.now()`. This will raise `AttributeError: module 'datetime' has no attribute 'now'` at runtime when any open position has a non-empty expiry string. The `dte_str` would silently remain empty if the exception is caught, but the bare `except Exception: pass` at line 1408 does suppress it. P&L is shown; DTE column will be blank for all open positions. | REQ-LIFE-06 AC1 |
| F-09 | Low | Local | REQ-SCREEN-03 AC1 requires `console.export_text()` output to contain `"WheelCandidateReport"` and `"IV Rank"` when Wheel Analyst is selected. The `render_wheel_candidate_panel` in CLI (line 1304) constructs `panel_content = f"## WheelCandidateReport\n\n{report_raw}"` — `"WheelCandidateReport"` will appear. The `render_wheel_candidate_report` render helper (schemas.py line 415) renders `"IV Rank (Volatility Environment Score, based on 30-day realised volatility)"` not just `"IV Rank"`. The AC literally requires the substring `"IV Rank"`, which IS a substring of the full label — the AC is technically met. Low severity for awareness only. | REQ-SCREEN-03 AC1 |

---

## Summary of P0 Requirement Coverage

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-DATA-01 | Satisfied | `get_options_chain` implemented; AC1–AC6 covered including empty-chain and network-error guards. `options_lookforward_days` default discrepancy noted in F-02. |
| REQ-DATA-02 | Satisfied | IV Rank/Percentile via 30-day realised vol; zero-variance sentinel implemented in `get_iv_metrics`; `iv_series` test seam present. |
| REQ-DATA-03 | Satisfied | BSM Greeks in `get_options_greeks`; all ACs including DTE=0, dte<0, IV=0, `^IRX` fallback. |
| REQ-DATA-04 | Satisfied | `get_next_earnings_date` with `within_options_cycle` flag; no-earnings graceful return. |
| REQ-DATA-05 | Satisfied | All four tools registered in `interface.py` under `"options_data"` category; Alpha Vantage stub entries present; tools route through `route_to_vendor`. |
| REQ-SCREEN-01 | Satisfied | `WheelAnalyst` evaluates all five criteria; zero-variance disclosure in prompt; `selected_analysts` guard in `setup.py`. |
| REQ-SCREEN-02 | Satisfied | `WheelCandidateReport` schema with all required fields, including `iv_assessment`; model validator enforces approved/rejection_reason contract. |
| REQ-TRADE-01 | Partially satisfied | `CspAgent` implemented with deterministic delta filter; **not reachable in screening flow due to missing graph edge (F-04)**. |
| REQ-TRADE-02 | Satisfied | `CspDecision` schema with all fields; `annualised_yield_pct` formula correct. |
| REQ-TRADE-03 | Satisfied | `CcAgent` with cost-basis filter; 28–45 DTE in prompt and config. |
| REQ-TRADE-04 | Satisfied | `CcDecision` schema with all fields including `strike_above_cost_basis`. |
| REQ-LIFE-01 | Partially satisfied | `WheelPhase` enum as `str, Enum`; `route_wheel_phase` routes all phases; `WheelStateError` raised correctly. **`csp_agent` unreachable from screening path (F-04)**.  AC2 cannot be validated end-to-end. |
| REQ-LIFE-02 | Satisfied | `WheelPosition` includes `csp_open_date` and `prior_analyst_bias` (v0.3.0 additions); atomic write via temp-file+rename; per-ticker file naming. |
| REQ-LIFE-03 | Partially satisfied | Rules 1, 2, 4, 5 implemented. Rule 3 only implements AC3a (breach_rule_roll). **AC3b (breach_rule_close when value < 50%) is not implemented (F-03)**. |
| REQ-LIFE-04 | Satisfied | `RollDecision` schema with all six trigger reasons defined; `trigger_reason` Literal field present. |

---

## Config Default Discrepancies (F-01, F-02 detail)

| Key | REQ v0.3.0 §7 Default | Implementation Default | Files affected |
|-----|----------------------|------------------------|----------------|
| `near_the_money_pct` | `0.05` | `0.10` | `default_config.py:179`, `wheel_analyst.py:67` |
| `options_lookforward_days` | `45` | `90` | `default_config.py:194`, `y_finance_options.py:51`, `setup.py:95` |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | F-04 (csp_agent orphan node): Was `csp_agent` intentionally deferred to a later routing pass (e.g., after Portfolio Manager completes screening), or is the edge from Portfolio Manager → csp_agent missing by oversight? REQ-LIFE-01 AC2 explicitly requires visiting CspAgent in the screening phase. |
| Q-02 | For F-01/F-02: The TSPEC and FSPEC both used 0.10 / 90 as the confirmed values prior to the REQ v0.3.0 update. The implementation reflects the pre-v0.3.0 values. Should these be treated as REQ authoring conflicts, or is the implementation expected to track the latest REQ §7 as authoritative? (PM position: REQ §7 is authoritative.) |
| Q-03 | REQ-DATA-01 description text still reads "default: 90 days" while REQ §7 now says 45. Is the REQ description text a known authoring gap (noted in the PLAN PM cross-review Q-02 as an open question), or does it represent an unresolved ambiguity about different look-ahead semantics? |

---

## Positive Observations

- `WheelPosition` correctly includes both `csp_open_date` and `prior_analyst_bias` — the two v0.3.0 additions to REQ-LIFE-02 — with clear field descriptions.
- Backward compatibility for non-wheel tickers is well-implemented: `wheel_phase=None` in `route_wheel_phase` passes directly to `first_analyst_node`; no wheel nodes are visited.
- The `wheel-status` CLI command is present and handles the "no positions" case with the exact string `"No open wheel positions"` matching REQ-LIFE-06 AC2.
- `WheelCandidateReport.iv_assessment` field is present in the schema and the render helper; the zero-variance disclosure note is required in the LLM prompt.
- All four options data tools follow the vendor-routing pattern through `route_to_vendor()` — they do not import `y_finance_options.py` directly.
- The `breach_rule_close` and `breach_rule_roll` trigger reasons are both defined in the `TriggerReason` Literal in `schemas.py`, demonstrating awareness of the two-case breach rule; the gap is in the evaluation logic only.
- The annualised return formula in `wheel_cycle_summary` uses 365 throughout (calendar days) consistent with REQ-LIFE-02 AC3a.
- Phase transitions are correctly encoded: `csp_agent` sets `wheel_phase = "csp_open"` on tradeable=True; `roll_check_agent` transitions to `STOCK_OWNED` / `CYCLE_COMPLETE` on CLOSE.

---

## What Must Change Before Approval

The following three items are blocking (High severity). Work can be done in parallel.

1. **F-01 — `near_the_money_pct` default:** Change `default_config.py` line 179 from `0.10` to `0.05`. Update the `wheel_analyst.py` fallback default (line 67) from `0.10` to `0.05`. Update the stale comment in `default_config.py` (F-07).

2. **F-02 — `options_lookforward_days` default:** Change `default_config.py` line 194 from `90` to `45`. Update fallback defaults in `y_finance_options.py` (line 51) and `setup.py` (line 95) from `90` to `45`. Update the stale comment (F-07). Note: the config-validation warning in `setup.py` that fires when `options_lookforward_days < recommended_dte_high` would trigger at the new default of 45 == recommended_dte_high=45 (not less than), so no spurious warning is expected.

3. **F-03 — `breach_rule_close` unimplemented:** Implement AC3b. In `_evaluate_rules`, split Rule 3 into two sub-rules based on `current_value_pct_of_premium`: when `abs_delta > 0.85 AND wheel_phase == "csp_open" AND current_value_pct >= 50` → `breach_rule_roll`; when `abs_delta > 0.85 AND wheel_phase == "csp_open" AND current_value_pct < 50` → `breach_rule_close`. In `_resolve_priority`, return `("CLOSE", "breach_rule_close")` for the second case.

4. **F-04 — `csp_agent` orphan node:** Wire `csp_agent` into the screening flow. The most natural connection is from `Portfolio Manager` to `csp_agent` (conditionally, when `wheel_selected` and `wheel_phase == "screening"`), with `csp_agent` then routing to `END`. This satisfies REQ-LIFE-01 AC2's requirement that "screening" visits CspAgent.

The Medium finding F-05 (zero-variance sentinel display) is a test-coverage and CLI rendering concern. It does not require a code change to the sentinel logic itself but would benefit from the CLI rendering the `iv_assessment` field explicitly rather than embedding it in a raw JSON blob.

---

## Recommendation

**Needs revision**

> Four High findings are present (F-01 through F-04). F-01 and F-02 are confirmed default value mismatches between REQ v0.3.0 §7 and the implementation. F-03 is a missing acceptance criterion (REQ-LIFE-03 AC3b). F-04 is a graph wiring gap that makes the primary P0 feature path (CSP trade recommendation in screening mode) unreachable at runtime.
