# FSPEC — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-25 |
| **Upstream** | REQ-wheel-options-trading.md v0.2.0 → **FSPEC** |
| **Downstream** | TSPEC, PROPERTIES |
| **Cross-Reviews** | _(none yet)_ |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2026-05-25 | Initial draft |

---

## Overview

This document specifies the functional behaviour of the Wheel Options Trading feature across four delivery phases. It covers the seven areas of behavioural complexity identified in the approved requirements that engineers must not decide alone: data tool routing, IV computation, suitability screening, CSP strike selection, covered call strike selection, roll/hold/close logic, and the wheel phase state machine.

Each section is self-contained and references the upstream REQ acceptance criteria that govern it.

---

## FSPEC-WHEEL-01: Options Data Tool Routing

**Linked requirements:** REQ-DATA-01, REQ-DATA-02, REQ-DATA-03, REQ-DATA-04, REQ-DATA-05

**Purpose:** Define how the four options data tool wrappers route through `interface.py`'s vendor layer so that swapping data providers requires no changes to agent code.

**Actors:**
- `options_data_tools.py` — the `@tool`-decorated LangChain wrapper layer
- `interface.py` — the vendor-routing hub
- `y_finance.py` — the Phase 1 yfinance implementation layer
- Any future Alpha Vantage or CBOE LiveVol adapter

**Behavioural Flow:**

1. An agent calls one of the four tool functions exposed by `options_data_tools.py`: `get_options_chain`, `get_iv_metrics`, `get_options_greeks`, or `get_next_earnings_date`.
2. The `@tool` wrapper in `options_data_tools.py` passes the call to `interface.py` via `route_to_vendor()`, supplying:
   - the category key `"options_data"`
   - the method name matching the underlying implementation (e.g., `"get_options_chain"`)
   - all caller-supplied arguments
3. `route_to_vendor()` reads `config["data_vendors"]["options_data"]` to determine the active vendor.
   - 3a. If the value is `"yfinance"`, the call is dispatched to the corresponding function in `y_finance.py`.
   - 3b. If the value is `"alpha_vantage"`, the call is dispatched to the Alpha Vantage adapter. In Phase 1, this adapter returns the stub string `"not implemented"` for all four methods.
   - 3c. If the value is any other string, `route_to_vendor()` returns an error string `"Unknown options_data vendor: {vendor}"`. It does not raise an exception.
4. The implementation function executes and returns either a result string/dict or a graceful error string (see individual FSPEC sections and REQ-NFR-06).
5. The `@tool` wrapper returns the result to the calling agent without modification.

**Business Rules:**
- `options_data_tools.py` wrappers must never import functions from `y_finance.py` directly; all calls must pass through `route_to_vendor()` in `interface.py`.
- The category key registered in `interface.py` for all four tools is exactly `"options_data"` — no variation (e.g., not `"options"` or `"wheel_data"`).
- All four tools must be listed in `VENDOR_METHODS` with at least: a yfinance entry and an Alpha Vantage stub entry.
- The config key controlling vendor selection is `config["data_vendors"]["options_data"]`.
- Errors from the vendor implementation layer are returned as strings. Exceptions must not propagate to the calling agent.

**Input / Output:**

| Tool | Input | Output |
|---|---|---|
| `get_options_chain` | `ticker: str`, `target_date: str`, `expiry_date: str \| None` | Formatted string with chain table, or error string |
| `get_iv_metrics` | `ticker: str`, `curr_date: str`, `lookback_days: int = 252`, `iv_series: list[float] \| None = None` | Structured dict / parseable string with IV metrics, or error string |
| `get_options_greeks` | `ticker: str`, `curr_date: str`, `expiry_date: str`, `strike: float`, `option_type: str` | Structured dict / parseable string with Greek values, or error string |
| `get_next_earnings_date` | `ticker: str`, `curr_date: str` | Structured string with date, days-until, and `within_options_cycle` flag, or error string |

**Edge Cases and Error Scenarios:**

- **Unknown vendor:** `route_to_vendor()` returns `"Unknown options_data vendor: {vendor}"` — no exception, no crash.
- **Alpha Vantage stub (Phase 1):** All four methods return `"not implemented"` for Alpha Vantage vendor. This is the expected and specified behaviour until a real adapter is provided.
- **Network failure in vendor layer:** The implementation (not the router) catches `HTTPError` and `ConnectionError` and returns a graceful error string. The routing layer does not handle network errors.

**Acceptance Tests:**

*Who:* Developer
*Given:* `config["data_vendors"]["options_data"] = "yfinance"` and an agent is instantiated
*When:* The agent calls any of the four options tools
*Then:* The call reaches the yfinance implementation layer and returns a result — the agent does not error on import or at call time.
(Covers REQ-DATA-05 AC1)

