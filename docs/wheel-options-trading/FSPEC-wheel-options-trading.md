# FSPEC — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.2.0 |
| **Created** | 2026-05-25 |
| **Upstream** | REQ-wheel-options-trading.md v0.2.0 → **FSPEC** |
| **Downstream** | TSPEC, PROPERTIES |
| **Cross-Reviews** | `CROSS-REVIEW-software-engineer-FSPEC.md`, `CROSS-REVIEW-test-engineer-FSPEC.md` |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.2.0 | 2026-05-25 | Address SE/TE FSPEC cross-review findings: fix route_to_vendor contract, add structured.py rule, resolve Rule 5 and Criterion 5 mechanisms, add FSPEC-WHEEL-08 and FSPEC-WHEEL-09, add boundary ACs, add test level annotations |
| 0.1.0 | 2026-05-25 | Initial draft |

---

## Overview

This document specifies the functional behaviour of the Wheel Options Trading feature across four delivery phases. It covers the nine areas of behavioural complexity identified in the approved requirements that engineers must not decide alone: data tool routing, IV computation, suitability screening, CSP strike selection, covered call strike selection, roll/hold/close logic, the wheel phase state machine, CLI wheel panel display, and risk debate options context injection.

Each section is self-contained and references the upstream REQ acceptance criteria that govern it.

---

## FSPEC-WHEEL-01: Options Data Tool Routing

**Linked requirements:** REQ-DATA-01, REQ-DATA-02, REQ-DATA-03, REQ-DATA-04, REQ-DATA-05

**Purpose:** Define how the four options data tool wrappers route through `interface.py`'s vendor layer so that swapping data providers requires no changes to agent code.

**Actors:**
- `options_data_tools.py` — the `@tool`-decorated LangChain wrapper layer
- `interface.py` — the vendor-routing hub (`route_to_vendor`, `TOOLS_CATEGORIES`, `get_category_for_method`)
- `y_finance.py` — the Phase 1 yfinance implementation layer
- Any future Alpha Vantage or CBOE LiveVol adapter

**Behavioural Flow:**

1. An agent calls one of the four tool functions exposed by `options_data_tools.py`: `get_options_chain`, `get_iv_metrics`, `get_options_greeks`, or `get_next_earnings_date`.
2. The `@tool` wrapper in `options_data_tools.py` passes the call to `interface.py` via `route_to_vendor()`, supplying:
   - the method name matching the underlying implementation (e.g., `"get_options_chain"`)
   - all caller-supplied arguments as positional args and/or keyword args
   - **No category argument is passed.** `route_to_vendor()` resolves the category internally via `get_category_for_method(method)`, which looks up the method name in `TOOLS_CATEGORIES`.
3. `route_to_vendor()` reads `config["data_vendors"]["options_data"]` to determine the active vendor.
   - 3a. If the value is `"yfinance"`, the call is dispatched to the corresponding function in `y_finance.py`.
   - 3b. If the value is `"alpha_vantage"`, the call is dispatched to the Alpha Vantage adapter. In Phase 1, this adapter returns the stub string `"not implemented"` for all four methods.
   - 3c. If `route_to_vendor()` cannot resolve the method (method not registered in `VENDOR_METHODS`), it raises `ValueError`. If no vendor is available after the fallback chain is exhausted, it raises `RuntimeError`.
4. The `@tool` wrapper in `options_data_tools.py` catches `ValueError` and `RuntimeError` from `route_to_vendor()` and converts them to a graceful error string before returning to the agent. This is where REQ-NFR-06 is satisfied — at the tool-wrapper layer, not inside the router.
5. The implementation function (in `y_finance.py`) catches `HTTPError` and `ConnectionError` and returns an error string. The implementation does not re-raise these to the router.
6. The `@tool` wrapper returns the result to the calling agent without modification.

**Business Rules:**
- `options_data_tools.py` wrappers must never import functions from `y_finance.py` directly; all calls must pass through `route_to_vendor()` in `interface.py`.
- The category key registered in `TOOLS_CATEGORIES` in `interface.py` for all four tools is exactly `"options_data"` — no variation (e.g., not `"options"` or `"wheel_data"`). This follows the existing pattern of `"core_stock_apis"`, `"technical_indicators"`, etc.
- All four tools must be listed in `VENDOR_METHODS` with at least: a yfinance entry and an Alpha Vantage stub entry.
- The config key controlling vendor selection is `config["data_vendors"]["options_data"]`.
- Errors from `route_to_vendor()` (`ValueError`, `RuntimeError`) are caught by the tool wrapper and converted to error strings. Errors from the vendor implementation layer (`HTTPError`, `ConnectionError`) are caught inside the data function (in `y_finance.py`) and returned as error strings. Exceptions must not propagate to the calling agent.
- The call pattern is `route_to_vendor("get_options_chain", ticker, target_date)` — method name first, then positional or keyword args. No category argument.

**Input / Output:**

| Tool | Input | Output |
|---|---|---|
| `get_options_chain` | `ticker: str`, `target_date: str`, `expiry_date: str \| None` | Formatted string with chain table, or error string |
| `get_iv_metrics` | `ticker: str`, `curr_date: str`, `lookback_days: int = 252`, `iv_series: list[float] \| None = None` | Structured dict / parseable string with IV metrics, or error string |
| `get_options_greeks` | `ticker: str`, `curr_date: str`, `expiry_date: str`, `strike: float`, `option_type: str` | Structured dict / parseable string with Greek values, or error string |
| `get_next_earnings_date` | `ticker: str`, `curr_date: str` | Structured string with date, days-until, and `within_options_cycle` flag, or error string |

**Edge Cases and Error Scenarios:**

- **Method not registered in `VENDOR_METHODS`:** `route_to_vendor()` raises `ValueError`. The tool wrapper catches this and returns `"Options data tool error: method not registered: {method}"`.
- **No vendor available after fallback chain:** `route_to_vendor()` raises `RuntimeError`. The tool wrapper catches this and returns `"Options data tool error: no vendor available for {method}"`.
- **Alpha Vantage stub (Phase 1):** All four methods return `"not implemented"` for Alpha Vantage vendor. This is the expected and specified behaviour until a real adapter is provided.
- **Network failure in vendor layer:** The implementation (in `y_finance.py`) catches `HTTPError` and `ConnectionError` and returns a graceful error string. The routing layer does not handle network errors.

**Acceptance Tests:**

*Who:* Developer | *Test level:* Integration
*Given:* `config["data_vendors"]["options_data"] = "yfinance"` and an agent is instantiated
*When:* The agent calls any of the four options tools
*Then:* The call reaches the yfinance implementation layer and returns a result — the agent does not error on import or at call time.
(Covers REQ-DATA-05 AC1)

*Who:* Developer | *Test level:* Integration
*Given:* A new Alpha Vantage options adapter is added and `config["data_vendors"]["options_data"] = "alpha_vantage"`
*When:* Any of the four tools is called
*Then:* The call routes to the new adapter without modifying any agent code.
(Covers REQ-DATA-05 AC2)

*Who:* Agent | *Test level:* Unit
*Given:* `config["data_vendors"]["options_data"] = "alpha_vantage"` (Phase 1, stub)
*When:* `get_options_chain("NVDA", "2024-05-10")` is called
*Then:* Returns `"not implemented"` — no exception is raised, and the agent receives a string.
(Covers REQ-DATA-01 AC3)

**Open Questions:**
- None at this stage. The routing pattern follows the established convention in `interface.py` for existing categories.

---

## FSPEC-WHEEL-02: IV Rank and IV Percentile Computation

**Linked requirements:** REQ-DATA-02

**Purpose:** Define the exact step-by-step computation of realised-volatility-based IV Rank and IV Percentile, including the zero-variance guard, the `iv_environment` enum derivation, and the injectable test seam.

**Actors:**
- `get_iv_metrics` function in `y_finance.py`
- `Ticker.history()` (yfinance) as the OHLCV data source
- Unit test layer (via the injectable `iv_series` parameter)

**Behavioural Flow:**

1. `get_iv_metrics(ticker, curr_date, lookback_days=252, iv_series=None)` is called.
2. **Branch — test seam:**
   - 2a. If `iv_series` is not `None`: use the provided list directly as the historical realised volatility series (one float per trading day, annualised). Skip steps 3–5. Proceed to step 6.
   - 2b. If `iv_series` is `None` (production path): proceed to step 3.
3. Fetch OHLCV data: call `yf.Ticker(ticker).history(period="max")` or equivalent, requesting at minimum `lookback_days` trading days of close prices ending on or before `curr_date`.
   - 3a. If fewer than `lookback_days` trading days are available: use all available days. Include in the output report a note of the form `"Lookback shortened to {n} trading days (fewer than {lookback_days} available)"`.
   - 3b. If zero trading days are available: return error string `"Insufficient OHLCV data for {ticker}"` and halt.
4. Compute log returns: `log_return[i] = ln(close[i] / close[i-1])` for each consecutive pair of close prices.
5. Compute the 30-day rolling realised volatility series: for each window of 30 consecutive log returns, compute the sample standard deviation, then annualise by multiplying by `sqrt(252)`. This produces one realised vol value per trading day in the lookback window (after the first 30 days of warmup). The resulting series contains `(available_days - 30)` values. The value for the most recent day is `current_vol`.
6. From the realised volatility series assembled in step 2a or step 5, extract:
   - `current_vol` — the most recent (last) value in the series.
   - `max_vol_lookback` — the maximum value across the entire series.
   - `min_vol_lookback` — the minimum value across the entire series.
7. **Zero-variance guard — Branch:**
   - 7a. If `max_vol_lookback == min_vol_lookback` (all values are identical, no variance): set `iv_rank = 50`, `iv_percentile = 50`. Include in the output report the note `"IV range is flat — rank set to neutral 50"`. Proceed to step 9.
   - 7b. Otherwise: proceed to step 8.
8. Compute the two metrics:
   - `iv_rank = (current_vol − min_vol_lookback) / (max_vol_lookback − min_vol_lookback) × 100`
   - `iv_percentile = (count of days in series where realised_vol < current_vol) / (total days in series) × 100`
   - Both results are clamped to [0, 100] to guard against floating-point edge cases.
9. Derive `iv_environment` from `iv_rank`:
   - If `iv_rank >= 50`: `iv_environment = "elevated"`
   - If `25 <= iv_rank < 50`: `iv_environment = "normal"`
   - If `iv_rank < 25`: `iv_environment = "compressed"`
   - Boundary `iv_rank == 50` maps to `"elevated"`.
   - Boundary `iv_rank == 25` maps to `"normal"`.
10. Assemble and return the output object with fields: `current_vol`, `max_vol_lookback`, `min_vol_lookback`, `iv_rank`, `iv_percentile`, `iv_environment`, and a formatted report string. No field may be `NaN`; if a computed value would be NaN, return an error string instead.

