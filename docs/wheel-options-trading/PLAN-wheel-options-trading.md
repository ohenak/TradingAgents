# PLAN — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | SE-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-25 |
| **Upstream** | REQ-wheel-options-trading.md v0.2.0 → FSPEC-wheel-options-trading.md v0.3.0 → TSPEC-wheel-options-trading.md v0.2.0 → DECISIONS-wheel-options-trading.md v0.3.0 → **PLAN** |
| **Downstream** | IMPL (se-implement), PROPERTIES |
| **Cross-Reviews** | none yet |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |
| **DECISIONS note** | DECISIONS document created (not skipped). Five ADRs: ADR-WHEEL-01 (IV data source), ADR-WHEEL-02 (WheelPhase storage), ADR-WHEEL-03 (graph architecture), ADR-WHEEL-04 (structured output fallback), ADR-WHEEL-05 (position persistence). |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2026-05-25 | Initial PLAN |

---

## 1. Summary

This execution plan implements the Wheel Options Trading feature across four phases. The feature adds:

1. **Phase 1 — Data Foundation:** Four new yfinance functions (`get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date`), their LangChain `@tool` wrappers, and vendor routing registration.
2. **Phase 2 — Screening:** `WheelAnalyst` agent with five suitability criteria, all new Pydantic schemas, `AgentState` extension, configuration additions, and CLI wheel panel display.
3. **Phase 3 — Trade Engine:** `CspAgent` and `CcAgent` for trade recommendation, plus risk debate options context injection.
4. **Phase 4 — Lifecycle:** `RollCheckAgent`, `WheelPosition` persistence, `wheel_cycle_summary` node, `ConditionalLogic.route_wheel_phase()`, graph wiring via `START → wheel_router`, and the `wheel-status` CLI sub-command.

Each batch is designed so tasks within it can be implemented in parallel by separate agents. Cross-batch dependency is strictly ordered: no task in Batch N starts until all tasks in Batch N-1 are complete.

The existing equity pipeline must remain fully functional throughout (REQ-NFR-01). When `wheel_phase is None`, all additions are transparent pass-throughs.

---

## 2. Pre-conditions

Before any batch begins, confirm:

- [ ] Feature branch `feat-wheel-options-trading` is checked out and up to date with `origin/feat-wheel-options-trading`.
- [ ] All upstream docs are approved: REQ v0.2.0, FSPEC v0.3.0, TSPEC v0.2.0, DECISIONS v0.3.0.
- [ ] `scipy` is available or an alternative implementation for `norm.cdf`/`norm.pdf` is chosen (TSPEC Section 10.7 open question — see Section 10 of this PLAN).
- [ ] `tests/fixtures/` directory exists; create it if absent.

---

## 3. DECISIONS carry-forward notes for implementers

| ADR | Binding constraint on this PLAN |
|---|---|
| ADR-WHEEL-01 | IV Rank and IV Percentile use 30-day realised vol from OHLCV. The CLI and `WheelCandidateReport.iv_assessment` must label this as 'Volatility Environment Score' or annotate it as 'based on 30-day realised volatility'. When the zero-variance sentinel fires (`iv_rank = 50`, flat series), the note `'IV range is flat — rank set to neutral 50'` must be surfaced in `iv_assessment` and CLI output. |
| ADR-WHEEL-02 | `wheel_phase` in `AgentState` is `Optional[str]`, not `Optional[WheelPhase]`. All writes must use `WheelPhase` enum constant values (e.g., `WheelPhase.SCREENING.value`). The unknown-value warning in `route_wheel_phase()` must be surfaced to the CLI user, not just logged to stderr. |
| ADR-WHEEL-03 | Graph uses a single shared `StateGraph`. The existing `workflow.add_edge(START, plan.specs[0].agent_node)` line in `setup.py` line 89 is replaced by `workflow.add_conditional_edges(START, conditional_logic.route_wheel_phase, mapping)`. One `propagate()` call handles exactly one ticker. |
| ADR-WHEEL-04 | All four wheel agents use the three-layer fallback: `bind_structured` → `invoke_structured_or_freetext` → `model_validate_json` → safe sentinel. `STRUCTURED_OUTPUT_SENTINEL = 'Structured output failed — safe fallback applied.'` must be defined in `structured.py` as a module-level constant. The sentinel string value is a contract — do not hardcode it in agents or tests; always import from `structured.py`. |
| ADR-WHEEL-05 | Position files: `{positions_dir}/{ticker}-cycle-{N}.json`. `load_latest_open_position` uses integer sort on cycle number, never lexicographic sort. All agent unit tests inject a `_position_loader` callable; no agent test writes to the real `positions_dir`. I/O-layer tests use `pytest tmp_path`. |

---

## 4. Test Strategy

Tests follow the three categories prescribed in TSPEC Section 10.2 and the ADR-WHEEL-04 test coverage requirements.

### Test levels used

| Level | Marker | Description |
|---|---|---|
| Unit | (no mark) | Mocked data layer and LLM; no filesystem writes to real dirs; no network calls |
| Integration | `@pytest.mark.integration` | Canned fixtures from `tests/fixtures/options_fixtures.py`, mocked LLM; may write to `tmp_path` |
| Smoke | `@pytest.mark.smoke` | Live yfinance network call; not run in CI by default |

### ADR test invariants (from DECISIONS doc)

