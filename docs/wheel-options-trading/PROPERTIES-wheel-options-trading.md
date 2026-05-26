# PROPERTIES — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | TE-Author (Claude Code) |
| **Version** | 0.2.0 |
| **Created** | 2026-05-26 |
| **Upstream** | REQ-wheel-options-trading.md v0.3.0 → FSPEC-wheel-options-trading.md v0.3.0 → TSPEC-wheel-options-trading.md v0.2.0 → PLAN-wheel-options-trading.md v0.3.0 → DECISIONS-wheel-options-trading.md v0.3.0 → **PROPERTIES** |
| **Downstream** | `IMPL tests` |
| **Cross-Reviews** | `CROSS-REVIEW-product-manager-PROPERTIES.md`, `CROSS-REVIEW-software-engineer-PROPERTIES.md` |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.2.0 | 2026-05-26 | Address PM cross-review (F-01 through F-06) and SE cross-review (F-01 through F-08): add PROP-SCREEN-07/08/09 (rejection reason substrings), PROP-DATA-17 (shortened lookback), fix PROP-SCREEN-02 source attribution, add PROP-TRADE-14 (nearest-delta relaxation note), add PROP-SCREEN-10/11 (progressive relaxation), add PROP-SCREEN-06 (all-five-criteria positive approval), add PROP-ROUTE-10 (csp_open guard), add PROP-LIFE-12 (prior_analyst_bias persistence); fix PROP-LIFE-07 test method, fix PROP-DATA-08 delta tolerance to ±0.0005, fix PROP-SCREEN-06 bind_structured test method, add PROP-DATA-13 precondition note, fix PROP-LIFE-03 callable, fix PROP-FALLBACK-13 test method to ast.parse; also fix stale "18+" count in PROP-CONFIG-01, fix PROP-DATA-02 boundary wording, rename old PROP-SCREEN-06/07/08 to PROP-SCREEN-12/13/14 to make room for new numbers |
| 0.1.0 | 2026-05-26 | Initial PROPERTIES document |

---

## 1. Overview

This document defines the testable properties (invariants, state-machine rules, mathematical properties, and interface contracts) that the Wheel Options Trading feature must satisfy. Each property maps to at least one source requirement or TSPEC section and specifies how it is verified.

Properties are organised into seven domains:

| Domain | Prefix | Covers |
|---|---|---|
| Data layer | PROP-DATA | `y_finance_options.py` functions, IV computation, BSM Greeks, earnings date tool |
| Screening | PROP-SCREEN | `WheelAnalyst`, `WheelCandidateReport` schema |
| Trade engine | PROP-TRADE | `CspAgent`, `CcAgent`, `CspDecision`, `CcDecision` schemas |
| Lifecycle | PROP-LIFE | State machine, `WheelPosition` persistence, `RollCheckAgent`, `RollDecision` |
| Routing | PROP-ROUTE | Graph router `route_wheel_phase()`, equity passthrough |
| Fallback | PROP-FALLBACK | Structured output three-layer fallback across all four agents |
| Configuration | PROP-CONFIG | `config["wheel"]` keys, env var overrides |

---

## 2. PROP-DATA — Data Layer Properties

### PROP-DATA-01

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-01 |
| **Description** | `get_options_chain` must return a formatted string (not raise an exception) in all scenarios: valid ticker with options, empty chain, network error (`HTTPError`, `ConnectionError`). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-01 AC2, AC5, AC6; FSPEC-WHEEL-01; TSPEC §2.1.1 |
| **Test method** | Mock `yf.Ticker` to (a) return a populated DataFrame, (b) return an empty DataFrame, (c) raise `HTTPError`. Assert each call returns a non-empty `str`. Assert network-error return contains the substring `"Error fetching options chain for"`. Assert empty-chain return contains `"No options chain available for"`. |

---

### PROP-DATA-02

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-02 |
| **Description** | When `get_options_chain` is called with a specific `expiry_date`, it must return chain data only for that expiration. When called without `expiry_date`, it must return chain data only for expirations within `[target_date, target_date + options_lookforward_days]` (inclusive). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-01 AC1, AC4; FSPEC-WHEEL-01; TSPEC §2.1.1 |
| **Test method** | Use `option_chain_fixture` with three expirations: one inside the window, one exactly on the boundary, one outside. (a) Assert exactly two expirations appear (inside and boundary); assert the outside expiration does NOT appear. (b) Assert only the requested expiration appears when `expiry_date` is provided. |

---

### PROP-DATA-03

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-03 |
| **Description** | `get_iv_metrics` must always return `iv_rank` in `[0, 100]` and `iv_percentile` in `[0, 100]` — no `NaN`, no values outside these bounds. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-02 AC1; FSPEC-WHEEL-02 step 8 (clamp rule); TSPEC §2.1.2 step 12 |
| **Test method** | Inject `iv_series` via the test seam. Test: (a) a normal series with realistic variance; (b) a series where `current_vol` equals `min_vol_lookback` (expect `iv_rank ≈ 0`); (c) a series where `current_vol` equals `max_vol_lookback` (expect `iv_rank ≈ 100`). Assert `0 <= iv_rank <= 100` and `0 <= iv_percentile <= 100` for all three. |

---

### PROP-DATA-04

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-04 |
| **Description** | `get_iv_metrics` must set `iv_environment = "elevated"` when `iv_rank >= 50`, `"normal"` when `25 <= iv_rank < 50`, and `"compressed"` when `iv_rank < 25`. Boundary cases: `iv_rank == 50` → `"elevated"`; `iv_rank == 25` → `"normal"`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-02 AC3, AC4; FSPEC-WHEEL-02 step 9 (boundary rules); TSPEC §2.1.2 step 13 |
| **Test method** | Inject `iv_series` with crafted values to produce `iv_rank` of exactly 49.9, 50.0, 25.0, 24.9, and ≥ 75. Assert `iv_environment` in each case. All five sub-cases must pass. |

---

### PROP-DATA-05

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-05 |
| **Description** | When the zero-variance sentinel fires (`max_vol_lookback == min_vol_lookback`), `get_iv_metrics` must return `iv_rank = 50.0`, `iv_percentile = 50.0`, and a report string containing the exact text `"IV range is flat — rank set to neutral 50"`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-02 AC5; FSPEC-WHEEL-02 step 7a; TSPEC §2.1.2 step 11; ADR-WHEEL-01 (zero-variance disclosure) |
| **Test method** | Inject `iv_series=[0.20] * 100` (all values equal). Assert `iv_rank == 50.0`, `iv_percentile == 50.0`, and the returned report string contains `"IV range is flat — rank set to neutral 50"` (exact substring, case-sensitive). |

---

### PROP-DATA-06

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-06 |
| **Description** | When the zero-variance sentinel fires, `WheelCandidateReport.iv_assessment` must contain the flat-volatility note verbatim (`"IV range is flat — rank set to neutral 50"`). The CLI must not present a sentinel-generated `iv_environment = "normal"` result without this disclosure. |
| **Type** | Integration |
| **Level** | P1 (should-pass) |
| **Source** | ADR-WHEEL-01 (zero-variance sentinel disclosure); REQ-SCREEN-02 (`iv_assessment` field) |
| **Test method** | Mock `get_iv_metrics` to return a zero-variance result (flat series). Run `WheelAnalyst` with mocked LLM. Assert `WheelCandidateReport.iv_assessment` contains `"IV range is flat — rank set to neutral 50"`. |

---

### PROP-DATA-07

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-07 |
| **Description** | `get_iv_metrics` must NOT call `yf.Ticker` when `iv_series` is provided (test seam isolation). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-02 description (injectable seam); FSPEC-WHEEL-02 step 2a; TSPEC §2.1.2 ("Do NOT call yf.Ticker when iv_series is not None") |
| **Test method** | Patch `yf.Ticker` to raise `AssertionError`. Call `get_iv_metrics(ticker, date, iv_series=[0.20]*50)`. Assert no `AssertionError` is raised (i.e., `yf.Ticker` was not called). |

---

### PROP-DATA-08

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-08 |
| **Description** | `get_options_greeks` BSM numerical anchor: given `S=100, K=100, r=0.05, σ=0.20, T=30/365`, the returned `Delta_put` must be approximately `−0.4602` (tolerance ±0.0005). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | TSPEC §2.1.3 BSM numeric verification ("tolerance ±0.0005 on Delta"); REQ-DATA-03 |
| **Test method** | Call `get_options_greeks` using test seams `_spot_price=100.0, _risk_free_rate=0.05, _sigma=0.20` for a put option with `strike=100`, `expiry_date = curr_date + 30 days`, `option_type="put"`. Parse the returned string for the Delta value. Assert `abs(delta - (-0.4602)) <= 0.0005`. |