**Business Rules:**
- The rolling window for realised vol computation is always exactly 30 trading days. This value is not configurable.
- Annualisation factor for realised vol is `sqrt(252)`. This value is not configurable.
- `iv_rank` and `iv_percentile` are expressed as values in [0, 100], not as decimals.
- The `iv_series` injectable parameter exists solely to support unit testing. When provided, it completely replaces step 3–5. The function must not call yfinance when `iv_series` is not `None`.
- The zero-variance guard (step 7a) fires only when `max_vol_lookback == min_vol_lookback` (exact floating-point equality is acceptable because a uniformly flat series would be fed from a test fixture, not live data).
- The output report string must include the flat-range note when the guard fires, and the shortened-lookback note when applicable.
- `iv_percentile` uses strict less-than: `(days where realised_vol < current_vol) / total_days × 100`. The boundary day (where `realised_vol == current_vol`) is not counted in the percentile. This matches REQ-DATA-02 formula exactly.

**Input / Output:**

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | The equity ticker symbol |
| `curr_date` | `str` | Reference date (YYYY-MM-DD); history is fetched up to this date |
| `lookback_days` | `int` | Number of trading days of history to request (default 252, configurable via `iv_rank_lookback_days`) |
| `iv_series` | `list[float] \| None` | Injectable test series; bypasses yfinance fetch when not `None` |

| Output Field | Type | Range | Notes |
|---|---|---|---|
| `current_vol` | `float` | > 0 | Annualised 30-day realised vol for most recent day |
| `max_vol_lookback` | `float` | >= `current_vol` | Max realised vol in the lookback window |
| `min_vol_lookback` | `float` | <= `current_vol` | Min realised vol in the lookback window |
| `iv_rank` | `float` | [0, 100] | Realised vol rank |
| `iv_percentile` | `float` | [0, 100] | Fraction of lookback days below current vol × 100 |
| `iv_environment` | `str` | `"elevated"` / `"normal"` / `"compressed"` | Derived from `iv_rank` thresholds |
| report string | `str` | — | Human-readable summary; includes warnings when applicable |

**Edge Cases and Error Scenarios:**

- **Fewer than 252 trading days available:** Computation proceeds on available data; report string notes `"Lookback shortened to {n} trading days"`. (Covers REQ-DATA-02 AC2)
- **Zero trading days available:** Return error string `"Insufficient OHLCV data for {ticker}"`. No partial result.
- **Zero-variance series (all realised vols identical):** `iv_rank = 50`, `iv_percentile = 50`, report includes flat-range note. (Covers REQ-DATA-02 AC5)
- **NaN in computed values:** Return error string rather than propagating NaN to the caller.
- **`iv_series` provided as empty list:** Return error string `"Provided iv_series is empty"`. No computation.

**Acceptance Tests:**

*Who:* Agent | *Test level:* Smoke (requires live yfinance network call)
*Given:* A valid ticker with 252+ trading days of OHLCV history
*When:* `get_iv_metrics(ticker, curr_date)` is called
*Then:* Returned dict contains `iv_rank` and `iv_percentile` in [0, 100] with no NaN values.
(Covers REQ-DATA-02 AC1)

*Who:* Agent | *Test level:* Unit (use `iv_series` seam with `iv_rank >= 50` result)
*Given:* `iv_rank >= 50` in the returned result
*When:* `iv_environment` field is read
*Then:* `iv_environment == "elevated"`.
(Covers REQ-DATA-02 AC3)

*Who:* Agent | *Test level:* Unit (use `iv_series` seam with `iv_rank < 25` result)
*Given:* `iv_rank < 25` in the returned result
*When:* `iv_environment` field is read
*Then:* `iv_environment == "compressed"`.
(Covers REQ-DATA-02 AC4)

*Who:* System | *Test level:* Unit
*Given:* `iv_series` is provided as a list where all values are equal (max == min)
*When:* `get_iv_metrics(ticker, curr_date, iv_series=[0.20] * 100)` is called
*Then:* `iv_rank == 50`, `iv_percentile == 50`, and the report string contains `"IV range is flat — rank set to neutral 50"`.
(Covers REQ-DATA-02 AC5)

*Who:* System | *Test level:* Unit
*Given:* `iv_series` is crafted so that `iv_rank == 25.0` exactly (e.g., `current_vol` is at the 25th percentile of the series range)
*When:* `get_iv_metrics(ticker, curr_date, iv_series=<crafted_series>)` is called
*Then:* `iv_environment == "normal"` (boundary: iv_rank exactly 25 maps to "normal", not "compressed").
(Covers boundary for FSPEC step 9, `25 <= iv_rank < 50`)

*Who:* System | *Test level:* Unit
*Given:* `iv_series` is crafted so that `iv_rank == 50.0` exactly
*When:* `get_iv_metrics(ticker, curr_date, iv_series=<crafted_series>)` is called
*Then:* `iv_environment == "elevated"` (boundary: iv_rank exactly 50 maps to "elevated", not "normal").
(Covers boundary for FSPEC step 9, `iv_rank >= 50`)

**Open Questions:**
- None. `iv_percentile` uses strict less-than per REQ-DATA-02 formula. Boundary day (where `realised_vol == current_vol`) is not counted in the percentile.

---

## FSPEC-WHEEL-03: WheelAnalyst Suitability Decision Flow

**Linked requirements:** REQ-SCREEN-01, REQ-SCREEN-02

**Purpose:** Define the five-criterion suitability evaluation flow that `WheelAnalyst` executes to produce an approved or rejected `WheelCandidateReport`, including criterion ordering, simultaneous-failure behaviour, and how the Delta-anchored `recommended_strike_range` is derived.

**Actors:**
- `WheelAnalyst` agent (`wheel_analyst.py`)
- Phase 1 data tools: `get_iv_metrics`, `get_options_chain`, `get_next_earnings_date`, `get_options_greeks`
- Existing analyst reports (as input context)
- `WheelCandidateReport` Pydantic schema (`schemas.py`)
- `AgentState.investment_plan` field (source for Criterion 5 consensus)

**Behavioural Flow:**

1. `WheelAnalyst` receives as input: the ticker, `curr_date`, the four existing analyst reports (Market, Social, News, Fundamentals), the `investment_plan` field from `AgentState`, and the wheel configuration.
2. **Criterion 1 — IV environment:** Call `get_iv_metrics(ticker, curr_date, lookback_days=iv_rank_lookback_days)`. Read `iv_rank` from the result.
   - 2a. If `iv_rank >= min_iv_rank` (config, default 25): criterion 1 passes. Record `iv_rank`, `iv_percentile`, `iv_environment`.
   - 2b. If `iv_rank < min_iv_rank`: criterion 1 fails. Record the failure reason `"IV Rank {iv_rank:.1f} below minimum {min_iv_rank}"`. Continue to criterion 2.
3. **Criterion 2 — Chain liquidity:** Call `get_options_chain(ticker, curr_date)`. Identify near-the-money strikes (within 10% of current spot price). For each near-the-money strike:
   - Check: `open_interest >= min_chain_oi` (config, default 100).
   - Check: `(ask - bid) / ((ask + bid) / 2) <= max_chain_spread_pct / 100` (config, default 0.10).
   - 3a. If at least one near-the-money strike satisfies both conditions: criterion 2 passes.
   - 3b. If no near-the-money strike has `open_interest >= min_chain_oi`: criterion 2 fails with reason `"Insufficient liquidity"`.
   - 3c. If no near-the-money strike has spread within the limit (but OI is sufficient): criterion 2 fails with reason `"Chain spread too wide"`.
   - 3d. If both OI and spread conditions are violated simultaneously for all strikes: criterion 2 fails with reason `"Insufficient liquidity"` (OI failure takes precedence in the rejection reason).
   - Continue to criterion 3 regardless of outcome.
4. **Criterion 3 — Earnings clearance:** Call `get_next_earnings_date(ticker, curr_date)`. Determine the target expiration (the midpoint DTE from `recommended_dte_range`, i.e. `(recommended_dte_low + recommended_dte_high) / 2` calendar days from `curr_date`, rounded up to the nearest integer).
   - 4a. If `next_earnings_date > target_expiration_date + timedelta(days=earnings_buffer_days)` (config, default 14): earnings clearance is confirmed; `earnings_clearance_ok = True`.
   - 4b. If `next_earnings_date <= target_expiration_date + timedelta(days=earnings_buffer_days)`: criterion 3 fails. `earnings_clearance_ok = False`. Record failure reason.
   - Continue to criterion 4.
5. **Criterion 4 — Price affordability:** Read the current spot price from the options chain or yfinance.
   - 5a. If `spot_price <= max_wheel_stock_price` (config, default 500): criterion 4 passes.
   - 5b. If `spot_price > max_wheel_stock_price`: criterion 4 fails with reason `"Stock price exceeds cash management limit"`. Continue to criterion 5.
6. **Criterion 5 — Analyst consensus:** Read the `investment_plan` field from `AgentState`. Parse the `recommendation` field from the serialised `ResearchPlan` contained in `investment_plan`.
   - The `recommendation` field takes one of the values: `Buy`, `Overweight`, `Hold`, `Underweight`, `Sell`.
   - 6a. If `recommendation` is `Buy`, `Overweight`, or `Hold`: criterion 5 passes. `analyst_bias = "bullish"` for `Buy`/`Overweight`; `analyst_bias = "neutral"` for `Hold`.
   - 6b. If `recommendation` is `Sell` or `Underweight`: criterion 5 fails with reason matching the analyst signal. `analyst_bias = "bearish"`.
   - 6c. If `investment_plan` is empty or the `recommendation` field cannot be parsed: criterion 5 defaults to **pass** (conservative: do not block the wheel on missing prior data). `analyst_bias = "neutral"`.
7. **Approval decision:** After all five criteria are evaluated:
   - 7a. If all five criteria passed: `approved = True`. `rejection_reason = None`.
   - 7b. If one or more criteria failed: `approved = False`. `rejection_reason` is populated by concatenating the failure reasons for all failed criteria, separated by `"; "`.
   - The evaluation always runs all five criteria regardless of how many fail. No short-circuiting.
8. **Recommended strike range derivation (runs only when `approved = True`):** Call `get_options_greeks` for put options at the strikes nearest to the bounds of the target Delta range (`target_csp_delta_low` and `target_csp_delta_high`).
   - 8a. Identify the put strike whose absolute Delta is closest to `target_csp_delta_low` (e.g., 0.20). This is `low_strike`.
   - 8b. Identify the put strike whose absolute Delta is closest to `target_csp_delta_high` (e.g., 0.30). This is `high_strike`.
   - 8c. Set `recommended_strike_range = [low_strike, high_strike]`.
   - 8d. If Greeks cannot be computed for either bound (e.g., no suitable strike exists): set `recommended_strike_range = [spot_price * (1 - target_csp_delta_high), spot_price * (1 - target_csp_delta_low)]` (price-based fallback, rounded to the nearest $0.50 increment).
9. Set `recommended_dte_range = [recommended_dte_low, recommended_dte_high]` from config (default `[28, 45]`).
10. Assemble and return `WheelCandidateReport` with all required schema fields.

