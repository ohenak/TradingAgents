# TSPEC — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | SE-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-25 |
| **Upstream** | REQ-wheel-options-trading.md v0.2.0 → FSPEC-wheel-options-trading.md v0.3.0 → **TSPEC** |
| **Downstream** | PLAN, PROPERTIES |
| **Cross-Reviews** | _(none yet)_ |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2026-05-25 | Initial draft |

---

## 1. Architecture Overview

### 1.1 Module Map

**New files created:**

| File | Purpose |
|---|---|
| `tradingagents/dataflows/y_finance_options.py` | Four yfinance options data functions: `get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date` |
| `tradingagents/agents/utils/options_data_tools.py` | `@tool`-decorated LangChain wrappers for the four options data functions; all calls route through `interface.py` |
| `tradingagents/agents/analysts/wheel_analyst.py` | `WheelAnalyst` agent — five-criterion suitability screening, produces `WheelCandidateReport` |
| `tradingagents/agents/options/__init__.py` | Package init for options agents |
| `tradingagents/agents/options/csp_agent.py` | `CspAgent` — deterministic pre-filter + LLM strike selection, produces `CspDecision` |
| `tradingagents/agents/options/cc_agent.py` | `CcAgent` — cost-basis-anchored CC selection, produces `CcDecision` |
| `tradingagents/agents/options/roll_agent.py` | `RollCheckAgent` — five-rule roll/hold/close evaluation, produces `RollDecision` |
| `tradingagents/graph/wheel_nodes.py` | `wheel_cycle_summary` node function and `WheelStateError` exception class |
| `tradingagents/models/wheel_position.py` | `WheelPosition` Pydantic model and atomic JSON persistence helpers |
| `tests/fixtures/options_fixtures.py` | `option_chain_fixture(ticker, expiry)` canonical pytest fixture |

**Existing files modified:**

| File | Modification |
|---|---|
| `tradingagents/dataflows/interface.py` | Add `"options_data"` to `TOOLS_CATEGORIES`; add four methods to `VENDOR_METHODS` |
| `tradingagents/agents/schemas.py` | Add `WheelPhase`, `TriggerReason`, `WheelCandidateReport`, `CspDecision`, `CcDecision`, `RollDecision` schemas plus render helpers |
| `tradingagents/agents/utils/agent_states.py` | Add five new `Optional[str]` fields to `AgentState` TypedDict |
| `tradingagents/graph/setup.py` | Add wheel agent factories, register new nodes, add `START → wheel_router` conditional edge, register options tool node |
| `tradingagents/graph/conditional_logic.py` | Add `route_wheel_phase()` method; update constructor to accept `first_analyst_node` and position store reference |
| `tradingagents/default_config.py` | Add `config["wheel"]` sub-dict with 18 keys; add `_ENV_OVERRIDES` entries; add `_apply_nested_env_overrides` helper |
| `tradingagents/agents/__init__.py` | Export new agent factory functions |

### 1.2 Dependency Diagram

```
                        ┌─────────────────────────────┐
                        │        default_config.py     │
                        │   config["wheel"] (18 keys)  │
                        └──────────────┬──────────────┘
                                       │ config
        ┌──────────────────────────────┼─────────────────────────────┐
        │                              │                             │
        ▼                              ▼                             ▼
┌───────────────┐          ┌───────────────────────┐    ┌──────────────────────┐
│  y_finance_   │          │  options_data_tools.py │    │  wheel_position.py   │
│  options.py   │◄─────────│  (@tool wrappers)      │    │  (WheelPosition +    │
│  (raw data    │ calls via │  route_to_vendor()     │    │   atomic JSON I/O)   │
│  functions)   │ interface │                        │    └──────────┬───────────┘
└───────────────┘          └──────────┬────────────┘               │ read/write
        ▲                             │ tools bound to              │
        │ registered in               ▼                             │
        │              ┌──────────────────────────────┐            │
        └──────────────│       interface.py            │            │
                       │  TOOLS_CATEGORIES["options_  │            │
                       │  data"], VENDOR_METHODS       │            │
                       └──────────────────────────────┘            │
                                                                    │
        ┌───────────────────────────────────────────────────────────┘
        │                                                           
        ▼                                                           
┌────────────────────────────────────────────────────────────────────┐
│                        Agent Layer                                  │
│                                                                    │
│  wheel_analyst.py    csp_agent.py    cc_agent.py    roll_agent.py  │
│  (WheelAnalyst)      (CspAgent)      (CcAgent)      (RollCheck     │
│        │                  │               │           Agent)       │
│        ▼                  ▼               ▼               │        │
│  WheelCandidateReport  CspDecision  CcDecision      RollDecision   │
│        │                  │               │               │        │
│        └─────────┬────────┴───────────────┴───────────────┘        │
│                  │ writes Optional[str] JSON to AgentState          │
└──────────────────┼─────────────────────────────────────────────────┘
                   │
        ┌──────────▼────────────────────────────────────────────────┐
        │                      Graph Layer                           │
        │                                                           │
        │  agent_states.py (AgentState TypedDict + 5 new fields)    │
        │  setup.py (GraphSetup.setup_graph — START→wheel_router)   │
        │  conditional_logic.py (route_wheel_phase)                 │
        │  wheel_nodes.py (wheel_cycle_summary, WheelStateError)    │
        └───────────────────────────────────────────────────────────┘
```

### 1.3 Integration Points

- **Dataflow layer:** Options data functions registered in `TOOLS_CATEGORIES["options_data"]` and `VENDOR_METHODS`. Vendor routing key: `config["data_vendors"]["options_data"]` (default `"yfinance"`).
- **Graph layer:** `setup_graph()` gains a `START → wheel_router` conditional edge before the first analyst node. Existing `START → plan.specs[0].agent_node` direct edge is removed and replaced by `add_conditional_edges(START, conditional_logic.route_wheel_phase, mapping)`.
- **State layer:** Five `Optional[str]` fields added to `AgentState`; all wheel schemas serialise to JSON strings for LangGraph checkpoint compatibility.
- **CLI layer:** `MessageBuffer` gains a `"wheel_candidate"` section key; Rich panel `"Wheel Suitability"` displayed after analyst panels when `"wheel"` is in `selected_analysts`. New sub-command `tradingagents wheel-status` reads position JSON files.
- **Memory layer:** `wheel_cycle_summary` node calls `TradingMemoryLog.store_decision()` with wheel-specific tag format at cycle completion.
- **Config layer:** All 18 new `config["wheel"]` keys added to `default_config.py`; env overrides applied via new `_apply_nested_env_overrides` helper.

---

## 2. Data Layer (Phase 1)

### 2.1 File: `tradingagents/dataflows/y_finance_options.py`

All four functions follow the existing `y_finance.py` pattern: return formatted strings, catch network exceptions internally, never raise to the caller.

---

#### 2.1.1 `get_options_chain`

```python
def get_options_chain(
    ticker: str,
    target_date: str,
    expiry_date: Optional[str] = None,
    config: Optional[dict] = None,
) -> str:
```

**Implementation notes:**
- Parse `target_date` as `datetime.strptime(target_date, "%Y-%m-%d")`.
- Call `yf.Ticker(ticker.upper()).options` to obtain the list of available expiration date strings.
- Compute look-ahead boundary: `cutoff = target_dt + timedelta(days=options_lookforward_days)` where `options_lookforward_days = (config or {}).get("wheel", {}).get("options_lookforward_days", 90)`.
- Filter expiration dates: retain those where `target_dt <= expiry_dt <= cutoff` (inclusive on both ends).
- If `expiry_date` is provided: filter to only that expiration date string. If it falls outside the look-ahead window, still return it (the caller requested a specific date).
- For each retained expiration, call `yf.Ticker(ticker.upper()).option_chain(expiry_str)` to obtain `calls` and `puts` DataFrames with columns: `strike`, `bid`, `ask`, `lastPrice`, `volume`, `openInterest`, `impliedVolatility`.
- If both DataFrames are empty for all expirations, return `f"No options chain available for {ticker}"`.
- Format output as a multi-section string: one section per expiration with a header line `f"=== Expiration: {expiry_str} ==="`, followed by a puts table and a calls table.
- Return the formatted string.

**Error handling:**
- Catch `requests.exceptions.HTTPError`, `requests.exceptions.ConnectionError`, and `Exception` (broad catch): return `f"Error fetching options chain for {ticker}: {type(e).__name__}"`.
- Empty DataFrame (valid ticker, no listed options): return `f"No options chain available for {ticker}"` — this path is distinct from a network error in the output string.

**Registration in `interface.py`:**

```python
# In TOOLS_CATEGORIES:
"options_data": {
    "description": "Options chain, IV metrics, Greeks, and earnings dates",
    "tools": [
        "get_options_chain",
        "get_iv_metrics",
        "get_options_greeks",
        "get_next_earnings_date",
    ]
}

# In VENDOR_METHODS:
"get_options_chain": {
    "yfinance": get_yfinance_options_chain,   # imported from y_finance_options.py
    "alpha_vantage": _stub_not_implemented,   # returns "not implemented"
},
```

`_stub_not_implemented` is a module-level function in `interface.py` that accepts `*args, **kwargs` and returns `"not implemented"`.

**LangChain `@tool` wrapper in `options_data_tools.py`:**