*Who:* Developer
*Given:* A new Alpha Vantage options adapter is added and `config["data_vendors"]["options_data"] = "alpha_vantage"`
*When:* Any of the four tools is called
*Then:* The call routes to the new adapter without modifying any agent code.
(Covers REQ-DATA-05 AC2)

*Who:* Agent
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

*Who:* Agent
*Given:* A valid ticker with 252+ trading days of OHLCV history
*When:* `get_iv_metrics(ticker, curr_date)` is called
*Then:* Returned dict contains `iv_rank` and `iv_percentile` in [0, 100] with no NaN values.
(Covers REQ-DATA-02 AC1)

*Who:* Agent
*Given:* `iv_rank >= 50` in the returned result
*When:* `iv_environment` field is read
*Then:* `iv_environment == "elevated"`.
(Covers REQ-DATA-02 AC3)

*Who:* Agent
*Given:* `iv_rank < 25` in the returned result
*When:* `iv_environment` field is read
*Then:* `iv_environment == "compressed"`.
(Covers REQ-DATA-02 AC4)

*Who:* System
*Given:* `iv_series` is provided as a list where all values are equal (max == min)
*When:* `get_iv_metrics(ticker, curr_date, iv_series=[0.20] * 100)` is called
*Then:* `iv_rank == 50`, `iv_percentile == 50`, and the report string contains `"IV range is flat — rank set to neutral 50"`.
(Covers REQ-DATA-02 AC5)

**Open Questions:**
- Should `iv_percentile` use strict-less-than (`< current_vol`) or less-than-or-equal (`<= current_vol`)? The REQ specifies `< current_vol` (strict). SE author should confirm this is intentional for the boundary day (where `realised_vol == current_vol`).

---

## FSPEC-WHEEL-03: WheelAnalyst Suitability Decision Flow

**Linked requirements:** REQ-SCREEN-01, REQ-SCREEN-02

**Purpose:** Define the five-criterion suitability evaluation flow that `WheelAnalyst` executes to produce an approved or rejected `WheelCandidateReport`, including criterion ordering, simultaneous-failure behaviour, and how the Delta-anchored `recommended_strike_range` is derived.

**Actors:**
- `WheelAnalyst` agent (`wheel_analyst.py`)
- Phase 1 data tools: `get_iv_metrics`, `get_options_chain`, `get_next_earnings_date`, `get_options_greeks`
- Existing analyst reports (as input context)
- `WheelCandidateReport` Pydantic schema (`schemas.py`)

**Behavioural Flow:**

1. `WheelAnalyst` receives as input: the ticker, `curr_date`, the four existing analyst reports (Market, Social, News, Fundamentals), and the wheel configuration.
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
6. **Criterion 5 — Analyst consensus:** Read the overall signal from the existing analyst reports. The consensus is determined by the Portfolio Manager's most recent `PortfolioDecision` signal, or if not yet available, by majority vote across the four analyst reports.
   - 6a. If consensus is `"Buy"`, `"Overweight"`, or `"Hold"`: criterion 5 passes. `analyst_bias = "bullish"` or `analyst_bias = "neutral"` respectively.
   - 6b. If consensus is `"Sell"` or `"Underweight"`: criterion 5 fails with reason matching the analyst signal. `analyst_bias = "bearish"`.
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
- When `selected_analysts` in the graph config does not include `"wheel"`, the `WheelAnalyst` node must not be present in the graph. The existing pipeline must run unmodified.

**Input / Output:**

Input:
- `ticker: str`
- `curr_date: str` (YYYY-MM-DD)
- Existing analyst reports (all four)
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
| `rationale` | `str` | Always |

**Edge Cases and Error Scenarios:**

- **`get_iv_metrics` returns an error string:** Criterion 1 fails with reason `"IV data unavailable: {error}"`. Evaluation continues.
- **`get_options_chain` returns `"No options chain available"` or an error string:** Criterion 2 fails with reason `"Options chain unavailable"`. Evaluation continues.
- **`get_next_earnings_date` returns `"No upcoming earnings date available"` for the ticker:** Criterion 3 passes by default (no earnings event means clearance is confirmed). `next_earnings_date = None`, `earnings_clearance_ok = True`.
- **All criteria fail simultaneously:** `approved = False`, `rejection_reason` contains all five failure reasons joined by `"; "`.
- **Delta-anchored strike computation fails (step 8d fallback):** `recommended_strike_range` is derived from spot price × delta bounds, rounded to nearest $0.50.
- **`WheelAnalyst` node absent from graph:** When `"wheel"` is not in `selected_analysts`, no node is registered. Graph topology is unchanged from existing equity flow.

**Acceptance Tests:**

*Who:* Agent
*Given:* All five criteria are met
*When:* WheelAnalyst runs
*Then:* `WheelCandidateReport.approved == True`.
(Covers REQ-SCREEN-01 AC1)