The following tests are **required by the DECISIONS document** and must each map to a named property in PROPERTIES:

| ADR | Required test | Property name |
|---|---|---|
| ADR-WHEEL-01 | `iv_percentile` does not equal 100 when `current_vol == max_vol_lookback`; zero-variance sentinel returns `iv_rank=50` with flat-range note | `PROP-IV-01`, `PROP-IV-02` |
| ADR-WHEEL-02 | Unknown `wheel_phase` string routes to equity path and emits a warning (captured via `caplog`) | `PROP-ROUTE-01` |
| ADR-WHEEL-03 | When `wheel_phase is None`, `wheel_router` routes to first analyst node; no options nodes visited; output `AgentState` fields (`market_report` etc.) are unchanged | `PROP-ROUTE-02` |
| ADR-WHEEL-04 | Three-level fallback per agent: (a) structured success path; (b) freetext-valid-JSON path (`model_validate_json` succeeds, sentinel NOT returned); (c) total failure → sentinel returned with `STRUCTURED_OUTPUT_SENTINEL` | `PROP-FALLBACK-01` through `PROP-FALLBACK-12` (3 × 4 agents) |
| ADR-WHEEL-05 | `load_latest_open_position` returns cycle-10 file (not cycle-9) when both exist in a `tmp_path` dir | `PROP-POSN-01` |
| ADR-WHEEL-05 | Unit tests inject `_position_loader`; no test writes to real `positions_dir` | Convention enforced in test code review |

### Canonical fixture

All options data unit tests must use:

```python
# tests/fixtures/options_fixtures.py
import pytest
import pandas as pd

@pytest.fixture
def option_chain_fixture():
    def _make(ticker: str, expiry: str) -> pd.DataFrame:
        return pd.DataFrame({
            "strike":           [135.0, 140.0, 145.0, 150.0, 155.0],
            "bid":              [  5.20,  3.40,  2.10,  1.20,  0.60],
            "ask":              [  5.40,  3.60,  2.30,  1.40,  0.80],
            "lastPrice":        [  5.30,  3.50,  2.20,  1.30,  0.70],
            "volume":           [   120,   250,   310,   180,    90],
            "openInterest":     [   450,   800,  1200,   600,   200],
            "impliedVolatility":[  0.35,  0.32,  0.30,  0.28,  0.26],
        })
    return _make
```

This fixture is referenced as `option_chain_fixture` in all unit tests for options data tools.

---

## 5. Execution Batches

The feature is divided into four implementation batches. Each batch corresponds to one delivery phase from the REQ. Tasks within a batch are independent and may be parallelised across agents. Tasks across batches are strictly ordered.

---

## BATCH 1 — Data Foundation (Phase 1)

**Prerequisite:** None.  
**Enables:** All subsequent batches.  
**All tasks parallelisable within this batch:** Yes (B1-T1 through B1-T4 are independent; B1-T5 depends on all four; B1-T6 depends on B1-T5).

| # | Task ID | File(s) | Description | Depends on | AC pointer |
|---|---|---|---|---|---|
| 1 | B1-T1 | `tradingagents/dataflows/y_finance_options.py` (create) | Implement `get_options_chain(ticker, target_date, expiry_date, config)`. Parse dates, fetch expiry list via `yf.Ticker.options`, filter by `options_lookforward_days` (default 90), call `option_chain()` per expiry, format multi-section string. Return `"No options chain available for {ticker}"` on empty; `"Error fetching options chain for {ticker}: {type}"` on network error. | None | REQ-DATA-01 AC1–AC6; FSPEC-WHEEL-01; TSPEC §2.1.1 |
| 2 | B1-T2 | `tradingagents/dataflows/y_finance_options.py` (extend) | Implement `get_iv_metrics(ticker, curr_date, lookback_days=252, iv_series=None)`. Test-seam branch (step 2a/2b in FSPEC-WHEEL-02). Production path: fetch OHLCV, compute log returns, 30-day rolling realised vol × √252. Zero-variance guard → sentinel 50. `iv_environment` derivation (≥50: elevated; 25–49: normal; <25: compressed). Return JSON + report string. | None | REQ-DATA-02 AC1–AC5; FSPEC-WHEEL-02 full algorithm; TSPEC §2.1.2 |
| 3 | B1-T3 | `tradingagents/dataflows/y_finance_options.py` (extend) | Implement `get_options_greeks(ticker, curr_date, expiry_date, strike, option_type, config, *, _spot_price, _risk_free_rate, _sigma)`. Three test seams. BSM: d1/d2 → Delta, Gamma, Vega, Theta_annual/365. `^IRX` risk-free rate with static fallback. DTE validation: `dte < 0` → expired error; `dte == 0` → expired error; IV=0 → error. | None | REQ-DATA-03 AC1–AC7; FSPEC-WHEEL-01; TSPEC §2.1.3 (including canonical BSM numeric verification test) |
| 4 | B1-T4 | `tradingagents/dataflows/y_finance_options.py` (extend) | Implement `get_next_earnings_date(ticker, curr_date)`. Parse `yf.Ticker.calendar`. Compute `days_until`. Compute `within_options_cycle` using front-month expiry (integer-string comparison per TSPEC §2.1.4). Return structured output string or `"No upcoming earnings date available for {ticker}"` on any error. | None | REQ-DATA-04 AC1–AC3; FSPEC-WHEEL-01; TSPEC §2.1.4 |
| 5 | B1-T5 | `tradingagents/agents/utils/options_data_tools.py` (create) | Four `@tool`-decorated wrappers calling `route_to_vendor()`. Catch `ValueError`/`RuntimeError` → graceful error string. Do NOT expose test-seam parameters (`iv_series`, `_spot_price`, etc.) in tool signatures. Tool for `get_options_greeks` exposes only five primary parameters. | B1-T1, B1-T2, B1-T3, B1-T4 | REQ-DATA-05 AC1–AC2; FSPEC-WHEEL-01 business rules; TSPEC §2.2 |
| 6 | B1-T6 | `tradingagents/dataflows/interface.py` (modify) | Add `"options_data"` category to `TOOLS_CATEGORIES`. Add `_stub_not_implemented` module-level function. Register all four methods in `VENDOR_METHODS` with yfinance implementations (imported from `y_finance_options.py`) and Alpha Vantage stub entries. | B1-T5 | REQ-DATA-05 AC1–AC2; FSPEC-WHEEL-01; TSPEC §2.1.1–2.1.4 registration blocks |
| 7 | B1-T7 | `tests/fixtures/options_fixtures.py` (create), `tests/test_options_data.py` (create) | Create canonical `option_chain_fixture` pytest fixture (TSPEC §2.2, REQ-NFR-05). Write unit tests for all four data functions using test seams (`iv_series`, `_spot_price`, `_risk_free_rate`, `_sigma`). Include BSM numeric verification test (TSPEC §2.1.3). Cover zero-variance guard, shortened lookback note, DTE validation errors, IV=0 error, expired option errors, static risk-free rate fallback. | B1-T1, B1-T2, B1-T3, B1-T4, B1-T5, B1-T6 | REQ-NFR-05; TSPEC §2.1.1–2.2 unit test specs; PROP-IV-01, PROP-IV-02 |