**Business Rules:**
- All five criteria are always evaluated. There is no early-exit on first failure.
- When multiple criteria fail simultaneously, `rejection_reason` contains all failure reasons joined by `"; "` in criterion order (1 through 5).
- `recommended_strike_range` is computed only when `approved = True`. When `approved = False`, `recommended_strike_range` may be set to `[0.0, 0.0]` as a null sentinel — it must not be `None` (schema requires `list[float]` with exactly 2 elements).
- `recommended_dte_range` is always populated from config, regardless of approval status.
- The `analyst_bias` field takes string values `"bullish"`, `"neutral"`, or `"bearish"`. These exact strings are required; no other values.
- The OI failure reason string must contain the substring `"Insufficient liquidity"` (exact, case-sensitive) to satisfy REQ-SCREEN-01 AC6.
- The spread failure reason string must contain the substring `"Chain spread too wide"` (exact, case-sensitive) to satisfy REQ-SCREEN-01 AC7.
- The affordability failure reason string must contain the substring `"Stock price exceeds cash management limit"` (exact, case-sensitive) to satisfy REQ-SCREEN-01 AC8.
- **Criterion 5 consensus extraction:** `analyst_bias` is derived from `AgentState.investment_plan`. The `investment_plan` field contains a serialised `ResearchPlan` with a `recommendation` field (one of: `Buy`, `Overweight`, `Hold`, `Underweight`, `Sell`). Criterion 5 passes when `recommendation` is `Buy`, `Overweight`, or `Hold`; fails when `Sell` or `Underweight`. If `investment_plan` is empty or the recommendation cannot be parsed, Criterion 5 defaults to pass (conservative: do not block the wheel on missing prior data).
- When `selected_analysts` in the graph config does not include `"wheel"`, the `WheelAnalyst` node must not be present in the graph. The existing pipeline must run unmodified.

**Input / Output:**

Input:
- `ticker: str`
- `curr_date: str` (YYYY-MM-DD)
- Existing analyst reports (all four)
- `AgentState.investment_plan` (for Criterion 5)
- Wheel configuration (from `config["wheel"]`)

Output: `WheelCandidateReport` with the following fields:

| Field | Type | Populated when |
|---|---|---|
| `approved` | `bool` | Always |
| `rejection_reason` | `str \| None` | Non-None when `approved=False` |
| `iv_rank` | `float` | Always |
| `iv_percentile` | `float` | Always |
| `iv_environment` | `str` | Always |
| `iv_assessment` | `str` | Always |
| `next_earnings_date` | `str \| None` | When earnings date is available |
| `earnings_clearance_ok` | `bool` | Always |
| `liquidity_ok` | `bool` | Always |
| `analyst_bias` | `str` | Always (`"bullish"` / `"neutral"` / `"bearish"`) |
| `recommended_strike_range` | `list[float]` (2 elements) | Always (sentinel `[0.0, 0.0]` when `approved=False`) |
| `recommended_dte_range` | `list[int]` (2 elements) | Always |
| `rationale` | `str` | Always (non-empty string) |

**Edge Cases and Error Scenarios:**

- **`get_iv_metrics` returns an error string:** Criterion 1 fails with reason `"IV data unavailable: {error}"`. Evaluation continues.
- **`get_options_chain` returns `"No options chain available"` or an error string:** Criterion 2 fails with reason `"Options chain unavailable"`. Evaluation continues.
- **`get_next_earnings_date` returns `"No upcoming earnings date available"` for the ticker:** Criterion 3 passes by default (no earnings event means clearance is confirmed). `next_earnings_date = None`, `earnings_clearance_ok = True`.
- **All criteria fail simultaneously:** `approved = False`, `rejection_reason` contains all five failure reasons joined by `"; "`.
- **Delta-anchored strike computation fails (step 8d fallback):** `recommended_strike_range` is derived from spot price × delta bounds, rounded to nearest $0.50.
- **`WheelAnalyst` node absent from graph:** When `"wheel"` is not in `selected_analysts`, no node is registered. Graph topology is unchanged from existing equity flow.
- **`investment_plan` is empty or unparseable (Criterion 5):** Criterion 5 defaults to pass; `analyst_bias = "neutral"`.

**Acceptance Tests:**

*Who:* Agent | *Test level:* Integration (mocked LLM, mocked data tools)
*Given:* All five criteria are met
*When:* WheelAnalyst runs
*Then:* `WheelCandidateReport.approved == True` and `recommended_strike_range` is a list of two positive floats, both greater than 0.0.
(Covers REQ-SCREEN-01 AC1, REQ-SCREEN-02 AC2)

*Who:* Agent | *Test level:* Integration (mocked LLM, mocked data tools)
*Given:* `iv_rank = 15` (below `min_iv_rank = 25`)
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` is a non-empty string.
(Covers REQ-SCREEN-01 AC2)

*Who:* Agent | *Test level:* Integration (mocked LLM, mocked data tools)
*Given:* Earnings is 12 days away and target expiry is 30 DTE (earnings within `earnings_buffer_days=14` of expiration)
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` is non-empty.
(Covers REQ-SCREEN-01 AC3)

*Who:* Agent | *Test level:* Integration (mocked LLM, mocked data tools with `investment_plan` containing recommendation=Sell)
*Given:* `investment_plan` contains recommendation=Sell
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` is non-empty.
(Covers REQ-SCREEN-01 AC4)

*Who:* Developer | *Test level:* Unit
*Given:* `selected_analysts` config does not include `"wheel"`
*When:* Graph is built
*Then:* `WheelAnalyst` node is absent; existing pipeline runs as before.
(Covers REQ-SCREEN-01 AC5)

*Who:* System | *Test level:* Unit
*Given:* All near-the-money strikes have `OI < 100`
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` contains `"Insufficient liquidity"`.
(Covers REQ-SCREEN-01 AC6)

*Who:* System | *Test level:* Unit
*Given:* `approved == True`
*When:* Schema is serialised
*Then:* `rejection_reason is None`.
(Covers REQ-SCREEN-02 AC2)

*Who:* System | *Test level:* Unit
*Given:* `approved == False`
*When:* Schema is serialised
*Then:* `rejection_reason` is a non-empty string.
(Covers REQ-SCREEN-02 AC3)

*Who:* System | *Test level:* Unit
*Given:* `investment_plan` contains `recommendation=Underweight`
*When:* WheelAnalyst evaluates Criterion 5
*Then:* `analyst_bias == "bearish"`, Criterion 5 fails, `approved == False`.
(Covers FSPEC-WHEEL-03 Criterion 5 test seam — FSPEC-TE-01 resolution)

*Who:* System | *Test level:* Unit
*Given:* Any terminal output from WheelAnalyst
*When:* `rationale` field is read
*Then:* It is a non-empty string.
(Schema contract — rationale is always populated)

**Open Questions:**
- **Criterion 2 boundary — what counts as "near-the-money"?** The REQ specifies "near-the-money strikes" without giving a numeric range. This FSPEC uses ±10% of spot price as the definition. SE author must confirm or adjust this threshold.
- **Criterion 3 target expiration calculation:** This FSPEC uses the midpoint DTE rounded up. SE author may prefer the lower bound (`recommended_dte_low`) as a more conservative anchor. Clarification needed.

---

## FSPEC-WHEEL-04: CSP Strike Selection Logic

**Linked requirements:** REQ-TRADE-01, REQ-TRADE-02

**Purpose:** Define the multi-step `CspAgent` flow from chain fetch through deterministic pre-filtering to LLM selection, including progressive relaxation when no strike meets all filters and the exact boundary between deterministic rules and LLM judgment.