*Who:* Agent
*Given:* `iv_rank = 15` (below `min_iv_rank = 25`)
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` is a non-empty string.
(Covers REQ-SCREEN-01 AC2)

*Who:* Agent
*Given:* Earnings is 12 days away and target expiry is 30 DTE (earnings within `earnings_buffer_days=14` of expiration)
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` is non-empty.
(Covers REQ-SCREEN-01 AC3)

*Who:* Agent
*Given:* Bull/Bear debate concluded with Sell rating
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` is non-empty.
(Covers REQ-SCREEN-01 AC4)

*Who:* Developer
*Given:* `selected_analysts` config does not include `"wheel"`
*When:* Graph is built
*Then:* `WheelAnalyst` node is absent; existing pipeline runs as before.
(Covers REQ-SCREEN-01 AC5)

*Who:* System
*Given:* All near-the-money strikes have `OI < 100`
*When:* WheelAnalyst runs
*Then:* `approved == False` and `rejection_reason` contains `"Insufficient liquidity"`.
(Covers REQ-SCREEN-01 AC6)

*Who:* System
*Given:* `approved == True`
*When:* Schema is serialised
*Then:* `rejection_reason is None`.
(Covers REQ-SCREEN-02 AC2)

*Who:* System
*Given:* `approved == False`
*When:* Schema is serialised
*Then:* `rejection_reason` is a non-empty string.
(Covers REQ-SCREEN-02 AC3)

**Open Questions:**
- **Criterion 2 boundary — what counts as "near-the-money"?** The REQ specifies "near-the-money strikes" without giving a numeric range. This FSPEC uses ±10% of spot price as the definition. SE author must confirm or adjust this threshold.
- **Criterion 5 consensus source:** When the `PortfolioDecision` is not yet available (e.g., WheelAnalyst runs before the Portfolio Manager), this FSPEC specifies majority vote across the four analyst reports. SE author must confirm the exact signal extraction logic from existing analyst report schemas.
- **Criterion 3 target expiration calculation:** This FSPEC uses the midpoint DTE rounded up. SE author may prefer the lower bound (`recommended_dte_low`) as a more conservative anchor. Clarification needed.

---

## FSPEC-WHEEL-04: CSP Strike Selection Logic

**Linked requirements:** REQ-TRADE-01, REQ-TRADE-02

**Purpose:** Define the multi-step `CspAgent` flow from chain fetch through deterministic pre-filtering to LLM selection, including progressive relaxation when no strike meets all filters and the exact boundary between deterministic rules and LLM judgment.

**Actors:**
- `CspAgent` (`csp_agent.py`)
- `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (Phase 1 data tools)
- `WheelCandidateReport` (from Phase 2, or config defaults if Phase 2 is skipped)
- LLM (receives only the pre-filtered strike candidates)
- `CspDecision` schema (`schemas.py`)

**Behavioural Flow:**

**Stage 1 — Data fetch:**
1. Receive input: ticker, `curr_date`, analyst reports, `WheelCandidateReport` (or wheel config defaults), wheel configuration.
2. Determine DTE bounds: use `WheelCandidateReport.recommended_dte_range` if available; otherwise use `[config["wheel"]["recommended_dte_low"], config["wheel"]["recommended_dte_high"]]` (default `[28, 45]` calendar days).
3. Call `get_options_chain(ticker, curr_date)` to retrieve all available put options within the DTE window.
4. Call `get_next_earnings_date(ticker, curr_date)` to retrieve the next earnings date.

**Stage 2 — Deterministic pre-filter (no LLM involvement):**
5. For each put strike in the chain, call `get_options_greeks(ticker, curr_date, expiry_date, strike, "put")` to obtain Delta.
6. **Filter A — Delta range:** Reject any put strike whose absolute Delta is outside `[target_csp_delta_low, target_csp_delta_high]` (config, default `[0.20, 0.30]`). Boundary values are inclusive (a strike with `abs(delta) == 0.20` is retained).
7. **Filter B — Earnings clearance:** Reject any expiration date where the next earnings date falls on or before that expiration date (i.e., `earnings_date <= expiration_date`). This enforces a hard earnings exclusion per REQ-DATA-04.
8. **Filter C — Minimum annualised yield:** Compute `annualised_yield_pct = (mid_premium / strike) × (365 / dte) × 100` for each remaining candidate. Reject any strike where `annualised_yield_pct < min_annualised_yield_pct` (config, default 12.0%).

Filters are applied in order A → B → C. A strike must pass all three to be presented to the LLM.