**Batch 1 Definition of Done:**
- [ ] All four functions in `y_finance_options.py` implemented and tested.
- [ ] All four `@tool` wrappers in `options_data_tools.py` implemented and tested.
- [ ] `interface.py` updated: `"options_data"` category registered, four methods in `VENDOR_METHODS`.
- [ ] `tests/fixtures/options_fixtures.py` created with canonical `option_chain_fixture`.
- [ ] BSM numeric verification test passes (`Delta_put ≈ −0.4602 ± 0.0005`, `Theta_daily ≈ −0.0314 ± 0.005`).
- [ ] Zero-variance guard test passes: `iv_series=[0.20]*100` → `iv_rank=50`, report contains `"IV range is flat — rank set to neutral 50"`.
- [ ] All unit tests pass with no network calls.

---

## BATCH 2 — Schemas, Config, State, Persistence Foundation (Phase 2 setup)

**Prerequisite:** Batch 1 complete.  
**Enables:** Batch 3 (agents depend on schemas and config).  
**All tasks parallelisable within this batch:** Yes (B2-T1 through B2-T4 are independent).

| # | Task ID | File(s) | Description | Depends on | AC pointer |
|---|---|---|---|---|---|
| 1 | B2-T1 | `tradingagents/agents/schemas.py` (modify) | Add `WheelPhase(str, Enum)`, `TriggerReason` Literal type alias, `WheelCandidateReport` (with `model_validator`), `CspDecision`, `CcDecision`, `RollDecision` Pydantic models, and four render helpers (`render_wheel_candidate_report`, `render_csp_decision`, `render_cc_decision`, `render_roll_decision`). `CspDecision` sentinel note: numeric field constraints apply only when `tradeable=True` (PM-TSPEC-06). | Batch 1 | REQ-SCREEN-02, REQ-TRADE-02, REQ-TRADE-04, REQ-LIFE-04; TSPEC §3.1–3.7 |
| 2 | B2-T2 | `tradingagents/agents/utils/structured.py` (modify) | Add module-level constant `STRUCTURED_OUTPUT_SENTINEL = 'Structured output failed — safe fallback applied.'` (ADR-WHEEL-04 contract). | Batch 1 | ADR-WHEEL-04; TSPEC §10.2 |
| 3 | B2-T3 | `tradingagents/agents/utils/agent_states.py` (modify) | Add five `Optional[str]` fields to `AgentState`: `wheel_phase`, `wheel_candidate_report`, `csp_decision`, `cc_decision`, `roll_decision`. Add `Optional` import if missing. No default values (callers must use `state.get(...)`). | Batch 1 | REQ-LIFE-01; TSPEC §4 |
| 4 | B2-T4 | `tradingagents/default_config.py` (modify) | Add `"wheel"` sub-dict with 18 keys and inline comments. Add `_WHEEL_ENV_OVERRIDES` dict (20 entries). Add `_apply_nested_env_overrides()` helper. Call both helpers at end of `DEFAULT_CONFIG` assembly: `_apply_nested_env_overrides(_apply_env_overrides({...}))`. Add config validation warning for `options_lookforward_days < recommended_dte_high`. | Batch 1 | REQ-NFR-03, REQ-NFR-07; TSPEC §8.1–8.3 |
| 5 | B2-T5 | `tradingagents/models/__init__.py` (create), `tradingagents/models/wheel_position.py` (create) | Create `tradingagents/models/` package. Implement `WheelPosition` Pydantic model (including `csp_open_date` and `prior_analyst_bias` TSPEC extensions). Implement `save_wheel_position`, `load_wheel_position`, `load_latest_open_position` (integer sort — not lexicographic). Atomic write via `tempfile.mkstemp` + `os.replace`. | Batch 1 | REQ-LIFE-02; TSPEC §9.1–9.3; ADR-WHEEL-05 |
| 6 | B2-T6 | `tests/test_schemas.py` (create), `tests/test_config_wheel.py` (create), `tests/test_wheel_position.py` (create) | Schema validation tests (all fields, `model_validator` enforcement, sentinel exemption, `iv_environment` boundaries). Config tests (18 keys present, env var overrides, `_apply_nested_env_overrides`, validation warning). Persistence tests using `tmp_path` (atomic write, `load_latest_open_position` with cycle-10 > cycle-9 regression test `PROP-POSN-01`, round-trip). | B2-T1, B2-T2, B2-T3, B2-T4, B2-T5 | REQ-SCREEN-02 AC1–AC3, REQ-NFR-03, REQ-NFR-05; TSPEC §3, §8, §9; ADR-WHEEL-05 |