**Actors:**
- `CspAgent` (`csp_agent.py`)
- `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (Phase 1 data tools)
- `WheelCandidateReport` (from Phase 2, or config defaults if Phase 2 is skipped)
- LLM (receives only the pre-filtered strike candidates, called via `bind_structured`)
- `CspDecision` schema (`schemas.py`)

**Behavioural Flow:**

**Stage 1 — Data fetch:**
1. Receive input: ticker, `curr_date`, analyst reports, `WheelCandidateReport` (or wheel config defaults), wheel configuration.
2. Determine DTE bounds: use `WheelCandidateReport.recommended_dte_range` if available; otherwise use `[config["wheel"]["recommended_dte_low"], config["wheel"]["recommended_dte_high"]]` (default `[28, 45]` calendar days).
3. Call `get_options_chain(ticker, curr_date)` to retrieve all available put options. The chain is fetched using the configured `options_lookforward_days` window. Filters for the target DTE window are applied in Stage 2.
4. Call `get_next_earnings_date(ticker, curr_date)` to retrieve the next earnings date.

**Stage 2 — Deterministic pre-filter (no LLM involvement):**
5. For each put strike in the chain, call `get_options_greeks(ticker, curr_date, expiry_date, strike, "put")` to obtain Delta.
6. **Filter A — Delta range:** Reject any put strike whose absolute Delta is outside `[target_csp_delta_low, target_csp_delta_high]` (config, default `[0.20, 0.30]`). Boundary values are inclusive (a strike with `abs(delta) == 0.20` is retained; a strike with `abs(delta) == 0.30` is retained).
7. **Filter B — Earnings clearance:** Reject any expiration date where the next earnings date falls on or before that expiration date (i.e., `earnings_date <= expiration_date`). This enforces a hard earnings exclusion per REQ-DATA-04.
8. **Filter C — Minimum annualised yield:** Compute `annualised_yield_pct = (mid_premium / strike) × (365 / dte) × 100` for each remaining candidate. Reject any strike where `annualised_yield_pct < min_annualised_yield_pct` (config, default 12.0%).

Filters are applied in order A → B → C. A strike must pass all three to be presented to the LLM.

**Stage 3 — Progressive relaxation (when no strike passes all filters):**
9. If the filtered candidate list is empty after Stage 2:
   - 9a. **Relaxation attempt 1 — drop Filter C:** Re-run with only Filters A and B. If candidates exist, note `"yield_filter_relaxed"` in the output and present these to the LLM.
   - 9b. **Relaxation attempt 2 — drop Filter B also:** Re-run with only Filter A. If candidates exist, note `"earnings_filter_relaxed"` in the output and present these to the LLM.
   - 9c. **Relaxation attempt 3 — nearest Delta match:** If Filter A itself eliminates all strikes, select the single strike with the absolute Delta closest to the midpoint of `[target_csp_delta_low, target_csp_delta_high]`. Populate `CspDecision` with `tradeable = True` and the note `"No strike matches Delta target; nearest available: {delta}"`. Present only this strike to the LLM.
   - 9d. **Earnings hard block:** If after relaxation attempts 1–3 the only remaining candidates all straddle an earnings date (i.e., relaxation attempt 2 yields no candidates because all strikes fail Filter B), return `CspDecision` with `tradeable = False` and `rejection_reason = "All suitable expirations overlap earnings"`. The LLM is not called.

**Stage 4 — LLM selection:**
10. Present the filtered (or relaxed) candidate strikes to the LLM along with: the analyst reports, the `WheelCandidateReport` rationale, and any relaxation notes from Stage 3.
11. The LLM call producing `CspDecision` **MUST** be made via `bind_structured(llm, CspDecision)` from `agents/utils/structured.py`. The FSPEC does not prescribe the provider-specific mechanism — that is handled by `structured.py` transparently. If the structured call fails and the free-text fallback also fails to produce a parseable `CspDecision` instance (via JSON extraction), return `CspDecision` with `tradeable = False` and `rejection_reason = "Schema validation failed after fallback"`. No additional retry is performed at the agent level beyond `structured.py`'s internal fallback.
12. The LLM may not select a strike that was not in the presented list.

**Stage 5 — Output assembly:**
13. Compute derived fields deterministically (not by LLM): `annualised_yield_pct`, `max_loss`, `breakeven_price`, `probability_of_profit`.
14. Set `earnings_clear = True` if the selected expiration does not straddle an earnings date; `False` otherwise.
15. Return the completed `CspDecision`.

**Business Rules:**
- Filter A, B, and C are deterministic and applied before the LLM sees any candidates. The LLM cannot override a filter decision.
- Delta range boundaries are inclusive on both ends: `target_csp_delta_low <= abs(delta) <= target_csp_delta_high`.
- DTE and annualisation always use calendar days with 365-day year. Trading-day adjustments are not applied.
- `mid_premium = (bid + ask) / 2`. This formula is used for all yield computations.
- `annualised_yield_pct = (mid_premium / strike) × (365 / dte) × 100`. Exactly this formula, no variation.
- `max_loss = (strike × 100) − (mid_premium × 100)` (per contract, 100 shares).
- `breakeven_price = strike − mid_premium`.
- `probability_of_profit = 1 − abs(delta)` (approximation; exactly this formula).
- `delta` in `CspDecision` is the put delta as a negative value (e.g., `-0.25`), not the absolute value.
- `theta` in `CspDecision` is daily theta (≤ 0).
- Progressive relaxation drops filters in order C → B → A-fallback. Relaxation never widens the Delta range.
- The earnings hard block in step 9d takes precedence over all other relaxation outcomes. If the only candidates straddle earnings, the result is always `tradeable = False`.
- Before calling `get_options_chain`, the agent must verify that `options_lookforward_days >= recommended_dte_high`. If `options_lookforward_days` is set below `recommended_dte_high`, the system logs a warning and uses `max(options_lookforward_days, recommended_dte_high + 7)` as the effective lookforward window.
- The LLM call must use `bind_structured(llm, CspDecision)` from `agents/utils/structured.py`. The agent does not implement its own retry logic beyond what `structured.py` provides.

**Input / Output:**

Input:
- `ticker: str`
- `curr_date: str` (YYYY-MM-DD)
- Analyst reports
- `WheelCandidateReport` or config defaults
- Wheel configuration

Output: `CspDecision` with fields as specified in REQ-TRADE-02.

| Key computed field | Formula |
|---|---|
| `mid_premium` | `(bid + ask) / 2` |
| `annualised_yield_pct` | `(mid_premium / strike) × (365 / dte) × 100` |
| `max_loss` | `(strike × 100) − (mid_premium × 100)` |
| `breakeven_price` | `strike − mid_premium` |
| `probability_of_profit` | `1 − abs(delta)` |

**Edge Cases and Error Scenarios:**

- **No strikes in chain within DTE window:** Return `tradeable = False`, `rejection_reason = "No options expiring within DTE window [{dte_low}, {dte_high}]"`. LLM is not called.
- **All strikes filtered by Delta (Filter A):** Relaxation step 9c activates — nearest-Delta strike is presented to LLM with the nearest-available note.
- **All suitable expirations overlap earnings:** Return `tradeable = False`, `rejection_reason = "All suitable expirations overlap earnings"`. LLM is not called. (Covers REQ-TRADE-01 AC3)
- **`get_options_greeks` returns an error for a candidate strike:** That strike is silently excluded from the candidate list. If all strikes error, treat as no candidates found.
- **`structured.py` fallback fails:** Return `tradeable = False`, `rejection_reason = "Schema validation failed after fallback"`.
- **Phase 2 skipped (no `WheelCandidateReport`):** Use config defaults for DTE range and Delta range. This is the specified fallback path and is a valid production scenario.
- **`options_lookforward_days` below `recommended_dte_high`:** Log warning and use `max(options_lookforward_days, recommended_dte_high + 7)` as effective lookforward.

**Acceptance Tests:**

*Who:* Agent | *Test level:* Integration (`@pytest.mark.integration`, canned fixture chain from `tests/fixtures/options_fixtures.py`, mocked LLM returning the first eligible candidate from the fixture)
*Given:* A valid approved candidate with chain data
*When:* CspAgent runs
*Then:* Returns a `CspDecision` with `tradeable = True`, `strike` populated, and `annualised_yield_pct >= min_annualised_yield_pct`.
(Covers REQ-TRADE-01 AC1; strike assertion is valid because LLM is mocked to return the fixture's first eligible strike)

*Who:* Agent | *Test level:* Integration (`@pytest.mark.integration`, fixture chain where all strikes fail Filter A, mocked LLM)
*Given:* No strike in the chain meets the Delta target (Filter A eliminates all)
*When:* CspAgent runs
*Then:* Returns `CspDecision` with `tradeable = True` and `rationale` contains `"No strike matches Delta target; nearest available: {delta}"`.
(Covers REQ-TRADE-01 AC2)

*Who:* Agent | *Test level:* Unit (deterministic; LLM not called)
*Given:* All acceptable expirations straddle an earnings date
*When:* CspAgent runs
*Then:* Returns `tradeable = False`, `rejection_reason = "All suitable expirations overlap earnings"`.
(Covers REQ-TRADE-01 AC3)

*Who:* System | *Test level:* Unit (mocked chain and Greeks, LLM mocked)
*Given:* Target Delta range is `[0.15, 0.25]` in config
*When:* The deterministic strike candidate filter function runs
*Then:* Filter rejects any strike whose `abs(put_delta)` is outside [0.15, 0.25] before presenting options to the LLM.
(Covers REQ-TRADE-01 AC4a)

*Who:* System | *Test level:* Unit
*Given:* `CspDecision` is produced with `tradeable = True`
*When:* `annualised_yield_pct` is validated
*Then:* Value matches `(mid_premium / strike) × (365 / dte) × 100` within 0.01%.
(Covers REQ-TRADE-02 AC3)

*Who:* System | *Test level:* Unit (mocked chain where delta boundary strike exactly matches `target_csp_delta_low`)
*Given:* A strike with `abs(delta) == target_csp_delta_low` (exact lower boundary)
*When:* Filter A runs
*Then:* The strike is INCLUDED in the filtered set (boundary is inclusive).
(Covers FSPEC step 6 inclusivity — FSPEC-TE-05 resolution)

*Who:* System | *Test level:* Unit (mocked chain where `current_value_pct_of_premium == 50.0`)
*Given:* `current_value_pct_of_premium == 50.0` (exact boundary)
*When:* Rule 1 (profit_capture) is evaluated in `RollCheckAgent` for the selected CSP
*Then:* Rule 1 fires (`trigger_reason = "profit_capture"`) — boundary is inclusive at `<= 50`.
(Boundary for take_profit_pct — referenced in FSPEC-WHEEL-06)

*Who:* System | *Test level:* Unit (mocked chain where all strikes pass A+B but fail C)
*Given:* No strike meets the yield filter but at least one strike meets delta and earnings filters
*When:* CspAgent Stage 3 relaxation runs
*Then:* System selects from yield-relaxed candidates (`tradeable = True`) and `CspDecision.rationale` notes the relaxed constraint (contains `"yield_filter_relaxed"`).
(Covers relaxation 9a — FSPEC-TE-08 resolution)

*Who:* System | *Test level:* Unit (mocked chain where all strikes pass A but fail B and C)
*Given:* No strike clears earnings AND delta filter but at least one strike meets only the delta filter (earnings clearance relaxed)
*When:* CspAgent Stage 3 relaxation runs
*Then:* System selects from earnings-relaxed candidates (`tradeable = True`) and `CspDecision.rationale` notes `"earnings_filter_relaxed"`.
(Covers relaxation 9b — FSPEC-TE-08 resolution; note: earnings filter IS relaxable at step 9b per FSPEC flow)

*Who:* System | *Test level:* Unit
*Given:* Any terminal output from CspAgent
*When:* `rationale` field is read
*Then:* It is a non-empty string.
(Schema contract — rationale always populated)

**Open Questions:**
- **`options_lookforward_days` config key:** This key should be added to REQ Section 7 (carry forward to TSPEC author). Currently defined in REQ-DATA-01 description but not in the Section 7 config table.
- **LLM retry:** `structured.py`'s internal fallback is the single retry. The agent does not add an outer retry. SE author must confirm this is acceptable.

---

## FSPEC-WHEEL-05: Covered Call Strike Selection Logic

**Linked requirements:** REQ-TRADE-03, REQ-TRADE-04

**Purpose:** Define the `CcAgent` flow for selecting a covered call strike after put assignment, including the cost-basis-anchored strike constraint and the "stock below cost basis" branch.

**Actors:**
- `CcAgent` (`cc_agent.py`)
- `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (Phase 1 data tools)
- `WheelPosition` (from position tracker — provides cost basis and assignment details)
- LLM (receives only pre-filtered call candidates, called via `bind_structured`)
- `CcDecision` schema (`schemas.py`)

**Behavioural Flow:**

**Stage 1 — Data fetch:**
1. Receive input: ticker, `curr_date`, analyst reports, `WheelPosition` (with `csp_strike`, `csp_premium_received`, `cost_basis_per_share`), wheel configuration.
2. Compute `cost_basis = cost_basis_per_share` from `WheelPosition` (which equals `csp_strike − csp_premium_received`).
3. Fetch current spot price from yfinance.
4. **Branch — stock below cost basis:**
   - 4a. If `spot_price < cost_basis`: proceed to Stage 2 normally. Filter A (strike ≥ cost_basis) is still applied. If at least one call strike at or above cost_basis exists in the chain (even though spot is below), the LLM is called with a warning note injected into the prompt noting the below-cost-basis situation. If NO strike ≥ cost_basis exists in the entire chain, return `CcDecision` with `tradeable = False` and `rejection_reason` noting below-cost-basis risk. The LLM is not called in this case.
   - 4b. If `spot_price >= cost_basis`: continue to Stage 2 normally with no warning note.
5. Call `get_options_chain(ticker, curr_date)` to retrieve all available call options.
6. Determine DTE bounds: same logic as FSPEC-WHEEL-04 step 2, using CC-specific config if present or the same shared defaults.
7. Call `get_next_earnings_date(ticker, curr_date)`.