---

### PROP-DATA-09

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-09 |
| **Description** | `get_options_greeks` BSM numerical anchor: for the same canonical inputs (`S=100, K=100, r=0.05, σ=0.20, T=30/365`), `Theta_put_daily` must be approximately `−0.0314` (tolerance ±0.005). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | TSPEC §2.1.3 BSM numeric verification (Theta tolerance ±0.005) |
| **Test method** | Same invocation as PROP-DATA-08. Parse returned string for Theta daily value. Assert `abs(theta_daily - (-0.0314)) <= 0.005`. |

---

### PROP-DATA-10

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-10 |
| **Description** | `get_options_greeks` must return a Delta in `(−0.55, −0.45)` for an ATM put option. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-03 AC2 |
| **Test method** | Call with `_spot_price = _strike = 100.0`, `_sigma=0.20`, `T=30/365` (via `expiry_date = curr_date + 30 days`), `option_type="put"`. Assert `-0.55 < delta < -0.45`. |

---

### PROP-DATA-11

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-11 |
| **Description** | `get_options_greeks` must return the error string `"Cannot compute Greeks for expired option"` when `dte == 0`, and `"Cannot compute Greeks: option has already expired"` when `dte < 0`. Neither should raise an exception. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-03 AC3, AC5; TSPEC §2.1.3 |
| **Test method** | Call with `expiry_date == curr_date` (dte=0) and `expiry_date < curr_date` (dte<0). Assert returns are error strings containing the specified substrings. Assert no exception is raised in either case. |

---

### PROP-DATA-12

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-12 |
| **Description** | `get_options_greeks` must return a validation error string when `option_type` is not `"put"` or `"call"`, and an error string when `sigma == 0`. Neither should raise an exception. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-03 AC4, AC6; TSPEC §2.1.3 |
| **Test method** | Call with `option_type="future"` and with `_sigma=0`. Assert each returns a non-empty error string and does not raise. |

---

### PROP-DATA-13

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-13 |
| **Description** | When `^IRX` is unavailable, `get_options_greeks` must fall back to `config["wheel"]["risk_free_rate_static"]` and include the note `"using static risk-free rate"` in the output. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-03 AC7; TSPEC §2.1.3 (risk-free rate fallback) |
| **Test method** | **Precondition:** set `config["wheel"]["risk_free_rate_source"] = "yfinance_irx"` (NOT `"static"`) before running the test to ensure the `^IRX` fetch path is exercised rather than the static shortcut. Use `_risk_free_rate=None` (so the test seam is not engaged), mock `yf.Ticker("^IRX")` to raise `Exception`. Assert the returned string contains `"using static risk-free rate"` and the computation completes without raising. |

---

### PROP-DATA-14

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-14 |
| **Description** | `get_next_earnings_date` must return `within_options_cycle=True` if and only if `next_earnings_date <= front_month_expiry`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-04 AC2; TSPEC §2.1.4 (`within_options_cycle` computation) |
| **Test method** | Mock `yf.Ticker.calendar` with an earnings date 10 days out. Mock `yf.Ticker.options` to return a front-month expiry 30 days out. Assert `within_options_cycle == True`. Change mock so earnings date is 35 days out (beyond front-month expiry). Assert `within_options_cycle == False`. |

---

### PROP-DATA-15

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-15 |
| **Description** | The four options tools (`get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date`) in `options_data_tools.py` must NOT import from `y_finance_options.py` directly. All calls must pass through `route_to_vendor()` in `interface.py`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-05; FSPEC-WHEEL-01 business rules; TSPEC §2.2 |
| **Test method** | Inspect module imports: assert `options_data_tools.py` does not contain any `from tradingagents.dataflows.y_finance_options import` statement. Set `config["data_vendors"]["options_data"] = "alpha_vantage"` and call each tool; assert return is `"not implemented"` (stub), confirming routing went through `interface.py`. |

---

### PROP-DATA-16

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-16 |
| **Description** | `get_iv_metrics` must return an error string (not raise) when `iv_series=[]` (empty list). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-02 edge case ("iv_series provided as empty list"); TSPEC §2.1.2 ("If `len(iv_series) == 0`: return error string") |
| **Test method** | Call `get_iv_metrics(ticker, date, iv_series=[])`. Assert returns `"Provided iv_series is empty"` (exact string). |

---

### PROP-DATA-17

| Field | Value |
|---|---|
| **Property ID** | PROP-DATA-17 |
| **Description** | When fewer than `lookback_days` trading days of OHLCV data are available (`n_available < lookback_days`), `get_iv_metrics` must use the available data only and the returned string must contain a note indicating the shortened lookback (e.g., containing `"days"` or `"lookback"` or `"available"`). The computation must still complete and return valid `iv_rank` and `iv_percentile` values in `[0, 100]`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-DATA-02 AC2; FSPEC-WHEEL-02 step 3a; TSPEC §2.1.2 step 14 ("Include `'Lookback shortened to {n_available} trading days'` when `n_available < lookback_days`") |
| **Test method** | Call `get_iv_metrics(ticker, date, lookback_days=252, iv_series=<series of length 30>)` (injecting a short series via the test seam). Assert the returned string contains at least one of the substrings `"days"`, `"lookback"`, or `"available"` (case-insensitive). Assert the returned string also contains `iv_rank` and `iv_percentile` values that are numeric and in `[0, 100]`. Assert no exception is raised. |

---

## 3. PROP-SCREEN — WheelAnalyst / WheelCandidateReport Properties

### PROP-SCREEN-01

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-01 |
| **Description** | Every `WheelCandidateReport` instance returned by `WheelAnalyst` must pass `WheelCandidateReport.model_validate()` without raising `ValidationError`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-02 AC1; TSPEC §3.3 |
| **Test method** | Mock `invoke_structured_or_freetext` to return valid JSON matching the schema. Run `WheelAnalyst` node. Deserialise the `AgentState["wheel_candidate_report"]` string with `WheelCandidateReport.model_validate_json()`. Assert no `ValidationError` is raised. |

---

### PROP-SCREEN-02

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-02 |
| **Description** | When `approved=True`, `recommended_strike_range` must have exactly two elements, both `> 0`, with `strike_range[0] < strike_range[1]`. The `model_validator` in `WheelCandidateReport` enforces this at construction time. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-03 step 8c; TSPEC §3.3 `model_validator` |
| **Test method** | (a) Construct `WheelCandidateReport(approved=True, recommended_strike_range=[95.0, 100.0], ...)` — assert no error. (b) Attempt to construct with `approved=True, recommended_strike_range=[0.0, 0.0]` — assert `ValidationError` is raised. (c) Attempt with `approved=True, recommended_strike_range=[105.0, 100.0]` (low > high) — assert `ValidationError` is raised. |

---

### PROP-SCREEN-03

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-03 |
| **Description** | When `approved=True`, `rejection_reason` must be `None`. When `approved=False`, `rejection_reason` must be a non-empty string. The `model_validator` in `WheelCandidateReport` enforces this at construction time. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-02 AC2, AC3; TSPEC §3.3 `model_validator` |
| **Test method** | (a) Construct `WheelCandidateReport(approved=True, rejection_reason=None, ...)` — assert no error. (b) Construct `WheelCandidateReport(approved=False, rejection_reason="IV too low", ...)` — assert no error. (c) Attempt to construct with `approved=False, rejection_reason=None` — assert `ValidationError`. (d) Attempt with `approved=False, rejection_reason=""` — assert `ValidationError`. |

---

### PROP-SCREEN-04

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-04 |
| **Description** | `WheelCandidateReport.iv_environment` must always be one of the three enum values: `"elevated"`, `"normal"`, `"compressed"`. No other string value is accepted by the schema. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-02 schema; TSPEC §3.3 (`iv_environment: Literal["elevated", "normal", "compressed"]`) |
| **Test method** | Attempt to construct `WheelCandidateReport` with `iv_environment="high"`. Assert `ValidationError` is raised. Construct with each of the three valid values and assert no error. |

---