**Stage 3 — Progressive relaxation (when no strike passes all filters):**
9. If the filtered candidate list is empty after Stage 2:
   - 9a. **Relaxation attempt 1 — drop Filter C:** Re-run with only Filters A and B. If candidates exist, note `"yield_filter_relaxed"` in the output and present these to the LLM.
   - 9b. **Relaxation attempt 2 — drop Filter B also:** Re-run with only Filter A. If candidates exist, note `"earnings_filter_relaxed"` in the output and present these to the LLM.
   - 9c. **Relaxation attempt 3 — nearest Delta match:** If Filter A itself eliminates all strikes, select the single strike with the absolute Delta closest to the midpoint of `[target_csp_delta_low, target_csp_delta_high]`. Populate `CspDecision` with `tradeable = True` and the note `"No strike matches Delta target; nearest available: {delta}"`. Present only this strike to the LLM.
   - 9d. **Earnings hard block:** If after relaxation attempts 1–3 the only remaining candidates all straddle an earnings date, return `CspDecision` with `tradeable = False` and `rejection_reason = "All suitable expirations overlap earnings"`. The LLM is not called.

**Stage 4 — LLM selection:**
10. Present the filtered (or relaxed) candidate strikes to the LLM along with: the analyst reports, the `WheelCandidateReport` rationale, and any relaxation notes from Stage 3.
11. The LLM selects one strike from the presented candidates and produces a `CspDecision`. The LLM may not select a strike that was not in the presented list.
12. Validate the LLM's output against the `CspDecision` schema. If schema validation fails, retry once; if the second attempt fails, return `CspDecision` with `tradeable = False` and `rejection_reason = "Schema validation failed after retry"`.

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
- **Schema validation fails twice:** Return `tradeable = False`, `rejection_reason = "Schema validation failed after retry"`.
- **Phase 2 skipped (no `WheelCandidateReport`):** Use config defaults for DTE range and Delta range. This is the specified fallback path and is a valid production scenario.

**Acceptance Tests:**

*Who:* Agent
*Given:* A valid approved candidate with chain data
*When:* CspAgent runs
*Then:* Returns a `CspDecision` with `tradeable = True`, `strike` populated, and `annualised_yield_pct >= min_annualised_yield_pct`.
(Covers REQ-TRADE-01 AC1)

*Who:* Agent
*Given:* No strike in the chain meets the Delta target (Filter A eliminates all)
*When:* CspAgent runs
*Then:* Returns `CspDecision` with `tradeable = True` and `rationale` contains `"No strike matches Delta target; nearest available: {delta}"`.
(Covers REQ-TRADE-01 AC2)

*Who:* Agent
*Given:* All acceptable expirations straddle an earnings date
*When:* CspAgent runs
*Then:* Returns `tradeable = False`, `rejection_reason = "All suitable expirations overlap earnings"`.
(Covers REQ-TRADE-01 AC3)

*Who:* System
*Given:* Target Delta range is `[0.15, 0.25]` in config
*When:* The deterministic strike candidate filter function runs (unit test, mocked LLM)
*Then:* Filter rejects any strike whose `abs(put_delta)` is outside [0.15, 0.25] before presenting options to the LLM.
(Covers REQ-TRADE-01 AC4a)

*Who:* System
*Given:* `CspDecision` is produced with `tradeable = True`
*When:* `annualised_yield_pct` is validated
*Then:* Value matches `(mid_premium / strike) × (365 / dte) × 100` within 0.01%.
(Covers REQ-TRADE-02 AC3)

**Open Questions:**
- **Relaxation priority between Filters B and C:** This FSPEC specifies relaxation order C then B (drop yield first, then drop earnings clearance). The REQ does not specify this order explicitly. SE author must confirm the intended priority — dropping earnings clearance before yield may be unacceptable from a risk standpoint.
- **LLM retry on schema validation failure:** The REQ does not specify retry count. This FSPEC specifies one retry (two total attempts). SE author should confirm or adjust.

---

## FSPEC-WHEEL-05: Covered Call Strike Selection Logic

**Linked requirements:** REQ-TRADE-03, REQ-TRADE-04

**Purpose:** Define the `CcAgent` flow for selecting a covered call strike after put assignment, including the cost-basis-anchored strike constraint and the "stock below cost basis" branch.