**Batch 2 Definition of Done:**
- [ ] All six schemas added to `schemas.py` with render helpers.
- [ ] `STRUCTURED_OUTPUT_SENTINEL` constant in `structured.py`.
- [ ] Five new `Optional[str]` fields in `AgentState`.
- [ ] `config["wheel"]` sub-dict with 18 keys and env var overrides.
- [ ] `tradingagents/models/wheel_position.py` with atomic I/O.
- [ ] `load_latest_open_position` integer-sort regression test passes (cycle-10 returned over cycle-9).
- [ ] All schema validation tests pass (including `model_validator` for `WheelCandidateReport`).
- [ ] No existing tests broken.

---

## BATCH 3 — Wheel Analyst and Options Agents (Phases 2 & 3)

**Prerequisite:** Batch 2 complete.  
**Enables:** Batch 4 (graph wiring depends on all four agents).  
**Tasks parallelisable:** B3-T1 (WheelAnalyst), B3-T2 (CspAgent), B3-T3 (CcAgent), B3-T4 (RollCheckAgent), B3-T5 (risk debate injection) are independent of each other; B3-T6 (tests) depends on all five.

| # | Task ID | File(s) | Description | Depends on | AC pointer |
|---|---|---|---|---|---|
| 1 | B3-T1 | `tradingagents/agents/analysts/wheel_analyst.py` (create) | Implement `create_wheel_analyst(llm)` factory. LLM tier: `deep_think_llm`. Tools: all four options tools. Five criteria evaluated in order (no early exit), all failures accumulated in `rejection_reason` joined by `"; "`. `recommended_strike_range` computed only when `approved=True` (Delta-anchored, with price-based fallback rounded to nearest $0.50). Three-layer structured output fallback using `STRUCTURED_OUTPUT_SENTINEL`. State reads/writes per TSPEC §5.1. ADR-WHEEL-01: `iv_assessment` must surface the zero-variance flat-range note when present. | Batch 2 | REQ-SCREEN-01 AC1–AC8; FSPEC-WHEEL-03; TSPEC §5.1 |
| 2 | B3-T2 | `tradingagents/agents/options/__init__.py` (create), `tradingagents/agents/options/csp_agent.py` (create) | Create `tradingagents/agents/options/` package. Implement `create_csp_agent(llm)` factory. LLM tier: `deep_think_llm`. Tools: `get_options_chain`, `get_options_greeks`, `get_next_earnings_date`. Deterministic `_filter_csp_candidates()` function (Filters A, B, C; inclusive boundaries; progressive relaxation order C→B→A-fallback). `options_lookforward_days` guard. Derived fields computed deterministically. Three-layer structured output fallback using `STRUCTURED_OUTPUT_SENTINEL`. | Batch 2 | REQ-TRADE-01 AC1–AC4b; FSPEC-WHEEL-04; TSPEC §5.2 |
| 3 | B3-T3 | `tradingagents/agents/options/cc_agent.py` (create) | Implement `create_cc_agent(llm, config, *, _position_loader=None)` factory. LLM tier: `deep_think_llm`. Tools: `get_options_chain`, `get_options_greeks`, `get_next_earnings_date`. `_position_loader` keyword-only test seam (default: `load_latest_open_position`). Deterministic `_filter_cc_candidates()` (Filters A=strike≥cost_basis [never relaxed], B=Delta, C=earnings, D=yield; relaxation: D→C→fallback). Below-cost-basis branch. Derived fields deterministic. Three-layer fallback using `STRUCTURED_OUTPUT_SENTINEL`. | Batch 2 | REQ-TRADE-03 AC1–AC3; FSPEC-WHEEL-05; TSPEC §5.3 |
| 4 | B3-T4 | `tradingagents/agents/options/roll_agent.py` (create) | Implement `create_roll_check_agent(llm, position_store_dir)` factory. LLM tier: `quick_think_llm`. Tools: `get_options_chain`, `get_options_greeks`, `get_next_earnings_date`. Five rules evaluated in full (no early exit). Priority resolution: Rule3 > Rule5 > Rule4 > Rule2 > Rule1. Rule3 CSP-only. Rule4 deep-OTM exclusive boundary (`abs(delta) < 0.10`). Rule5 reads/writes `WheelPosition.prior_analyst_bias`. ROLL path populates `new_strike`/`new_expiration`/`estimated_debit_or_credit`. Three-layer fallback using `STRUCTURED_OUTPUT_SENTINEL` (sentinel: `action='HOLD'`, `trigger_reason='profit_capture'`). | Batch 2 | REQ-LIFE-03 AC1–AC4; FSPEC-WHEEL-06; TSPEC §5.4 |
| 5 | B3-T5 | `tradingagents/agents/utils/agent_utils.py` (modify) | Add `_build_options_context(state: AgentState) -> str` helper. Inject `{options_context}` block into each debate agent's prompt after `{market_context}` and before role-assignment instruction. When `wheel_phase is None` (equity-only): `options_context = ""` — debate prompt unchanged. `CspDecision` injection includes `mid_premium`, `probability_of_profit`, `max_loss`, `breakeven_price`, `earnings_clear`. `CcDecision` injection includes `mid_premium`, `upside_to_strike_pct`, `cost_basis`, `earnings_clear`. | Batch 2 | REQ-TRADE-05 AC1–AC3; FSPEC-WHEEL-09; TSPEC §5.5 |
| 6 | B3-T6 | `tests/test_wheel_analyst.py` (create), `tests/test_csp_agent.py` (create), `tests/test_cc_agent.py` (create), `tests/test_roll_agent.py` (create), `tests/test_risk_debate_injection.py` (create) | Agent unit tests using mocked LLM and mocked data tools. Assert on schema fields (not free-text rationale). Three-layer fallback coverage per agent (12 total, PROP-FALLBACK-01–PROP-FALLBACK-12). Filter unit tests: inclusive Delta boundaries (both ends), earnings filter, yield filter, progressive relaxation paths. `_filter_csp_candidates` and `_filter_cc_candidates` tested independently. Rule priority tests for RollCheckAgent. Prompt-content assertions for risk debate injection (REQ-TRADE-05 AC1, AC2, AC3). `_position_loader` test seam used in CcAgent and RollCheckAgent tests. | B3-T1, B3-T2, B3-T3, B3-T4, B3-T5 | REQ-SCREEN-01, REQ-TRADE-01, REQ-TRADE-03, REQ-LIFE-03; REQ-NFR-05; ADR-WHEEL-04 |