### PROP-SCREEN-05

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-05 |
| **Description** | When the zero-variance sentinel fired in `get_iv_metrics`, `WheelCandidateReport.iv_assessment` must contain the note `"IV range is flat — rank set to neutral 50"` verbatim. |
| **Type** | Integration |
| **Level** | P1 (should-pass) |
| **Source** | ADR-WHEEL-01 zero-variance disclosure; FSPEC-WHEEL-03 (WheelAnalyst criterion 1 uses `iv_assessment`) |
| **Test method** | Mock `get_iv_metrics` to return a result with the flat-range note included. Mock LLM to return the flat-range note in `iv_assessment`. Assert `WheelCandidateReport.iv_assessment` contains `"IV range is flat — rank set to neutral 50"`. |

---

### PROP-SCREEN-06

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-06 |
| **Description** | When all five WheelAnalyst screening criteria pass (`iv_rank >= min_iv_rank`, at least one NTM strike meets liquidity constraints, earnings sufficiently clear, `spot_price <= max_wheel_stock_price`, analyst consensus is bullish/neutral), `WheelCandidateReport.approved` must be `True`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-01 AC1; FSPEC-WHEEL-03 step 7a |
| **Test method** | Mock all four data tools to return passing values (iv_rank=60, liquidity passes, no near-term earnings, spot=$200 with max=$500, investment_plan="Hold"). Mock LLM to return a `WheelCandidateReport` with `approved=True`. Run `WheelAnalyst`. Assert `WheelCandidateReport.approved == True`. |

---

### PROP-SCREEN-07

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-07 |
| **Description** | When `WheelCandidateReport.approved=False` and the rejection is due to insufficient liquidity (all near-the-money strikes have OI below threshold), `rejection_reason` must contain `"Insufficient liquidity"` (case-insensitive substring match). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-01 AC6; FSPEC-WHEEL-03 business rules |
| **Test method** | Mock `get_options_chain` to return a chain where all NTM strikes have `openInterest < min_chain_oi`. Mock LLM to return `approved=False` with a `rejection_reason` containing the required substring. Run `WheelAnalyst`. Assert `WheelCandidateReport.approved == False`. Assert `"insufficient liquidity"` appears in `rejection_reason.lower()`. |

---

### PROP-SCREEN-08

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-08 |
| **Description** | When `WheelCandidateReport.approved=False` and the rejection is due to bid-ask spread too wide (all NTM strikes have spread above `max_chain_spread_pct`), `rejection_reason` must contain `"Chain spread too wide"` (case-insensitive substring match). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-01 AC7; FSPEC-WHEEL-03 business rules |
| **Test method** | Mock `get_options_chain` to return a chain where all NTM strikes have `(ask - bid) / mid > max_chain_spread_pct / 100`. Mock LLM to return `approved=False` with a `rejection_reason` containing the required substring. Assert `"chain spread too wide"` appears in `rejection_reason.lower()`. |

---

### PROP-SCREEN-09

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-09 |
| **Description** | When `WheelCandidateReport.approved=False` and the rejection is due to stock price exceeding account affordability (`spot_price > max_wheel_stock_price`), `rejection_reason` must contain `"Stock price exceeds cash management limit"` (case-insensitive substring match). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-01 AC8; FSPEC-WHEEL-03 business rules |
| **Test method** | Mock spot price fetch to return $600 with `config["wheel"]["max_wheel_stock_price"] = 500`. Mock LLM to return `approved=False` with the required rejection substring. Assert `"stock price exceeds cash management limit"` appears in `rejection_reason.lower()`. |

---

### PROP-SCREEN-10

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-10 |
| **Description** | When the WheelAnalyst yield filter (Criterion 3 threshold) is relaxed because no candidate met the minimum yield, the approved candidate report must contain a yield-filter-relaxed note in `iv_assessment` (or `rationale`). `WheelCandidateReport.approved` must be `True` for the relaxed candidate. |
| **Type** | Unit |
| **Level** | P1 (should-pass) |
| **Source** | FSPEC-WHEEL-04 §9a (yield_filter_relaxed relaxation path); FSPEC acceptance test FSPEC-TE-08 resolution |
| **Test method** | Configure chain such that all passes Filters A and B but fail Filter C (yield too low). Run `CspAgent` (WheelAnalyst feeds into CspAgent relaxation). Assert `CspDecision.tradeable == True`. Assert `CspDecision.rationale` contains `"yield_filter_relaxed"`. |

---

### PROP-SCREEN-11

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-11 |
| **Description** | When the WheelAnalyst earnings filter is relaxed (earnings check bypassed because all Filter A+B+C candidates were eliminated), the resulting `CspDecision` must be `tradeable=True` and `rationale` must contain `"earnings_filter_relaxed"`. |
| **Type** | Unit |
| **Level** | P1 (should-pass) |
| **Source** | FSPEC-WHEEL-04 §9b (earnings_filter_relaxed relaxation path); FSPEC acceptance test FSPEC-TE-08 resolution |
| **Test method** | Configure chain such that all strikes pass Filter A but fail Filters B and C (earnings straddle + yield too low). Run `CspAgent`. Assert `CspDecision.tradeable == True`. Assert `CspDecision.rationale` contains `"earnings_filter_relaxed"`. |

---

### PROP-SCREEN-12

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-12 |
| **Description** | `WheelAnalyst` must call `bind_structured` with exactly three arguments: `(llm, WheelCandidateReport, "wheel_analyst")`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-03; TSPEC §5.1; ADR-WHEEL-04 (bind_structured three-arg contract) |
| **Test method** | Mock `bind_structured`. Call the `create_wheel_analyst(llm)` factory function. Assert `bind_structured` was called exactly once via `mock.assert_called_once_with(llm, WheelCandidateReport, "wheel_analyst")`. Do NOT use `inspect.signature` — it returns the function's own parameter types, not call arguments, and passes vacuously. |

---

### PROP-SCREEN-13

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-13 |
| **Description** | When `"wheel"` is not in `selected_analysts`, the `WheelAnalyst` node must be absent from the compiled graph, and the existing equity pipeline must run without any wheel-related state changes. |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | REQ-SCREEN-01 AC5; REQ-NFR-01; FSPEC-WHEEL-03 business rules |
| **Test method** | Build graph with `selected_analysts` not containing `"wheel"`. Invoke graph with `wheel_phase=None`. Assert `"wheel_analyst"` node is not in `workflow.nodes`. Assert output `AgentState` has no `wheel_candidate_report` key set. |

---

### PROP-SCREEN-14

| Field | Value |
|---|---|
| **Property ID** | PROP-SCREEN-14 |
| **Description** | `WheelCandidateReport.analyst_bias` must always be one of `"bullish"`, `"neutral"`, or `"bearish"`. No other value is accepted by the schema. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | TSPEC §3.3 (`analyst_bias: Literal["bullish", "neutral", "bearish"]`); FSPEC-WHEEL-03 Criterion 5 |
| **Test method** | Attempt to construct `WheelCandidateReport` with `analyst_bias="positive"`. Assert `ValidationError`. Construct with each valid value and assert no error. |

---

## 4. PROP-TRADE — CspAgent / CcAgent / Trade Schema Properties

### PROP-TRADE-01

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-01 |
| **Description** | Every `CspDecision` returned by `CspAgent` must pass `CspDecision.model_validate()` without raising `ValidationError`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-02 AC1; TSPEC §3.4 |
| **Test method** | Mock `invoke_structured_or_freetext` to return valid `CspDecision` JSON. Run `CspAgent`. Deserialise `AgentState["csp_decision"]` with `CspDecision.model_validate_json()`. Assert no `ValidationError`. |

---

### PROP-TRADE-02

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-02 |
| **Description** | Every `CcDecision` returned by `CcAgent` must pass `CcDecision.model_validate()` without raising `ValidationError`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-04 AC1; TSPEC §3.5 |
| **Test method** | Mock `invoke_structured_or_freetext` to return valid `CcDecision` JSON. Run `CcAgent`. Deserialise `AgentState["cc_decision"]` with `CcDecision.model_validate_json()`. Assert no `ValidationError`. |

---

### PROP-TRADE-03

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-03 |
| **Description** | When `CspDecision.tradeable=True`, `recommended_strike` must be `> 0` and `expiration_date` must be a valid ISO 8601 date string (`YYYY-MM-DD`). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-02 AC2; FSPEC-WHEEL-04 Stage 5 |
| **Test method** | Construct a `CspDecision(tradeable=True, strike=145.0, expiration_date="2024-06-21", ...)`. Assert `strike > 0`. Assert `datetime.strptime(expiration_date, "%Y-%m-%d")` does not raise (valid ISO date). |

