# REQ — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.2.0 |
| **Created** | 2026-05-25 |
| **Upstream** | Feasibility Analysis (ARCHITECTURE.md, FLOW_DIAGRAM.md, DEPENDENCY_GRAPH.md, CAPABILITIES.md) → **REQ** |
| **Downstream** | FSPEC, TSPEC, PROPERTIES |
| **Cross-Reviews** | `CROSS-REVIEW-software-engineer-REQ.md`, `CROSS-REVIEW-test-engineer-REQ.md` |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.2.0 | 2026-05-25 | Address SE and TE cross-review v1 findings (9 High, 13 Medium, 6 Low) |
| 0.1.0 | 2026-05-25 | Initial draft |

---

## 1. Problem Statement

The existing TradingAgents codebase delivers strong equity buy/hold/sell recommendations through a multi-agent LLM pipeline. However, it cannot support **wheel options trading** — a systematic premium-income strategy that sells cash-secured puts (CSP) on desired stocks and covered calls (CC) on assigned shares.

The gaps identified in the feasibility analysis are:

1. No options chain data is fetched or exposed to agents (strikes, expirations, bid/ask, open interest, implied volatility).
2. No options Greeks are calculated or retrievable (Delta, Theta, Vega, Gamma).
3. No IV Rank / IV Percentile computation exists — the primary entry signal for premium sellers.
4. The decision schema (Buy/Overweight/Hold/Underweight/Sell) does not map to options trade selection.
5. The graph has no wheel phase state machine: it cannot track CSP → Assignment → CC → Cycle repeat.
6. No position tracking: no cost basis, no cumulative premium income, no P&L per cycle.

Wheel trading is a well-defined, rules-governed strategy. An LLM agent system is well-suited to automate the qualitative judgment calls (is this stock suitable? should I roll?) while the quantitative mechanics are precisely specified in requirements.

---

## 2. User Stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | Options trader | Screen stocks for wheel suitability using the existing analyst pipeline | I can quickly identify high-probability candidates without manual research |
| US-02 | Options trader | Know the IV environment before selling premium | I can sell when IV is elevated and avoid selling into crushed volatility |
| US-03 | Options trader | Receive a specific CSP recommendation (strike, expiration, premium, delta) | I can place a trade immediately without doing options chain math manually |
| US-04 | Options trader | Receive a specific CC recommendation after assignment | I can continue the wheel on assigned shares toward a favourable exit |
| US-05 | Options trader | Track open wheel positions and their cost basis | I know my break-even price and total income collected so far |
| US-06 | Options trader | Receive a roll / hold / close recommendation at defined checkpoints | I can manage positions reactively rather than guessing |
| US-07 | Options trader | See a running P&L and annualised yield for each wheel cycle | I can evaluate strategy performance across multiple tickers |
| US-08 | Options trader | Avoid earnings events when selling options | I don't take on binary event risk unintentionally |
| US-09 | Options trader | Use the existing CLI with wheel-specific prompts | I don't need to learn a new tool — the familiar interface works |
| US-10 | Developer | Configure data vendor and model settings for options features via env vars | I can deploy the options layer without code changes |

---

## 3. Scope

### In Scope
- Options chain data ingestion via yfinance (Phase 1)
- IV Rank and IV Percentile calculation from 30-day realised historical volatility percentile using OHLCV close prices (Phase 1)
- Black-Scholes-Merton Greeks calculation for at-the-money and near-the-money strikes (Phase 1)
- Wheel suitability screening agent integrating into the existing analyst pipeline (Phase 2)
- CSP selection agent producing a structured, actionable recommendation (Phase 3)
- CC selection agent producing a structured, actionable recommendation (Phase 3)
- Wheel phase state machine (CSP → Assignment → CC → Called Away → Repeat) (Phase 4)
- Position tracker recording cost basis, premium collected, and cycle P&L (Phase 4)
- Roll/hold/close decision agent at configurable checkpoints (Phase 4)
- CLI extensions exposing wheel-mode prompts and position display (Phases 2–4)
- Memory log integration for wheel cycle history (Phase 4)

### Out of Scope (all phases)
- Broker API integration or live order execution (no IBKR, Tastytrade, Schwab)
- Real-time streaming options data (tick-level or Level 2 quotes)
- Multi-leg spreads (strangles, straddles, butterflies, calendars)
- Portfolio-level margin / buying-power calculation
- Backtesting engine
- Options on ETFs or indices (SPX, NDX) — strategy is equity-focused
- Cryptocurrency options

### Assumptions
- A1: `yfinance` options chain data (via `Ticker.option_chain()`) is sufficient for Phase 1–3 data needs. Premium data providers (CBOE LiveVol, ORATS) are deferred.
- A2: Greeks are computed locally via Black-Scholes-Merton using yfinance-supplied IV as the volatility input. This introduces model risk on illiquid names; acceptable for MVP.
- A3: **IV Rank is computed as a realised volatility percentile from OHLCV close prices, not from historical options IV.** Specifically: a 30-day rolling realised volatility (annualised) is computed from `Ticker.history()` close prices over `iv_rank_lookback_days` trading days. IV Rank = `(current_realised_vol − min_realised_vol_lookback) / (max_realised_vol_lookback − min_realised_vol_lookback) × 100`. IV Percentile = fraction of days where realised vol was below today's level. This approach is implementable from OHLCV data alone; yfinance does not provide a historical IV time series. The terms "IV Rank" and "IV Percentile" are retained for user familiarity but refer to realised volatility rank/percentile.
- A4: The existing `AgentState` TypedDict can be extended without breaking existing equity-analysis flows.
- A5: The system produces recommendations only. The human trader executes via their own broker.
- A6: A "wheel cycle" is one complete CSP→Assignment→CC→CallAway sequence on a single ticker.

---

## 4. Delivery Phases

The feature is decomposed into four phases. Each phase ships independently useful functionality.

```
Phase 1 — Options Data Foundation       (Prerequisite for all later phases)
  ↓
Phase 2 — Wheel Candidate Screening     (Identify stocks worth wheeling)
  ↓
Phase 3 — Trade Recommendation Engine   (Generate CSP and CC trade specs)
  ↓
Phase 4 — Wheel Lifecycle Management    (Track positions, roll decisions, P&L)
```

---

## 5. Requirements

---

### PHASE 1 — Options Data Foundation

**Goal:** Expose raw options data, IV metrics, and Greeks as LangChain tools callable by any agent. No new agents yet — this is a pure data layer.

---