**Batch 3 Definition of Done:**
- [ ] `tradingagents/agents/options/` package created with `__init__.py`, `csp_agent.py`, `cc_agent.py`, `roll_agent.py`.
- [ ] `tradingagents/agents/analysts/wheel_analyst.py` created.
- [ ] All four agents use `STRUCTURED_OUTPUT_SENTINEL` (imported from `structured.py`, never hardcoded).
- [ ] All three-layer fallback tests pass (12 test cases across 4 agents).
- [ ] Filter inclusivity boundary tests pass (Delta lower and upper bounds, inclusive).
- [ ] RollCheckAgent priority resolution test: Rule3 > Rule1 and Rule2 > Rule1 both verified.
- [ ] Prompt-content assertion tests pass for risk debate injection.
- [ ] All existing tests still pass.

---

## BATCH 4 — Graph Wiring, Lifecycle, and CLI (Phase 4)

**Prerequisite:** Batch 3 complete.  
**Tasks parallelisable:** B4-T1 (wheel_nodes.py), B4-T2 (conditional_logic.py), B4-T3 (setup.py), B4-T4 (CLI panel), B4-T5 (wheel-status CLI) are largely independent; B4-T3 has a soft dependency on B4-T1 and B4-T2 being designed (can be done in parallel but B4-T3 implementer must coordinate). B4-T6 (tests) depends on all five.