```python
@tool
def get_options_chain(
    ticker: str,
    target_date: str,
    expiry_date: Optional[str] = None,
) -> str:
    """Retrieve options chain for a ticker. Returns puts and calls with
    strike, bid, ask, volume, open interest, and implied volatility."""
    try:
        return route_to_vendor("get_options_chain", ticker, target_date, expiry_date)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"
```

---

#### 2.1.2 `get_iv_metrics`

```python
def get_iv_metrics(
    ticker: str,
    curr_date: str,
    lookback_days: int = 252,
    iv_series: Optional[list[float]] = None,
) -> str:
```

**Full realised-volatility algorithm (production path, `iv_series is None`):**

1. Call `yf.Ticker(ticker.upper()).history(period="max")` to fetch full OHLCV history.
2. Filter to rows with date index `<= curr_date`. Sort ascending.
3. Take the last `lookback_days` rows. If fewer are available, use all available; note actual count `n_available`.
4. If `n_available == 0`: return `f"Insufficient OHLCV data for {ticker}"`.
5. Extract the `Close` column as a Series.
6. Compute log returns: `log_returns = np.log(close / close.shift(1)).dropna()`.
7. Compute 30-day rolling realised vol: `rolling_vol = log_returns.rolling(window=30).std() * np.sqrt(252)`. Drop NaN values (first 29 rows of the window). The resulting Series has `(n_available - 30)` values after dropping NaN.
8. If the rolling vol series is empty (fewer than 31 close prices): return `f"Insufficient data to compute rolling vol for {ticker} (need >= 31 close prices)"`.
9. Extract scalars: `current_vol = float(rolling_vol.iloc[-1])`, `max_vol_lookback = float(rolling_vol.max())`, `min_vol_lookback = float(rolling_vol.min())`.
10. Guard NaN: if any of these three values is `math.isnan(...)`, return `f"IV computation returned NaN for {ticker} — check data quality"`.
11. Zero-variance guard: if `max_vol_lookback == min_vol_lookback`: `iv_rank = 50.0`, `iv_percentile = 50.0`; set `flat_note = "IV range is flat — rank set to neutral 50"`.
12. Otherwise: `iv_rank = (current_vol - min_vol_lookback) / (max_vol_lookback - min_vol_lookback) * 100`; `iv_percentile = (rolling_vol < current_vol).sum() / len(rolling_vol) * 100` (strict less-than). Clamp both to `[0.0, 100.0]`.
13. Derive `iv_environment`: `"elevated"` if `iv_rank >= 50`; `"normal"` if `25 <= iv_rank < 50`; `"compressed"` if `iv_rank < 25`.
14. Assemble output dict and format report string. Include `flat_note` when the zero-variance guard fired. Include `"Lookback shortened to {n_available} trading days (fewer than {lookback_days} available)"` when `n_available < lookback_days`.
15. Return the formatted string representation of the dict (use `json.dumps` for the dict then attach the report string).

**Test seam (when `iv_series is not None`):**
- If `len(iv_series) == 0`: return `"Provided iv_series is empty"`.
- Skip steps 1–8. Use `iv_series` directly as the rolling vol series. `current_vol = iv_series[-1]`, `max_vol_lookback = max(iv_series)`, `min_vol_lookback = min(iv_series)`. Proceed from step 9 (the NaN guard uses `math.isnan` on these Python floats).
- Do NOT call `yf.Ticker` when `iv_series is not None`.

**Error handling:** Catch `Exception` broadly around the yfinance fetch; return graceful error string.

**Registration in `interface.py`:** `"get_iv_metrics": {"yfinance": get_yfinance_iv_metrics, "alpha_vantage": _stub_not_implemented}`

---

#### 2.1.3 `get_options_greeks`

```python
def get_options_greeks(
    ticker: str,
    curr_date: str,
    expiry_date: str,
    strike: float,
    option_type: str,
    config: Optional[dict] = None,
) -> str:
```

**Implementation notes:**
- Validate `option_type in ("put", "call")`. If not: return `f"Invalid option_type '{option_type}': must be 'put' or 'call'"`.
- Parse `curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")` and `expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")`.
- Compute `dte = (expiry_dt - curr_dt).days` (calendar days).
- If `dte < 0`: return `"Cannot compute Greeks: option has already expired"`.
- If `dte == 0`: return `"Cannot compute Greeks for expired option"`.
- Compute `T = dte / 365.0` (always 365, not 252).
- Fetch `S` (underlying price): `yf.Ticker(ticker.upper()).history(period="1d")["Close"].iloc[-1]`.
- Fetch `r` (risk-free rate):
  - If `config` is provided and `config.get("wheel", {}).get("risk_free_rate_source") == "static"`: use `r = float(config["wheel"]["risk_free_rate_static"])` directly; set `rate_note = "using static risk-free rate"`.
  - Otherwise: try `irx = yf.Ticker("^IRX").history(period="1d")["Close"].iloc[-1] / 100.0`. On any exception: fall back to `config.get("wheel", {}).get("risk_free_rate_static", 0.0525)`; set `rate_note = "using static risk-free rate"`. If successful: `r = float(irx)`, `rate_note = ""`.
- Fetch IV for the specific strike from the options chain: call `yf.Ticker(ticker.upper()).option_chain(expiry_date)`, read `puts` or `calls` DataFrame, find the row where `strike` matches (nearest match within $0.01). Extract `impliedVolatility`.
- If IV is 0 or NaN: return `f"Cannot compute Greeks: implied volatility is zero for strike {strike}"`.
- Compute `sigma = float(iv_value)`.

**BSM formulae** (call flag `flag = 1` for call, `flag = -1` for put):
```
d1 = (ln(S / K) + (r + 0.5 * sigma^2) * T) / (sigma * sqrt(T))
d2 = d1 - sigma * sqrt(T)
N(x) = scipy.stats.norm.cdf(x)
n(x) = scipy.stats.norm.pdf(x)

Delta = flag * N(flag * d1)
Gamma = n(d1) / (S * sigma * sqrt(T))
Theta_annual = (-S * n(d1) * sigma / (2 * sqrt(T)) - flag * r * K * exp(-r * T) * N(flag * d2))
Theta = Theta_annual / 365   # daily theta
Vega = S * n(d1) * sqrt(T) / 100  # per 1% change in vol
```

Where `K = strike`.

- Assemble output string with Greek values and plain-English interpretations (e.g., `"Delta {delta:.4f} — this strike is approximately {abs(delta)*100:.0f}% likely to be in-the-money at expiration"`).
- Include `rate_note` in output when non-empty.

**Error handling:**
- Catch `requests.exceptions.HTTPError`, `requests.exceptions.ConnectionError`, `Exception`: return `f"Error computing Greeks for {ticker} {option_type} strike {strike}: {type(e).__name__}"`.

**Registration:** `"get_options_greeks": {"yfinance": get_yfinance_options_greeks, "alpha_vantage": _stub_not_implemented}`

---

#### 2.1.4 `get_next_earnings_date`

```python
def get_next_earnings_date(
    ticker: str,
    curr_date: str,
) -> str:
```