#### REQ-DATA-01: Options Chain Retrieval Tool

| Field | Value |
|---|---|
| **ID** | REQ-DATA-01 |
| **Title** | Options chain retrieval as a callable tool |
| **Priority** | P0 |
| **Phase** | 1 |
| **Source stories** | US-03, US-04, US-08 |
| **Dependencies** | None |

**Description**

A new tool function `get_options_chain(ticker, target_date, expiry_date?)` must be added to `tradingagents/dataflows/y_finance.py` and registered in `tradingagents/dataflows/interface.py`. It must return a structured text summary of the available options chain (calls and puts) for the given ticker on or closest to `target_date`, with columns: strike, bid, ask, last, volume, open_interest, implied_volatility. When `expiry_date` is omitted, all available expiration dates within a configurable look-ahead window (default: 90 days, calendar days, inclusive boundary `expiry_date <= target_date + timedelta(days=options_lookforward_days)` anchored to `target_date`) are returned as a summary.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | A valid ticker and target date | `get_options_chain("NVDA", "2024-05-10")` is called | Returns a formatted string containing put and call chains for all expirations within 90 calendar days of `target_date` (inclusive), with strike, bid, ask, volume, OI, and IV columns |
| AC2 | Agent | A ticker with no available options (empty DataFrame from yfinance) | Tool is called | Returns `"No options chain available for {ticker}"` rather than raising an exception |
| AC3 | Developer | `config["data_vendors"]["options_data"]` is set to `"alpha_vantage"` | Tool is called | Routes to Alpha Vantage adapter (stub returning "not implemented" is acceptable in Phase 1) |
| AC4 | Agent | A valid ticker and a specific expiry date | `get_options_chain("NVDA", "2024-05-10", expiry_date="2024-06-21")` is called | Returns only the chain for that single expiration |
| AC5 | Agent | yfinance raises `HTTPError` or `ConnectionError` | Tool is called | Returns `"Error fetching options chain for {ticker}: {error_type}"` rather than raising an exception |
| AC6 | Agent | `option_chain()` returns an empty DataFrame (valid ticker, no listed options) | Tool is called | Returns `"No options chain available for {ticker}"` (distinct from network error in AC5) |

---

#### REQ-DATA-02: IV Rank and IV Percentile Calculation

| Field | Value |
|---|---|
| **ID** | REQ-DATA-02 |
| **Title** | IV Rank and IV Percentile as callable tools (realised volatility proxy) |
| **Priority** | P0 |
| **Phase** | 1 |
| **Source stories** | US-02 |
| **Dependencies** | None |

**Description**

A new tool function `get_iv_metrics(ticker, curr_date, lookback_days=252, iv_series: Optional[list[float]] = None)` must be added to `tradingagents/dataflows/y_finance.py`. When `iv_series` is provided (non-None), it is used directly as the historical volatility series, bypassing the yfinance historical fetch — this parameter exists solely to support unit testing. When `iv_series` is None (production path), the function computes a 30-day rolling realised volatility (annualised standard deviation of log returns) from `Ticker.history()` close prices over `lookback_days` trading days.

**Rationale for OHLCV approach:** yfinance does not provide a historical IV time series; `Ticker.option_chain()` returns only a snapshot at call time. Building a 252-day daily IV series via repeated historical calls is not supported by the yfinance API. Using 30-day realised volatility from OHLCV is the implementable proxy; the user-facing terminology "IV Rank" and "IV Percentile" is retained for familiarity.

The function returns a structured object (or parseable dict) with: `current_vol`, `max_vol_lookback`, `min_vol_lookback`, `iv_rank` (0–100), `iv_percentile` (0–100), `iv_environment: Literal["elevated", "normal", "compressed"]`, and a formatted report string. The `iv_environment` field is set as: `"elevated"` when `iv_rank >= 50`, `"normal"` when `25 <= iv_rank < 50`, `"compressed"` when `iv_rank < 25`.

**Formulae:**
- `iv_rank = (current_vol − min_vol_lookback) / (max_vol_lookback − min_vol_lookback) × 100`
- `iv_percentile = (days where realised_vol < current_vol) / total_days × 100`
- When `max_vol_lookback == min_vol_lookback` (zero variance): `iv_rank = 50`, `iv_percentile = 50`, and the report includes the note `"IV range is flat — rank set to neutral 50"`.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | A valid ticker with 252+ trading days of OHLCV history | Tool is called | Returns `iv_rank` and `iv_percentile` in [0, 100] with no NaN values |
| AC2 | Agent | A ticker with fewer than 252 trading days of OHLCV history | Tool is called | Uses available days and notes the shorter lookback in the output |
| AC3 | Agent | `iv_rank >= 50` | Tool result is read | Returned `iv_environment` is `"elevated"` |
| AC4 | Agent | `iv_rank < 25` | Tool result is read | Returned `iv_environment` is `"compressed"` |
| AC5 | System | `max_vol_lookback == min_vol_lookback` (zero IV variance) | Tool is called | Returns `iv_rank = 50` and the report string includes `"IV range is flat — rank set to neutral 50"` |

---

#### REQ-DATA-03: Options Greeks Calculation

| Field | Value |
|---|---|
| **ID** | REQ-DATA-03 |
| **Title** | Black-Scholes-Merton Greeks for near-the-money strikes |
| **Priority** | P0 |
| **Phase** | 1 |
| **Source stories** | US-03, US-04 |
| **Dependencies** | REQ-DATA-01 |

**Description**

A new tool function `get_options_greeks(ticker, curr_date, expiry_date, strike, option_type)` must be added. It uses Black-Scholes-Merton with: underlying price from yfinance, risk-free rate sourced per `config["wheel"]["risk_free_rate_source"]` (see Section 7), IV from the chain for that specific strike, and time-to-expiry in **calendar days / 365** (DTE is always calendar days; annualisation uses 365 throughout). It returns Delta, Gamma, Theta (daily), Vega, and a plain-English interpretation for each Greek relevant to a premium-selling context (e.g., "Delta 0.28 — this strike is approximately 28% likely to be in-the-money at expiration").