**Actors:**
- `CcAgent` (`cc_agent.py`)
- `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (Phase 1 data tools)
- `WheelPosition` (from position tracker — provides cost basis and assignment details)
- LLM (receives only pre-filtered call candidates)
- `CcDecision` schema (`schemas.py`)

**Behavioural Flow:**

**Stage 1 — Data fetch:**
1. Receive input: ticker, `curr_date`, analyst reports, `WheelPosition` (with `csp_strike`, `csp_premium_received`, `cost_basis_per_share`), wheel configuration.
2. Compute `cost_basis = cost_basis_per_share` from `WheelPosition` (which equals `csp_strike − csp_premium_received`).
3. Fetch current spot price from yfinance.
4. **Branch — stock below cost basis:**
   - 4a. If `spot_price < cost_basis`: set `strike_above_cost_basis = False`. Populate `CcDecision` with `tradeable = False` (or `tradeable = True` with strong warning at LLM's discretion — see Business Rules). Set `rejection_reason` to a non-empty string noting below-cost-basis risk. Skip to Stage 4 (LLM selection is still invoked, but with the warning note in the prompt).
   - 4b. If `spot_price >= cost_basis`: set `strike_above_cost_basis = True`. Continue to Stage 2.
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
    - 13c. **No call strikes above cost basis meet Delta:** Return `tradeable = False`, `rejection_reason` non-empty. (Covers REQ-TRADE-03 AC3) LLM is not called.
    - 13d. **Earnings hard block:** Same as FSPEC-WHEEL-04 step 9d — if all remaining candidates straddle earnings, return `tradeable = False`.

**Stage 4 — LLM selection:**
14. Present the filtered (or relaxed) candidates to the LLM with analyst reports, `WheelPosition` context, and any relaxation or warning notes.
15. The LLM selects one call strike and produces a `CcDecision`.
16. Validate against the `CcDecision` schema. Retry once on failure; after two failures return `tradeable = False`.

**Stage 5 — Output assembly:**
17. Compute derived fields deterministically: `annualised_yield_on_cost_pct`, `upside_to_strike_pct`, `strike_above_cost_basis`.
18. Set `earnings_clear` based on the selected expiration.
19. Populate `assigned_at = WheelPosition.csp_strike`, `cost_basis = WheelPosition.cost_basis_per_share`.
20. Return the completed `CcDecision`.

**Business Rules:**
- Filter A (strike ≥ cost basis) is always applied and cannot be relaxed. The strike must be at or above cost basis to be presented to the LLM.
- When `spot_price < cost_basis`, the result is always `tradeable = False` with a non-empty `rejection_reason` noting the below-cost-basis risk. The LLM is not called in this branch.
- `strike_above_cost_basis` is a computed boolean: `strike >= cost_basis`. It is not set by the LLM.
- `delta` in `CcDecision` is the call delta as a positive value (e.g., `0.25`).
- `annualised_yield_on_cost_pct = (mid_premium / cost_basis) × (365 / dte) × 100`. The denominator is `cost_basis`, not `strike` (this differs from CSP yield computation).
- `upside_to_strike_pct = (strike − spot_price) / spot_price × 100`.
- DTE and annualisation always use calendar days with 365-day year.
- Relaxation drops filters in order D → C → fallback (no relaxation of Filters A or B).
- `assigned_at` is the CSP strike from the prior `WheelPosition`. `cost_basis` is `assigned_at − csp_premium_received`. These are sourced from the `WheelPosition` record, not computed by the LLM.

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

- **`spot_price < cost_basis`:** `tradeable = False`, `rejection_reason` non-empty noting below-cost-basis risk. `strike_above_cost_basis = False`. (Covers REQ-TRADE-03 AC2)
- **No call strikes above cost basis meet Delta target:** `tradeable = False`, `rejection_reason` non-empty. (Covers REQ-TRADE-03 AC3)
- **`cost_basis` is zero or negative (data integrity error):** Return `tradeable = False`, `rejection_reason = "Invalid cost basis: {cost_basis}"`.
- **`WheelPosition` is missing or incomplete:** Return `tradeable = False`, `rejection_reason = "Missing position data"`. CcAgent requires a valid `WheelPosition`.
- **`get_options_greeks` errors on a candidate:** That candidate is silently excluded.

**Acceptance Tests:**

*Who:* Agent
*Given:* Cost basis is $140, current price is $145
*When:* CcAgent runs
*Then:* Selected `CcDecision.strike >= 140.0`.
(Covers REQ-TRADE-03 AC1)

*Who:* Agent
*Given:* Current spot price is below cost basis
*When:* CcAgent runs
*Then:* `CcDecision.strike_above_cost_basis == False` and `rejection_reason` is non-empty noting below-cost-basis risk.
(Covers REQ-TRADE-03 AC2)

*Who:* Agent
*Given:* No call strikes above cost basis meet the Delta target
*When:* CcAgent runs
*Then:* `CcDecision.tradeable == False` and `rejection_reason` is non-empty.
(Covers REQ-TRADE-03 AC3)

*Who:* System
*Given:* `CcDecision` is produced with `tradeable = True`
*When:* `strike_above_cost_basis` is validated
*Then:* `strike_above_cost_basis == (CcDecision.strike >= CcDecision.cost_basis)`.
(Covers REQ-TRADE-04 AC1)

**Open Questions:**
- **Below-cost-basis branch — should `tradeable` always be `False`?** This FSPEC sets `tradeable = False` unconditionally when `spot_price < cost_basis` and the LLM is not called. The REQ (AC2) says `strike_above_cost_basis = False` and `rejection_reason` is non-empty, but does not explicitly say `tradeable = False`. SE author must confirm whether the LLM should have any role in the below-cost-basis path (e.g., could it still recommend a strike if the trader accepts the risk consciously?).
- **CC DTE defaults:** The REQ description mentions "21–45 DTE" for CC (vs "30–45 DTE" for CSP) but the config table only shows one shared `recommended_dte_low = 28`. SE author should confirm whether CC uses the same DTE bounds as CSP or a distinct set.

---

## FSPEC-WHEEL-06: Roll/Hold/Close Decision Logic

**Linked requirements:** REQ-LIFE-03, REQ-LIFE-04

**Purpose:** Define the `RollCheckAgent` rule-evaluation flow — the priority order of the five rules, simultaneous-firing behaviour, the ROLL vs CLOSE criterion on breach, and how `trigger_reason` is assigned.

**Actors:**
- `RollCheckAgent` (`roll_agent.py`)
- `get_options_chain`, `get_options_greeks`, `get_next_earnings_date` (Phase 1 data tools)
- Existing analyst reports (current run)
- `WheelPosition` (from position tracker)
- `RollDecision` schema (`schemas.py`)

**Behavioural Flow:**

1. `RollCheckAgent` receives: `WheelPosition`, `curr_date`, current analyst reports, and the current options chain for the open position.
2. Determine the open contract's current market value: call `get_options_greeks` or read from the current chain to obtain `current_contract_value` (use `mid_premium` of the current position on the chain).
3. Compute `current_value_pct_of_premium = (current_contract_value / original_premium_received) × 100`.
4. Compute `current_dte` = calendar days from `curr_date` to the open contract's expiration date.
5. Evaluate the five rules in strict priority order (Rule 1 through Rule 5). Each rule is evaluated regardless of whether a prior rule fired.

**Rule evaluation:**

- **Rule 1 — Profit capture:** If `current_value_pct_of_premium <= take_profit_pct` (config, default 50): Rule 1 fires with `trigger_reason = "profit_capture"`, proposed `action = "HOLD"`.
- **Rule 2 — DTE:** If `current_dte <= dte_to_roll` (config, default 21): Rule 2 fires with `trigger_reason = "dte_rule"`, proposed `action = "ROLL"`.
- **Rule 3 — Breach:** For CSP positions only: if the current spot price is ≥ 15% below the CSP strike:
  - 3a. If `current_value_pct_of_premium >= 50`: Rule 3 fires with `trigger_reason = "breach_rule_roll"`, proposed `action = "ROLL"`.
  - 3b. If `current_value_pct_of_premium < 50`: Rule 3 fires with `trigger_reason = "breach_rule_close"`, proposed `action = "CLOSE"`.
  - The 15% threshold is: `spot_price <= csp_strike × 0.85`.
- **Rule 4 — Earnings:** Call `get_next_earnings_date(ticker, curr_date)`. If the next earnings date falls within the remaining DTE (i.e., `earnings_date <= expiration_date`) AND the position is not "deep OTM":
  - "Deep OTM" for a CSP is defined as `abs(current_delta) < 0.10`.
  - 4a. If not deep OTM: Rule 4 fires with `trigger_reason = "earnings_rule"`, proposed `action = "CLOSE"`.
  - 4b. If deep OTM: Rule 4 does not fire (the position is considered safe through earnings).
- **Rule 5 — Analyst update:** If the latest analyst consensus has changed from bullish (prior run) to bearish (current run): Rule 5 fires with `trigger_reason = "analyst_update"`, proposed `action = "CLOSE"`.

6. **Multi-rule firing — final action determination:**

After all five rules are evaluated, determine the final `action` and `trigger_reason` as follows:

Priority order for `trigger_reason` (highest to lowest): **Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1**.

- If Rule 3 fired: final `action` and `trigger_reason` come from Rule 3 (either `"breach_rule_roll"` + `ROLL` or `"breach_rule_close"` + `CLOSE`).
- Else if Rule 5 fired: final `action = "CLOSE"`, `trigger_reason = "analyst_update"`.
- Else if Rule 4 fired: final `action = "CLOSE"`, `trigger_reason = "earnings_rule"`.
- Else if Rule 2 fired: final `action = "ROLL"`, `trigger_reason = "dte_rule"`.
- Else if Rule 1 fired: final `action = "HOLD"`, `trigger_reason = "profit_capture"`.
- If no rule fired: final `action = "HOLD"`, `trigger_reason = "profit_capture"` (default — the position is within normal parameters).

7. **`ROLL` action — new contract specification:** When the final action is `ROLL`, determine `new_strike`, `new_expiration`, and `new_dte`:
   - Target the next standard expiration at least `dte_to_roll` calendar days beyond the current expiration.
   - For a strike-selection-on-roll: target the same Delta range as the original trade type (CSP → `[target_csp_delta_low, target_csp_delta_high]`; CC → `[target_cc_delta_low, target_cc_delta_high]`).
   - Compute `estimated_debit_or_credit`: `new_mid_premium − current_contract_value` (positive = credit received, negative = debit paid).
8. Assemble and return `RollDecision` with all required fields.

**Business Rules:**
- All five rules are always evaluated. There is no early-exit.
- When multiple rules fire, the priority order (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1) determines the final `action` and `trigger_reason`. Only one `trigger_reason` appears in the output.
- Rule 3 (Breach) applies only to CSP positions (`wheel_phase == "csp_open"`). For CC positions (`wheel_phase == "cc_open"`), Rule 3 is skipped.
- Rule 1 (Profit capture) fires when `current_value_pct_of_premium <= take_profit_pct`. When Rule 1 fires alone (no higher-priority rule fires), the action is `"HOLD"` — the position has hit its profit target and no action beyond monitoring is required. If the trader chooses to close, that is a separate manual decision; the agent recommends HOLD at this stage.
- The 15% breach threshold for Rule 3 is not configurable in Phase 1. It is the literal value `0.85` applied to the CSP strike.
- "Deep OTM" for the earnings rule (Rule 4) is defined as `abs(current_delta) < 0.10`. This boundary is exclusive (`< 0.10`; a delta of exactly `0.10` is not deep OTM).
- `trigger_reason` must be exactly one of the six Literal values in the `RollDecision` schema. No free-text values are permitted.
- `new_strike`, `new_expiration`, and `new_dte` are populated only when `action == "ROLL"`. They are `None` for `HOLD` and `CLOSE` actions.
- `estimated_debit_or_credit` is populated only when `action == "ROLL"`. It is `None` for `HOLD` and `CLOSE`.

**Input / Output:**

Input:
- `WheelPosition` (open position details including `csp_strike`, `csp_premium_received`, `cc_strike`, `cc_premium_received` as applicable)
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
| `rationale` | `str` | Always |

**Edge Cases and Error Scenarios:**

- **No rule fires:** Return `action = "HOLD"`, `trigger_reason = "profit_capture"` (default). The position is within normal parameters.
- **`get_next_earnings_date` returns no upcoming earnings:** Rule 4 is not evaluated (no earnings event detected). Evaluation continues with remaining rules.
- **`current_delta` is unavailable (Greeks fetch fails):** Rule 4's deep-OTM check cannot be performed. Rule 4 fires conservatively (treat as NOT deep OTM, meaning `CLOSE` is recommended if earnings is within DTE).
- **`WheelPosition` is for `wheel_phase == "cc_open"`:** Rule 3 is skipped entirely. `current_strike` is `cc_strike`; `original_premium_received` is `cc_premium_received`.
- **`original_premium_received` is zero (data integrity error):** Return `action = "HOLD"`, add note `"Cannot compute value pct: original premium is zero"` to rationale.
- **Both Rule 1 and Rule 2 fire:** Rule 2 takes precedence (`dte_rule` > `profit_capture` in priority). Final `action = "ROLL"`, `trigger_reason = "dte_rule"`.

**Acceptance Tests:**

*Who:* Agent
*Given:* Premium is at 50% of received value and `current_dte = 30`
*When:* RollCheckAgent runs
*Then:* `RollDecision.action == "HOLD"` and `trigger_reason == "profit_capture"`.
(Covers REQ-LIFE-03 AC1)

*Who:* Agent
*Given:* `current_dte = 18` (≤ `dte_to_roll = 21`)
*When:* RollCheckAgent runs
*Then:* `action == "ROLL"`, `trigger_reason == "dte_rule"`, and `new_expiration` is populated.
(Covers REQ-LIFE-03 AC2)

*Who:* Agent
*Given:* Stock dropped ≥ 15% below CSP strike AND `current_value_pct_of_premium >= 50`
*When:* RollCheckAgent runs
*Then:* `action == "ROLL"` and `trigger_reason == "breach_rule_roll"`.
(Covers REQ-LIFE-03 AC3a)

*Who:* Agent
*Given:* Stock dropped ≥ 15% below CSP strike AND `current_value_pct_of_premium < 50`
*When:* RollCheckAgent runs
*Then:* `action == "CLOSE"` and `trigger_reason == "breach_rule_close"`.
(Covers REQ-LIFE-03 AC3b)

*Who:* Agent
*Given:* Analyst consensus changed from bullish to bearish
*When:* RollCheckAgent runs
*Then:* `action == "CLOSE"` and `trigger_reason == "analyst_update"`.
(Covers REQ-LIFE-03 AC4)

**Open Questions:**
- **Rule 1 action when profit target is hit:** The REQ AC1 specifies `action = "HOLD"` when premium is at 50% of received value with DTE = 30. This FSPEC follows the REQ. However, many wheel traders would close at 50% profit rather than hold. SE author should confirm whether `HOLD` is the correct recommendation at the 50% profit target, or whether it should be `CLOSE` with `trigger_reason = "profit_capture"`.
- **Breach threshold configurability:** The 15% breach threshold is hardcoded in this FSPEC. SE author should confirm if this should be a configurable `config["wheel"]` key for Phase 1 or a later addition.
- **Analyst consensus "changed from bullish to bearish" definition:** Rule 5 requires comparing the current analyst consensus to the prior run. This requires access to prior-run state. SE author must specify how the prior consensus is stored and retrieved (e.g., in `WheelPosition.notes`, a separate state field, or the memory log).

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
   - 3a. If `wheel_phase is None`: route to the existing first analyst node unchanged. No options nodes are visited. All existing equity-analysis flows run as before. (Covers REQ-LIFE-01 AC1)
4. **Branch — unknown value:**
   - 4b. If `wheel_phase` is a string not in the set `{"screening", "csp_open", "stock_owned", "cc_open", "cycle_complete"}`: log a warning `"Unknown wheel_phase value '{value}' — falling back to equity-only path"`, set effective routing to the equity-only path (same as 3a). (Covers REQ-LIFE-01 AC6)
5. **Branch — "screening":**
   - Route: analyst pipeline → WheelAnalyst → CspAgent. (Covers REQ-LIFE-01 AC2)
6. **Branch — "csp_open":**
   - Validate: look up open `WheelPosition` for the ticker. If none found or if `WheelPosition` does not have `csp_strike` set: raise `WheelStateError("No open CSP position found for phase 'csp_open'")`. (Related to REQ-LIFE-01 AC5)
   - Route: RollCheckAgent for the open CSP.
7. **Branch — "stock_owned":**
   - Route: analyst pipeline → CcAgent. CspAgent is skipped. (Covers REQ-LIFE-01 AC3)
8. **Branch — "cc_open":**
   - Validate: look up open `WheelPosition` for the ticker. If the position exists but `cc_strike` is `None`: raise `WheelStateError("No open CC position found for phase 'cc_open'")`. (Covers REQ-LIFE-01 AC5)
   - Route: RollCheckAgent for the open CC.
9. **Branch — "cycle_complete":**
   - Emit cycle summary (formatted `WheelPosition` report with `cycle_pnl` and `cycle_annualised_return_pct`).
   - Append cycle summary to `TradingMemoryLog` (per REQ-LIFE-05).
   - Reset `wheel_phase` to `"screening"` in the state and in the `WheelPosition`-derived context.
   - Create a new `WheelPosition` record with `cycle_number` incremented.

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

**Acceptance Tests:**

*Who:* System
*Given:* `wheel_phase = None`
*When:* Graph is invoked
*Then:* Existing equity pipeline runs unchanged; no options nodes are visited.
(Covers REQ-LIFE-01 AC1)

*Who:* System
*Given:* `wheel_phase = "screening"`
*When:* Graph is invoked
*Then:* Analyst pipeline + WheelAnalyst + CspAgent nodes are visited.
(Covers REQ-LIFE-01 AC2)

*Who:* System
*Given:* `wheel_phase = "stock_owned"`
*When:* Graph is invoked
*Then:* CcAgent node is visited; CspAgent node is not visited.
(Covers REQ-LIFE-01 AC3)

*Who:* System
*Given:* Phase transition occurs (CSP assigned — `assignment_date` is written to `WheelPosition`)
*When:* State is updated
*Then:* `wheel_phase` in `AgentState` changes from `"csp_open"` to `"stock_owned"`.
(Covers REQ-LIFE-01 AC4)

*Who:* System
*Given:* `wheel_phase = "cc_open"` but no `WheelPosition` with `cc_strike` set exists for the ticker
*When:* Graph is invoked
*Then:* Graph raises `WheelStateError`.
(Covers REQ-LIFE-01 AC5)

*Who:* System
*Given:* `wheel_phase = "invalid_phase"`
*When:* Graph is invoked
*Then:* Graph falls back to equity-only path and logs a warning. No exception is raised.
(Covers REQ-LIFE-01 AC6)

**Open Questions:**
- **`"csp_open"` → `"stock_owned"` trigger:** The REQ specifies "CSP expires worthless OR assignment is detected." Both events are external to the system (they happen at the broker). How does the system detect these events? This FSPEC assumes the human trader manually updates `wheel_phase` in the state when assignment occurs. SE author must confirm whether there is an automated assignment-detection mechanism or whether this is always a manual state update.
- **`"cc_open"` → `"stock_owned"` on CC expiry worthless:** After a CC expires worthless, the transition table shows the state returns to `"stock_owned"` for a new CC selection. How is this triggered? Same question as above — manual or automated? SE author to clarify.
- **`cycle_complete` → `"screening"` reset:** After emitting the cycle summary, `wheel_phase` resets to `"screening"`. Does this happen within the same graph invocation, or does the next invocation start in `"screening"`? This FSPEC specifies that the reset happens within the same invocation (the router sets `wheel_phase = "screening"` in the outbound state). SE author to confirm.