**Implementation notes:**
- Parse `curr_dt = datetime.strptime(curr_date, "%Y-%m-%d").date()`.
- Call `yf.Ticker(ticker.upper()).calendar`. This returns a DataFrame or dict; extract the `"Earnings Date"` field. yfinance typically returns a list of upcoming dates; take the first date strictly after `curr_dt`.
- If no upcoming earnings date: return `f"No upcoming earnings date available for {ticker}"`.
- Compute `days_until = (earnings_date - curr_dt).days`.
- `within_options_cycle` is not computed here (it depends on the caller's target expiration); this field is set by the calling agent, not by this function. The function returns `earnings_date_str`, `days_until`, and notes that the caller must compute `within_options_cycle` from `earnings_date <= expiration_date`.

**Output string format:**
```
Next earnings date for {ticker}: {earnings_date_str}
Days until earnings: {days_until}
```

**Error handling:**
- Catch `Exception`: return `f"No upcoming earnings date available for {ticker}"` (treating fetch errors equivalently to no-data, matching REQ-DATA-04 AC3).

**Registration:** `"get_next_earnings_date": {"yfinance": get_yfinance_next_earnings_date, "alpha_vantage": _stub_not_implemented}`

---

### 2.2 `options_data_tools.py` — Full tool wrapper pattern

File path: `tradingagents/agents/utils/options_data_tools.py`

```python
from langchain_core.tools import tool
from typing import Optional
from tradingagents.dataflows.interface import route_to_vendor

@tool
def get_options_chain(ticker: str, target_date: str, expiry_date: Optional[str] = None) -> str:
    """..."""
    try:
        return route_to_vendor("get_options_chain", ticker, target_date, expiry_date)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"

@tool
def get_iv_metrics(ticker: str, curr_date: str, lookback_days: int = 252) -> str:
    """..."""
    try:
        return route_to_vendor("get_iv_metrics", ticker, curr_date, lookback_days)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"

@tool
def get_options_greeks(
    ticker: str, curr_date: str, expiry_date: str, strike: float, option_type: str
) -> str:
    """..."""
    try:
        return route_to_vendor("get_options_greeks", ticker, curr_date, expiry_date, strike, option_type)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"

@tool
def get_next_earnings_date(ticker: str, curr_date: str) -> str:
    """..."""
    try:
        return route_to_vendor("get_next_earnings_date", ticker, curr_date)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"
```

Note: The `@tool` wrappers do NOT pass `iv_series` through (that is a test-seam parameter on the raw function, not a tool parameter). The `config` parameter is also not passed through the tool layer; it is injected at function-call time in the raw function via `get_config()` from `tradingagents/dataflows/config.py`.

Note: `ValueError` and `RuntimeError` from `route_to_vendor()` are caught by the tool wrapper and converted to graceful error strings (FSPEC-WHEEL-01 rule). Network errors (`HTTPError`, `ConnectionError`) are caught inside the data functions and returned as error strings — they do not propagate to the wrapper.

---

## 3. Schema Layer (Phases 1–4)

File: `tradingagents/agents/schemas.py` (additions)

### 3.1 `WheelPhase` Enum

```python
class WheelPhase(str, Enum):
    """Wheel strategy lifecycle phases. str, Enum ensures JSON-serialisability."""
    SCREENING      = "screening"
    CSP_OPEN       = "csp_open"
    STOCK_OWNED    = "stock_owned"
    CC_OPEN        = "cc_open"
    CYCLE_COMPLETE = "cycle_complete"
```

### 3.2 `TriggerReason` Type

```python
from typing import Literal

TriggerReason = Literal[
    "profit_capture",
    "dte_rule",
    "breach_rule_roll",
    "breach_rule_close",
    "earnings_rule",
    "analyst_update",
]
```

### 3.3 `WheelCandidateReport`

```python
class WheelCandidateReport(BaseModel):
    """Wheel suitability screening report produced by WheelAnalyst."""

    approved: bool = Field(
        description="True if all five criteria passed and the stock is suitable for the wheel."
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Semicolon-delimited failure reasons when approved=False. Null when approved=True.",
    )
    iv_rank: float = Field(
        description="Realised-vol-based IV Rank in [0, 100]."
    )
    iv_percentile: float = Field(
        description="Fraction of lookback days with lower vol than today, expressed as [0, 100]."
    )
    iv_environment: Literal["elevated", "normal", "compressed"] = Field(
        description="Derived from iv_rank: elevated>=50, normal 25-50, compressed<25."
    )
    iv_assessment: str = Field(
        description="Plain-English summary of the current IV environment."
    )
    next_earnings_date: Optional[str] = Field(
        default=None,
        description="Next earnings date in YYYY-MM-DD format, or None if unavailable.",
    )
    earnings_clearance_ok: bool = Field(
        description="True if next earnings is sufficiently beyond the target expiration."
    )
    liquidity_ok: bool = Field(
        description="True if at least one near-the-money strike meets OI and spread criteria."
    )
    analyst_bias: Literal["bullish", "neutral", "bearish"] = Field(
        description="Derived from the existing investment_plan recommendation field."
    )
    recommended_strike_range: list[float] = Field(
        min_length=2,
        max_length=2,
        description="[low_strike, high_strike] anchored to target Delta bounds. Sentinel [0.0, 0.0] when approved=False.",
    )
    recommended_dte_range: list[int] = Field(
        min_length=2,
        max_length=2,
        description="[dte_low, dte_high] in calendar days from config.",
    )
    rationale: str = Field(
        description="Always-populated rationale string; non-empty even when approved=False."
    )
```

### 3.4 `CspDecision`

```python
class CspDecision(BaseModel):
    """Cash-secured put trade recommendation produced by CspAgent."""

    tradeable: bool = Field(description="True if a viable CSP trade was found.")
    rejection_reason: Optional[str] = Field(default=None)
    ticker: str = Field(description="Equity ticker.")
    option_type: Literal["put"] = Field(default="put")
    strike: float = Field(description="Selected put strike price.")
    expiration_date: str = Field(description="Expiration date in YYYY-MM-DD.")
    dte: int = Field(description="Calendar days to expiration from trade_date.")
    bid: float = Field(description="Put bid price.")
    ask: float = Field(description="Put ask price.")
    mid_premium: float = Field(description="(bid + ask) / 2.")
    delta: float = Field(description="Put delta as a negative value, e.g. -0.25.")
    theta: float = Field(description="Daily theta decay (<=0).")
    annualised_yield_pct: float = Field(
        description="(mid_premium / strike) * (365 / dte) * 100."
    )
    max_loss: float = Field(description="(strike * 100) - (mid_premium * 100) per contract.")
    breakeven_price: float = Field(description="strike - mid_premium.")
    probability_of_profit: float = Field(description="1 - abs(delta).")
    earnings_clear: bool = Field(
        description="True if selected expiration does not straddle an earnings date."
    )
    rationale: str = Field(description="Always-populated rationale string.")
```

### 3.5 `CcDecision`

```python
class CcDecision(BaseModel):
    """Covered call trade recommendation produced by CcAgent."""

    tradeable: bool = Field(description="True if a viable CC trade was found.")
    rejection_reason: Optional[str] = Field(default=None)
    ticker: str = Field(description="Equity ticker.")
    option_type: Literal["call"] = Field(default="call")
    strike: float = Field(description="Selected call strike price.")
    expiration_date: str = Field(description="Expiration date in YYYY-MM-DD.")
    dte: int = Field(description="Calendar days to expiration from trade_date.")
    bid: float
    ask: float
    mid_premium: float = Field(description="(bid + ask) / 2.")
    delta: float = Field(description="Call delta as a positive value, e.g. 0.25.")
    theta: float = Field(description="Daily theta (<=0).")
    annualised_yield_on_cost_pct: float = Field(
        description="(mid_premium / cost_basis) * (365 / dte) * 100."
    )
    assigned_at: float = Field(description="The CSP strike from the prior WheelPosition.")
    cost_basis: float = Field(description="assigned_at - csp_premium_received.")
    strike_above_cost_basis: bool = Field(description="Computed: strike >= cost_basis.")
    upside_to_strike_pct: float = Field(
        description="(strike - current_price) / current_price * 100."
    )
    earnings_clear: bool
    rationale: str = Field(description="Always-populated rationale string.")
```

### 3.6 `RollDecision`

```python
class RollDecision(BaseModel):
    """Roll/hold/close recommendation produced by RollCheckAgent."""

    action: Literal["HOLD", "ROLL", "CLOSE"] = Field(
        description="Recommended action for the open position."
    )
    ticker: str
    current_strike: float
    current_expiration: str = Field(description="YYYY-MM-DD.")
    current_dte: int = Field(description="Calendar days remaining.")
    current_value_pct_of_premium: float = Field(
        description="(current_contract_value / original_premium_received) * 100, in [0, 100]."
    )
    trigger_reason: TriggerReason = Field(
        description="Which rule fired. One of six Literal values."
    )
    new_strike: Optional[float] = Field(default=None, description="Populated for ROLL action.")
    new_expiration: Optional[str] = Field(default=None, description="YYYY-MM-DD. Populated for ROLL.")
    new_dte: Optional[int] = Field(default=None)
    estimated_debit_or_credit: Optional[float] = Field(
        default=None,
        description="new_mid_premium - current_contract_value. Positive=credit. Populated for ROLL.",
    )
    rationale: str = Field(description="Always-populated rationale string.")
```

### 3.7 Render Helpers

Each schema has a corresponding render function that converts the Pydantic instance to a markdown string for storage in `AgentState` and display:

```python
def render_wheel_candidate_report(r: WheelCandidateReport) -> str: ...
def render_csp_decision(d: CspDecision) -> str: ...
def render_cc_decision(d: CcDecision) -> str: ...
def render_roll_decision(d: RollDecision) -> str: ...
```

These follow the `render_research_plan` / `render_pm_decision` pattern already in `schemas.py`: assemble a `"\n".join(parts)` string with `**Field**: value` lines.

---

## 4. AgentState Extension (Phase 2)

File: `tradingagents/agents/utils/agent_states.py`

Add the following five fields to the `AgentState` TypedDict, following the `Annotated[type, "description"]` pattern used by existing fields:

```python
class AgentState(MessagesState):
    # ... existing fields unchanged ...

    # Wheel options trading fields (Phase 2–4)
    # All stored as raw JSON strings for LangGraph checkpoint serialisation.
    # Agents deserialise on read using Schema.model_validate_json().
    wheel_phase: Annotated[
        Optional[str],
        "WheelPhase string value ('screening', 'csp_open', 'stock_owned', 'cc_open', 'cycle_complete', or None for equity-only mode)"
    ]
    wheel_candidate_report: Annotated[
        Optional[str],
        "Serialised JSON of WheelCandidateReport; written by WheelAnalyst, read by CLI layer and CspAgent"
    ]
    csp_decision: Annotated[
        Optional[str],
        "Serialised JSON of CspDecision; written by CspAgent, read by CLI layer and risk debate"
    ]
    cc_decision: Annotated[
        Optional[str],
        "Serialised JSON of CcDecision; written by CcAgent, read by CLI layer and risk debate"
    ]
    roll_decision: Annotated[
        Optional[str],
        "Serialised JSON of RollDecision; written by RollCheckAgent, read by CLI layer"
    ]
```

The `Optional` import must be added (`from typing import Optional`) if not already present. No default values are set (TypedDict fields without defaults require the caller to supply them or accept `KeyError` on absent keys; callers must use `state.get("wheel_phase")` for safe access).

---

## 5. Agent Implementations (Phases 2–4)

### 5.1 `WheelAnalyst`

**File:** `tradingagents/agents/analysts/wheel_analyst.py`

**Node function signature:**
```python
def create_wheel_analyst(llm: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    """Factory returning the wheel_analyst node function."""
    structured_llm = bind_structured(llm, WheelCandidateReport, "wheel_analyst")

    def wheel_analyst(state: AgentState, config: RunnableConfig) -> dict:
        ...
    return wheel_analyst
```

**LLM tier:** `deep_think_llm`. Rationale: the WheelAnalyst synthesises five distinct criterion evaluations plus a Delta-anchored strike range computation. This requires multi-step reasoning that benefits from the deeper model's accuracy; errors here propagate to all downstream trade recommendations.

**Tools bound:** `get_iv_metrics`, `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (all four from `options_data_tools.py`). Tools are bound using the existing `bind_tools` mechanism used for the four standard analysts.

**Structured output:**
- Construction: `structured_llm = bind_structured(llm, WheelCandidateReport, "wheel_analyst")`
- Invocation: `raw = invoke_structured_or_freetext(structured_llm, plain_llm, prompt, render_wheel_candidate_report, "wheel_analyst")`
- `invoke_structured_or_freetext` always returns `str` (see FSPEC-SE3-01). The render path produces a formatted markdown string. The freetext fallback path may return JSON in the string.
- Post-invocation parsing: `try: report = WheelCandidateReport.model_validate_json(raw)` — this succeeds on the freetext path if the LLM produced JSON, fails on the rendered-markdown path (expected). The state stores the raw `str` in `wheel_candidate_report`. The agent uses `report` (the parsed instance) only to evaluate the five criteria deterministically.
- If both the structured call and `model_validate_json` fail: write a sentinel `WheelCandidateReport` with `approved=False`, `rejection_reason="Structured output failed — safe fallback applied."`, `iv_rank=0.0`, `iv_percentile=0.0`, `iv_environment="compressed"`, `iv_assessment=""`, `earnings_clearance_ok=False`, `liquidity_ok=False`, `analyst_bias="neutral"`, `recommended_strike_range=[0.0, 0.0]`, `recommended_dte_range=[28, 45]`, `rationale="Structured output failed — safe fallback applied."`.

**State reads:** `state["company_of_interest"]`, `state["trade_date"]`, `state["market_report"]`, `state["sentiment_report"]`, `state["news_report"]`, `state["fundamentals_report"]`, `state["investment_plan"]`, `state.get("past_context", "")`.

**State writes:** `{"wheel_candidate_report": raw_str}` where `raw_str` is the string returned by `invoke_structured_or_freetext`.

**Key prompt context injected:**
- All four analyst reports
- Current `investment_plan` (for Criterion 5 consensus extraction)
- Wheel config thresholds: `min_iv_rank`, `earnings_buffer_days`, `max_wheel_stock_price`, `min_chain_oi`, `max_chain_spread_pct`, `near_the_money_pct`, `recommended_dte_low`, `recommended_dte_high`
- `past_context` string from `AgentState`
- Instruction to call all four data tools to gather required data, then produce a `WheelCandidateReport`

**Criterion evaluation order (deterministic, performed on the parsed `WheelCandidateReport` instance):**

The five criteria are evaluated in order 1→5 with no early exit. All failures are accumulated. The LLM's structured output is validated against the deterministic criterion results:

| Criterion | Check | Config key | Pass condition |
|---|---|---|---|
| 1 — IV environment | `iv_rank >= min_iv_rank` | `min_iv_rank` (default 25) | `iv_rank >= 25` |
| 2 — Chain liquidity | At least one NTM strike: `OI >= min_chain_oi` AND `(ask-bid)/mid <= max_chain_spread_pct/100` | `min_chain_oi`, `max_chain_spread_pct`, `near_the_money_pct` | Any NTM strike passes both sub-checks |
| 3 — Earnings clearance | `next_earnings > target_expiry + timedelta(days=earnings_buffer_days)` where `target_expiry = curr_date + timedelta(days=ceil((dte_low+dte_high)/2))` | `earnings_buffer_days`, `recommended_dte_low/high` | Earnings sufficiently clear |
| 4 — Price affordability | `spot_price <= max_wheel_stock_price` | `max_wheel_stock_price` (default 500) | Spot at or below cap |
| 5 — Analyst consensus | `recommendation in {Buy, Overweight, Hold}` parsed from `investment_plan` | None | Not Sell/Underweight; default pass if unparseable |

**`recommended_strike_range` computation (runs only when `approved=True`):**

1. Obtain the current options chain (already fetched for Criterion 2).
2. For each put strike in the chain, get Delta via `get_options_greeks`.
3. `low_strike`: strike whose `abs(put_delta)` is closest to `target_csp_delta_low` (e.g. 0.20).
4. `high_strike`: strike whose `abs(put_delta)` is closest to `target_csp_delta_high` (e.g. 0.30).
5. `recommended_strike_range = [low_strike, high_strike]`.
6. Fallback (if Greeks fail): `[round(spot * (1 - target_csp_delta_high) * 2) / 2, round(spot * (1 - target_csp_delta_low) * 2) / 2]` (rounded to nearest $0.50).

---

### 5.2 `CspAgent`

**File:** `tradingagents/agents/options/csp_agent.py`

**Node function signature:**
```python
def create_csp_agent(llm: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    structured_llm = bind_structured(llm, CspDecision, "csp_agent")

    def csp_agent(state: AgentState, config: RunnableConfig) -> dict:
        ...
    return csp_agent
```

**LLM tier:** `deep_think_llm`. Rationale: CspAgent selects a specific strike and expiration that must satisfy multiple simultaneous constraints (Delta range, yield, earnings clearance). The LLM's role is to weigh qualitative factors (support/resistance context from analyst reports, overall market tone) when multiple filtered candidates remain — a judgment-heavy task requiring the deeper model.

**Tools bound:** `get_options_chain`, `get_options_greeks`, `get_next_earnings_date`.

**Structured output pattern (identical for all three options agents; described fully here, referenced by name in 5.3 and 5.4):**

Construction (at factory call time):
```python
structured_llm = bind_structured(llm, CspDecision, "csp_agent")
```

Invocation (inside the node function):
```python
raw: str = invoke_structured_or_freetext(
    structured_llm, plain_llm, prompt, render_csp_decision, "csp_agent"
)
# raw is always str. Try JSON extraction:
try:
    decision = CspDecision.model_validate_json(raw)
    # If this succeeds, the freetext path returned JSON — use the parsed instance.
except Exception:
    # If this fails, raw is a rendered markdown string from the structured-success path.
    # The rendered string is already valid for state storage.
    # Attempt to find JSON block in raw (rendered markdown may contain JSON in a code block):
    decision = None  # state stores raw string; downstream reads the string

# On total failure of structured call AND no parseable JSON in raw:
# Return sentinel:
decision = CspDecision(
    tradeable=False,
    ticker=state["company_of_interest"],
    option_type="put",
    strike=0.0, expiration_date="", dte=0, bid=0.0, ask=0.0,
    mid_premium=0.0, delta=0.0, theta=0.0, annualised_yield_pct=0.0,
    max_loss=0.0, breakeven_price=0.0, probability_of_profit=0.0,
    earnings_clear=False,
    rationale="Structured output failed — safe fallback applied.",
)
raw = render_csp_decision(decision)
```

State write: `{"csp_decision": raw}`.

**State reads:** `state["company_of_interest"]`, `state["trade_date"]`, `state["market_report"]`, `state["sentiment_report"]`, `state["news_report"]`, `state["fundamentals_report"]`, `state.get("wheel_candidate_report")` (deserialised via `WheelCandidateReport.model_validate_json()` if present; config defaults used if absent), `state.get("past_context", "")`.

**State writes:** `{"csp_decision": raw_str}`.

**Key prompt context:** Analyst reports, `WheelCandidateReport` (or config DTE/Delta defaults), pre-filtered candidate strikes (from deterministic Stage 2), relaxation notes (from Stage 3), earnings date context. The prompt instructs the LLM to select one of the presented candidates and fill in the `CspDecision` schema fields.

**Deterministic filter function (separate, unit-testable):**

```python
def _filter_csp_candidates(
    chain_df: pd.DataFrame,       # puts DataFrame from options chain
    greeks_lookup: dict,           # {strike: delta_float}
    earnings_date: Optional[date],
    config: dict,
) -> list[dict]:
    """Apply Filters A, B, C in order. Return list of passing candidate dicts."""
```

This function is called before the LLM. The LLM receives only the output list. Filters:
- **A:** `target_csp_delta_low <= abs(delta) <= target_csp_delta_high` (inclusive both ends)
- **B:** `earnings_date is None` OR `earnings_date > expiration_date` (hard earnings exclusion per FSPEC-WHEEL-04)
- **C:** `annualised_yield_pct = (mid_premium / strike) * (365 / dte) * 100 >= min_annualised_yield_pct`

Progressive relaxation order: A+B+C → A+B (note `"yield_filter_relaxed"`) → A only (note `"earnings_filter_relaxed"`) → nearest-Delta fallback (note `"No strike matches Delta target; nearest available: {delta}"`). If all candidates straddle earnings after relaxation, return `CspDecision(tradeable=False, rejection_reason="All suitable expirations overlap earnings", ...)` without calling LLM.

**`options_lookforward_days` guard:** Before calling `get_options_chain`, compare `options_lookforward_days` to `recommended_dte_high`. If `options_lookforward_days < recommended_dte_high`, log warning and use `max(options_lookforward_days, recommended_dte_high + 7)` as effective window.

**Derived fields** (computed deterministically after LLM selects strike, never delegated to LLM):
- `mid_premium = (bid + ask) / 2`
- `annualised_yield_pct = (mid_premium / strike) * (365 / dte) * 100`
- `max_loss = (strike * 100) - (mid_premium * 100)`
- `breakeven_price = strike - mid_premium`
- `probability_of_profit = 1 - abs(delta)`

---

### 5.3 `CcAgent`

**File:** `tradingagents/agents/options/cc_agent.py`

**Node function signature:**
```python
def create_cc_agent(llm: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    structured_llm = bind_structured(llm, CcDecision, "cc_agent")

    def cc_agent(state: AgentState, config: RunnableConfig) -> dict:
        ...
    return cc_agent
```

**LLM tier:** `deep_think_llm`. Rationale: CC strike selection involves weighing the cost-basis constraint against Delta targets and yield requirements in the context of current market tone — judgment-heavy and consequential (suboptimal CC strike selection caps upside unnecessarily or generates inadequate premium).

**Tools bound:** `get_options_chain`, `get_options_greeks`, `get_next_earnings_date`.

**Structured output:** Same three-step pattern as CspAgent (Section 5.2), with `CcDecision` schema and `render_cc_decision` render function, `agent_name='cc_agent'`. Sentinel: `CcDecision(tradeable=False, ..., rationale="Structured output failed — safe fallback applied.")`.

**State reads:** `state["company_of_interest"]`, `state["trade_date"]`, analyst reports, `state.get("wheel_candidate_report")`. Additionally reads `WheelPosition` from the position store (loaded by file path: `{positions_dir}/{ticker}-cycle-{N}.json`; the most recent non-complete position file for the ticker) to obtain `csp_strike`, `csp_premium_received`, `cost_basis_per_share`.

**State writes:** `{"cc_decision": raw_str}`.

**Key prompt context:** Analyst reports, `WheelPosition` (cost basis, assigned strike, shares held), current spot price, pre-filtered candidate call strikes, earnings date, relaxation notes, below-cost-basis warning (if applicable).

**Deterministic filter function:**

```python
def _filter_cc_candidates(
    chain_df: pd.DataFrame,       # calls DataFrame
    greeks_lookup: dict,
    earnings_date: Optional[date],
    cost_basis: float,
    config: dict,
) -> list[dict]:
    """Apply Filters A (strike >= cost_basis), B (Delta range), C (earnings), D (yield). Return passing candidates."""
```

Filter order: A → B → C → D. Filter A is never relaxed. Relaxation order: A+B+C+D → A+B+C (drop D, yield) → A+B (drop C, earnings). If A+B yields no candidates: `tradeable=False`.

**Below-cost-basis branch:** Before Stage 2, fetch current spot price. If `spot < cost_basis` and no call strike `>= cost_basis` exists in the entire chain: return `CcDecision(tradeable=False, rejection_reason="No call strikes at or above cost basis available — spot price below cost basis", ...)`. LLM is not called. If strikes `>= cost_basis` exist despite spot being below cost basis: inject warning note into LLM prompt; `tradeable` may still be `True`.

**Derived fields** (computed deterministically):
- `annualised_yield_on_cost_pct = (mid_premium / cost_basis) * (365 / dte) * 100`
- `upside_to_strike_pct = (strike - spot_price) / spot_price * 100`
- `strike_above_cost_basis = strike >= cost_basis`
- `assigned_at` and `cost_basis` sourced from `WheelPosition`, not from LLM.

---

### 5.4 `RollCheckAgent`

**File:** `tradingagents/agents/options/roll_agent.py`

**Node function signature:**
```python
def create_roll_check_agent(llm: Any, position_store_dir: str) -> Callable[[AgentState, RunnableConfig], dict]:
    structured_llm = bind_structured(llm, RollDecision, "roll_check_agent")

    def roll_check_agent(state: AgentState, config: RunnableConfig) -> dict:
        ...
    return roll_check_agent
```

**LLM tier:** `quick_think_llm`. Rationale: RollCheckAgent's five rules are all deterministic; the LLM's role is limited to providing rationale text for the pre-determined action and populating the `new_strike`/`new_expiration` fields for ROLL actions. This is a lower-stakes judgment call relative to initial trade selection, making the faster model appropriate.

**Tools bound:** `get_options_chain`, `get_options_greeks`, `get_next_earnings_date`.

**Structured output:** Same three-step pattern as CspAgent (Section 5.2), with `RollDecision` schema and `render_roll_decision` render function, `agent_name='roll_check_agent'`. Sentinel: `RollDecision(action="HOLD", ticker=..., current_strike=0.0, current_expiration="", current_dte=0, current_value_pct_of_premium=0.0, trigger_reason="profit_capture", rationale="Structured output failed — safe fallback applied.")`.

**State reads:** `state["company_of_interest"]`, `state["trade_date"]`, `state["wheel_phase"]`, `state["investment_plan"]`, analyst reports, `state.get("past_context", "")`. Loads `WheelPosition` from the position store.

**State writes:** `{"roll_decision": raw_str}`. Also writes updated `WheelPosition` JSON to disk (updating `prior_analyst_bias`).

**Key prompt context:** `WheelPosition` details (open strike, expiration, premium received), current contract value (from chain mid-price), `current_dte`, pre-computed `current_value_pct_of_premium`, all five rule evaluation results (which rules fired, why), `current_analyst_bias`, `prior_analyst_bias`. The prompt presents the deterministic rule outcome and asks the LLM to confirm/populate the `RollDecision` schema and provide rationale. The final `action` and `trigger_reason` are determined by the deterministic priority logic before the LLM call; the prompt informs the LLM of the determined action.

**Five rules with exact firing conditions:**

| Rule | Firing condition | Proposed action | `trigger_reason` |
|---|---|---|---|
| 1 — Profit capture | `current_value_pct_of_premium <= take_profit_pct` (default 50, inclusive) | `"HOLD"` | `"profit_capture"` |
| 2 — DTE | `current_dte <= dte_to_roll` (default 21, inclusive) | `"ROLL"` | `"dte_rule"` |
| 3 — Breach (CSP only) | `spot_price <= csp_strike * 0.85` (inclusive; `wheel_phase == "csp_open"` only) | `"ROLL"` if `current_value_pct_of_premium >= 50`; else `"CLOSE"` | `"breach_rule_roll"` or `"breach_rule_close"` |
| 4 — Earnings | Earnings within remaining DTE AND `abs(current_delta) >= 0.10` (NOT deep OTM; exclusive: `== 0.10` fires) | `"CLOSE"` | `"earnings_rule"` |
| 5 — Analyst update | `prior_analyst_bias == "bullish"` AND `current_analyst_bias == "bearish"` | `"CLOSE"` | `"analyst_update"` |

**Priority resolution (highest to lowest):** Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1. Only one `trigger_reason` in output. Default (no rule fires): `action="HOLD"`, `trigger_reason="profit_capture"`.

**`trigger_reason` assignment code pattern:**
```python
action, trigger_reason = "HOLD", "profit_capture"  # default

rule1_fires = current_value_pct_of_premium <= take_profit_pct
rule2_fires = current_dte <= dte_to_roll
rule3_roll = (wheel_phase == "csp_open" and spot <= csp_strike * 0.85 and current_value_pct_of_premium >= 50)
rule3_close = (wheel_phase == "csp_open" and spot <= csp_strike * 0.85 and current_value_pct_of_premium < 50)
rule4_fires = (earnings_within_dte and current_delta_abs >= 0.10)
rule5_fires = (prior_analyst_bias == "bullish" and current_analyst_bias == "bearish")

# Priority: Rule3 > Rule5 > Rule4 > Rule2 > Rule1
if rule3_close:
    action, trigger_reason = "CLOSE", "breach_rule_close"
elif rule3_roll:
    action, trigger_reason = "ROLL", "breach_rule_roll"
elif rule5_fires:
    action, trigger_reason = "CLOSE", "analyst_update"
elif rule4_fires:
    action, trigger_reason = "CLOSE", "earnings_rule"
elif rule2_fires:
    action, trigger_reason = "ROLL", "dte_rule"
elif rule1_fires:
    action, trigger_reason = "HOLD", "profit_capture"
# else: default HOLD / profit_capture already set
```

**`prior_analyst_bias` read and write:**
- Read: `position.prior_analyst_bias` (from loaded `WheelPosition`; `None` on first run → Rule 5 does not fire).
- `current_analyst_bias` derivation: parse `ResearchPlan.recommendation` from `state["investment_plan"]` using `ResearchPlan.model_validate_json()`. Map: `Buy`/`Overweight` → `"bullish"`, `Hold` → `"neutral"`, `Underweight`/`Sell` → `"bearish"`. If unparseable: `"neutral"`.
- Write: after rule evaluation (regardless of action taken), update `position.prior_analyst_bias = current_analyst_bias` and persist the updated `WheelPosition` JSON atomically.

**`current_delta` fetch for Rule 4:** Call `get_options_greeks` for the current strike/expiration to obtain `current_delta`. If the call fails: treat `abs(current_delta)` as NOT deep OTM (conservative: Rule 4 fires if earnings is within DTE). This matches the FSPEC-WHEEL-06 edge case specification.

**ROLL action — new contract specification:**
- Target expiration: next standard expiration date at least `dte_to_roll` calendar days beyond the current expiration.
- Delta target: CSP roll → `[target_csp_delta_low, target_csp_delta_high]`; CC roll → `[target_cc_delta_low, target_cc_delta_high]`.
- `estimated_debit_or_credit = new_mid_premium - current_contract_value` (positive = net credit).

---

## 6. Graph Integration (Phase 4)

### 6.1 `setup_graph()` Modifications

File: `tradingagents/graph/setup.py`

**New nodes registered:**

```python
# Wheel analyst (conditional on "wheel" in selected_analysts)
if "wheel" in selected_analysts:
    wheel_analyst_node = create_wheel_analyst(self.deep_thinking_llm)
    workflow.add_node("wheel_analyst", wheel_analyst_node)

# Options agents (always registered if any wheel phase is active)
csp_agent_node = create_csp_agent(self.deep_thinking_llm)
cc_agent_node = create_cc_agent(self.deep_thinking_llm)
roll_check_agent_node = create_roll_check_agent(self.quick_thinking_llm, config["wheel"]["positions_dir"])

workflow.add_node("csp_agent", csp_agent_node)
workflow.add_node("cc_agent", cc_agent_node)
workflow.add_node("roll_check_agent", roll_check_agent_node)
workflow.add_node("wheel_cycle_summary", wheel_cycle_summary_node)

# Options data tool node (registered alongside existing tool nodes)
options_tool_node = ToolNode([get_options_chain, get_iv_metrics, get_options_greeks, get_next_earnings_date])
workflow.add_node("tools_options", options_tool_node)
```

**`ConditionalLogic` construction change:**
```python
# In setup_graph(), after building the plan:
self.conditional_logic.first_analyst_node = plan.specs[0].agent_node
self.conditional_logic.position_store_dir = config["wheel"]["positions_dir"]
```

**Replacing the direct `START → first_analyst` edge:**

The existing line:
```python
workflow.add_edge(START, plan.specs[0].agent_node)
```
is replaced by:
```python
# Build the mapping of all possible return values from route_wheel_phase
wheel_route_mapping = {
    plan.specs[0].agent_node: plan.specs[0].agent_node,
    "roll_check_agent": "roll_check_agent",
    "cc_agent": "cc_agent",
    "wheel_cycle_summary": "wheel_cycle_summary",
}
workflow.add_conditional_edges(
    START,
    self.conditional_logic.route_wheel_phase,
    wheel_route_mapping,
)
```

**WheelAnalyst → CspAgent edge** (inserted after the last analyst's `clear_node` → Bull Researcher edge, when `"wheel"` is in `selected_analysts`):

```python
# In the analyst-chaining loop, after the last analyst connects to Bull Researcher:
if "wheel" in selected_analysts:
    # WheelAnalyst runs after Bull Researcher → Research Manager → Trader chain
    # is complete; insert it between Trader and Aggressive Analyst
    # WheelAnalyst node is placed between Trader output and Aggressive Analyst
    workflow.add_edge("Trader", "wheel_analyst")
    workflow.add_edge("wheel_analyst", "Aggressive Analyst")
else:
    workflow.add_edge("Trader", "Aggressive Analyst")
```

Note: When `"wheel"` is NOT in `selected_analysts`, the `"Trader" → "Aggressive Analyst"` direct edge is preserved exactly as today (REQ-SCREEN-01 AC5, REQ-NFR-01).

**`wheel_cycle_summary` → `END` edge:**
```python
workflow.add_edge("wheel_cycle_summary", END)
```

---

### 6.2 `ConditionalLogic.route_wheel_phase()`

File: `tradingagents/graph/conditional_logic.py`

```python
def route_wheel_phase(self, state: AgentState) -> str:
    """Route to the appropriate node based on wheel_phase value.
    
    Returns a node name string. Raises WheelStateError on illegal transitions.
    """
    phase = state.get("wheel_phase")  # None or string
    
    if phase is None:
        return self.first_analyst_node
    
    if phase == "screening":
        return self.first_analyst_node
    
    if phase == "csp_open":
        position = self._load_position(state["company_of_interest"])
        if position is None or position.csp_strike is None:
            raise WheelStateError("No open CSP position found for phase 'csp_open'")
        return "roll_check_agent"
    
    if phase == "stock_owned":
        return "cc_agent"
    
    if phase == "cc_open":
        position = self._load_position(state["company_of_interest"])
        if position is None or position.cc_strike is None:
            raise WheelStateError("No open CC position found for phase 'cc_open'")
        return "roll_check_agent"
    
    if phase == "cycle_complete":
        return "wheel_cycle_summary"
    
    # Unknown value — fall back to equity-only path with warning
    import logging
    logging.getLogger(__name__).warning(
        "Unknown wheel_phase value '%s' — falling back to equity-only path", phase
    )
    return self.first_analyst_node
```

**Return value table:**

| `wheel_phase` value | Returns | Guard check |
|---|---|---|
| `None` | `first_analyst_node` | None |
| `"screening"` | `first_analyst_node` | None |
| `"csp_open"` | `"roll_check_agent"` | Position with `csp_strike` must exist |
| `"stock_owned"` | `"cc_agent"` | None |
| `"cc_open"` | `"roll_check_agent"` | Position with `cc_strike` must exist |
| `"cycle_complete"` | `"wheel_cycle_summary"` | None |
| unknown string | `first_analyst_node` | None (logs warning) |

`ConditionalLogic.__init__` gains two new parameters:
```python
def __init__(
    self,
    max_debate_rounds: int = 1,
    max_risk_discuss_rounds: int = 1,
    first_analyst_node: str = "Market Analyst",     # injected by setup_graph()
    position_store_dir: str = "memory/wheel_positions",  # injected by setup_graph()
):
```

`_load_position(ticker)` is a private helper that reads the most recent non-complete `WheelPosition` JSON file for the given ticker from `position_store_dir`.

---

### 6.3 `wheel_cycle_summary` Node

File: `tradingagents/graph/wheel_nodes.py`

```python
def wheel_cycle_summary(state: AgentState, config: RunnableConfig) -> dict:
    """Emit cycle summary, persist completed WheelPosition, write memory log entry.
    
    Returns: {'wheel_phase': None} to signal pipeline end.
    """
```

**What it does:**
1. Load the `WheelPosition` JSON file for the current ticker (most recent cycle file).
2. Compute `cycle_duration_days = (call_away_date_dt - csp_open_date_dt).days` (calendar days).
3. Compute `cycle_pnl = (cc_strike - csp_strike + cumulative_premium_received) * shares_held`.
   - For CLOSE (early close) paths: `cycle_pnl` is computed from the net premium vs. cost incurred.
4. Compute `cycle_annualised_return_pct = (cycle_pnl / (csp_strike * shares_held)) * (365 / cycle_duration_days) * 100`.
5. Update `WheelPosition`: set `cycle_pnl`, `cycle_annualised_return_pct`, `wheel_phase = "cycle_complete"`. Write atomically.
6. Write `TradingMemoryLog` entry: use `memory_log.store_decision(ticker, trade_date, summary_text)` where `summary_text` is a formatted string containing ticker, cycle number, cycle duration, premiums collected (formatted to 2 decimal places), `cycle_pnl` (formatted to 2 decimal places), and `cycle_annualised_return_pct`. This satisfies REQ-LIFE-05's requirement that `past_context` on subsequent runs contains `cycle_pnl` formatted to 2 decimal places.
7. If memory log write fails: log the error, do not raise; the cycle summary is still returned to the user.
8. Format a human-readable cycle summary string for display in the CLI.
9. Return `{"wheel_phase": None}` to reset the phase for the next graph invocation. This causes LangGraph to write `None` into `AgentState["wheel_phase"]`.

**`WheelStateError` class:**
```python
class WheelStateError(Exception):
    """Raised when a wheel phase transition guard fails or state is inconsistent."""
```

Defined at module level in `tradingagents/graph/wheel_nodes.py`. Imported by `conditional_logic.py`.

---

## 7. CLI Integration (Phases 2 + 4)

### 7.1 `WheelCandidateReport` in `MessageBuffer`

The existing `MessageBuffer` class (in the CLI display module) gains a new section key:

```python
report_buffer.update_report_section("wheel_candidate", report_text)
```

Where `report_text` is assembled from the `WheelCandidateReport` instance as follows:

```
## WheelCandidateReport
Approved: Yes   [or: Approved: No]
[Rejection reason: {rejection_reason}]   (only when approved=False)
IV Rank: {iv_rank:.1f}
IV Percentile: {iv_percentile:.1f}
IV Environment: {iv_environment}
Earnings Clearance: {'OK' if earnings_clearance_ok else 'FAIL'}
Recommended Strike Range: [{recommended_strike_range[0]:.2f}, {recommended_strike_range[1]:.2f}]
Recommended DTE Range: [{recommended_dte_range[0]}, {recommended_dte_range[1]}] calendar days
Rationale: {rationale[:300]}{'...' if len(rationale) > 300 else ''}
```

Rich panel title: `"Wheel Suitability"`.

Rich style rules:
- Panel title uses default neutral style when `approved=True`.
- Panel title uses `"bold red"` style when `approved=False`.
- The body always opens with `## WheelCandidateReport` (the literal string, not styled) to satisfy both `console.export_text()` test assertions.
- `rejection_reason` is displayed on its own line whenever non-None.

Display guard: The panel is rendered only when `"wheel"` is in `selected_analysts` AND `state.get("wheel_candidate_report")` is not `None`. When either condition is absent, the existing CLI output is unchanged (REQ-NFR-01).

### 7.2 `tradingagents wheel-status` CLI Sub-command

Implemented as a new Click command (or Typer command, matching the existing CLI framework pattern):

```python
@app.command("wheel-status")
def wheel_status():
    """Display all open wheel positions and completed cycle history."""
```

**Behaviour:**
1. Load `config["wheel"]["positions_dir"]`.
2. Glob all `*.json` files in that directory.
3. Parse each file as `WheelPosition`. Separate into `open_positions` (where `wheel_phase != "cycle_complete"`) and `completed_cycles` (where `wheel_phase == "cycle_complete"`).
4. Fetch current spot price via `yf.Ticker(position.ticker).history(period="1d")["Close"].iloc[-1]` for each open position.
5. Compute current unrealised P&L for open positions: for `csp_open` phase — `(original_premium - current_contract_value) * shares_held`; for `stock_owned` / `cc_open` — `(spot - cost_basis_per_share) * shares_held + cumulative_premium_received * shares_held`.

**Rich Table 1 — Open Positions:**

| Column | Source |
|---|---|
| Ticker | `position.ticker` |
| Phase | `position.wheel_phase` |
| Strike | `csp_strike` or `cc_strike` |
| Expiration | `csp_expiration` or `cc_expiration` |
| DTE | Computed from today's date |
| Cost Basis | `cost_basis_per_share` |
| Premium Collected | `cumulative_premium_received` |
| Current P&L | Computed (see above) |

**Rich Table 2 — Completed Cycles:**

| Column | Source |
|---|---|
| Ticker | `position.ticker` |
| Cycle # | `position.cycle_number` |
| Duration (days) | `(call_away_date - assignment_date).days` |
| Total Premium | `cumulative_premium_received` |
| Cycle P&L | `cycle_pnl` |
| Ann. Return % | `cycle_annualised_return_pct` |

When no open positions: print `"No open wheel positions"` (exact string required by REQ-LIFE-06 AC2).

---

## 8. Configuration (All Phases)

### 8.1 `config["wheel"]` in `default_config.py`

Add the following sub-dict to `DEFAULT_CONFIG`:

```python
"wheel": {
    # Screening thresholds
    "min_iv_rank": 25,                    # int: minimum IV Rank to approve a wheel candidate
    "earnings_buffer_days": 14,           # int: min days between target expiry and next earnings
    "max_wheel_stock_price": 500.0,       # float: maximum stock price for cash manageability
    "near_the_money_pct": 0.10,           # float: ±% of spot price defining near-the-money strikes (Criterion 2)
    
    # CSP parameters
    "target_csp_delta_low": 0.20,         # float: lower bound of target put delta (inclusive)
    "target_csp_delta_high": 0.30,        # float: upper bound of target put delta (inclusive)
    
    # CC parameters
    "target_cc_delta_low": 0.20,          # float: lower bound of target call delta (inclusive)
    "target_cc_delta_high": 0.35,         # float: upper bound of target call delta (inclusive)
    
    # Yield and timing
    "min_annualised_yield_pct": 12.0,     # float: minimum annualised premium yield to accept a trade
    "recommended_dte_low": 28,            # int: minimum DTE (calendar days) for new positions
    "recommended_dte_high": 45,           # int: maximum DTE (calendar days) for new positions
    "options_lookforward_days": 90,       # int: chain look-ahead window (calendar days); must be >= recommended_dte_high
    
    # Roll management
    "take_profit_pct": 50.0,             # float: roll/close when contract value is at or below this % of premium received
    "dte_to_roll": 21,                    # int: roll when DTE falls to or below this value (calendar days)
    
    # IV computation
    "iv_rank_lookback_days": 252,         # int: trading days for IV Rank/Percentile computation
    
    # Liquidity filters
    "min_chain_oi": 100,                  # int: minimum open interest for a strike to be liquid
    "max_chain_spread_pct": 10.0,         # float: max bid/ask spread as % of mid for liquidity filter
    
    # Risk-free rate
    "risk_free_rate_source": "yfinance_irx",  # str: "yfinance_irx" or "static"
    "risk_free_rate_static": 0.0525,      # float: static risk-free rate (decimal, not percent)
    
    # Position persistence
    "positions_dir": "memory/wheel_positions",  # str: directory for per-position JSON files
},
```

Total: 18 keys. All keys have inline comments as required by REQ-NFR-07.

### 8.2 `_ENV_OVERRIDES` Additions

Because `_apply_env_overrides` only handles flat top-level keys (noted in the constraints section below), wheel config overrides require a separate helper. Add to `default_config.py`:

```python
_WHEEL_ENV_OVERRIDES = {
    "TRADINGAGENTS_WHEEL_MIN_IV_RANK":              ("wheel", "min_iv_rank"),
    "TRADINGAGENTS_WHEEL_EARNINGS_BUFFER_DAYS":     ("wheel", "earnings_buffer_days"),
    "TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE":    ("wheel", "max_wheel_stock_price"),
    "TRADINGAGENTS_WHEEL_NEAR_THE_MONEY_PCT":       ("wheel", "near_the_money_pct"),
    "TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_LOW":     ("wheel", "target_csp_delta_low"),
    "TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_HIGH":    ("wheel", "target_csp_delta_high"),
    "TRADINGAGENTS_WHEEL_TARGET_CC_DELTA_LOW":      ("wheel", "target_cc_delta_low"),
    "TRADINGAGENTS_WHEEL_TARGET_CC_DELTA_HIGH":     ("wheel", "target_cc_delta_high"),
    "TRADINGAGENTS_WHEEL_MIN_ANNUALISED_YIELD_PCT": ("wheel", "min_annualised_yield_pct"),
    "TRADINGAGENTS_WHEEL_RECOMMENDED_DTE_LOW":      ("wheel", "recommended_dte_low"),
    "TRADINGAGENTS_WHEEL_RECOMMENDED_DTE_HIGH":     ("wheel", "recommended_dte_high"),
    "TRADINGAGENTS_WHEEL_OPTIONS_LOOKFORWARD_DAYS": ("wheel", "options_lookforward_days"),
    "TRADINGAGENTS_WHEEL_TAKE_PROFIT_PCT":          ("wheel", "take_profit_pct"),
    "TRADINGAGENTS_WHEEL_DTE_TO_ROLL":              ("wheel", "dte_to_roll"),
    "TRADINGAGENTS_WHEEL_IV_RANK_LOOKBACK_DAYS":    ("wheel", "iv_rank_lookback_days"),
    "TRADINGAGENTS_WHEEL_MIN_CHAIN_OI":             ("wheel", "min_chain_oi"),
    "TRADINGAGENTS_WHEEL_MAX_CHAIN_SPREAD_PCT":     ("wheel", "max_chain_spread_pct"),
    "TRADINGAGENTS_WHEEL_RISK_FREE_RATE_SOURCE":    ("wheel", "risk_free_rate_source"),
    "TRADINGAGENTS_WHEEL_RISK_FREE_RATE_STATIC":    ("wheel", "risk_free_rate_static"),
    "TRADINGAGENTS_WHEEL_POSITIONS_DIR":            ("wheel", "positions_dir"),
}


def _apply_nested_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_WHEEL_* env vars to nested config['wheel'] sub-dict."""
    for env_var, (section, key) in _WHEEL_ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        reference = config.get(section, {}).get(key)
        config[section][key] = _coerce(raw, reference)
    return config
```

Call `_apply_nested_env_overrides(config)` at the end of `DEFAULT_CONFIG` assembly (after `_apply_env_overrides`).

### 8.3 Config Validation

At `setup_graph()` time (or at `TradingAgentGraph.__init__`), add a validation check:

```python
if config["wheel"]["options_lookforward_days"] < config["wheel"]["recommended_dte_high"]:
    import warnings
    warnings.warn(
        f"options_lookforward_days ({config['wheel']['options_lookforward_days']}) is less than "
        f"recommended_dte_high ({config['wheel']['recommended_dte_high']}). "
        f"The effective lookforward window will be extended automatically.",
        UserWarning,
        stacklevel=2,
    )
```

This satisfies the constraint from FSPEC-WHEEL-04 and the open question closed in the FSPEC.

---

## 9. `WheelPosition` Persistence

### 9.1 Model Definition

File: `tradingagents/models/wheel_position.py`

```python
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class WheelPosition(BaseModel):
    """Persistent record of a single wheel strategy cycle for one ticker."""

    ticker: str = Field(description="Equity ticker symbol.")
    wheel_phase: str = Field(description="WheelPhase string value.")
    cycle_number: int = Field(description="Monotonically increasing per ticker.")
    
    # CSP fields
    csp_open_date: Optional[str] = Field(default=None, description="YYYY-MM-DD when CSP was opened.")
    csp_strike: Optional[float] = Field(default=None)
    csp_expiration: Optional[str] = Field(default=None, description="YYYY-MM-DD.")
    csp_premium_received: Optional[float] = Field(default=None)
    
    # Assignment fields
    assignment_date: Optional[str] = Field(default=None, description="YYYY-MM-DD if assigned.")
    shares_held: Optional[int] = Field(default=None, description="Always 100 per contract.")
    cost_basis_per_share: Optional[float] = Field(
        default=None,
        description="csp_strike - csp_premium_received.",
    )
    
    # CC fields
    cc_strike: Optional[float] = Field(default=None)
    cc_expiration: Optional[str] = Field(default=None, description="YYYY-MM-DD.")
    cc_premium_received: Optional[float] = Field(default=None)
    
    # Completion fields
    call_away_date: Optional[str] = Field(default=None, description="YYYY-MM-DD if called away.")
    cumulative_premium_received: float = Field(default=0.0)
    cycle_pnl: Optional[float] = Field(default=None, description="Realised at cycle end.")
    cycle_annualised_return_pct: Optional[float] = Field(default=None)
    
    # Roll/analyst tracking
    prior_analyst_bias: Optional[str] = Field(
        default=None,
        description="Analyst bias from the previous RollCheckAgent run: 'bullish', 'neutral', or 'bearish'.",
    )
    notes: str = Field(default="")
```

### 9.2 File Path Convention

```
{config["wheel"]["positions_dir"]}/{ticker}-cycle-{cycle_number}.json
```

Example: `memory/wheel_positions/NVDA-cycle-1.json`

### 9.3 Atomic Write Pattern

```python
import os
import tempfile
from pathlib import Path


def save_wheel_position(position: WheelPosition, positions_dir: str) -> None:
    """Write WheelPosition to disk using atomic temp-file + os.replace pattern."""
    dir_path = Path(positions_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    
    file_path = dir_path / f"{position.ticker}-cycle-{position.cycle_number}.json"
    json_str = position.model_dump_json(indent=2)
    
    # Write to temp file in the same directory (same filesystem → atomic rename)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(json_str)
        os.replace(tmp_path, file_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_wheel_position(ticker: str, cycle_number: int, positions_dir: str) -> Optional[WheelPosition]:
    """Load a WheelPosition JSON file. Returns None if file does not exist."""
    file_path = Path(positions_dir) / f"{ticker}-cycle-{cycle_number}.json"
    if not file_path.exists():
        return None
    return WheelPosition.model_validate_json(file_path.read_text(encoding="utf-8"))


def load_latest_open_position(ticker: str, positions_dir: str) -> Optional[WheelPosition]:
    """Load the most recent non-complete WheelPosition for the given ticker."""
    dir_path = Path(positions_dir)
    if not dir_path.exists():
        return None
    
    # Find all cycle files for this ticker, sorted by cycle_number descending
    pattern = f"{ticker}-cycle-*.json"
    candidates = sorted(dir_path.glob(pattern), reverse=True)
    
    for path in candidates:
        pos = WheelPosition.model_validate_json(path.read_text(encoding="utf-8"))
        if pos.wheel_phase != "cycle_complete":
            return pos
    return None
```

This atomic write pattern (`tempfile.mkstemp` + `os.replace`) matches the `TradingMemoryLog.update_with_outcome()` pattern at lines 161–163 of `memory.py`.

### 9.4 `cycle_annualised_return_pct` Formula

```
cycle_annualised_return_pct = (cycle_pnl / (csp_strike × shares_held)) × (365 / cycle_duration_days) × 100
```

Where `cycle_duration_days` is the number of **calendar days** from `csp_open_date` to `call_away_date` (or to the `CLOSE` action date for early-close cycles). Division by `csp_strike × shares_held` represents the capital at risk for the full cycle. Annualisation uses 365 (calendar days, consistent with all other yield calculations in this feature).

**Numeric example (REQ-LIFE-02 AC3a):**
- `cycle_pnl = 930`, `csp_strike = 140`, `shares_held = 100`, `cycle_duration_days = 73`
- `cycle_annualised_return_pct = (930 / (140 × 100)) × (365 / 73) × 100 = (930 / 14000) × 5.0 × 100 ≈ 33.21%`

---

## 10. Constraints and Open Questions

### 10.1 Decisions Deferred to PLAN Authoring

1. **WheelAnalyst graph position:** This TSPEC specifies WheelAnalyst is inserted between the Trader output and the Aggressive Analyst (Section 6.1). This preserves the `investment_plan` field written by the Research Manager for Criterion 5 consensus extraction. PLAN author must confirm this position does not disrupt any existing edge in the current graph topology.

2. **`csp_open` → `stock_owned` trigger mechanism:** The FSPEC-WHEEL-07 open question notes this is a manual state update by the human trader. The TSPEC defers the exact mechanism (e.g., a CLI command `tradingagents wheel-assign {ticker} {date}` vs. a state file update) to the PLAN. The `WheelPosition` model is fully specified; only the trigger-entry CLI path is undefined.

3. **`cc_open` → `stock_owned` on CC expiry worthless:** Same deferral as above — the mechanism for detecting "CC expired worthless and stock is still held" is a PLAN decision.

4. **`options_data_tools.py` tool registration with the existing analyst tool nodes:** The PLAN must specify how the `tools_options` ToolNode is wired into the graph for agents that call options tools during their tool-use turns (WheelAnalyst, CspAgent, CcAgent, RollCheckAgent each call tools via the LangGraph tool-calling pattern).

5. **CC DTE lower bound:** The FSPEC-WHEEL-05 open question notes REQ mentions "21–45 DTE" for CC (vs "28–45" for CSP) but the config table only has one shared `recommended_dte_low = 28`. This TSPEC uses the shared `recommended_dte_low = 28` for both CSP and CC (following the config table). PLAN/PROPERTIES author should flag if a distinct CC lower bound is required in Phase 2.

### 10.2 FSPEC-SE3-01 Carry-Forward

**Critical implementation note for all three options agents (CspAgent, CcAgent, RollCheckAgent) and WheelAnalyst:**

`invoke_structured_or_freetext` (in `tradingagents/agents/utils/structured.py`, lines 48–73) always returns `str`. It never returns a Pydantic instance.

- When the structured call succeeds: returns `render_fn(validated_instance)` — a formatted markdown string.
- When the structured call fails and falls back to freetext: returns `response.content` — the LLM's raw string, which may contain JSON.

**Correct implementation pattern in each agent:**

```python
raw: str = invoke_structured_or_freetext(
    structured_llm, plain_llm, prompt, render_schema, agent_name
)

# Try JSON extraction from the returned string.
# This succeeds on the freetext path (if LLM produced JSON).
# This fails on the render path (rendered markdown is not JSON) — expected.
decision = None
try:
    decision = Schema.model_validate_json(raw)
except Exception:
    pass

# If JSON extraction failed, raw is the rendered markdown string.
# This is still a valid string for state storage.
# Only produce the sentinel if we have neither a parsed instance
# nor a non-empty rendered string:
if decision is None and (not raw or raw.strip() == ""):
    decision = sentinel_schema_instance
    raw = render_schema(decision)

# Write raw (str) to state:
return {state_key: raw}
```

The agent should NOT unconditionally apply `model_validate_json` and treat failure as a total-failure sentinel — the rendered-markdown path (structured success) is the happy path and produces a non-JSON `raw` string by design.

### 10.3 Nested Config Override Constraint

`_apply_env_overrides` in `default_config.py` (lines 34–41) only handles flat top-level keys of the form `config[key]`. It cannot override `config["wheel"]["min_iv_rank"]` because `_ENV_OVERRIDES` maps to plain string keys, not nested paths.

**Resolution:** Add `_WHEEL_ENV_OVERRIDES` (a separate mapping to `(section, key)` tuples) and `_apply_nested_env_overrides()` helper (Section 8.2). The existing `_apply_env_overrides` is not modified. The `DEFAULT_CONFIG` initialisation calls both helpers in sequence:

```python
DEFAULT_CONFIG = _apply_nested_env_overrides(_apply_env_overrides({
    ...
    "wheel": { ... },
}))
```

### 10.4 `options_lookforward_days` Validation

`options_lookforward_days` must satisfy `options_lookforward_days >= config["wheel"]["recommended_dte_high"]` at runtime. If the env var sets `options_lookforward_days` below `recommended_dte_high`, the system logs a `UserWarning` at graph setup time and `CspAgent`/`CcAgent` both use `max(options_lookforward_days, recommended_dte_high + 7)` as the effective lookforward window when calling `get_options_chain`. The raw config value is not mutated.

### 10.5 Rule 1 Action (HOLD vs CLOSE at 50% Profit Target)

The FSPEC-WHEEL-06 open question asks whether `action="HOLD"` or `action="CLOSE"` is correct when the profit target is hit. This TSPEC follows the REQ-LIFE-03 AC1 specification: `action="HOLD"` when `current_value_pct_of_premium <= take_profit_pct` and no higher-priority rule fires. The PLAN author may wish to revisit this with the product owner before implementation.

### 10.6 Breach Threshold Configurability

The 15% breach threshold (`csp_strike * 0.85`) is hardcoded in this TSPEC (not configurable in Phase 1). Adding a `breach_threshold_pct` key to `config["wheel"]` is deferred to a future phase. The PLAN author should note this as a known gap.

### 10.7 `scipy` Dependency

`get_options_greeks` requires `scipy.stats.norm.cdf` and `scipy.stats.norm.pdf` for the BSM formulae. The PLAN must add `scipy` to the project dependencies (`pyproject.toml` or `requirements.txt`) if not already present. Alternatively, implement the standard normal CDF using the `math.erfc` approximation to avoid the `scipy` dependency — this is a PLAN-level decision.