**Risk-free rate:** The primary source is `yf.Ticker("^IRX")` (13-week T-bill yield, returned by yfinance as a percentage — divide by 100 before use in BSM). When `^IRX` is unavailable, the function falls back to `config["wheel"]["risk_free_rate_static"]` (default: 0.0525).

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | A valid strike, expiry, and option type (put/call) | Tool is called | Returns Delta, Gamma, Theta, Vega as numeric values + interpretations |
| AC2 | System | A put option at ATM strike | Greeks are computed | Delta is in the range (−0.55, −0.45) |
| AC3 | System | An option with 0 DTE | Tool is called | Returns an error `"Cannot compute Greeks for expired option"` rather than dividing by zero |
| AC4 | Agent | `option_type` is not "put" or "call" | Tool is called | Returns a clear validation error |
| AC5 | System | `dte < 0` (expiry already past) | Tool is called | Returns `"Cannot compute Greeks: option has already expired"` |
| AC6 | System | IV = 0 for the requested strike | Tool is called | Returns `"Cannot compute Greeks: implied volatility is zero for strike {strike}"` |
| AC7 | System | `^IRX` yfinance ticker is unavailable | Tool is called | Falls back to `config["wheel"]["risk_free_rate_static"]` and includes the note `"using static risk-free rate"` in the output |

---

#### REQ-DATA-04: Earnings Date Lookup Tool

| Field | Value |
|---|---|
| **ID** | REQ-DATA-04 |
| **Title** | Next earnings date retrieval |
| **Priority** | P0 |
| **Phase** | 1 |
| **Source stories** | US-08 |
| **Dependencies** | None |

**Description**

A new tool function `get_next_earnings_date(ticker, curr_date)` must be added to `tradingagents/dataflows/y_finance.py`. It returns the next scheduled earnings date after `curr_date`, the number of calendar days until that date, and a flag `within_options_cycle: bool`. The flag is `True` if the next earnings date falls **on or before** the front-month expiration date — meaning the earnings event will occur before the option expires (i.e., `earnings_date <= expiration_date`). Sourced via `yf.Ticker.calendar`.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | A ticker with a known upcoming earnings date | Tool is called | Returns date string, days_until, and within_options_cycle accurately |
| AC2 | Agent | Earnings is 10 days away and the next expiration is 30 days away | Tool is called | `within_options_cycle` is `True` because the earnings event falls within the option's remaining life (earnings date < expiry date) |
| AC3 | Agent | No earnings date is available | Tool is called | Returns `"No upcoming earnings date available for {ticker}"` |

---

#### REQ-DATA-05: Options Data Tool Registration

| Field | Value |
|---|---|
| **ID** | REQ-DATA-05 |
| **Title** | All options tools registered in interface.py and exposed as LangChain tools |
| **Priority** | P0 |
| **Phase** | 1 |
| **Source stories** | US-10 |
| **Dependencies** | REQ-DATA-01, REQ-DATA-02, REQ-DATA-03, REQ-DATA-04 |

**Description**

All four new data functions must be wrapped as `@tool`-decorated LangChain tools in a new module `tradingagents/agents/utils/options_data_tools.py` and registered in `tradingagents/dataflows/interface.py` under the `"options_data"` category (matching the existing category naming convention: `"core_stock_apis"`, `"technical_indicators"`, etc.). The `@tool` wrappers in `options_data_tools.py` **must** call `interface.py`'s `route_to_vendor()` and **must not** import `y_finance.py` functions directly, so that vendor routing and fallback chains are preserved. All four methods must be registered in `VENDOR_METHODS` with yfinance implementations and Alpha Vantage stub entries. The config routing key is `config["data_vendors"]["options_data"]`.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Developer | `config["data_vendors"]["options_data"] = "yfinance"` | An agent is instantiated | The agent can bind options tools via the existing tool-binding pattern |
| AC2 | Developer | A new Alpha Vantage options adapter is added | Config switches to `"alpha_vantage"` | All four tools route to the new adapter without changing agent code |

---

### PHASE 2 — Wheel Candidate Screening

**Goal:** Add a `WheelAnalyst` agent that evaluates whether a given ticker is a suitable wheel candidate, integrating with the existing four-analyst pipeline. Deliverable: a `WheelCandidateReport` that approves or rejects the ticker with rationale, a recommended strike anchor range, and a recommended DTE window.

---

#### REQ-SCREEN-01: Wheel Analyst Agent

| Field | Value |
|---|---|
| **ID** | REQ-SCREEN-01 |
| **Title** | WheelAnalyst agent for options-specific suitability assessment |
| **Priority** | P0 |
| **Phase** | 2 |
| **Source stories** | US-01, US-02, US-08 |
| **Dependencies** | REQ-DATA-01, REQ-DATA-02, REQ-DATA-03, REQ-DATA-04 |

**Description**

A new agent `WheelAnalyst` must be created at `tradingagents/agents/analysts/wheel_analyst.py`. It runs after the existing four analysts and uses the Phase 1 tools plus the existing analyst reports to produce a `WheelCandidateReport`. The agent evaluates:

1. **IV environment** — Is IV Rank ≥ 25 (configurable threshold `min_iv_rank`)?
2. **Chain liquidity** — Are there near-the-money strikes with OI ≥ 100 and bid/ask spread ≤ 10% of mid-price?
3. **Earnings clearance** — Is the next earnings date more than `earnings_buffer_days` (default 14) days beyond the target expiration?
4. **Price affordability** — Is the stock price ≤ `max_wheel_stock_price` (default $500) so that one contract is cash-manageable?
5. **Existing analyst consensus** — Does the underlying analyst pipeline indicate a neutral-to-bullish bias (Hold, Overweight, or Buy)?

`WheelAnalyst` calls `get_options_greeks` to compute a Delta-anchored strike range for the `recommended_strike_range` field in `WheelCandidateReport`. This grounds the recommended range in Delta values consistent with REQ-TRADE-01's Delta-based strike selection.

Agent unit tests must mock the LLM and assert on structured-output schema fields (e.g., `approved: bool`, `rejection_reason: str`), not on free-text `rationale` strings.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | All five criteria are met | WheelAnalyst runs | Report is `approved: true` |
| AC2 | Agent | IV Rank is 15 (below threshold) | WheelAnalyst runs | Report is `approved: false` with `rejection_reason` non-empty |
| AC3 | Agent | Earnings is 12 days away and target expiry is 30 DTE | WheelAnalyst runs | Report is `approved: false` with `rejection_reason` non-empty |
| AC4 | Agent | Bull/Bear debate concluded with Sell rating | WheelAnalyst runs | Report is `approved: false` with `rejection_reason` non-empty |
| AC5 | Developer | `selected_analysts` config does not include "wheel" | Graph is built | WheelAnalyst node is excluded and the pipeline runs as before |
| AC6 | System | All near-the-money strikes have OI < 100 | WheelAnalyst runs | Report is `approved: false` with `rejection_reason` containing `"Insufficient liquidity"` |
| AC7 | System | All near-the-money strikes have bid/ask spread > 10% of mid | WheelAnalyst runs | Report is `approved: false` with `rejection_reason` containing `"Chain spread too wide"` |
| AC8 | System | Stock price is $600 with `max_wheel_stock_price=500` | WheelAnalyst runs | Report is `approved: false` with `rejection_reason` containing `"Stock price exceeds cash management limit"` |