**Stage 2 — Deterministic pre-filter:**
8. For each call strike in the chain, call `get_options_greeks(ticker, curr_date, expiry_date, strike, "call")` to obtain Delta.
9. **Filter A — Strike above cost basis:** Reject any call strike where `strike < cost_basis`. Boundary: `strike == cost_basis` is retained (called away at exact cost basis is profitable given premium received).
10. **Filter B — Delta range:** Reject any call strike whose Delta is outside `[target_cc_delta_low, target_cc_delta_high]` (config, default `[0.20, 0.35]`). Boundary values are inclusive.
11. **Filter C — Earnings clearance:** Same logic as FSPEC-WHEEL-04 Filter B — reject expirations where `earnings_date <= expiration_date`.
12. **Filter D — Minimum annualised yield on cost basis:** Compute `annualised_yield_on_cost_pct = (mid_premium / cost_basis) × (365 / dte) × 100`. Reject any strike where this value is below `min_annualised_yield_pct` (config, default 12.0%).

Filters are applied in order A → B → C → D.

**Stage 3 — Progressive relaxation (when no strike passes all filters):**
13. If the candidate list is empty after Stage 2:
    - 13a. **Relaxation attempt 1 — drop Filter D:** Re-run with Filters A, B, C only.
    - 13b. **Relaxation attempt 2 — drop Filter C:** Re-run with Filters A and B only.
    - 13c. **No call strikes above cost basis meet Delta:** If Filters A and B together yield no candidates, return `tradeable = False`, `rejection_reason` non-empty. (Covers REQ-TRADE-03 AC3) LLM is not called.
    - 13d. **Earnings hard block:** Same as FSPEC-WHEEL-04 step 9d — if all remaining candidates straddle earnings, return `tradeable = False`.

**Stage 4 — LLM selection:**
14. Present the filtered (or relaxed) candidates to the LLM with analyst reports, `WheelPosition` context, and any relaxation or warning notes.
15. The LLM call producing `CcDecision` **MUST** be made via `bind_structured(llm, CcDecision)` from `agents/utils/structured.py`. The FSPEC does not prescribe the provider-specific mechanism — that is handled by `structured.py` transparently. If the structured call fails and the free-text fallback also fails to produce a parseable `CcDecision` instance (via JSON extraction), return `CcDecision` with `tradeable = False` and `rejection_reason = "Schema validation failed after fallback"`. No additional retry is performed at the agent level.

**Stage 5 — Output assembly:**
16. Compute derived fields deterministically: `annualised_yield_on_cost_pct`, `upside_to_strike_pct`, `strike_above_cost_basis`.
17. Set `earnings_clear` based on the selected expiration.
18. Populate `assigned_at = WheelPosition.csp_strike`, `cost_basis = WheelPosition.cost_basis_per_share`.
19. Return the completed `CcDecision`.

**Business Rules:**
- Filter A (strike ≥ cost basis) is always applied and cannot be relaxed. The strike must be at or above cost basis to be presented to the LLM.
- When `spot_price < cost_basis`:
  - If at least one call strike ≥ cost_basis exists in the chain: proceed normally through Filters A–D (and relaxation). The LLM is still called, with a warning note injected into the prompt noting the below-cost-basis spot price. `tradeable` may be `True` if the LLM selects a valid strike.
  - If NO call strike ≥ cost_basis exists in the entire chain: return `tradeable = False`, `rejection_reason` non-empty noting below-cost-basis risk. The LLM is not called.
- `strike_above_cost_basis` is a computed boolean: `strike >= cost_basis`. It is not set by the LLM.
- `delta` in `CcDecision` is the call delta as a positive value (e.g., `0.25`).
- `annualised_yield_on_cost_pct = (mid_premium / cost_basis) × (365 / dte) × 100`. The denominator is `cost_basis`, not `strike` (this differs from CSP yield computation).
- `upside_to_strike_pct = (strike − spot_price) / spot_price × 100`.
- DTE and annualisation always use calendar days with 365-day year.
- Relaxation drops filters in order D → C → fallback (no relaxation of Filters A or B).
- `assigned_at` is the CSP strike from the prior `WheelPosition`. `cost_basis` is `assigned_at − csp_premium_received`. These are sourced from the `WheelPosition` record, not computed by the LLM.
- The LLM call must use `bind_structured(llm, CcDecision)` from `agents/utils/structured.py`.

**Input / Output:**

Input:
- `ticker: str`
- `curr_date: str`
- Analyst reports
- `WheelPosition` (with `csp_strike`, `csp_premium_received`, `cost_basis_per_share`)
- Wheel configuration

Output: `CcDecision` with fields as specified in REQ-TRADE-04.

| Key computed field | Formula |
|---|---|
| `annualised_yield_on_cost_pct` | `(mid_premium / cost_basis) × (365 / dte) × 100` |
| `upside_to_strike_pct` | `(strike − spot_price) / spot_price × 100` |
| `strike_above_cost_basis` | `strike >= cost_basis` |

**Edge Cases and Error Scenarios:**

- **`spot_price < cost_basis` with no call strike ≥ cost_basis in chain:** `tradeable = False`, `rejection_reason` non-empty noting below-cost-basis risk. `strike_above_cost_basis = False`. (Covers REQ-TRADE-03 AC2)
- **`spot_price < cost_basis` with at least one call strike ≥ cost_basis in chain:** Flow continues normally; LLM called with warning note. `tradeable` may be `True`.
- **No call strikes above cost basis meet Delta target:** `tradeable = False`, `rejection_reason` non-empty. (Covers REQ-TRADE-03 AC3)
- **`cost_basis` is zero or negative (data integrity error):** Return `tradeable = False`, `rejection_reason = "Invalid cost basis: {cost_basis}"`.
- **`WheelPosition` is missing or incomplete:** Return `tradeable = False`, `rejection_reason = "Missing position data"`. CcAgent requires a valid `WheelPosition`.
- **`get_options_greeks` errors on a candidate:** That candidate is silently excluded.

**Acceptance Tests:**