---

### PROP-TRADE-04

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-04 |
| **Description** | When `CcDecision.tradeable=True`, `recommended_strike` must be `> 0` and `expiration_date` must be a valid ISO 8601 date string. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-04 AC2; FSPEC-WHEEL-05 Stage 5 |
| **Test method** | Same pattern as PROP-TRADE-03, using `CcDecision` with `tradeable=True`. |

---

### PROP-TRADE-05

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-05 |
| **Description** | When `CspDecision.tradeable=False`, `rejection_reason` must be a non-empty string. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-01 AC3; FSPEC-WHEEL-04 Stage 3 (hard blocks); TSPEC §3.4 |
| **Test method** | Construct `CspDecision(tradeable=False, rejection_reason=None, ...)`. Assert this raises `ValidationError` or that the agent enforces a non-None `rejection_reason`. Construct with `rejection_reason=""` — assert error. Construct with `rejection_reason="All suitable expirations overlap earnings"` — assert no error. |

---

### PROP-TRADE-06

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-06 |
| **Description** | When `CcDecision.tradeable=False`, `rejection_reason` must be a non-empty string. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-03 AC2, AC3; FSPEC-WHEEL-05 Stage 3 |
| **Test method** | Same pattern as PROP-TRADE-05 using `CcDecision`. |

---

### PROP-TRADE-07

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-07 |
| **Description** | `CspDecision.delta` (when `tradeable=True`) must always be a negative value in the open interval `(−1, 0)` — it is a put delta. `CspDecision.theta` (when `tradeable=True`) must always be `<= 0` — time decay is never positive. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-02 AC1; FSPEC-WHEEL-04 business rules ("delta in CspDecision is the put delta as a negative value"); TSPEC §3.4 note on sentinels |
| **Test method** | Use `option_chain_fixture`. Mock LLM to select a valid candidate. Assert `CspDecision.delta` is in `(-1, 0)` (strictly negative, strictly greater than -1). Assert `CspDecision.theta <= 0`. Note: assertions must be restricted to `tradeable=True` path; sentinel (`tradeable=False`) is exempt. |

---

### PROP-TRADE-08

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-08 |
| **Description** | `CspDecision.recommended_strike` (when `tradeable=True`) must always be `< spot_price`. A cash-secured put strike is always below the current share price. |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-01 (put selection at Delta 0.20–0.30 targets OTM strikes); FSPEC-WHEEL-04 business rules |
| **Test method** | Inject a `WheelCandidateReport` and `option_chain_fixture`. Mock LLM to return the first eligible strike from the filtered list. Assert `CspDecision.strike < spot_price`. |

---

### PROP-TRADE-09

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-09 |
| **Description** | `CcDecision.recommended_strike` (when `tradeable=True`) must always be `>= cost_basis`. A covered call must not be sold below cost basis (which would realise a loss on call-away). |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-03 AC1; FSPEC-WHEEL-05 Filter A ("strike >= cost_basis") |
| **Test method** | Inject a `WheelPosition` with `csp_strike=140, csp_premium_received=2.50` (cost_basis=137.50). Mock LLM to return the first eligible strike. Assert `CcDecision.strike >= 137.50`. |

---

### PROP-TRADE-10

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-10 |
| **Description** | `CspDecision.annualised_yield_pct` must exactly equal `(mid_premium / strike) × (365 / dte) × 100` within ±0.01% tolerance. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-02 AC3; FSPEC-WHEEL-04 business rules (formula); TSPEC §5.2 derived fields |
| **Test method** | Construct a `CspDecision` with known `mid_premium=2.50`, `strike=145.0`, `dte=35`. Expected: `(2.50/145.0) × (365/35) × 100 ≈ 17.97%`. Assert `abs(annualised_yield_pct - 17.97) <= 0.01`. |

---

### PROP-TRADE-11

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-11 |
| **Description** | `CspAgent` Filter A must reject any put strike whose `abs(delta)` is strictly outside `[target_csp_delta_low, target_csp_delta_high]`. Boundary values are inclusive: a strike with `abs(delta) == target_csp_delta_low` must be retained; a strike with `abs(delta) == target_csp_delta_high` must be retained. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-01 AC4a; FSPEC-WHEEL-04 step 6 (inclusive boundaries); FSPEC acceptance tests (FSPEC-TE2-01) |
| **Test method** | Call `_filter_csp_candidates` directly with a mocked `greeks_lookup`. Include strikes at `abs(delta) = 0.15, 0.20, 0.25, 0.30, 0.35` and config `target_csp_delta_low=0.20, target_csp_delta_high=0.30`. Assert only `0.20, 0.25, 0.30` pass. Assert `0.15` and `0.35` are filtered out. |

---

### PROP-TRADE-12

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-12 |
| **Description** | When all put expirations within the DTE window straddle an earnings date, `CspAgent` must return `CspDecision(tradeable=False, rejection_reason="All suitable expirations overlap earnings")` without calling the LLM. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-01 AC3; FSPEC-WHEEL-04 step 9d |
| **Test method** | Mock `get_next_earnings_date` to return an earnings date before every available expiration in the fixture. Assert the LLM is NOT called (mock is not invoked). Assert `CspDecision.tradeable == False` and `rejection_reason == "All suitable expirations overlap earnings"`. |

---

### PROP-TRADE-13

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-13 |
| **Description** | `CcDecision.strike_above_cost_basis` must equal `strike >= cost_basis` (computed boolean, not set by LLM). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-TRADE-04 AC1; FSPEC-WHEEL-05 Stage 5 (deterministic derived fields) |
| **Test method** | For a `CcDecision` with `strike=145.0, cost_basis=140.0`, assert `strike_above_cost_basis == True`. Construct another with `strike=135.0, cost_basis=140.0`, assert `strike_above_cost_basis == False`. Assert these match `strike >= cost_basis` in both cases. |

---

### PROP-TRADE-14

| Field | Value |
|---|---|
| **Property ID** | PROP-TRADE-14 |
| **Description** | When `CspDecision.tradeable=True` and the exact target-delta strike is unavailable (Filter A eliminated all strikes), the `recommended_strike` is the nearest available strike (nearest-Delta fallback) and `CspDecision.rationale` must contain the annotation `"No strike matches Delta target; nearest available:"` followed by the delta value. |
| **Type** | Unit |
| **Level** | P1 (should-pass) |
| **Source** | REQ-TRADE-01 AC2; FSPEC-WHEEL-04 step 9c (nearest-Delta fallback) |
| **Test method** | Configure `option_chain_fixture` such that all strikes have `abs(delta)` outside the `[target_csp_delta_low, target_csp_delta_high]` range (Filter A eliminates all). Mock LLM to return the nearest-Delta candidate. Assert `CspDecision.tradeable == True`. Assert `CspDecision.rationale` contains `"No strike matches Delta target; nearest available:"`. |

---

## 5. PROP-LIFE — Lifecycle / State Machine Properties

### PROP-LIFE-01

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-01 |
| **Description** | `WheelPhase` transitions are acyclic in the forward direction. The valid forward path is: `None → "screening" → "csp_open" → "stock_owned" → "cc_open" → "cycle_complete" → None`. No backward transitions exist in the specification. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01; FSPEC-WHEEL-07 transition table |
| **Test method** | Enumerate the transition table from FSPEC-WHEEL-07. For each valid forward transition, assert the target phase is the expected next state. Assert there is no transition row in the table where `to_phase` equals a phase earlier in the forward sequence. (This is a specification-compliance test — checked against the table, not the runtime.) |

---

### PROP-LIFE-02

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-02 |
| **Description** | `wheel_cycle_summary` must output `wheel_phase = None` (not `"screening"`) to reset the lifecycle. After the `wheel_cycle_summary` node runs, the graph terminates. The next invocation starts fresh in equity-only mode. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-07 ("wheel_cycle_summary outputs wheel_phase: None"); PLAN v0.3.0 (PM-v2-F-01: "resets to None not 'screening'") |
| **Test method** | Run `wheel_cycle_summary` node with a `WheelPosition` fixture that has `wheel_phase="cycle_complete"` and all required fields set. Assert the returned state dict contains `{"wheel_phase": None}`. Assert `wheel_phase != "screening"`. |

---