| # | Task ID | File(s) | Description | Depends on | AC pointer |
|---|---|---|---|---|---|
| 1 | B4-T1 | `tradingagents/graph/wheel_nodes.py` (create) | Create `WheelStateError(Exception)` class. Implement `wheel_cycle_summary(state, config)` node function: load `WheelPosition`, compute `cycle_duration_days` (calendar days from `csp_open_date` to `call_away_date`), compute `cycle_pnl`, compute `cycle_annualised_return_pct = (cycle_pnl / (csp_strike × shares_held)) × (365 / cycle_duration_days) × 100`. Write updated `WheelPosition` atomically. Write `TradingMemoryLog` entry (non-blocking on failure). Format human-readable summary. Return `{"wheel_phase": None}`. | Batch 3 | REQ-LIFE-01 routing to `wheel_cycle_summary`; REQ-LIFE-02 AC3/AC3a (33.21%, not 33.25%); REQ-LIFE-05; TSPEC §6.3 |
| 2 | B4-T2 | `tradingagents/graph/conditional_logic.py` (modify) | Extend `ConditionalLogic.__init__` to accept `first_analyst_node: str = "Market Analyst"` and `position_store_dir: str = "memory/wheel_positions"`. Add `_load_position(ticker)` private helper using `load_latest_open_position`. Implement `route_wheel_phase(state)` method with full routing table. Raise `WheelStateError` on guard failures for `"csp_open"` and `"cc_open"` branches. Log warning (and surface to CLI user per ADR-WHEEL-02) on unknown `wheel_phase` value; return `first_analyst_node` as fallback. Import `WheelStateError` from `wheel_nodes.py`. | Batch 3 | REQ-LIFE-01 AC1–AC6; FSPEC-WHEEL-07; TSPEC §6.2; ADR-WHEEL-03 |
| 3 | B4-T3 | `tradingagents/graph/setup.py` (modify), `tradingagents/agents/__init__.py` (modify) | **setup.py changes:** Replace `workflow.add_edge(START, plan.specs[0].agent_node)` (line 89) with `workflow.add_conditional_edges(START, self.conditional_logic.route_wheel_phase, wheel_route_mapping)`. Pass `first_analyst_node` and `position_store_dir` to `ConditionalLogic` at construction time. Conditionally register `wheel_analyst` node when `"wheel" in selected_analysts`. Register `csp_agent`, `cc_agent`, `roll_check_agent`, `wheel_cycle_summary` nodes. Register `tools_options` ToolNode. Add `"Trader" → "wheel_analyst" → "Aggressive Analyst"` edge when wheel selected; `"Trader" → "Aggressive Analyst"` otherwise. Add `"wheel_cycle_summary" → END` edge. Add config validation warning for `options_lookforward_days`. **agents/__init__.py:** Export new agent factory functions. | Batch 3, B4-T1, B4-T2 | REQ-LIFE-01; REQ-SCREEN-01 AC5; REQ-NFR-01; TSPEC §6.1; ADR-WHEEL-03 |
| 4 | B4-T4 | CLI display module (modify — identify exact file via `grep -r "MessageBuffer\|update_report_section" tradingagents/`) | Add `"wheel_candidate"` section key to `MessageBuffer`. Assemble `report_text` from `WheelCandidateReport` following exact TSPEC §7.1 template (opens with `## WheelCandidateReport`). Rich panel title `"Wheel Suitability"`. Style: `"bold red"` when `approved=False`, default when `approved=True`. Display guard: only when `"wheel" in selected_analysts` AND `state.get("wheel_candidate_report")` is not None. Surface ADR-WHEEL-02 unknown-phase warning to CLI output. ADR-WHEEL-01: surface zero-variance flat-range note in `iv_assessment` display. | Batch 3 | REQ-SCREEN-03 AC1–AC3; FSPEC-WHEEL-08; TSPEC §7.1 |
| 5 | B4-T5 | CLI entry point (modify — identify via `grep -r "@app.command\|typer\|click" tradingagents/` or main CLI file) | Add `wheel-status` sub-command per TSPEC §7.2. Glob `*.json` from `positions_dir`. Parse each as `WheelPosition`. Separate into open and completed. Fetch live spot prices via yfinance. Compute unrealised P&L. Render Rich Table 1 (open positions: ticker, phase, strike, expiration, DTE, cost basis, premium collected, P&L) and Table 2 (completed cycles: ticker, cycle#, duration, total premium, P&L, ann. return). When no open positions: output exact string `"No open wheel positions"` (REQ-LIFE-06 AC2). | Batch 3 | REQ-LIFE-06 AC1–AC3; TSPEC §7.2 |
| 6 | B4-T6 | `tests/test_graph_routing.py` (create), `tests/test_wheel_nodes.py` (create), `tests/test_cli_wheel.py` (create) | **Graph routing tests:** `wheel_phase=None` → equity path (PROP-ROUTE-02: equity-passthrough integration test invariant, ADR-WHEEL-03). `wheel_phase="cc_open"` with no WheelPosition → `WheelStateError`. `wheel_phase="invalid_phase"` → equity path + warning log (PROP-ROUTE-01, ADR-WHEEL-02). `wheel_phase="screening"` → first analyst node. `wheel_phase="stock_owned"` → `cc_agent`. `wheel_phase="cycle_complete"` → `wheel_cycle_summary`. **Wheel nodes tests:** `cycle_annualised_return_pct` formula verification: inputs `cycle_pnl=930, csp_strike=140, shares_held=100, cycle_duration_days=73` → result `≈ 33.21%` (not 33.25%, TSPEC §9.4 discrepancy note). Memory log write failure does not block state reset. **CLI tests:** Rich `Console(file=StringIO())` injection. `console.export_text()` assertions on `"WheelCandidateReport"`, `"Wheel Suitability"`, `"IV Rank"`, `rejection_reason`. `"No open wheel positions"` string. Annualised return in completed cycle table. | B4-T1, B4-T2, B4-T3, B4-T4, B4-T5 | REQ-LIFE-01 AC1–AC6; REQ-SCREEN-03; REQ-LIFE-06; ADR-WHEEL-02, ADR-WHEEL-03, ADR-WHEEL-05; PROP-ROUTE-01, PROP-ROUTE-02 |

**Batch 4 Definition of Done:**
- [ ] `wheel_nodes.py` created with `WheelStateError` and `wheel_cycle_summary` node.
- [ ] `conditional_logic.py` extended with `route_wheel_phase()` and `_load_position()`.
- [ ] `setup.py` modified: `START → wheel_router` conditional edge replaces direct edge (line 89).
- [ ] `"wheel"` in `selected_analysts` conditionally adds `wheel_analyst` node and routes `"Trader" → "wheel_analyst" → "Aggressive Analyst"`.
- [ ] `tools_options` ToolNode registered in graph.
- [ ] CLI panel for WheelCandidateReport renders with correct strings for both approved and rejected cases.
- [ ] `wheel-status` CLI sub-command outputs correct Rich tables and `"No open wheel positions"` string.
- [ ] Equity-passthrough integration test passes: `wheel_phase=None` → first analyst node, no options nodes visited, no wheel state fields written.
- [ ] `cycle_annualised_return_pct` test passes with 33.21% (not 33.25%).
- [ ] All existing tests still pass.

---

## 6. Key Files Reference

### New files created

| File | Batch | Purpose |
|---|---|---|
| `tradingagents/dataflows/y_finance_options.py` | B1 | Four yfinance options data functions |
| `tradingagents/agents/utils/options_data_tools.py` | B1 | `@tool`-decorated LangChain wrappers |
| `tradingagents/models/__init__.py` | B2 | Package init |
| `tradingagents/models/wheel_position.py` | B2 | `WheelPosition` model + atomic JSON I/O |
| `tradingagents/agents/options/__init__.py` | B3 | Package init |
| `tradingagents/agents/options/csp_agent.py` | B3 | `CspAgent` — CSP trade recommendation |
| `tradingagents/agents/options/cc_agent.py` | B3 | `CcAgent` — covered call recommendation |
| `tradingagents/agents/options/roll_agent.py` | B3 | `RollCheckAgent` — roll/hold/close decision |
| `tradingagents/agents/analysts/wheel_analyst.py` | B3 | `WheelAnalyst` — suitability screening |
| `tradingagents/graph/wheel_nodes.py` | B4 | `wheel_cycle_summary` node + `WheelStateError` |
| `tests/fixtures/options_fixtures.py` | B1 | Canonical `option_chain_fixture` |
| `tests/test_options_data.py` | B1 | Data function unit tests |
| `tests/test_schemas.py` | B2 | Schema validation tests |
| `tests/test_config_wheel.py` | B2 | Config + env override tests |
| `tests/test_wheel_position.py` | B2 | Persistence tests (tmp_path isolated) |
| `tests/test_wheel_analyst.py` | B3 | WheelAnalyst unit tests |
| `tests/test_csp_agent.py` | B3 | CspAgent unit + integration tests |
| `tests/test_cc_agent.py` | B3 | CcAgent unit tests |
| `tests/test_roll_agent.py` | B3 | RollCheckAgent unit tests |
| `tests/test_risk_debate_injection.py` | B3 | Prompt-content assertion tests |
| `tests/test_graph_routing.py` | B4 | Graph routing + state machine tests |
| `tests/test_wheel_nodes.py` | B4 | `wheel_cycle_summary` unit tests |
| `tests/test_cli_wheel.py` | B4 | CLI panel + wheel-status tests |

### Existing files modified

| File | Batch | Modification |
|---|---|---|
| `tradingagents/dataflows/interface.py` | B1 | Add `"options_data"` category and four methods to `VENDOR_METHODS` |
| `tradingagents/agents/utils/structured.py` | B2 | Add `STRUCTURED_OUTPUT_SENTINEL` constant |
| `tradingagents/agents/schemas.py` | B2 | Add 6 new schemas + 4 render helpers |
| `tradingagents/agents/utils/agent_states.py` | B2 | Add 5 `Optional[str]` fields to `AgentState` |
| `tradingagents/default_config.py` | B2 | Add `config["wheel"]` sub-dict + env overrides |
| `tradingagents/agents/utils/agent_utils.py` | B3 | Add `_build_options_context` and inject into debate prompts |
| `tradingagents/agents/__init__.py` | B4 | Export new agent factory functions |
| `tradingagents/graph/conditional_logic.py` | B4 | Add `route_wheel_phase()` method |
| `tradingagents/graph/setup.py` | B4 | Replace `START → first_analyst` direct edge; register wheel nodes |
| CLI entry module | B4 | Add `wheel-status` sub-command; add wheel panel to `MessageBuffer` |

---

## 7. Integration Points

| Integration point | Existing code | What changes |
|---|---|---|
| `START → first_analyst` edge in `setup.py` line 89 | `workflow.add_edge(START, plan.specs[0].agent_node)` | Replaced by `workflow.add_conditional_edges(START, conditional_logic.route_wheel_phase, mapping)` |
| `ConditionalLogic.__init__` | `def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1)` | Add `first_analyst_node: str` and `position_store_dir: str` parameters |
| `TOOLS_CATEGORIES` in `interface.py` | Four categories: `core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data` | New fifth category: `"options_data"` |
| `AgentState` TypedDict | 9 existing fields | Five new `Optional[str]` fields appended; no existing fields changed |
| `DEFAULT_CONFIG` in `default_config.py` | Flat config + `_apply_env_overrides` | New `"wheel"` sub-dict; new `_apply_nested_env_overrides` helper called in tandem |
| `"Trader" → "Aggressive Analyst"` edge (setup.py line 129) | Direct unconditional edge | Conditional: when `"wheel" in selected_analysts`, route through `"wheel_analyst"` first |
| Debate agent prompt assembly in `agent_utils.py` | No options context | `_build_options_context` injected after `{market_context}`, before role-assignment instruction |

---

## 8. Open Issues (carry-forward from TSPEC §10)

These items were deferred to PLAN authoring by the TSPEC. They must be resolved before Batch 3–4 implementation begins:

| # | Issue | Decision required | Owner |
|---|---|---|---|
| OI-01 | **`scipy` dependency** (TSPEC §10.7): `get_options_greeks` needs `scipy.stats.norm.cdf`/`pdf` for BSM. | Add `scipy` to `pyproject.toml` / `requirements.txt` OR implement standard normal CDF via `math.erfc` to avoid the dependency. Either is acceptable for MVP. | B1-T3 implementer to decide before starting |
| OI-02 | **`csp_open` → `stock_owned` trigger** (TSPEC §10.2 item 2): Assignment detection is manual (human updates `wheel_phase`). | Confirm: no automated assignment detection in Phase 1. A future CLI command `tradingagents wheel-assign {ticker} {date}` is noted as a Phase 5 addition. | Confirm with product owner before B4-T2 |
| OI-03 | **`cc_open` → `stock_owned` on CC expiry worthless** (TSPEC §10.2 item 3): Same as OI-02. | Same as OI-02 — manual state update. | Confirm with product owner before B4-T2 |
| OI-04 | **CLI module location for wheel panel and `wheel-status`** (B4-T4, B4-T5): The exact CLI entry file must be identified before B4-T4/T5 implementation. | Run `grep -r "MessageBuffer\|update_report_section\|@app.command" tradingagents/` to locate the target file. | B4-T4/T5 implementer to identify at start |
| OI-05 | **Rule 1 action at 50% profit target** (TSPEC §10.5): REQ-LIFE-03 AC1 specifies `action="HOLD"`. The TSPEC follows REQ. | HOLD is confirmed. If product owner wishes to change to CLOSE, a REQ patch is required before implementation. No change in this PLAN. | Noted; no blocking action |
| OI-06 | **Breach threshold configurability** (TSPEC §10.6): 15% threshold hardcoded. | Hardcoded in Phase 1. Add `breach_threshold_pct` to `config["wheel"]` in a future phase. | Noted; no blocking action |
| OI-07 | **`options_data_tools.py` wiring to agent tool-calling turns** (TSPEC §10.2 item 4): The `tools_options` ToolNode must be wired so WheelAnalyst, CspAgent, CcAgent, and RollCheckAgent can call tools during their turns. | WheelAnalyst uses the existing analyst tool-call pattern (`should_continue_wheel` conditional edge → `tools_options` → back to agent). Options agents use direct calls to the raw functions in the factory (not via ToolNode), matching the pattern used by traders and researchers. PLAN author recommendation: confirm with existing tool-binding pattern before B4-T3. | B4-T3 implementer to confirm tool-calling pattern |

---

## 9. `cycle_annualised_return_pct` discrepancy note

The REQ v0.2.0 AC3a states "approximately 33.25%". The arithmetically correct value for the AC3a test inputs (`cycle_pnl=930, csp_strike=140, shares_held=100, cycle_duration_days=73`) is **33.21%**. The TSPEC v0.2.0 §9.4 is authoritative. All tests must assert against **33.21%** (tolerance ±0.01%) and include a comment:

```python
# NOTE: REQ v0.2.0 AC3a states "approximately 33.25%" but the
# arithmetically correct value is 33.21%. See TSPEC §9.4 discrepancy note.
# TSPEC is authoritative. REQ v0.3.0 patch pending.
```

---

## 10. scipy decision (OI-01)

**Recommendation:** Add `scipy` to project dependencies. `scipy.stats.norm.cdf` and `.pdf` are well-established, fast, and already available in nearly all Python ML environments. The `math.erfc` approximation introduces numeric deviation from the canonical Hull 10e BSM values and would require a separate test calibration. Given the TSPEC's explicit numeric verification requirement (tolerance ±0.0005 on Delta), `scipy` is the safer choice.

**Action for B1-T3 implementer:** Check `pyproject.toml` and/or `requirements.txt` for existing `scipy` entry. If absent, add `scipy>=1.10.0` to the appropriate dependency list before implementing `get_options_greeks`.

---

## 11. Definition of Done (Feature-level)

The entire wheel-options-trading feature is complete when:

- [ ] All four batches (B1–B4) are complete.
- [ ] All unit tests pass (no `@pytest.mark.smoke` tests required for CI pass).
- [ ] The equity-passthrough integration test passes: a graph invocation with `wheel_phase=None` produces output identical to a pre-feature equity-only invocation (PROP-ROUTE-02).
- [ ] The integer-sort regression test passes (PROP-POSN-01).
- [ ] All 12 structured-output fallback test cases pass (PROP-FALLBACK-01 through PROP-FALLBACK-12).
- [ ] `STRUCTURED_OUTPUT_SENTINEL` is imported (never hardcoded) in all four agents and in CLI display.
- [ ] IV environment label in CLI annotated as realised-volatility-based (ADR-WHEEL-01).
- [ ] Zero-variance flat-range note surfaced in `iv_assessment` and CLI when it fires (ADR-WHEEL-01).
- [ ] `cycle_annualised_return_pct` test asserts 33.21% with discrepancy comment (TSPEC §9.4).
- [ ] No existing tests broken (REQ-NFR-01 backward compatibility).
- [ ] All new `config["wheel"]` keys have inline comments (REQ-NFR-07).
- [ ] PROPERTIES document references this PLAN for property-to-task traceability.