---

#### REQ-SCREEN-02: WheelCandidateReport Schema

| Field | Value |
|---|---|
| **ID** | REQ-SCREEN-02 |
| **Title** | Structured WheelCandidateReport Pydantic schema |
| **Priority** | P0 |
| **Phase** | 2 |
| **Source stories** | US-01, US-02, US-03 |
| **Dependencies** | REQ-SCREEN-01 |

**Description**

A Pydantic model `WheelCandidateReport` must be added to `tradingagents/agents/schemas.py`:

```
WheelCandidateReport
├── approved: bool
├── rejection_reason: Optional[str]          # populated when approved=False
├── iv_rank: float                            # 0–100
├── iv_percentile: float                      # 0–100
├── iv_environment: Literal["elevated", "normal", "compressed"]
├── iv_assessment: str                        # plain-English summary
├── next_earnings_date: Optional[str]         # YYYY-MM-DD
├── earnings_clearance_ok: bool
├── liquidity_ok: bool
├── analyst_bias: str                         # "bullish" | "neutral" | "bearish"
├── recommended_strike_range: list[float] = Field(min_length=2, max_length=2)   # [low_strike, high_strike]
├── recommended_dte_range: list[int] = Field(min_length=2, max_length=2)        # e.g. [28, 45]
└── rationale: str
```

**Note on list fields:** `recommended_strike_range` and `recommended_dte_range` use `list` with `Field(min_length=2, max_length=2)` rather than `tuple` to ensure JSON-serialisability across all LLM provider structured-output modes and LangGraph checkpoint serialisation. The `iv_environment` field carries a machine-readable enum value derived from `iv_rank` for deterministic test assertions.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | WheelAnalyst produces output | Schema validation runs | All fields are present and correctly typed; no extra fields pass through |
| AC2 | System | `approved=True` | Schema is serialised | `rejection_reason` is `None` |
| AC3 | System | `approved=False` | Schema is serialised | `rejection_reason` is a non-empty string |

---

#### REQ-SCREEN-03: CLI Integration for Wheel Screening Mode

| Field | Value |
|---|---|
| **ID** | REQ-SCREEN-03 |
| **Title** | CLI exposes "wheel" as a selectable analyst and shows WheelCandidateReport |
| **Priority** | P1 |
| **Phase** | 2 |
| **Source stories** | US-09 |
| **Dependencies** | REQ-SCREEN-01, REQ-SCREEN-02 |

**Description**

The CLI analyst selection prompt must include "Wheel Analyst" as an optional analyst. When selected, the Rich report panel must display the `WheelCandidateReport` as a dedicated section: approval status (coloured ✓ / ✗), IV Rank/Percentile, earnings clearance, recommended strike and DTE ranges, and rationale. This section is inserted after the four standard analyst reports.

**Test strategy:** CLI display tests use Rich's `console.export_text()` to capture terminal output and assert on the presence of key strings (e.g., `"IV Rank"`, `"WheelCandidateReport"`, `"No open wheel positions"`). Tests use a Rich `Console(file=StringIO())` injected via the CLI test harness.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | User | Wheel Analyst is selected in CLI | Analysis runs | `console.export_text()` output contains `"WheelCandidateReport"` and `"IV Rank"` |
| AC2 | User | Wheel Analyst is not selected | Analysis runs | No wheel-specific section appears; existing behaviour is unchanged |
| AC3 | User | Report shows `approved: false` | Report is displayed | `console.export_text()` output contains the rejection reason string |

---

### PHASE 3 — Trade Recommendation Engine

**Goal:** Generate specific, actionable options trade recommendations. Given an approved wheel candidate (from Phase 2) or a manually specified ticker, produce a concrete CSP or CC trade specification with strike, expiration, premium, and supporting rationale.

---

#### REQ-TRADE-01: CSP Selection Agent

| Field | Value |
|---|---|
| **ID** | REQ-TRADE-01 |
| **Title** | CspAgent producing a structured CspDecision |
| **Priority** | P0 |
| **Phase** | 3 |
| **Source stories** | US-03 |
| **Dependencies** | REQ-DATA-01, REQ-DATA-03, REQ-SCREEN-02 |

**Description**

A new agent `CspAgent` at `tradingagents/agents/options/csp_agent.py` generates a cash-secured put recommendation. It receives the analyst reports, `WheelCandidateReport` (or wheel config defaults if Phase 2 is skipped), the full options chain, and the Greeks tool. Before presenting candidates to the LLM, a deterministic filter function rejects any strike whose put delta (absolute value) is outside `[target_csp_delta_low, target_csp_delta_high]`. The agent selects:

- **Strike** — targeting a put Delta between `target_delta_low` and `target_delta_high` (default: 0.20–0.30), aligned to a technically significant support level where possible (using the Market Analyst's support/resistance commentary)
- **Expiration** — within the `recommended_dte_range` from `WheelCandidateReport`, defaulting to 30–45 DTE (calendar days)
- **Premium** — must meet `min_annualised_yield` (default: 12% p.a., configurable)
- **Earnings check** — expiration must not straddle an earnings date (using REQ-DATA-04)

Output: `CspDecision` schema (REQ-TRADE-02).

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | A valid approved candidate with chain data | CspAgent runs | Returns a CspDecision with strike, expiry, and premium ≥ min_annualised_yield |
| AC2 | Agent | No strike in the chain meets the Delta target | CspAgent runs | Returns the closest acceptable strike with a note `"No strike matches Delta target; nearest available: {delta}"` |
| AC3 | Agent | All acceptable expirations straddle an earnings date | CspAgent runs | Returns `tradeable: false` with reason `"All suitable expirations overlap earnings"` |
| AC4a | System | Target delta range is `[0.15, 0.25]` in config | Strike candidate filter function runs (unit test, mocked LLM) | Filter rejects any strike whose put delta (abs) is outside [0.15, 0.25] before presenting options to the LLM |
| AC4b | System | Target delta range is `[0.15, 0.25]` in config | CspAgent completes with live LLM (@pytest.mark.integration) | Final `CspDecision.delta` is in the range [−0.25, −0.15] |

---

#### REQ-TRADE-02: CspDecision Schema

| Field | Value |
|---|---|
| **ID** | REQ-TRADE-02 |
| **Title** | Structured CspDecision Pydantic schema |
| **Priority** | P0 |
| **Phase** | 3 |
| **Source stories** | US-03 |
| **Dependencies** | REQ-TRADE-01 |

**Description**

A Pydantic model `CspDecision` must be added to `tradingagents/agents/schemas.py`. DTE is always **calendar days**; annualisation uses **365** throughout:

```
CspDecision
├── tradeable: bool
├── rejection_reason: Optional[str]
├── ticker: str
├── option_type: Literal["put"]
├── strike: float
├── expiration_date: str                # YYYY-MM-DD
├── dte: int                            # calendar days to expiration from trade_date
├── bid: float
├── ask: float
├── mid_premium: float                  # (bid + ask) / 2
├── delta: float                        # put delta (negative value, e.g. -0.25)
├── theta: float                        # daily theta decay (≤ 0)
├── annualised_yield_pct: float         # (mid_premium / strike) × (365/dte) × 100
├── max_loss: float                     # strike * 100 - premium * 100
├── breakeven_price: float              # strike - mid_premium
├── probability_of_profit: float        # approx 1 - abs(delta)
├── earnings_clear: bool
└── rationale: str
```

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | CspAgent produces output | Schema validates | All numeric fields other than `delta` and `theta` are non-negative; `delta` is in (−1, 0); `theta` is ≤ 0 |
| AC2 | System | `tradeable=True` | Fields checked | `strike`, `expiration_date`, `mid_premium` are all non-null |
| AC3 | System | `annualised_yield_pct` is computed | Value checked | Matches formula `(mid_premium / strike) × (365/dte) × 100` within 0.01% |

---

#### REQ-TRADE-03: CC Selection Agent

| Field | Value |
|---|---|
| **ID** | REQ-TRADE-03 |
| **Title** | CcAgent producing a structured CcDecision after assignment |
| **Priority** | P0 |
| **Phase** | 3 |
| **Source stories** | US-04 |
| **Dependencies** | REQ-DATA-01, REQ-DATA-03, REQ-TRADE-02 |

**Description**

A new agent `CcAgent` at `tradingagents/agents/options/cc_agent.py` generates a covered-call recommendation for a stock position that was acquired through put assignment. It receives: the assigned stock's cost basis (put strike − premium received), current market price, the analyst reports, and the full options chain. The agent selects:

- **Strike** — must be ≥ cost basis (so called-away is profitable), targeting a call Delta between `cc_target_delta_low` and `cc_target_delta_high` (default: 0.20–0.35)
- **Expiration** — within `recommended_dte_range`, default 21–45 DTE (calendar days)
- **Premium** — must meet `min_annualised_yield` on the cost basis

Output: `CcDecision` schema (REQ-TRADE-04).

Agent unit tests must mock the LLM and assert on structured-output schema fields, not on free-text `rationale` strings.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | Cost basis is $140, current price $145 | CcAgent runs | Selected strike is ≥ $140 |
| AC2 | Agent | Current price is below cost basis | CcAgent runs | Schema field `strike_above_cost_basis` is `False`; `rejection_reason` is non-empty noting below-cost-basis risk |
| AC3 | Agent | No call strikes above cost basis meet the Delta target | CcAgent runs | Returns `tradeable: false` with `rejection_reason` non-empty |

---

#### REQ-TRADE-04: CcDecision Schema

| Field | Value |
|---|---|
| **ID** | REQ-TRADE-04 |
| **Title** | Structured CcDecision Pydantic schema |
| **Priority** | P0 |
| **Phase** | 3 |
| **Source stories** | US-04 |
| **Dependencies** | REQ-TRADE-03 |

**Description**

A Pydantic model `CcDecision` must be added to `tradingagents/agents/schemas.py`:

```
CcDecision
├── tradeable: bool
├── rejection_reason: Optional[str]
├── ticker: str
├── option_type: Literal["call"]
├── strike: float
├── expiration_date: str
├── dte: int                            # calendar days
├── bid: float
├── ask: float
├── mid_premium: float
├── delta: float                        # call delta (positive value)
├── theta: float
├── annualised_yield_on_cost_pct: float # (mid_premium / cost_basis) × (365/dte) × 100
├── assigned_at: float                  # put strike from prior CSP
├── cost_basis: float                   # assigned_at - csp_premium_received
├── strike_above_cost_basis: bool
├── upside_to_strike_pct: float         # (strike - current_price) / current_price × 100
├── earnings_clear: bool
└── rationale: str
```

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | CcAgent produces output | Schema validates | `strike_above_cost_basis` matches `strike >= cost_basis` |
| AC2 | System | `tradeable=True` | Fields checked | `assigned_at` and `cost_basis` are non-null |

---

#### REQ-TRADE-05: Risk Debate Adaptation for Options

| Field | Value |
|---|---|
| **ID** | REQ-TRADE-05 |
| **Title** | Risk debate agents receive options context and reason about options-specific risk |
| **Priority** | P1 |
| **Phase** | 3 |
| **Source stories** | US-03, US-04 |
| **Dependencies** | REQ-TRADE-01, REQ-TRADE-03 |

**Description**

The existing Aggressive, Conservative, and Neutral risk debaters must receive the `CspDecision` or `CcDecision` in their prompt context when the system is in wheel mode. Their debate should consider: max-loss scenario (assignment at strike on CSP; stock drop below cost basis on CC), probability of profit, IV contraction risk post-trade, and earnings/event risk. The Portfolio Manager produces a final `PortfolioDecision` that either confirms the trade or recommends passing.

**Test strategy:** ACs are expressed as prompt-content assertions (verifying the prompt sent to the LLM contains the required data fields). These are deterministic and do not depend on LLM free-text output.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | System is in wheel mode with a `CspDecision` | Prompt is assembled for risk debate agents | The prompt string contains the serialised `CspDecision` fields `mid_premium` and `probability_of_profit` |
| AC2 | System | `CspDecision.earnings_clear` is `False` | Prompt is assembled for the Conservative debater | The prompt string contains the `earnings_date` string from the `CspDecision` context |
| AC3 | Agent | Mode is equity (no wheel) | Risk debate runs | Agents receive no options-specific context; existing behaviour unchanged |

---

### PHASE 4 — Wheel Lifecycle Management

**Goal:** Track open wheel positions through the full CSP → Assignment → CC → Called Away cycle, provide roll/hold/close recommendations at configurable checkpoints, record cumulative premium income, and persist cycle history to the memory log.

---

#### REQ-LIFE-01: Wheel Phase State Machine

| Field | Value |
|---|---|
| **ID** | REQ-LIFE-01 |
| **Title** | WheelPhase enum and phase-aware routing in the LangGraph graph |
| **Priority** | P0 |
| **Phase** | 4 |
| **Source stories** | US-05, US-06 |
| **Dependencies** | REQ-TRADE-02, REQ-TRADE-04 |

**Description**

A `WheelPhase` enum must be defined as `class WheelPhase(str, Enum)` with **lowercase string values** (e.g., `SCREENING = "screening"`, `CSP_OPEN = "csp_open"`, `STOCK_OWNED = "stock_owned"`, `CC_OPEN = "cc_open"`, `CYCLE_COMPLETE = "cycle_complete"`). Declaring it as `str, Enum` ensures JSON-serialisability in LangGraph checkpoint infrastructure and in the `WheelPosition` JSON persistence layer. The `AgentState` TypedDict must be extended with a `wheel_phase: Optional[str]` field (stored as the string value of the enum); enum validation occurs on read.

The values and transitions:
- `"screening"` → runs analyst pipeline + WheelAnalyst → CspAgent
- `"csp_open"` → runs RollCheckAgent (REQ-LIFE-03) for the existing CSP
- `"stock_owned"` → runs analyst pipeline + CcAgent
- `"cc_open"` → runs RollCheckAgent for the existing CC
- `"cycle_complete"` → emits cycle summary and resets phase to `"screening"`

When `wheel_phase` is `None`, the graph follows the existing equity-only path unchanged.

**Architecture Note — Graph Integration:** The wheel phase routing must be implemented as a new preamble conditional edge `START → wheel_router` added to the existing `setup_graph()` function in `graph/setup.py`. A new `ConditionalLogic.route_wheel_phase()` method handles the routing logic. When `wheel_phase is None`, the router passes through to the existing first analyst node unchanged, preserving all existing equity-analysis flows. Tool nodes for options data tools must be registered alongside existing tool nodes in the graph. This is a requirements-level integration constraint ensuring the implementation stays within the existing `StateGraph` topology rather than introducing a separate sub-graph.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | `wheel_phase=None` | Graph is invoked | Existing equity pipeline runs unchanged; no options nodes are visited |
| AC2 | System | `wheel_phase="screening"` | Graph is invoked | Analyst pipeline + WheelAnalyst + CspAgent nodes are visited |
| AC3 | System | `wheel_phase="stock_owned"` | Graph is invoked | CcAgent node is visited; CspAgent is skipped |
| AC4 | System | Phase transition occurs (CSP assigned) | State is updated | `wheel_phase` changes from `"csp_open"` to `"stock_owned"` |
| AC5 | System | `wheel_phase="cc_open"` but no `WheelPosition` with `cc_strike` exists in the positions store | Graph is invoked | Graph raises `WheelStateError` exception |
| AC6 | System | `wheel_phase` is set to an unknown string value (e.g., `"invalid_phase"`) | Graph is invoked | Graph falls back to the equity-only path and logs a warning |

---

#### REQ-LIFE-02: Position Tracker

| Field | Value |
|---|---|
| **ID** | REQ-LIFE-02 |
| **Title** | WheelPosition model tracking cost basis and cumulative premium |
| **Priority** | P0 |
| **Phase** | 4 |
| **Source stories** | US-05, US-07 |
| **Dependencies** | REQ-LIFE-01 |

**Description**

A Pydantic model `WheelPosition` must be added and persisted as JSON per position. DTE is always **calendar days**; annualisation uses **365** throughout.

**cycle_annualised_return_pct formula:**
```
cycle_annualised_return_pct = (cycle_pnl / (csp_strike × shares_held)) × (365 / cycle_duration_days) × 100
```
where `cycle_duration_days` is the number of **calendar days** from the CSP open date to the CC call-away date.

```
WheelPosition
├── ticker: str
├── wheel_phase: str                     # WheelPhase string value (str, Enum)
├── cycle_number: int                    # monotonically increasing per ticker
├── csp_strike: Optional[float]
├── csp_expiration: Optional[str]
├── csp_premium_received: Optional[float]
├── assignment_date: Optional[str]       # YYYY-MM-DD, if assigned
├── shares_held: Optional[int]           # always 100 per contract
├── cost_basis_per_share: Optional[float]  # csp_strike - csp_premium_received
├── cc_strike: Optional[float]
├── cc_expiration: Optional[str]
├── cc_premium_received: Optional[float]
├── call_away_date: Optional[str]        # YYYY-MM-DD, if called away
├── cumulative_premium_received: float   # sum of all premiums in this cycle
├── cycle_pnl: Optional[float]           # realised at cycle end
├── cycle_annualised_return_pct: Optional[float]
└── notes: str
```

**Position file storage:** Each position is written to `{config["wheel"]["positions_dir"]}/{ticker}-cycle-{cycle_number}.json`. Writes must use the same atomic temp-file + rename pattern as `TradingMemoryLog` to prevent concurrent-write corruption.

The position file must be updated at every phase transition. On `CYCLE_COMPLETE`, `cycle_pnl` and `cycle_annualised_return_pct` must be computed and stored.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | CSP is opened at $140 strike, $2.50 premium | Position is written | `cost_basis_per_share = 137.50`, `cumulative_premium_received = 2.50` |
| AC2 | System | CC is opened at $145 strike, $1.80 premium | Position is updated | `cumulative_premium_received = 4.30` |
| AC3 | System | CC is called away | `CYCLE_COMPLETE` triggers | `cycle_pnl = (145 − 140 + 4.30) × 100 = 930`, `cycle_annualised_return_pct` computed |
| AC3a | System | `cycle_pnl=930`, `csp_strike=140`, `shares_held=100`, `cycle_duration_days=73` | `cycle_annualised_return_pct` is computed | Value is approximately `33.25%` (formula: `(930 / (140 × 100)) × (365 / 73) × 100`) |
| AC4 | System | Multiple concurrent wheel positions exist | Each has a distinct ticker | Each position file is written to `{positions_dir}/{ticker}-cycle-{cycle_number}.json` |

---

#### REQ-LIFE-03: Roll / Hold / Close Decision Agent

| Field | Value |
|---|---|
| **ID** | REQ-LIFE-03 |
| **Title** | RollCheckAgent producing a RollDecision at configurable checkpoints |
| **Priority** | P0 |
| **Phase** | 4 |
| **Source stories** | US-06 |
| **Dependencies** | REQ-LIFE-01, REQ-LIFE-02, REQ-DATA-01, REQ-DATA-03 |

**Description**

A new agent `RollCheckAgent` at `tradingagents/agents/options/roll_agent.py` evaluates an open position and recommends one of three actions: `HOLD` (do nothing), `ROLL` (close current contract and open a new one), or `CLOSE` (take profit or cut loss). Evaluation is triggered when `wheel_phase` is `"csp_open"` or `"cc_open"`. The agent checks:

1. **Profit capture rule:** If current contract value has declined to ≤ `take_profit_pct` (default: 50%) of premium received, recommend `ROLL` or `HOLD`.
2. **DTE rule:** If DTE ≤ `dte_to_roll` (default: 21), recommend `ROLL` to the next standard expiration.
3. **Breach rule:** For CSPs — if stock price has dropped ≥ 15% below the strike: if `current_value_pct_of_premium >= 50` (position retains value), return `ROLL` with `trigger_reason="breach_rule_roll"`; if `current_value_pct_of_premium < 50` (deep loss), return `CLOSE` with `trigger_reason="breach_rule_close"`.
4. **Earnings rule:** If an earnings date falls within the remaining DTE, recommend `CLOSE` unless the position is deep OTM.
5. **Analyst update:** If the analyst pipeline's new run has changed from bullish to bearish, recommend `CLOSE`.

Tests assert on `trigger_reason` (enum field in REQ-LIFE-04), not on free-text `rationale`.

Output: `RollDecision` schema (REQ-LIFE-04).

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Agent | Premium at 50% of received value, DTE = 30 | RollCheckAgent runs | Returns `action="HOLD"` with `trigger_reason="profit_capture"` |
| AC2 | Agent | DTE = 18 | RollCheckAgent runs | Returns `action="ROLL"` with `trigger_reason="dte_rule"` and a specific target expiration |
| AC3a | Agent | Stock dropped ≥ 15% below CSP strike AND `current_value_pct_of_premium >= 50` | RollCheckAgent runs | Returns `action="ROLL"` with `trigger_reason="breach_rule_roll"` |
| AC3b | Agent | Stock dropped ≥ 15% below CSP strike AND `current_value_pct_of_premium < 50` | RollCheckAgent runs | Returns `action="CLOSE"` with `trigger_reason="breach_rule_close"` |
| AC4 | Agent | Analyst consensus changed from bullish to bearish | RollCheckAgent runs | Returns `action="CLOSE"` with `trigger_reason="analyst_update"` |

---

#### REQ-LIFE-04: RollDecision Schema

| Field | Value |
|---|---|
| **ID** | REQ-LIFE-04 |
| **Title** | Structured RollDecision Pydantic schema |
| **Priority** | P0 |
| **Phase** | 4 |
| **Source stories** | US-06 |
| **Dependencies** | REQ-LIFE-03 |

**Description**

```
RollDecision
├── action: Literal["HOLD", "ROLL", "CLOSE"]
├── ticker: str
├── current_strike: float
├── current_expiration: str
├── current_dte: int
├── current_value_pct_of_premium: float   # how much value remains (0–100)
├── trigger_reason: Literal["profit_capture", "dte_rule", "breach_rule_roll", "breach_rule_close", "earnings_rule", "analyst_update"]
├── new_strike: Optional[float]           # populated for ROLL
├── new_expiration: Optional[str]         # populated for ROLL
├── new_dte: Optional[int]
├── estimated_debit_or_credit: Optional[float]  # net premium for roll
└── rationale: str
```

The `trigger_reason` field is a `Literal` enum drawn from the six values above, enabling deterministic test assertions on which rule fired. Tests assert on `trigger_reason`, not on the free-text `rationale` field.

---

#### REQ-LIFE-05: Memory Log Integration for Wheel Cycles

| Field | Value |
|---|---|
| **ID** | REQ-LIFE-05 |
| **Title** | Wheel cycle outcomes stored in TradingMemoryLog with LLM reflection |
| **Priority** | P1 |
| **Phase** | 4 |
| **Source stories** | US-07 |
| **Dependencies** | REQ-LIFE-02 |

**Description**

When a wheel cycle reaches `CYCLE_COMPLETE`, the system must append a summary entry to `TradingMemoryLog` containing: ticker, cycle number, duration (days), premiums collected, cycle P&L, annualised return, and a brief LLM-generated reflection on what worked and what didn't (using the existing `reflect_on_entry()` pattern). On subsequent runs for the same ticker, this context is injected into the WheelAnalyst and CspAgent prompts as `past_context`. The `past_context` string must contain: ticker, `cycle_pnl` formatted to 2 decimal places, and `cycle_annualised_return_pct`.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | System | Cycle completes with positive P&L | Memory log is written | Entry contains ticker, premiums, P&L, and annualised return |
| AC2 | System | Cycle completes with `cycle_pnl < 0` | Memory log is written | The memory log entry's `notes` field is non-empty |
| AC3 | Agent | A second wheel cycle starts on same ticker | Prompts are assembled | `past_context` string contains: ticker, `cycle_pnl` formatted to 2 decimal places, and `cycle_annualised_return_pct` |
| AC4 | System | A cycle completes (any outcome) | Memory log entry is written | Entry contains all required `WheelPosition` fields with `cycle_pnl` and `cycle_annualised_return_pct` non-null |

---

#### REQ-LIFE-06: Wheel Portfolio Summary CLI View

| Field | Value |
|---|---|
| **ID** | REQ-LIFE-06 |
| **Title** | CLI command to display all open wheel positions and cycle history |
| **Priority** | P1 |
| **Phase** | 4 |
| **Source stories** | US-07, US-09 |
| **Dependencies** | REQ-LIFE-02 |

**Description**

A new CLI sub-command `tradingagents wheel-status` must display a Rich table of all open wheel positions: ticker, current phase, strike(s), expiration(s), DTE, cost basis, cumulative premium received, current P&L (using live yfinance price). A second table shows completed cycles and their annualised returns.

**Test strategy:** CLI display tests use Rich's `console.export_text()` to capture terminal output and assert on the presence of key strings (e.g., `"IV Rank"`, `"WheelCandidateReport"`, `"No open wheel positions"`). Tests use a Rich `Console(file=StringIO())` injected via the CLI test harness.

**Acceptance Criteria**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | User | Two open positions exist | `tradingagents wheel-status` is run | `console.export_text()` output contains both tickers with current DTE and P&L |
| AC2 | User | No positions exist | Command is run | `console.export_text()` output contains `"No open wheel positions"` |
| AC3 | User | A cycle is complete | Completed cycles table is shown | `console.export_text()` output contains the annualised return for each completed cycle |

---

## 6. Non-Functional Requirements

| ID | Category | Requirement | Phase |
|---|---|---|---|
| REQ-NFR-01 | Backwards compatibility | All Phase 1–4 additions must leave the existing equity analysis pipeline fully functional when `wheel_phase` is `None` or wheel analysts are not selected | All |
| REQ-NFR-02 | Performance | The `get_options_chain()` function, measured from call entry to return, must complete within 10 seconds at p95 on a live yfinance network call (pytest `integration` mark, not mocked). In unit tests with a mocked network, no timing constraint applies. | 1 |
| REQ-NFR-03 | Configurability | All thresholds (IV rank, delta targets, DTE ranges, yield targets, earnings buffer) must be exposed in `default_config.py` under a `wheel` key and overridable via `TRADINGAGENTS_WHEEL_*` env vars (naming convention: `TRADINGAGENTS_WHEEL_{UPPER_SNAKE_CASE_KEY}`) | 1–4 |
| REQ-NFR-04 | Structured output | All new decision schemas must use the existing `structured.py` wrapper so they work across all supported LLM providers | 3–4 |
| REQ-NFR-05 | Testability | Every new agent must have at least one unit test with a mocked data layer; every schema must have a validation test. Agent unit tests must mock the LLM and assert on structured-output schema fields (e.g., `approved: bool`, `action: str`), not on free-text `rationale` strings. Prompt-content assertions (verifying the prompt sent to the LLM contains required data fields) are the approved integration test pattern. A canonical pytest fixture `option_chain_fixture(ticker, expiry)` returning a `pd.DataFrame` with columns `[strike, bid, ask, lastPrice, volume, openInterest, impliedVolatility]` must be provided in `tests/fixtures/options_fixtures.py`. All unit tests for options data tools must use this fixture. `get_iv_metrics` must accept an injectable `iv_series: Optional[list[float]]` parameter for testing; when provided, it bypasses the yfinance historical fetch. | All |
| REQ-NFR-06 | Error handling | Data fetch failures (yfinance rate limits, missing options data) must return a graceful error string to the agent, not raise exceptions that crash the graph | 1 |
| REQ-NFR-07 | Documentation | `default_config.py` must contain inline comments for every new `wheel` config key | All |

---

## 7. Configuration Keys (new)

All under `config["wheel"]` in `default_config.py`. Env var override naming convention: `TRADINGAGENTS_WHEEL_{UPPER_SNAKE_CASE_KEY}` (e.g., `TRADINGAGENTS_WHEEL_MIN_IV_RANK` for `min_iv_rank`). Each key must have an explicit entry in `_ENV_OVERRIDES` in `default_config.py`.

| Key | Default | Env Var | Type | Description |
|---|---|---|---|---|
| `min_iv_rank` | `25` | `TRADINGAGENTS_WHEEL_MIN_IV_RANK` | int | Minimum IV Rank to approve a wheel candidate |
| `earnings_buffer_days` | `14` | `TRADINGAGENTS_WHEEL_EARNINGS_BUFFER_DAYS` | int | Minimum days between target expiration and next earnings |
| `max_wheel_stock_price` | `500` | `TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE` | float | Maximum stock price (cash management) |
| `target_csp_delta_low` | `0.20` | `TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_LOW` | float | Lower bound of target put delta for CSP |
| `target_csp_delta_high` | `0.30` | `TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_HIGH` | float | Upper bound of target put delta for CSP |
| `target_cc_delta_low` | `0.20` | `TRADINGAGENTS_WHEEL_TARGET_CC_DELTA_LOW` | float | Lower bound of target call delta for CC |
| `target_cc_delta_high` | `0.35` | `TRADINGAGENTS_WHEEL_TARGET_CC_DELTA_HIGH` | float | Upper bound of target call delta for CC |
| `min_annualised_yield_pct` | `12.0` | `TRADINGAGENTS_WHEEL_MIN_ANNUALISED_YIELD_PCT` | float | Minimum annualised premium yield to accept a trade |
| `recommended_dte_low` | `28` | `TRADINGAGENTS_WHEEL_RECOMMENDED_DTE_LOW` | int | Minimum DTE (calendar days) for new positions |
| `recommended_dte_high` | `45` | `TRADINGAGENTS_WHEEL_RECOMMENDED_DTE_HIGH` | int | Maximum DTE (calendar days) for new positions |
| `take_profit_pct` | `50` | `TRADINGAGENTS_WHEEL_TAKE_PROFIT_PCT` | float | Close/roll when contract value reaches this % of premium received |
| `dte_to_roll` | `21` | `TRADINGAGENTS_WHEEL_DTE_TO_ROLL` | int | Roll when DTE falls to or below this value (calendar days) |
| `iv_rank_lookback_days` | `252` | `TRADINGAGENTS_WHEEL_IV_RANK_LOOKBACK_DAYS` | int | Trading days for IV Rank/Percentile (realised vol) computation |
| `min_chain_oi` | `100` | `TRADINGAGENTS_WHEEL_MIN_CHAIN_OI` | int | Minimum open interest for a strike to be considered liquid |
| `max_chain_spread_pct` | `10.0` | `TRADINGAGENTS_WHEEL_MAX_CHAIN_SPREAD_PCT` | float | Maximum bid/ask spread as % of mid for liquidity filter |
| `risk_free_rate_source` | `"yfinance_irx"` | `TRADINGAGENTS_WHEEL_RISK_FREE_RATE_SOURCE` | str | Source for BSM risk-free rate: `"yfinance_irx"` or `"static"` |
| `risk_free_rate_static` | `0.0525` | `TRADINGAGENTS_WHEEL_RISK_FREE_RATE_STATIC` | float | Static risk-free rate (decimal, not percent) used when `risk_free_rate_source="static"` or `^IRX` is unavailable |
| `positions_dir` | `"memory/wheel_positions"` | `TRADINGAGENTS_WHEEL_POSITIONS_DIR` | str | Directory for per-position JSON files (`{ticker}-cycle-{N}.json`) |