### PROP-LIFE-03

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-03 |
| **Description** | `WheelPosition.cycle_annualised_return_pct` must equal `(cycle_pnl / (csp_strike × shares_held)) × (365 / cycle_duration_days) × 100` within ±0.01% tolerance. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-02 AC3a; TSPEC §9.4 (formula, 33.21% verified value) |
| **Test method** | Test the `wheel_cycle_summary` node directly (not a standalone formula helper — the formula is inlined in the node per TSPEC §6.3). Inject an `AgentState` dict containing a `WheelPosition` fixture (via `tmp_path`) with: `cycle_pnl=930`, `csp_strike=140`, `shares_held=100`, `csp_open_date="2024-01-01"`, `call_away_date="2024-03-14"` (73 calendar days). Call `wheel_cycle_summary(state, config)`. Assert the updated `WheelPosition` (loaded from `tmp_path` after the call) has `cycle_annualised_return_pct` within `abs(value - 33.21) <= 0.01`. Note: REQ v0.2.0 stated 33.25%; 33.21% is the arithmetically correct value (TSPEC §9.4 TE-TSPEC-05). |

---

### PROP-LIFE-04

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-04 |
| **Description** | `load_latest_open_position` must return the cycle-10 position over cycle-9 when both exist in the positions directory (integer sort, not lexicographic). |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | TSPEC §9.3 (`load_latest_open_position` integer-sort fix TE-TSPEC-04); ADR-WHEEL-05 (integer-sort regression guard) |
| **Test method** | Using `pytest tmp_path`, create two files: `{ticker}-cycle-9.json` (with `wheel_phase="csp_open"`) and `{ticker}-cycle-10.json` (with `wheel_phase="csp_open"`). Call `load_latest_open_position(ticker, tmp_path)`. Assert the returned position has `cycle_number == 10`. Assert `cycle_number != 9`. |

---

### PROP-LIFE-05

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-05 |
| **Description** | All `WheelPosition` writes must use the atomic `os.replace` pattern (tempfile in same directory + rename). A write must not leave a partial or corrupt file visible to readers. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-02 (atomic write requirement); TSPEC §9.3 (`save_wheel_position` implementation) |
| **Test method** | Using `pytest tmp_path`, call `save_wheel_position(position, str(tmp_path))`. Assert the final file is a valid `WheelPosition` JSON (readable by `model_validate_json`). Assert no `.tmp` files remain in `tmp_path` after a successful write. Mock `os.replace` to raise `OSError`, assert `len(list(tmp_path.glob("*.tmp"))) == 0` after the exception is caught. |

---

### PROP-LIFE-06

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-06 |
| **Description** | Every `RollDecision` returned by `RollCheckAgent` must pass `RollDecision.model_validate()` without raising `ValidationError`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-04; TSPEC §3.6 |
| **Test method** | Mock `invoke_structured_or_freetext` to return valid `RollDecision` JSON. Run `RollCheckAgent`. Deserialise `AgentState["roll_decision"]` with `RollDecision.model_validate_json()`. Assert no `ValidationError`. |

---

### PROP-LIFE-07

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-07 |
| **Description** | When a prior wheel cycle exists for a ticker, `_build_options_context` must inject `CspDecision` fields (`mid_premium`, `probability_of_profit`, `delta`, `max_loss`, `earnings_clear`) into the debate prompts. When no prior cycle exists (both `csp_decision` and `cc_decision` are None), no "Past Cycle Performance" section must appear in the prompt. |
| **Type** | Unit |
| **Level** | P1 (should-pass) |
| **Source** | REQ-LIFE-05 AC3; TSPEC §5.5 (`_build_options_context`); PLAN B3-T6 (past_context injection) |
| **Test method** | (a) With CSP decision: construct `AgentState` with a valid `CspDecision` JSON string containing known values (`mid_premium=2.50`, `probability_of_profit=0.75`, `delta=-0.25`, `max_loss=14250.0`, `earnings_clear=True`). Call `_build_options_context(state)`. Assert the returned string contains `"2.50"` and `"0.75"` and `"0.25"` (from the known delta). (b) Without decision: construct `AgentState` with `csp_decision=None` and `cc_decision=None`. Call `_build_options_context(state)`. Assert the returned string does not contain `"Past Cycle Performance"` and is empty or equals `""`. Note: `cycle_pnl` and `cycle_annualised_return_pct` are NOT fields on `CspDecision` — those live on `WheelPosition`. Do NOT use those fields in this test. |

---

### PROP-LIFE-08

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-08 |
| **Description** | `RollCheckAgent` Rule 3 (breach rule) must fire when `spot_price <= csp_strike × 0.85` (inclusive at exact boundary). It must NOT fire when `spot_price > csp_strike × 0.85`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-06 Rule 3 (15% breach, inclusive boundary); FSPEC acceptance tests (FSPEC-TE-06, FSPEC-TE2-02) |
| **Test method** | Create a `WheelPosition` with `csp_strike=100.0, wheel_phase="csp_open"`. (a) Set `spot_price=85.0` (exactly 15% below): assert Rule 3 fires. (b) Set `spot_price=85.1` (just above threshold): assert Rule 3 does NOT fire. Use deterministic rule-evaluation code path directly (not via LLM). |

---

### PROP-LIFE-09

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-09 |
| **Description** | `RollCheckAgent` priority: when both Rule 3 (breach) and Rule 1 (profit_capture) fire simultaneously, the final `trigger_reason` must be from Rule 3 (`"breach_rule_roll"` or `"breach_rule_close"`), not `"profit_capture"`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-06 multi-rule priority (Rule 3 > Rule 1); FSPEC acceptance tests (FSPEC-TE-09) |
| **Test method** | Set up conditions where both rules fire: `spot_price <= csp_strike * 0.85` and `current_value_pct_of_premium <= take_profit_pct`. Assert final `trigger_reason` is `"breach_rule_roll"` or `"breach_rule_close"`, not `"profit_capture"`. |

---

### PROP-LIFE-10

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-10 |
| **Description** | `RollCheckAgent` Rule 4 (deep OTM rule): Rule 4 fires when `abs(current_delta) < 0.10` (strictly less than — exclusive upper bound). `abs(current_delta) == 0.10` must NOT fire Rule 4. `abs(current_delta) == 0.09` must fire Rule 4. This matches FSPEC-WHEEL-06: "Deep OTM is abs(delta) < 0.10, exclusive". |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-06 Rule 4 ("Deep OTM is abs(delta) < 0.10, exclusive"); FSPEC acceptance tests (FSPEC-TE2-02); TE-F-02 (v2 review inversion correction) |
| **Test method** | (a) `abs(current_delta) = 0.10`: assert Rule 4 does NOT fire (exclusive boundary). (b) `abs(current_delta) = 0.09`: assert Rule 4 fires (deep OTM). Both boundary cases must be tested. |

---

### PROP-LIFE-11

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-11 |
| **Description** | Unit tests for `save_wheel_position`, `load_wheel_position`, and `load_latest_open_position` must use a `pytest tmp_path`-scoped directory and must NOT write to `config["wheel"]["positions_dir"]`. Agent-level tests must inject `_position_loader` and must NOT touch the filesystem. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-05 (I/O-layer test isolation); PLAN (TE-v2-F-02: `_position_loader` injectable requirement) |
| **Test method** | Inspect test code: assert all I/O-layer function tests pass a `tmp_path`-derived directory string. Assert no agent test (`test_csp_agent.py`, `test_cc_agent.py`, `test_roll_agent.py`) calls `save_wheel_position` or reads from `config["wheel"]["positions_dir"]` directly. |

---

### PROP-LIFE-12

| Field | Value |
|---|---|
| **Property ID** | PROP-LIFE-12 |
| **Description** | After any `WheelAnalyst` or `RollCheckAgent` run that produces an `investment_plan` bias, the persisted `WheelPosition` file must contain `prior_analyst_bias` equal to the agent's most recent derived bias string (`"bullish"`, `"neutral"`, or `"bearish"`). |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | TSPEC §9.1 (`prior_analyst_bias` read/write, "PROPERTIES tests must cover this field"); ADR-WHEEL-05 Consequences; FSPEC-WHEEL-06 Rule 5 |
| **Test method** | Run `RollCheckAgent` via its factory (`create_roll_check_agent`) with: a mock LLM returning known `investment_plan` with `recommendation="Buy"` (maps to bias `"bullish"`), a `WheelPosition` fixture injected via `_position_loader` lambda returning a position with `prior_analyst_bias=None`, and `tmp_path` as the positions directory. After the agent completes, load the `WheelPosition` from `tmp_path` using `load_latest_open_position`. Assert `position.prior_analyst_bias == "bullish"`. Run a second invocation with `recommendation="Sell"` (bias `"bearish"`). Assert `prior_analyst_bias == "bearish"` in the updated file. |