*Who:* Agent | *Test level:* Integration (`@pytest.mark.integration`, canned fixture chain, mocked LLM returning the first eligible strike from the fixture)
*Given:* Cost basis is $140, current price is $145
*When:* CcAgent runs
*Then:* Selected `CcDecision.strike >= 140.0`.
(Covers REQ-TRADE-03 AC1; strike assertion valid because LLM is mocked to return fixture's first eligible strike)

*Who:* Agent | *Test level:* Unit (no call strike ≥ cost_basis in fixture chain)
*Given:* Current spot price is below cost basis AND no call strike ≥ cost_basis exists in the chain
*When:* CcAgent runs
*Then:* `CcDecision.tradeable == False` and `rejection_reason` is non-empty noting below-cost-basis risk.
(Covers REQ-TRADE-03 AC2 — the full no-eligible-strike path)

*Who:* Agent | *Test level:* Unit
*Given:* No call strikes above cost basis meet the Delta target (Filters A+B together yield no candidates)
*When:* CcAgent runs
*Then:* `CcDecision.tradeable == False` and `rejection_reason` is non-empty.
(Covers REQ-TRADE-03 AC3)

*Who:* System | *Test level:* Unit
*Given:* `CcDecision` is produced with `tradeable = True`
*When:* `strike_above_cost_basis` is validated
*Then:* `strike_above_cost_basis == (CcDecision.strike >= CcDecision.cost_basis)`.
(Covers REQ-TRADE-04 AC1)

*Who:* System | *Test level:* Unit
*Given:* Any terminal output from CcAgent
*When:* `rationale` field is read
*Then:* It is a non-empty string.
(Schema contract — rationale always populated)

**Open Questions:**
- **CC DTE defaults:** The REQ description mentions "21–45 DTE" for CC (vs "28–45 DTE" for CSP) but the config table only shows one shared `recommended_dte_low = 28`. SE author should confirm whether CC uses the same DTE bounds as CSP or a distinct set.

---

## FSPEC-WHEEL-06: Roll/Hold/Close Decision Logic

**Linked requirements:** REQ-LIFE-03, REQ-LIFE-04

**Purpose:** Define the `RollCheckAgent` rule-evaluation flow — the priority order of the five rules, simultaneous-firing behaviour, the ROLL vs CLOSE criterion on breach, and how `trigger_reason` is assigned.

**Actors:**
- `RollCheckAgent` (`roll_agent.py`)
- `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (Phase 1 data tools)
- Existing analyst reports (current run)
- `WheelPosition` (from position tracker — includes `prior_analyst_bias: Optional[str]`)
- `RollDecision` schema (`schemas.py`)

**Behavioural Flow:**

1. `RollCheckAgent` receives: `WheelPosition`, `curr_date`, current analyst reports, and the current options chain for the open position.
2. Determine the open contract's current market value: call `get_options_greeks` or read from the current chain to obtain `current_contract_value` (use `mid_premium` of the current position on the chain).
3. Compute `current_value_pct_of_premium = (current_contract_value / original_premium_received) × 100`.
4. Compute `current_dte` = calendar days from `curr_date` to the open contract's expiration date.
5. Determine `current_analyst_bias`: read from the current run's `AgentState.investment_plan` field using the same extraction logic as FSPEC-WHEEL-03 Criterion 5 (parse `recommendation` from `ResearchPlan`; map to `"bullish"`, `"neutral"`, or `"bearish"`).
6. Evaluate the five rules in strict priority order (Rule 1 through Rule 5). Each rule is evaluated regardless of whether a prior rule fired.

**Rule evaluation:**

- **Rule 1 — Profit capture:** If `current_value_pct_of_premium <= take_profit_pct` (config, default 50): Rule 1 fires with `trigger_reason = "profit_capture"`, proposed `action = "HOLD"`.
- **Rule 2 — DTE:** If `current_dte <= dte_to_roll` (config, default 21): Rule 2 fires with `trigger_reason = "dte_rule"`, proposed `action = "ROLL"`.
- **Rule 3 — Breach:** For CSP positions only: if the current spot price is ≥ 15% below the CSP strike (i.e., `spot_price <= csp_strike × 0.85`):
  - 3a. If `current_value_pct_of_premium >= 50`: Rule 3 fires with `trigger_reason = "breach_rule_roll"`, proposed `action = "ROLL"`.
  - 3b. If `current_value_pct_of_premium < 50`: Rule 3 fires with `trigger_reason = "breach_rule_close"`, proposed `action = "CLOSE"`.
  - The 15% threshold comparison is: `spot_price <= csp_strike × 0.85` (inclusive — exact 15% breach fires the rule).
- **Rule 4 — Earnings:** Call `get_next_earnings_date(ticker, curr_date)`. If the next earnings date falls within the remaining DTE (i.e., `earnings_date <= expiration_date`) AND the position is not "deep OTM":
  - "Deep OTM" for a CSP is defined as `abs(current_delta) < 0.10` (exclusive boundary — `abs(delta) == 0.10` is NOT deep OTM).
  - 4a. If not deep OTM: Rule 4 fires with `trigger_reason = "earnings_rule"`, proposed `action = "CLOSE"`.
  - 4b. If deep OTM: Rule 4 does not fire (the position is considered safe through earnings).
- **Rule 5 — Analyst update:** Rule 5 fires when ALL of the following are true:
  - `current_analyst_bias` (from current run's `investment_plan`) is `"bearish"` (i.e., `recommendation` is `Sell` or `Underweight`).
  - `WheelPosition.prior_analyst_bias` is `"bullish"` (i.e., the prior run recorded a `Buy` or `Overweight` recommendation).
  - If `WheelPosition.prior_analyst_bias` is `None` (first run for this position) or `"neutral"`, Rule 5 does not fire.
  - When Rule 5 fires: `trigger_reason = "analyst_update"`, proposed `action = "CLOSE"`.
  - After all rules are evaluated, `WheelPosition.prior_analyst_bias` is updated to `current_analyst_bias` regardless of which action was taken.

7. **Multi-rule firing — final action determination:**

After all five rules are evaluated, determine the final `action` and `trigger_reason` as follows:

Priority order for `trigger_reason` (highest to lowest): **Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1**.

- If Rule 3 fired: final `action` and `trigger_reason` come from Rule 3 (either `"breach_rule_roll"` + `ROLL` or `"breach_rule_close"` + `CLOSE`).
- Else if Rule 5 fired: final `action = "CLOSE"`, `trigger_reason = "analyst_update"`.
- Else if Rule 4 fired: final `action = "CLOSE"`, `trigger_reason = "earnings_rule"`.
- Else if Rule 2 fired: final `action = "ROLL"`, `trigger_reason = "dte_rule"`.
- Else if Rule 1 fired: final `action = "HOLD"`, `trigger_reason = "profit_capture"`.
- If no rule fired: final `action = "HOLD"`, `trigger_reason = "profit_capture"` (this aliases both "Rule 1 fired — profit target hit" and "no rule fired — position within normal parameters"; the schema's `Literal` set does not include a distinct `"no_trigger"` value, and `"profit_capture"` is the specified default per REQ-LIFE-04).

8. **`ROLL` action — new contract specification:** When the final action is `ROLL`, determine `new_strike`, `new_expiration`, and `new_dte`:
   - Target the next standard expiration at least `dte_to_roll` calendar days beyond the current expiration.
   - For a strike-selection-on-roll: target the same Delta range as the original trade type (CSP → `[target_csp_delta_low, target_csp_delta_high]`; CC → `[target_cc_delta_low, target_cc_delta_high]`).
   - Compute `estimated_debit_or_credit`: `new_mid_premium − current_contract_value` (positive = credit received, negative = debit paid).
9. The LLM call producing `RollDecision` **MUST** be made via `bind_structured(llm, RollDecision)` from `agents/utils/structured.py`. The FSPEC does not prescribe the provider-specific mechanism — that is handled by `structured.py` transparently. If the structured call fails and the free-text fallback also fails, return `RollDecision` with `action = "HOLD"`, `trigger_reason = "profit_capture"`, and a `rationale` noting the schema failure.
10. Assemble and return `RollDecision` with all required fields.

**Business Rules:**
- All five rules are always evaluated. There is no early-exit.
- When multiple rules fire, the priority order (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1) determines the final `action` and `trigger_reason`. Only one `trigger_reason` appears in the output.
- Rule 3 (Breach) applies only to CSP positions (`wheel_phase == "csp_open"`). For CC positions (`wheel_phase == "cc_open"`), Rule 3 is skipped.
- Rule 1 (Profit capture) fires when `current_value_pct_of_premium <= take_profit_pct` (boundary inclusive). When Rule 1 fires alone (no higher-priority rule fires), the action is `"HOLD"`.
- The 15% breach threshold for Rule 3 is `spot_price <= csp_strike × 0.85` (inclusive boundary). It is not configurable in Phase 1.
- "Deep OTM" for the earnings rule (Rule 4) is defined as `abs(current_delta) < 0.10` (exclusive: `abs(delta) == 0.10` is NOT deep OTM, so Rule 4 fires at that boundary).
- **Rule 5 mechanism:** `WheelPosition.prior_analyst_bias` stores the analyst bias from the prior `RollCheckAgent` run for this position (one of `"bullish"`, `"neutral"`, `"bearish"`, or `None`). The `current_analyst_bias` is derived from `AgentState.investment_plan` using the same extraction logic as FSPEC-WHEEL-03 Criterion 5. Rule 5 fires when `prior_analyst_bias == "bullish"` AND `current_analyst_bias == "bearish"`. At the end of each `RollCheckAgent` run, `WheelPosition.prior_analyst_bias` is updated to `current_analyst_bias`.
- `trigger_reason` must be exactly one of the six Literal values in the `RollDecision` schema. No free-text values are permitted.
- `new_strike`, `new_expiration`, and `new_dte` are populated only when `action == "ROLL"`. They are `None` for `HOLD` and `CLOSE` actions.
- `estimated_debit_or_credit` is populated only when `action == "ROLL"`. It is `None` for `HOLD` and `CLOSE`.
- The `"profit_capture"` trigger_reason covers both "Rule 1 fired (profit target hit)" and "no rule fired (position within normal parameters)." This aliasing is intentional and documented here for downstream test assertion consistency.
- The LLM call must use `bind_structured(llm, RollDecision)` from `agents/utils/structured.py`.

**Input / Output:**

Input:
- `WheelPosition` (open position details including `csp_strike`, `csp_premium_received`, `cc_strike`, `cc_premium_received` as applicable, and `prior_analyst_bias: Optional[str]`)
- `curr_date: str`
- Current analyst reports
- Wheel configuration

Output: `RollDecision` with fields:

| Field | Type | Populated when |
|---|---|---|
| `action` | `"HOLD"` / `"ROLL"` / `"CLOSE"` | Always |
| `ticker` | `str` | Always |
| `current_strike` | `float` | Always |
| `current_expiration` | `str` | Always |
| `current_dte` | `int` | Always |
| `current_value_pct_of_premium` | `float` (0–100) | Always |
| `trigger_reason` | Literal (one of 6 values) | Always |
| `new_strike` | `float \| None` | When `action == "ROLL"` |
| `new_expiration` | `str \| None` | When `action == "ROLL"` |
| `new_dte` | `int \| None` | When `action == "ROLL"` |
| `estimated_debit_or_credit` | `float \| None` | When `action == "ROLL"` |
| `rationale` | `str` | Always (non-empty string) |

**Edge Cases and Error Scenarios:**

- **No rule fires:** Return `action = "HOLD"`, `trigger_reason = "profit_capture"` (default aliasing — see Business Rules).
- **`get_next_earnings_date` returns no upcoming earnings:** Rule 4 is not evaluated (no earnings event detected). Evaluation continues with remaining rules.
- **`current_delta` is unavailable (Greeks fetch fails):** Rule 4's deep-OTM check cannot be performed. Rule 4 fires conservatively (treat as NOT deep OTM, meaning `CLOSE` is recommended if earnings is within DTE).
- **`WheelPosition` is for `wheel_phase == "cc_open"`:** Rule 3 is skipped entirely. `current_strike` is `cc_strike`; `original_premium_received` is `cc_premium_received`.
- **`original_premium_received` is zero (data integrity error):** Return `action = "HOLD"`, add note `"Cannot compute value pct: original premium is zero"` to rationale.
- **Both Rule 1 and Rule 2 fire:** Rule 2 takes precedence (`dte_rule` > `profit_capture` in priority). Final `action = "ROLL"`, `trigger_reason = "dte_rule"`.
- **`WheelPosition.prior_analyst_bias` is `None` (first run):** Rule 5 does not fire.

**Acceptance Tests:**

*Who:* Agent | *Test level:* Integration (mocked LLM and data tools)
*Given:* Premium is at 50% of received value and `current_dte = 30`
*When:* RollCheckAgent runs
*Then:* `RollDecision.action == "HOLD"` and `trigger_reason == "profit_capture"`.
(Covers REQ-LIFE-03 AC1)

*Who:* Agent | *Test level:* Integration (mocked LLM and data tools)
*Given:* `current_dte = 18` (≤ `dte_to_roll = 21`)
*When:* RollCheckAgent runs
*Then:* `action == "ROLL"`, `trigger_reason == "dte_rule"`, and `new_expiration` is populated.
(Covers REQ-LIFE-03 AC2)

*Who:* Agent | *Test level:* Integration (mocked LLM and data tools)
*Given:* Stock dropped ≥ 15% below CSP strike AND `current_value_pct_of_premium >= 50`
*When:* RollCheckAgent runs
*Then:* `action == "ROLL"` and `trigger_reason == "breach_rule_roll"`.
(Covers REQ-LIFE-03 AC3a)

*Who:* Agent | *Test level:* Integration (mocked LLM and data tools)
*Given:* Stock dropped ≥ 15% below CSP strike AND `current_value_pct_of_premium < 50`
*When:* RollCheckAgent runs
*Then:* `action == "CLOSE"` and `trigger_reason == "breach_rule_close"`.
(Covers REQ-LIFE-03 AC3b)

*Who:* Agent | *Test level:* Integration (mocked LLM; `WheelPosition.prior_analyst_bias = "bullish"`, current `investment_plan` contains recommendation=Sell)
*Given:* `investment_plan` contains `Sell` (bearish), `past_context` contains prior `Buy` entry (i.e., `WheelPosition.prior_analyst_bias = "bullish"`)
*When:* RollCheckAgent runs
*Then:* `action == "CLOSE"` and `trigger_reason == "analyst_update"`.
(Covers REQ-LIFE-03 AC4)

*Who:* System | *Test level:* Unit
*Given:* Stock price equals exactly `csp_strike × 0.85` (15% breach threshold exactly)
*When:* Rule 3 is evaluated
*Then:* Rule 3 fires (`breach_rule` fires at exact boundary).
(Covers breach threshold inclusivity — FSPEC-TE-06 resolution)

*Who:* System | *Test level:* Unit
*Given:* Rule 3 (breach) and Rule 1 (profit_capture) both fire simultaneously
*When:* Final action is determined
*Then:* `trigger_reason == "breach_rule_close"` or `"breach_rule_roll"` (Rule 3 takes priority over Rule 1).
(Covers multi-rule priority — FSPEC-TE-09 resolution)

*Who:* System | *Test level:* Unit
*Given:* Rule 2 (DTE) and Rule 1 (profit_capture) both fire simultaneously
*When:* Final action is determined
*Then:* `trigger_reason == "dte_rule"` and `action == "ROLL"` (Rule 2 takes priority over Rule 1).
(Covers multi-rule priority Rule 2 > Rule 1 — FSPEC-TE-09 resolution)

*Who:* System | *Test level:* Unit
*Given:* Any terminal output from RollCheckAgent
*When:* `rationale` field is read
*Then:* It is a non-empty string.
(Schema contract — rationale always populated)

**Open Questions:**
- **Rule 1 action when profit target is hit:** The REQ AC1 specifies `action = "HOLD"` when premium is at 50% of received value with DTE = 30. This FSPEC follows the REQ. However, many wheel traders would close at 50% profit rather than hold. SE author should confirm whether `HOLD` is the correct recommendation at the 50% profit target, or whether it should be `CLOSE` with `trigger_reason = "profit_capture"`.
- **Breach threshold configurability:** The 15% breach threshold is hardcoded in this FSPEC. SE author should confirm if this should be a configurable `config["wheel"]` key for Phase 1 or a later addition.

---

## FSPEC-WHEEL-07: Wheel Phase State Machine

**Linked requirements:** REQ-LIFE-01, REQ-LIFE-02

**Purpose:** Define the full wheel lifecycle phase transitions, the data required before each transition, the LangGraph conditional router logic, and the behaviour on illegal transitions.

**Actors:**
- `WheelPhase` enum (`str, Enum`)
- `AgentState` TypedDict (`wheel_phase: Optional[str]` field)
- `ConditionalLogic.route_wheel_phase()` method (new, in `graph/setup.py`)
- `setup_graph()` function (extended with `START → wheel_router` preamble edge)
- `WheelPosition` model and position store
- `WheelStateError` exception

**Phase Definitions:**

| Phase value | Meaning | Entry condition |
|---|---|---|
| `None` | Equity-only mode | `wheel_phase` is absent from state |
| `"screening"` | Analyst pipeline + WheelAnalyst + CspAgent | No prior open position for ticker |
| `"csp_open"` | CSP is live; RollCheckAgent evaluates it | A `WheelPosition` exists with `csp_strike` set and no `assignment_date` |
| `"stock_owned"` | Stock assigned; CcAgent selects CC | A `WheelPosition` exists with `assignment_date` set and no `cc_strike` |
| `"cc_open"` | CC is live; RollCheckAgent evaluates it | A `WheelPosition` exists with `cc_strike` set and no `call_away_date` |
| `"cycle_complete"` | Cycle finished; summary emitted | A `WheelPosition` exists with `call_away_date` set |

**Transition Table:**

| From phase | Trigger event | To phase | Required state data |
|---|---|---|---|
| `None` | `wheel_phase` is set externally | `"screening"` | ticker, `curr_date` |
| `"screening"` | `WheelCandidateReport.approved == True` AND `CspDecision.tradeable == True` | `"csp_open"` | `CspDecision` fields written to `WheelPosition` |
| `"screening"` | Either report is false/not tradeable | remains `"screening"` | No position created |
| `"csp_open"` | CSP expires worthless OR assignment is detected | `"stock_owned"` | `WheelPosition.assignment_date` set, `shares_held = 100` |
| `"csp_open"` | `RollDecision.action == "ROLL"` | remains `"csp_open"` | `WheelPosition` updated with new CSP details |
| `"csp_open"` | `RollDecision.action == "CLOSE"` | `"cycle_complete"` | `WheelPosition.cycle_pnl` computed (loss realised) |
| `"stock_owned"` | `CcDecision.tradeable == True` | `"cc_open"` | `WheelPosition.cc_strike`, `cc_expiration`, `cc_premium_received` set |
| `"stock_owned"` | `CcDecision.tradeable == False` | remains `"stock_owned"` | No CC opened |
| `"cc_open"` | CC expires worthless | remains `"stock_owned"` | `WheelPosition` CC fields cleared; new CC selection required |
| `"cc_open"` | CC is called away (stock sold at `cc_strike`) | `"cycle_complete"` | `WheelPosition.call_away_date` set, `cycle_pnl` computed |
| `"cc_open"` | `RollDecision.action == "ROLL"` | remains `"cc_open"` | `WheelPosition` updated with new CC details |
| `"cc_open"` | `RollDecision.action == "CLOSE"` | `"stock_owned"` | CC closed; position reverts to stock-only state |
| `"cycle_complete"` | Cycle summary emitted | `"screening"` | `cycle_number` incremented; new `WheelPosition` record created |

**Behavioural Flow — Router:**

1. The `START → wheel_router` conditional edge fires at the beginning of every graph invocation.
2. `ConditionalLogic.route_wheel_phase()` reads `state["wheel_phase"]`.
3. **Branch — None (equity-only):**
   - 3a. If `wheel_phase is None`: return the name of the first analyst node. The first analyst node name is determined by the existing analyst execution plan (`plan.specs[0].agent_node`), which is passed to `ConditionalLogic` at construction time during `setup_graph()`. No options nodes are visited. All existing equity-analysis flows run as before. (Covers REQ-LIFE-01 AC1)
4. **Branch — unknown value:**
   - 4b. If `wheel_phase` is a string not in the set `{"screening", "csp_open", "stock_owned", "cc_open", "cycle_complete"}`: log a warning `"Unknown wheel_phase value '{value}' — falling back to equity-only path"`, return the first analyst node name (same as 3a). (Covers REQ-LIFE-01 AC6)
5. **Branch — "screening":**
   - Return: name of first analyst node (analyst pipeline runs, followed by WheelAnalyst and CspAgent nodes). (Covers REQ-LIFE-01 AC2)
6. **Branch — "csp_open":**
   - Validate: look up open `WheelPosition` for the ticker. If none found or if `WheelPosition` does not have `csp_strike` set: raise `WheelStateError("No open CSP position found for phase 'csp_open'")`. (Related to REQ-LIFE-01 AC5)
   - Return: `"roll_check_agent"` (node name for RollCheckAgent).
7. **Branch — "stock_owned":**
   - Return: `"cc_agent"` (node name for CcAgent). CspAgent is skipped. (Covers REQ-LIFE-01 AC3)
8. **Branch — "cc_open":**
   - Validate: look up open `WheelPosition` for the ticker. If the position exists but `cc_strike` is `None`: raise `WheelStateError("No open CC position found for phase 'cc_open'")`. (Covers REQ-LIFE-01 AC5)
   - Return: `"roll_check_agent"` (node name for RollCheckAgent).
9. **Branch — "cycle_complete":**
   - Emit cycle summary (formatted `WheelPosition` report with `cycle_pnl` and `cycle_annualised_return_pct`).
   - Append cycle summary to `TradingMemoryLog` (per REQ-LIFE-05).
   - Return: `"signal_processor"` (or equivalent terminal node). The `wheel_phase = "screening"` reset is written to the output state of the `cycle_complete` node. The graph invocation terminates normally. The next `graph.invoke()` call starts in `"screening"`. No intra-invocation loop is added.

**Phase Transition Guards:**

Each transition has a required-data guard. If required data is missing, the transition is rejected and `WheelStateError` is raised:

| Attempted transition | Required guard | Error if guard fails |
|---|---|---|
| `"screening"` → `"csp_open"` | `CspDecision` present and `tradeable == True` | `WheelStateError("Cannot enter csp_open: no tradeable CspDecision")` |
| `"csp_open"` → `"stock_owned"` | `WheelPosition.csp_strike` is set | `WheelStateError("Cannot enter stock_owned: no CSP strike on position")` |
| `"stock_owned"` → `"cc_open"` | `WheelPosition.assignment_date` is set | `WheelStateError("Cannot enter cc_open: no assignment_date on position")` |
| `"cc_open"` → `"cycle_complete"` | `WheelPosition.cc_strike` is set | `WheelStateError("Cannot enter cycle_complete from cc_open: no CC strike on position")` |

**Business Rules:**
- `WheelPhase` is declared as `class WheelPhase(str, Enum)` with lowercase string values. JSON serialisation relies on the string value, not the enum name.
- `AgentState["wheel_phase"]` is stored as a raw string (the enum's `.value`). Enum validation (conversion from string to `WheelPhase`) occurs on read, not on write.
- When `wheel_phase is None`, the graph topology is identical to the existing equity-only flow. No wheel nodes are visited and no position lookups occur.
- `WheelStateError` is a custom exception class. It must not be silently swallowed within the graph — it propagates to the caller. The graph does not catch `WheelStateError`.
- Unknown `wheel_phase` strings fall back to the equity-only path with a warning log. They do not raise `WheelStateError`.
- Illegal transitions (where required guard fails) always raise `WheelStateError`. There is no silent degradation for these cases.
- The `START → wheel_router` conditional edge is a preamble to the existing graph topology, not a separate sub-graph. Tool nodes for options data tools are registered alongside existing tool nodes.
- The `WheelPosition` file for the current cycle is updated at every phase transition. The atomic temp-file + rename pattern must be used to prevent corruption.
- **`route_wheel_phase()` return values:** The method returns a string node name consumed by LangGraph's `add_conditional_edges`. The full set of possible return values is:
  - `wheel_phase is None` → `plan.specs[0].agent_node` (first analyst node, determined at `setup_graph()` time)
  - `wheel_phase == "screening"` → `plan.specs[0].agent_node` (first analyst node)
  - `wheel_phase == "csp_open"` → `"roll_check_agent"`
  - `wheel_phase == "stock_owned"` → `"cc_agent"`
  - `wheel_phase == "cc_open"` → `"roll_check_agent"`
  - `wheel_phase == "cycle_complete"` → `"signal_processor"`
  - Unknown value → `plan.specs[0].agent_node` (equity-only fallback)
  - `ConditionalLogic` must be constructed with the first analyst node name injected at `setup_graph()` time so the router has a static value to return for the `None` and `"screening"` branches.

**Input / Output:**

Input to `route_wheel_phase()`:
- `state: AgentState` (read-only within the router)
- Position store access (read-only lookup)

Output from `route_wheel_phase()`:
- A node name string directing the `StateGraph` to the appropriate next node.
- Or: raises `WheelStateError` on illegal transition.

**Edge Cases and Error Scenarios:**

- **`wheel_phase = None`:** Equity-only path. No options nodes. (Covers REQ-LIFE-01 AC1)
- **`wheel_phase = "cc_open"` with no `WheelPosition.cc_strike`:** Raises `WheelStateError`. (Covers REQ-LIFE-01 AC5)
- **`wheel_phase = "invalid_phase"`:** Falls back to equity-only path; logs warning. (Covers REQ-LIFE-01 AC6)
- **Phase transition with missing required data:** `WheelStateError` is raised with a descriptive message indicating which guard failed.
- **`cycle_complete` emitted but memory log write fails:** Log the error; do not block the state reset. The cycle summary is still emitted to the user even if persistence fails.
- **Multiple tickers in parallel:** Each ticker has its own `WheelPosition` file. The router uses the ticker from the current state to look up the correct position.
- **`cycle_complete` → `"screening"` reset:** The reset is written to the output state of the `cycle_complete` node. The graph terminates normally. The next invocation starts in `"screening"`. No loop-back edge is added.

**Acceptance Tests:**

*Who:* System | *Test level:* Unit
*Given:* `wheel_phase = None`
*When:* Graph is invoked
*Then:* Existing equity pipeline runs unchanged; no options nodes are visited.
(Covers REQ-LIFE-01 AC1)

*Who:* System | *Test level:* Integration
*Given:* `wheel_phase = "screening"`
*When:* Graph is invoked
*Then:* Analyst pipeline + WheelAnalyst + CspAgent nodes are visited.
(Covers REQ-LIFE-01 AC2)

*Who:* System | *Test level:* Integration
*Given:* `wheel_phase = "stock_owned"`
*When:* Graph is invoked
*Then:* CcAgent node is visited; CspAgent node is not visited.
(Covers REQ-LIFE-01 AC3)

*Who:* System | *Test level:* Unit
*Given:* Phase transition occurs (CSP assigned — `assignment_date` is written to `WheelPosition`)
*When:* State is updated
*Then:* `wheel_phase` in `AgentState` changes from `"csp_open"` to `"stock_owned"`.
(Covers REQ-LIFE-01 AC4)

*Who:* System | *Test level:* Unit
*Given:* `wheel_phase = "cc_open"` but no `WheelPosition` with `cc_strike` set exists for the ticker
*When:* Graph is invoked
*Then:* Graph raises `WheelStateError`.
(Covers REQ-LIFE-01 AC5)

*Who:* System | *Test level:* Unit
*Given:* `wheel_phase = "invalid_phase"`
*When:* Graph is invoked
*Then:* Graph falls back to equity-only path and logs a warning. No exception is raised.
(Covers REQ-LIFE-01 AC6)

**Open Questions:**
- **`"csp_open"` → `"stock_owned"` trigger:** The REQ specifies "CSP expires worthless OR assignment is detected." Both events are external to the system (they happen at the broker). This FSPEC assumes the human trader manually updates `wheel_phase` in the state when assignment occurs. SE author must confirm whether there is an automated assignment-detection mechanism or whether this is always a manual state update.
- **`"cc_open"` → `"stock_owned"` on CC expiry worthless:** Same question as above — manual or automated? SE author to clarify.

---

## FSPEC-WHEEL-08: CLI Wheel Panel Display

**Linked requirements:** REQ-SCREEN-03

**Purpose:** Define how the `WheelCandidateReport` is rendered in the CLI's Rich panel after WheelAnalyst runs, including field layout, approval/rejection styling, and the display guard for non-wheel runs.

**Actors:**
- CLI `MessageBuffer` (existing)
- Rich `Console` (existing)
- `WheelCandidateReport` Pydantic schema (serialised to display text)
- `update_report_section()` method on the CLI message buffer

**Behavioural Flow:**

1. After the `WheelAnalyst` node completes and produces a `WheelCandidateReport`:
2. `WheelCandidateReport` is serialised to a formatted display string (`report_text`) containing:
   - Approval status line: `"Approved: Yes"` / `"Approved: No"` with `rejection_reason` on the next line (when non-None).
   - IV Rank, IV Percentile, and IV Environment.
   - Earnings clearance status.
   - Recommended strike range: `[low_strike, high_strike]`.
   - Recommended DTE range: `[dte_low, dte_high]`.
   - Rationale (truncated to 300 characters for display; full text in logs).
3. CLI calls `update_report_section("wheel_candidate", report_text)`.
4. Rich `Console` renders the section as a dedicated panel with title `"Wheel Suitability"`.
5. Styling:
   - If `approved == True`: section header uses the default (neutral) Rich style.
   - If `approved == False`: section header uses Rich `"bold red"` style.
   - `rejection_reason` is always displayed when non-None, regardless of other fields.

**Business Rules:**
- The `"Wheel Suitability"` section is rendered only when `"wheel"` is in `selected_analysts`. When `"wheel"` is not selected, no wheel-specific panel appears and existing CLI behaviour is unchanged.
- `approved == True` renders the section header in default style.
- `approved == False` renders the section header in Rich `"bold red"` style.
- `rejection_reason` is always displayed in the panel body when non-None (even if other display elements are suppressed).
- The panel is inserted after the four standard analyst report panels and before the Portfolio Manager recommendation panel.
- CLI display tests use Rich's `console.export_text()` to capture terminal output and assert on string presence. Tests inject a Rich `Console(file=StringIO())` via the CLI test harness.

**Input / Output:**

Input:
- `WheelCandidateReport` (from `AgentState` after WheelAnalyst node completes)
- `selected_analysts: list[str]` (from graph config)

Output:
- Rich panel titled `"Wheel Suitability"` rendered to the CLI console.
- `console.export_text()` contains: `"WheelCandidateReport"` string (or panel title), `"IV Rank"`, and `rejection_reason` when `approved == False`.

**Edge Cases and Error Scenarios:**

- **`"wheel"` not in `selected_analysts`:** No panel rendered. Existing output unchanged.
- **`WheelCandidateReport` not available in state (e.g., node did not run):** No panel rendered. Log a warning.
- **`rejection_reason` is None (approved=True):** Approval line shows `"Approved: Yes"`. No rejection line rendered.

**Acceptance Tests:**

*Who:* User | *Test level:* Unit (mocked `WheelCandidateReport`, Rich `Console(file=StringIO())`)
*Given:* Wheel Analyst is selected in CLI (i.e., `"wheel"` in `selected_analysts`) and analysis runs
*When:* `console.export_text()` is called
*Then:* Output contains `"Wheel Suitability"` (panel title) and `"IV Rank"`.
(Covers REQ-SCREEN-03 AC1)

*Who:* User | *Test level:* Unit (mocked run with `"wheel"` absent from `selected_analysts`)
*Given:* Wheel Analyst is not selected
*When:* `console.export_text()` is called
*Then:* No wheel-specific section appears; existing behaviour is unchanged.
(Covers REQ-SCREEN-03 AC2)

*Who:* User | *Test level:* Unit (mocked `WheelCandidateReport` with `approved=False` and non-empty `rejection_reason`)
*Given:* Report shows `approved: False`
*When:* `console.export_text()` is called
*Then:* Output contains the `rejection_reason` string.
(Covers REQ-SCREEN-03 AC3)

**Open Questions:**
- **Panel title string:** This FSPEC uses `"Wheel Suitability"` as the panel title. SE author should confirm the exact title string and whether it should match `"WheelCandidateReport"` verbatim (per REQ-SCREEN-03 AC1 which checks for `"WheelCandidateReport"` in output). If the AC asserts on that exact string, the panel title or a subtitle must include it.

---

## FSPEC-WHEEL-09: Risk Debate Options Context Injection

**Linked requirements:** REQ-TRADE-05

**Purpose:** Define how `CspDecision` or `CcDecision` context is injected into the risk debate agents' system prompts when the system is in wheel mode, and how the injection is suppressed in equity-only mode.

**Actors:**
- Risk debate prompt assembler (existing prompt-building logic for Aggressive, Conservative, Neutral debaters)
- `CspDecision` / `CcDecision` (from `AgentState` after CspAgent or CcAgent runs)
- Aggressive, Conservative, and Neutral risk debate agents
- Portfolio Manager agent

**Behavioural Flow:**

1. Before each risk debate agent's system prompt is assembled:
2. **Branch — wheel mode (`wheel_phase` is not None):**
   - Retrieve the relevant decision from `AgentState`: `CspDecision` (when `wheel_phase == "csp_open"` or `"screening"`) or `CcDecision` (when `wheel_phase == "cc_open"` or `"stock_owned"`).
   - Serialise the following fields from the decision into `options_context`:
     - `action` (or trade type: `"cash-secured put"` / `"covered call"`)
     - `strike`
     - `expiration_date`
     - `mid_premium`
     - `probability_of_profit`
     - `earnings_clear` (boolean)
     - For `CspDecision`: also include `max_loss` and `breakeven_price`.
     - For `CcDecision`: also include `upside_to_strike_pct` and `cost_basis`.
   - Inject `options_context` as the `{options_context}` template variable into each debate agent's system prompt. The variable is inserted at a defined injection point in the existing debate prompt template.
3. **Branch — equity-only mode (`wheel_phase` is None):**
   - The `{options_context}` template variable is omitted (or replaced with an empty string) from the debate prompt. Existing prompt behaviour is unchanged.
4. Each debate agent (Aggressive, Conservative, Neutral) receives the assembled prompt including `options_context` and produces its position.
5. Portfolio Manager receives the debate outputs and produces a `PortfolioDecision` that either confirms the options trade or recommends passing.

**Business Rules:**
- Injection happens only when `wheel_phase` is not `None`. If `wheel_phase is None`, the prompt template is unchanged and agents receive no options-specific context.
- `options_context` must include at minimum: `action` (trade type), `strike`, `expiration_date`, `mid_premium`, `probability_of_profit`, `earnings_clear`.
- `options_context` must include `max_loss` and `breakeven_price` when the decision is a `CspDecision`.
- `options_context` must include `upside_to_strike_pct` and `cost_basis` when the decision is a `CcDecision`.
- The injected context is formatted as a structured text block (not raw JSON) for LLM readability. Field names and values are written as `"Field: value"` pairs, one per line.
- The existing risk debate prompt structure is not altered except for the addition of the `{options_context}` injection point. No existing debate prompt content is removed.
- Prompt-content ACs assert on the assembled prompt string before it is sent to the LLM (deterministic assertion — does not depend on LLM output).

**Input / Output:**

Input:
- `AgentState` (contains `wheel_phase`, and either `csp_decision` or `cc_decision` as serialised JSON strings)
- Existing debate prompt templates

Output:
- Assembled system prompt strings for each debate agent, containing `{options_context}` when in wheel mode.

**Edge Cases and Error Scenarios:**

- **`wheel_phase` is not None but neither `csp_decision` nor `cc_decision` is present in state:** Log a warning; proceed with equity-only prompt (no injection). Do not error.
- **`wheel_phase` is None:** Prompt unchanged. Existing equity-only debate behaviour preserved. (Covers REQ-TRADE-05 AC3)
- **`earnings_clear` is `False`:** The `options_context` block must include the `expiration_date` prominently so the Conservative debater can reason about the earnings risk. (Covers REQ-TRADE-05 AC2)

**Acceptance Tests:**

*Who:* System | *Test level:* Unit (prompt-content assertion on assembled prompt string, no LLM call)
*Given:* System is in wheel mode (`wheel_phase` is not None) with a `CspDecision` in `AgentState`
*When:* Prompt is assembled for risk debate agents
*Then:* The prompt string contains the serialised `CspDecision` fields `mid_premium` and `probability_of_profit`.
(Covers REQ-TRADE-05 AC1)

*Who:* System | *Test level:* Unit (prompt-content assertion)
*Given:* `CspDecision.earnings_clear` is `False` (earnings date within option's expiration)
*When:* Prompt is assembled for the Conservative debater
*Then:* The prompt string contains `expiration_date` from the `CspDecision` context.
(Covers REQ-TRADE-05 AC2)

*Who:* Agent | *Test level:* Integration (mocked debate agents)
*Given:* Mode is equity (`wheel_phase` is None)
*When:* Risk debate runs
*Then:* Agents receive no options-specific context; existing behaviour unchanged.
(Covers REQ-TRADE-05 AC3)

**Open Questions:**
- **Injection point location in debate prompt:** This FSPEC specifies that `{options_context}` is injected at a "defined injection point" in the existing prompt template. SE author must specify where in the prompt structure this injection point is placed (e.g., after the standard market context block, before the debate instructions).
- **`CspDecision`/`CcDecision` state field names:** This FSPEC references `csp_decision` and `cc_decision` as `AgentState` fields (serialised JSON strings). SE author must confirm these field names and their types (raw JSON string vs Pydantic instance) match the state layout defined in FSPEC-WHEEL-07.