---

## 6. PROP-ROUTE — Graph Routing Properties

### PROP-ROUTE-01

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-01 |
| **Description** | When `wheel_phase=None`, `route_wheel_phase()` must route to `fundamental_analyst` (or the configured first analyst node). No options tools must be invoked. Output `AgentState` fields (`market_report`, `sentiment_report`, etc.) must be functionally equivalent to a pre-feature equity-only baseline. |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01 AC1; REQ-NFR-01; FSPEC-WHEEL-07 step 3a; ADR-WHEEL-03 (equity-passthrough integration test invariant) |
| **Test method** | `@pytest.mark.integration`. Invoke graph with `wheel_phase=None`. Assert no wheel-related tool (`get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date`) is called. Assert output `wheel_phase` remains `None`. Assert standard analyst output fields are populated. |

---

### PROP-ROUTE-02

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-02 |
| **Description** | When `wheel_phase="screening"`, `route_wheel_phase()` must route to the first analyst node (which leads to the full analyst pipeline + WheelAnalyst + CspAgent). |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01 AC2; FSPEC-WHEEL-07 step 5 |
| **Test method** | Mock all agent nodes. Invoke graph with `wheel_phase="screening"`. Assert the first analyst node is visited. Assert `WheelAnalyst` node is visited. Assert `CspAgent` node is visited. |

---

### PROP-ROUTE-03

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-03 |
| **Description** | When `wheel_phase="csp_open"`, `route_wheel_phase()` must route to `"roll_check_agent"`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01; FSPEC-WHEEL-07 step 6 |
| **Test method** | Construct `ConditionalLogic` with a mock position store that returns a valid `WheelPosition` with `csp_strike=140.0`. Call `route_wheel_phase({"wheel_phase": "csp_open", "company_of_interest": "NVDA"})`. Assert return value is `"roll_check_agent"`. |

---

### PROP-ROUTE-04

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-04 |
| **Description** | When `wheel_phase="stock_owned"`, `route_wheel_phase()` must route to `"cc_agent"`. CspAgent must not be visited. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01 AC3; FSPEC-WHEEL-07 step 7 |
| **Test method** | Call `route_wheel_phase({"wheel_phase": "stock_owned", ...})`. Assert return value is `"cc_agent"`. |

---

### PROP-ROUTE-05

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-05 |
| **Description** | When `wheel_phase="cc_open"`, `route_wheel_phase()` must route to `"roll_check_agent"`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-07 step 8 |
| **Test method** | Construct `ConditionalLogic` with a mock position store returning a valid `WheelPosition` with `cc_strike=150.0`. Call `route_wheel_phase({"wheel_phase": "cc_open", ...})`. Assert return value is `"roll_check_agent"`. |

---

### PROP-ROUTE-06

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-06 |
| **Description** | When `wheel_phase="cycle_complete"`, `route_wheel_phase()` must route to `"wheel_cycle_summary"`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | FSPEC-WHEEL-07 step 9 |
| **Test method** | Call `route_wheel_phase({"wheel_phase": "cycle_complete", ...})`. Assert return value is `"wheel_cycle_summary"`. |

---

### PROP-ROUTE-07

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-07 |
| **Description** | When `wheel_phase` is an unknown string (e.g., `"invalid_phase"`), `route_wheel_phase()` must fall back to the equity-only path (return the first analyst node name) and emit a warning log. It must NOT raise an exception. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01 AC6; FSPEC-WHEEL-07 step 4b; ADR-WHEEL-02 |
| **Test method** | Call `route_wheel_phase({"wheel_phase": "invalid_phase", ...})`. Assert return value equals `first_analyst_node`. Assert no exception is raised. Capture logs (via `caplog`) and assert a warning message containing `"Unknown wheel_phase"` or `"falling back to equity-only"` was emitted. |

---

### PROP-ROUTE-08

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-08 |
| **Description** | When `wheel_phase="cc_open"` but no `WheelPosition` with `cc_strike` set exists for the ticker, `route_wheel_phase()` must raise `WheelStateError`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-LIFE-01 AC5; FSPEC-WHEEL-07 step 8 guard |
| **Test method** | Construct `ConditionalLogic` with a mock position store that returns either `None` or a `WheelPosition` with `cc_strike=None`. Call `route_wheel_phase({"wheel_phase": "cc_open", ...})`. Assert `WheelStateError` is raised. |

---

### PROP-ROUTE-09

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-09 |
| **Description** | Equity passthrough: when `wheel_phase=None`, no options tools (`get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date`) are invoked during graph execution, and all existing equity output fields are populated. |
| **Type** | Integration |
| **Level** | P0 (must-pass) |
| **Source** | REQ-NFR-01; ADR-WHEEL-03 (equity-passthrough integration test invariant) |
| **Test method** | `@pytest.mark.integration`. Track tool calls via mock. Invoke full graph with `wheel_phase=None`. Assert call count for all four options tools is `0`. Assert `AgentState["market_report"]` and `AgentState["fundamentals_report"]` are non-empty strings. Note: shares the same test fixture as PROP-ROUTE-01; a single integration test function may satisfy both properties. |

---

### PROP-ROUTE-10

| Field | Value |
|---|---|
| **Property ID** | PROP-ROUTE-10 |
| **Description** | When `wheel_phase="csp_open"` but no `WheelPosition` with `csp_strike` set exists for the ticker, `route_wheel_phase()` must raise `WheelStateError`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | TSPEC §6.2 (`route_wheel_phase` `csp_open` guard: `if position is None or position.csp_strike is None: raise WheelStateError`); symmetric with PROP-ROUTE-08 for `cc_open` |
| **Test method** | Construct `ConditionalLogic` with a mock position store that returns either `None` or a `WheelPosition` with `csp_strike=None`. Call `route_wheel_phase({"wheel_phase": "csp_open", "company_of_interest": "NVDA"})`. Assert `WheelStateError` is raised with a message containing `"csp_open"`. |

---

## 7. PROP-FALLBACK — Structured Output Fallback Properties

> **Note:** These 12 properties cover 4 agents × 3 scenarios. All test files must import `STRUCTURED_OUTPUT_SENTINEL` from `tradingagents.agents.utils.structured` rather than hardcoding the sentinel string. This enforces that any mutation of the constant surfaces as a test failure.

---

### PROP-FALLBACK-01 — WheelAnalyst: structured success

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-01 |
| **Description** | When `invoke_structured_or_freetext` returns a valid Pydantic-rendered string (structured-success path), `WheelAnalyst` must correctly parse it and NOT return the sentinel. `AgentState["wheel_candidate_report"]` must not contain `STRUCTURED_OUTPUT_SENTINEL`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (a); TSPEC §10.2 (FSPEC-SE3-01 carry-forward) |
| **Test method** | Mock `invoke_structured_or_freetext` to return a rendered markdown string of a valid `WheelCandidateReport`. Run `WheelAnalyst`. Assert `AgentState["wheel_candidate_report"]` does not contain `STRUCTURED_OUTPUT_SENTINEL` (imported, not hardcoded). |

---

### PROP-FALLBACK-02 — WheelAnalyst: freetext valid JSON (level-2 fallback)

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-02 |
| **Description** | When `invoke_structured_or_freetext` returns a bare valid JSON string matching `WheelCandidateReport`, `WheelAnalyst` must parse it via `model_validate_json` and NOT return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (b) (level-2 freetext-JSON guard); TSPEC §5.1 |
| **Test method** | Mock `invoke_structured_or_freetext` to return a valid JSON string (e.g., `WheelCandidateReport(...).model_dump_json()`). Assert `model_validate_json` succeeds and the result is used. Assert `STRUCTURED_OUTPUT_SENTINEL` (imported) is not present in output state. |

---

### PROP-FALLBACK-03 — WheelAnalyst: total failure sentinel

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-03 |
| **Description** | When both the structured and freetext paths return unparseable content, `WheelAnalyst` must return a sentinel `WheelCandidateReport` with `approved=False` and `rationale` equal to `STRUCTURED_OUTPUT_SENTINEL`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (c); TSPEC §5.1 (sentinel definition) |
| **Test method** | Mock `invoke_structured_or_freetext` to return `"not-valid-json %%%"`. Assert `AgentState["wheel_candidate_report"]` contains `STRUCTURED_OUTPUT_SENTINEL` (imported). Assert `WheelCandidateReport.model_validate_json(state["wheel_candidate_report"]).approved == False`. |

---

### PROP-FALLBACK-04 — CspAgent: structured success

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-04 |
| **Description** | When `invoke_structured_or_freetext` returns a valid rendered `CspDecision` string, `CspAgent` must not return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (a); TSPEC §5.2 |
| **Test method** | Same pattern as PROP-FALLBACK-01 using `CspDecision`. Assert `STRUCTURED_OUTPUT_SENTINEL` (imported) not in output. |

---

### PROP-FALLBACK-05 — CspAgent: freetext valid JSON

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-05 |
| **Description** | When `invoke_structured_or_freetext` returns a bare valid `CspDecision` JSON string, `CspAgent` must parse it and not return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (b); TSPEC §5.2 |
| **Test method** | Same pattern as PROP-FALLBACK-02 using `CspDecision`. |

---

### PROP-FALLBACK-06 — CspAgent: total failure sentinel

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-06 |
| **Description** | When both paths fail, `CspAgent` must return a sentinel with `tradeable=False` and `rationale == STRUCTURED_OUTPUT_SENTINEL`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (c); TSPEC §5.2 (sentinel definition); REQ-NFR-06 |
| **Test method** | Mock `invoke_structured_or_freetext` to return unparseable content. Assert `CspDecision.tradeable == False`. Assert `CspDecision.rationale == STRUCTURED_OUTPUT_SENTINEL` (imported constant). |

---

### PROP-FALLBACK-07 — CcAgent: structured success

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-07 |
| **Description** | When `invoke_structured_or_freetext` returns a valid rendered `CcDecision` string, `CcAgent` must not return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (a); TSPEC §5.3 |
| **Test method** | Same pattern as PROP-FALLBACK-01 using `CcDecision`. |

---

### PROP-FALLBACK-08 — CcAgent: freetext valid JSON

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-08 |
| **Description** | When `invoke_structured_or_freetext` returns a bare valid `CcDecision` JSON string, `CcAgent` must parse it and not return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (b); TSPEC §5.3 |
| **Test method** | Same pattern as PROP-FALLBACK-02 using `CcDecision`. |

---

### PROP-FALLBACK-09 — CcAgent: total failure sentinel

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-09 |
| **Description** | When both paths fail, `CcAgent` must return a sentinel with `tradeable=False` and `rationale == STRUCTURED_OUTPUT_SENTINEL`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (c); TSPEC §5.3 |
| **Test method** | Same pattern as PROP-FALLBACK-06 using `CcDecision`. |

---

### PROP-FALLBACK-10 — RollCheckAgent: structured success

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-10 |
| **Description** | When `invoke_structured_or_freetext` returns a valid rendered `RollDecision` string, `RollCheckAgent` must not return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (a); TSPEC §5.4 |
| **Test method** | Same pattern as PROP-FALLBACK-01 using `RollDecision`. |

---

### PROP-FALLBACK-11 — RollCheckAgent: freetext valid JSON

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-11 |
| **Description** | When `invoke_structured_or_freetext` returns a bare valid `RollDecision` JSON string, `RollCheckAgent` must parse it and not return the sentinel. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (b); TSPEC §5.4 |
| **Test method** | Same pattern as PROP-FALLBACK-02 using `RollDecision`. |

---

### PROP-FALLBACK-12 — RollCheckAgent: total failure sentinel

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-12 |
| **Description** | When both paths fail, `RollCheckAgent` must return a sentinel with `action="HOLD"`, `trigger_reason="profit_capture"`, and `rationale == STRUCTURED_OUTPUT_SENTINEL`. The sentinel must not cause a graph crash. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 scenario (c); TSPEC §5.4 (sentinel definition) |
| **Test method** | Mock both paths to return unparseable content. Assert `RollDecision.action == "HOLD"`. Assert `RollDecision.trigger_reason == "profit_capture"`. Assert `RollDecision.rationale == STRUCTURED_OUTPUT_SENTINEL` (imported constant). |

---

### PROP-FALLBACK-13 — Sentinel constant: import, not hardcode

| Field | Value |
|---|---|
| **Property ID** | PROP-FALLBACK-13 |
| **Description** | `STRUCTURED_OUTPUT_SENTINEL` must be defined as a module-level constant in `tradingagents/agents/utils/structured.py`. All four wheel agents and all test files asserting on sentinel values must import it from `structured.py` — it must not be hardcoded as a string literal anywhere else. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | ADR-WHEEL-04 (sentinel constant enforcement) |
| **Test method** | Write a pytest test in `test_sentinel_enforcement.py`. Use `ast.parse()` + `ast.walk()` to scan the source of each of the four wheel agent files (`wheel_analyst.py`, `csp_agent.py`, `cc_agent.py`, `roll_agent.py`) and `structured.py`. Walk all `ast.Constant` nodes in the agent files. Assert that the sentinel string literal value appears in `structured.py` (in the constant definition) and does NOT appear as an `ast.Constant` node in any of the four agent source files. Also assert that each agent file contains an import statement referencing `STRUCTURED_OUTPUT_SENTINEL` from `tradingagents.agents.utils.structured`. |

---

## 8. PROP-CONFIG — Configuration Properties

### PROP-CONFIG-01

| Field | Value |
|---|---|
| **Property ID** | PROP-CONFIG-01 |
| **Description** | `config["wheel"]` must contain all 20 required keys with the correct default values. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ §7 config table; TSPEC §8.1 (20 keys total, including `near_the_money_pct` and `options_lookforward_days` as TSPEC extensions); REQ-NFR-07 |
| **Test method** | Import `DEFAULT_CONFIG` from `default_config.py`. Assert all 20 keys exist in `DEFAULT_CONFIG["wheel"]`: `min_iv_rank`, `earnings_buffer_days`, `max_wheel_stock_price`, `near_the_money_pct`, `target_csp_delta_low`, `target_csp_delta_high`, `target_cc_delta_low`, `target_cc_delta_high`, `min_annualised_yield_pct`, `recommended_dte_low`, `recommended_dte_high`, `options_lookforward_days`, `take_profit_pct`, `dte_to_roll`, `iv_rank_lookback_days`, `min_chain_oi`, `max_chain_spread_pct`, `risk_free_rate_source`, `risk_free_rate_static`, `positions_dir`. |

---

### PROP-CONFIG-02

| Field | Value |
|---|---|
| **Property ID** | PROP-CONFIG-02 |
| **Description** | `near_the_money_pct` default must be `0.05` and `options_lookforward_days` default must be `45`. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ §7 (v0.3.0 additions); TSPEC §8.1 note (PM-TSPEC-02) |
| **Test method** | Assert `DEFAULT_CONFIG["wheel"]["near_the_money_pct"] == 0.05`. Assert `DEFAULT_CONFIG["wheel"]["options_lookforward_days"] == 45`. |

---

### PROP-CONFIG-03

| Field | Value |
|---|---|
| **Property ID** | PROP-CONFIG-03 |
| **Description** | All 20 `config["wheel"]` keys must have corresponding `TRADINGAGENTS_WHEEL_*` env var override entries in `_WHEEL_ENV_OVERRIDES`. Setting an env var must override the config value at runtime. |
| **Type** | Unit |
| **Level** | P0 (must-pass) |
| **Source** | REQ-NFR-03; TSPEC §8.2 (`_WHEEL_ENV_OVERRIDES` mapping) |
| **Test method** | (a) Assert all 20 config keys appear as values in `_WHEEL_ENV_OVERRIDES`. (b) Set `TRADINGAGENTS_WHEEL_MIN_IV_RANK=30` in the environment. Call `_apply_nested_env_overrides(DEFAULT_CONFIG.copy())`. Assert `config["wheel"]["min_iv_rank"] == 30`. Restore env. |

---

### PROP-CONFIG-04

| Field | Value |
|---|---|
| **Property ID** | PROP-CONFIG-04 |
| **Description** | `default_config.py` must contain inline comments for every new `config["wheel"]` key. |
| **Type** | Unit |
| **Level** | P1 (should-pass) |
| **Source** | REQ-NFR-07 |
| **Test method** | Read `default_config.py`. For each of the 20 wheel config keys, assert the key definition line is followed by or preceded by a comment (lines starting with `#`). |

---

### PROP-CONFIG-05

| Field | Value |
|---|---|
| **Property ID** | PROP-CONFIG-05 |
| **Description** | `options_lookforward_days >= recommended_dte_high` must be enforced at graph setup time. When `options_lookforward_days < recommended_dte_high`, a `UserWarning` must be emitted (not an exception), and `CspAgent`/`CcAgent` must use `max(options_lookforward_days, recommended_dte_high + 7)` as the effective window. |
| **Type** | Unit |
| **Level** | P1 (should-pass) |
| **Source** | TSPEC §8.3 (config validation at setup time); TSPEC §10.4 |
| **Test method** | Set `config["wheel"]["options_lookforward_days"] = 30` and `recommended_dte_high = 45`. Build graph. Assert `UserWarning` is emitted containing `"options_lookforward_days"`. Assert `CspAgent` uses effective window of `max(30, 45+7) = 52` when calling `get_options_chain`. |

---

## 9. Coverage Matrix

The following table maps each upstream requirement to the PROPERTIES that cover it. An uncovered requirement (no PROP mapped) is a gap requiring attention.

| Requirement | Properties |
|---|---|
| REQ-DATA-01 | PROP-DATA-01, PROP-DATA-02, PROP-DATA-15 |
| REQ-DATA-02 | PROP-DATA-03, PROP-DATA-04, PROP-DATA-05, PROP-DATA-06, PROP-DATA-07, PROP-DATA-16, PROP-DATA-17 |
| REQ-DATA-03 | PROP-DATA-08, PROP-DATA-09, PROP-DATA-10, PROP-DATA-11, PROP-DATA-12, PROP-DATA-13 |
| REQ-DATA-04 | PROP-DATA-14 |
| REQ-DATA-05 | PROP-DATA-15 |
| REQ-SCREEN-01 | PROP-SCREEN-01, PROP-SCREEN-05, PROP-SCREEN-06, PROP-SCREEN-07, PROP-SCREEN-08, PROP-SCREEN-09, PROP-SCREEN-10, PROP-SCREEN-11, PROP-SCREEN-13 |
| REQ-SCREEN-02 | PROP-SCREEN-01, PROP-SCREEN-02, PROP-SCREEN-03, PROP-SCREEN-04, PROP-SCREEN-14 |
| REQ-SCREEN-03 | *(CLI display — integration/E2E; not covered in this property set; see gap note §10)* |
| REQ-TRADE-01 | PROP-TRADE-08, PROP-TRADE-11, PROP-TRADE-12, PROP-TRADE-14 |
| REQ-TRADE-02 | PROP-TRADE-01, PROP-TRADE-03, PROP-TRADE-05, PROP-TRADE-07, PROP-TRADE-10 |
| REQ-TRADE-03 | PROP-TRADE-06, PROP-TRADE-09 |
| REQ-TRADE-04 | PROP-TRADE-02, PROP-TRADE-04, PROP-TRADE-13 |
| REQ-TRADE-05 | PROP-LIFE-07 |
| REQ-LIFE-01 | PROP-ROUTE-01 through PROP-ROUTE-10, PROP-LIFE-01 |
| REQ-LIFE-02 | PROP-LIFE-03, PROP-LIFE-04, PROP-LIFE-05, PROP-LIFE-11 |
| REQ-LIFE-03 | PROP-LIFE-08, PROP-LIFE-09, PROP-LIFE-10 |
| REQ-LIFE-04 | PROP-LIFE-06 |
| REQ-LIFE-05 | PROP-LIFE-07 |
| REQ-LIFE-06 | *(CLI display — E2E; see gap note §10)* |
| REQ-NFR-01 | PROP-ROUTE-01, PROP-ROUTE-09, PROP-SCREEN-13 |
| REQ-NFR-03 | PROP-CONFIG-03 |
| REQ-NFR-04 | PROP-FALLBACK-01 through PROP-FALLBACK-13 |
| REQ-NFR-06 | PROP-DATA-01, PROP-FALLBACK-06, PROP-FALLBACK-09, PROP-FALLBACK-12 |
| REQ-NFR-07 | PROP-CONFIG-04 |
| ADR-WHEEL-01 | PROP-DATA-05, PROP-DATA-06, PROP-SCREEN-05 |
| ADR-WHEEL-02 | PROP-ROUTE-07 |
| ADR-WHEEL-03 | PROP-ROUTE-01, PROP-ROUTE-09 |
| ADR-WHEEL-04 | PROP-FALLBACK-01 through PROP-FALLBACK-13 |
| ADR-WHEEL-05 | PROP-LIFE-04, PROP-LIFE-05, PROP-LIFE-11, PROP-LIFE-12 |
| TSPEC §8.1 | PROP-CONFIG-01, PROP-CONFIG-02 |
| TSPEC §8.2 | PROP-CONFIG-03 |
| TSPEC §9.1 | PROP-LIFE-12 |
| TSPEC §9.3 (int-sort) | PROP-LIFE-04 |
| TSPEC §9.4 (formula) | PROP-LIFE-03 |
| TSPEC §10.2 (FSPEC-SE3-01) | PROP-FALLBACK-01 through PROP-FALLBACK-12 |
| FSPEC-WHEEL-04 §9a, §9b | PROP-SCREEN-10, PROP-SCREEN-11 |
| FSPEC-WHEEL-04 §9c | PROP-TRADE-14 |

---

## 10. Known Gaps

| Gap ID | Description | Disposition |
|---|---|---|
| GAP-01 | REQ-SCREEN-03 (CLI `WheelCandidateReport` display) has no Unit/Integration property defined. CLI output assertions require a Rich `Console(file=StringIO())` harness. The deferral is because the CLI code is not yet implemented. Once the CLI lands, properties can activate with `@pytest.mark.skip` guards removed. ADR-WHEEL-01 zero-variance disclosure propagation to `console.export_text()` output (PM-F-07) is also deferred here — the `iv_assessment` propagation at the integration layer (PROP-DATA-06, PROP-SCREEN-05) covers the functional chain; the final CLI assertion is a display concern deferred with GAP-01. | Add PROP-CLI-01 through PROP-CLI-03 when CLI is implemented. |
| GAP-02 | REQ-LIFE-06 (`wheel-status` CLI sub-command) has no property defined. | Add PROP-CLI-04 through PROP-CLI-06 when CLI is implemented. |
| GAP-03 | REQ-NFR-02 (p95 ≤ 10s latency for `get_options_chain`) requires a live network call. No Unit/Integration property is defined here — this is a performance benchmark, not an invariant. | Covered by a dedicated `@pytest.mark.integration` performance test in the test suite (not a PROPERTIES invariant). |
| GAP-04 | `cycle_pnl` formula (`(cc_strike - csp_strike + cumulative_premium_received) × shares_held`) is not separately verified — only `cycle_annualised_return_pct` (PROP-LIFE-03) uses it as an input. REQ-LIFE-02 AC3 explicitly states the expected numeric value (`cycle_pnl = (145 − 140 + 4.30) × 100 = 930`). | Elevated to Medium priority. Add PROP-LIFE-13 in v0.3.0: verify `cycle_pnl` against REQ-LIFE-02 AC3 numeric example (expected: 930). |
| GAP-05 | FSPEC-WHEEL-03 step 8d (price-based fallback for `recommended_strike_range` when Delta-anchored computation fails) has no property. The fallback formula is `[spot_price × (1 − target_csp_delta_high), spot_price × (1 − target_csp_delta_low)]`, rounded to nearest $0.50. | Add PROP-SCREEN-15 in v0.3.0. |
| GAP-06 | PROP-ROUTE-01 and PROP-ROUTE-09 require: (a) invoking the full compiled LangGraph, (b) asserting call count == 0 for all four options tools (`get_options_chain`, `get_iv_metrics`, `get_options_greeks`, `get_next_earnings_date`), and (c) asserting output fields `market_report` and `fundamentals_report` are populated. The `TestEquityPassthroughIntegration` class in `tests/test_graph_routing.py` exercises `route_wheel_phase()` in isolation only — no compiled graph, no tool-call count assertions, no output-field assertions. Full compiled-graph integration requires a LangGraph testing harness that is not yet available. The test class docstring was updated (TE-F-01) to accurately state the scope limitation. | Add PROP-ROUTE-01-INT and PROP-ROUTE-09-INT when LangGraph integration harness is available. |
