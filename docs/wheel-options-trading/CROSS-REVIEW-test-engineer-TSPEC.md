# Cross-Review — Test Engineer — TSPEC
# Document: TSPEC-wheel-options-trading.md v0.1.0

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Document reviewed | TSPEC-wheel-options-trading.md v0.1.0 |
| Recommendation | Needs revision |

---

## Summary

The TSPEC is well-structured overall. Test seams for the data layer are mostly present, but three are absent or incomplete: `get_options_greeks` has no injectable seam for its yfinance calls, `CcAgent` reads `WheelPosition` via a hardcoded filesystem path with no injected loader, and `load_latest_open_position` uses lexicographic sort that breaks at cycle numbers ≥ 10. Two formula correctness issues were found: the BSM Theta formula is missing the put-pricing sign term, and the `cycle_annualised_return_pct` numeric example disagrees between the REQ (33.25%) and the TSPEC (33.21%). A significant spec deviation exists: the TSPEC explicitly omits `within_options_cycle` from `get_next_earnings_date` output despite REQ-DATA-04 AC1–2 and the FSPEC I/O table requiring it. The atomic write pattern is correct for Windows. Four findings are High severity; three are Medium; one is Low.

---

## Findings

### [TE-TSPEC-01] [High] — `get_options_greeks` has no injectable test seam — yfinance calls cannot be mocked at unit-test level

**TSPEC section:** Section 2.1.3 `get_options_greeks`

**Finding:** `get_options_greeks` makes three uncancellable yfinance calls at the raw-function level: (1) `yf.Ticker(ticker).history(period="1d")` to fetch the spot price `S`, (2) `yf.Ticker("^IRX").history(period="1d")` to fetch the risk-free rate, and (3) `yf.Ticker(ticker).option_chain(expiry_date)` to fetch the implied volatility for the specific strike. The function signature has no injectable parameters for these values (`s: Optional[float] = None`, `r: Optional[float] = None`, `iv: Optional[float] = None`), unlike `get_iv_metrics` which provides `iv_series`. REQ-NFR-05 requires "every new agent must have at least one unit test with a mocked data layer" and specifically requires that `get_iv_metrics` accept an injectable `iv_series` parameter — the same testability principle must apply to all data functions. Without a seam, the BSM computation (pure math) cannot be tested independently from the network I/O.

**Impact:** All unit tests for Greek values, Delta boundary conditions, the `dte == 0` guard, the `dte < 0` guard, and the `iv == 0` guard (REQ-DATA-03 ACs 2–6) will require a live yfinance call or a full `unittest.mock.patch` of three separate yfinance internal methods. This is fragile and significantly more complex than a simple fixture parameter. Integration boundary between pure BSM math and I/O is blurred.

**Suggested resolution:** Add three optional injectable parameters to the raw function signature:
```python
def get_options_greeks(
    ticker: str,
    curr_date: str,
    expiry_date: str,
    strike: float,
    option_type: str,
    config: Optional[dict] = None,
    # Test seams — bypass yfinance when provided:
    spot_price: Optional[float] = None,
    risk_free_rate: Optional[float] = None,
    implied_volatility: Optional[float] = None,
) -> str:
```
When all three test seams are provided, skip all yfinance calls. The `@tool` wrapper in `options_data_tools.py` does not expose these parameters (matching the `iv_series` precedent). Document these as "test seam parameters — not exposed to agents."

---

### [TE-TSPEC-02] [High] — BSM Theta formula is missing the put risk-free-rate discount term's sign

**TSPEC section:** Section 2.1.3 BSM formulae block

**Finding:** The TSPEC specifies Theta as:
```
Theta_annual = (-S * n(d1) * sigma / (2 * sqrt(T)) - flag * r * K * exp(-r * T) * N(flag * d2))
Theta = Theta_annual / 365
```
For a **put** (`flag = -1`), the second term becomes `−(−1) × r × K × exp(−rT) × N(−d2)` = `+r × K × exp(−rT) × N(−d2)`. This is correct for put Theta, which is:

```
Theta_put = (-S * n(d1) * sigma / (2 * sqrt(T)) + r * K * exp(-r * T) * N(-d2))
```

The standard BSM Theta for a **call** (`flag = 1`) is:
```
Theta_call = (-S * n(d1) * sigma / (2 * sqrt(T)) - r * K * exp(-r * T) * N(d2))
```

The unified `flag` formulation appears mathematically consistent on paper. However, REQ-DATA-03 AC1 specifies that Theta is returned as "daily theta decay (≤ 0)." For an ATM put with positive `r`, the put Theta formula above produces a value with a positive second term (`+r*K*exp(-rT)*N(-d2) > 0`), which partially offsets the negative first term. This is numerically correct — put Theta can be less negative than call Theta at the same strike due to the interest component. The concern is that the formulation using `flag` is non-standard and error-prone to verify. The TSPEC should confirm this matches a canonical reference (e.g., Hull Chapter 19) with an explicit numeric example using known inputs.

**Impact:** If the formula is implemented with an off-by-one sign on the flag-based unified expression, Theta values will be incorrect for one or both option types. This cannot be caught by schema validation — only by a deterministic numeric unit test. The TSPEC provides no numeric example for Greeks to validate against.

**Suggested resolution:** Add a numeric verification example to the TSPEC using known inputs (e.g., S=100, K=100, T=30/365, r=0.05, sigma=0.20) with expected Delta, Gamma, Theta, Vega values derived from a canonical reference. This becomes the basis for a deterministic unit test using the `spot_price` / `risk_free_rate` / `implied_volatility` test seams (requested in TE-TSPEC-01). Reference Hull (Options, Futures, and Other Derivatives) or Haug for the exact expected values.

---

### [TE-TSPEC-03] [High] — `get_next_earnings_date` omits `within_options_cycle` field required by REQ-DATA-04

**TSPEC section:** Section 2.1.4 `get_next_earnings_date`

**Finding:** REQ-DATA-04 Description states the function "returns the next scheduled earnings date after `curr_date`, the number of calendar days until that date, and a flag `within_options_cycle: bool`." REQ-DATA-04 AC1 requires "Returns date string, days_until, and `within_options_cycle` accurately." REQ-DATA-04 AC2 specifies `within_options_cycle` is `True` when earnings falls within the option's remaining life. The FSPEC-WHEEL-01 I/O table lists the output as including `within_options_cycle`. However, TSPEC Section 2.1.4 explicitly states: "`within_options_cycle` is not computed here (it depends on the caller's target expiration); this field is set by the calling agent, not by this function." The output format shows only `earnings_date_str` and `days_until`.

**Impact:** This is a spec deviation that cannot be silently closed — two accepted REQ ACs are not satisfied by the TSPEC design. Tests written against REQ-DATA-04 AC1–2 will assert on a field the implementation does not return, causing test failures. Any agent that parses the output string expecting `within_options_cycle` will fail silently (string parsing will not find the field).

**Suggested resolution:** Either (a) restore the `within_options_cycle` field to the function output — the function should accept an optional `expiration_date: Optional[str] = None` parameter; when provided, compute and include `within_options_cycle = (earnings_date <= expiry_date_parsed)` in the output string; or (b) file a formal REQ amendment removing `within_options_cycle` from REQ-DATA-04 AC1–2 and the FSPEC-WHEEL-01 I/O table, and document that callers compute this comparison directly. Option (a) is preferred — it keeps the test seam self-contained.

---

### [TE-TSPEC-04] [High] — `load_latest_open_position` uses lexicographic glob sort — breaks at cycle ≥ 10

**TSPEC section:** Section 9.3 `load_latest_open_position`

**Finding:** The implementation is specified as:
```python
candidates = sorted(dir_path.glob(pattern), reverse=True)
```
`Path.glob()` returns `Path` objects; `sorted()` on `Path` objects uses lexicographic string ordering of the full path. For files `NVDA-cycle-9.json` and `NVDA-cycle-10.json`, lexicographic sort places `NVDA-cycle-9.json` **after** `NVDA-cycle-10.json` (because `"9" > "1"` character-by-character). With `reverse=True`, the sort returns `NVDA-cycle-9.json` first, selecting cycle 9 instead of cycle 10. This is a silent data-correctness bug that only manifests after a position's tenth cycle.

**Impact:** `CcAgent`, `RollCheckAgent`, and `route_wheel_phase()` all call `load_latest_open_position`. They will read stale cycle data silently. The `prior_analyst_bias` will be read from the wrong position, potentially triggering incorrect Rule 5 (analyst update) evaluations. This is untestable with the fixture provided in `tests/fixtures/options_fixtures.py` (which only covers options chains, not position files). No unit test will catch this unless fixtures exercise cycle numbers ≥ 10.

**Suggested resolution:** Extract the cycle number from the filename for sorting:
```python
def _cycle_number_from_path(p: Path) -> int:
    try:
        return int(p.stem.rsplit("-cycle-", 1)[-1])
    except (ValueError, IndexError):
        return -1

candidates = sorted(dir_path.glob(pattern), key=_cycle_number_from_path, reverse=True)
```
Add an explicit unit test with fixture files `TICKER-cycle-9.json` and `TICKER-cycle-10.json` asserting that cycle 10 is returned.

---

### [TE-TSPEC-05] [Medium] — `cycle_annualised_return_pct` numeric example disagrees between REQ and TSPEC

**TSPEC section:** Section 9.4 `cycle_annualised_return_pct` Formula

**Finding:** REQ-LIFE-02 AC3a states: "Value is approximately `33.25%`." TSPEC Section 9.4 states: "≈ 33.21%." Computing directly: `(930 / (140 × 100)) × (365 / 73) × 100 = (930 / 14000) × 5.00000 × 100 = 0.066429 × 5.0 × 100 = 33.2143%`. The TSPEC value (33.21%) is arithmetically correct; the REQ value (33.25%) is wrong by 0.04 percentage points. However, the discrepancy creates an ambiguity for PROPERTIES authoring: which value should a numeric test assert on — 33.21% or 33.25%?

**Impact:** A PROPERTIES test asserting the REQ value (33.25%) will fail against a correct implementation. A test asserting the TSPEC value (33.21%) is correct but deviates from the approved REQ. The REQ should be corrected to match the arithmetic.

**Suggested resolution:** File a REQ amendment to correct AC3a to read `"Value is approximately 33.21% (formula: (930 / (140 × 100)) × (365 / 73) × 100)"`. Until the REQ is amended, PROPERTIES should assert against 33.21% with a tolerance of ±0.01% and include a comment referencing this discrepancy.

---

### [TE-TSPEC-06] [Medium] — `CcAgent` reads `WheelPosition` via hardcoded filesystem path — not unit-testable without real files

**TSPEC section:** Section 5.3 `CcAgent` State reads

**Finding:** TSPEC Section 5.3 specifies: "Additionally reads `WheelPosition` from the position store (loaded by file path: `{positions_dir}/{ticker}-cycle-{N}.json`; the most recent non-complete position file for the ticker) to obtain `csp_strike`, `csp_premium_received`, `cost_basis_per_share`." The mechanism is `load_latest_open_position(ticker, positions_dir)`, which reads from disk. By contrast, `CspAgent` receives its `WheelCandidateReport` from `AgentState` (an in-memory string), which is injectable. `CcAgent`'s position reading is not injectable via constructor or argument — it is always a filesystem call.

**Impact:** Unit tests for `CcAgent` (e.g., REQ-TRADE-03 ACs 1–3, FSPEC-WHEEL-05 ACs) must either write real files to a temp directory or patch `load_latest_open_position` at the module level. Module-level patching is fragile and not documented as the intended pattern. The FSPEC states "Agent unit tests must mock the LLM and assert on structured-output schema fields" (REQ-NFR-05) — this is difficult if the agent also calls the filesystem before calling the LLM.

**Suggested resolution:** The `create_cc_agent` factory should accept an injectable position loader callable:
```python
def create_cc_agent(
    llm: Any,
    position_loader: Callable[[str, str], Optional[WheelPosition]] = load_latest_open_position,
) -> Callable[[AgentState, RunnableConfig], dict]:
```
Unit tests inject a `position_loader` lambda returning a `WheelPosition` fixture. Production code uses the default `load_latest_open_position`. Apply the same pattern to `create_roll_check_agent(llm, position_store_dir)` (Section 5.4) and `route_wheel_phase()` (Section 6.2 `_load_position`).

---

### [TE-TSPEC-07] [Medium] — `WheelAnalyst` sentinel fallback (`approved=False`) populates `recommended_strike_range=[0.0, 0.0]` but `WheelCandidateReport` schema has no validator enforcing this sentinel contract

**TSPEC section:** Section 5.1 WheelAnalyst structured output + Section 3.3 `WheelCandidateReport`

**Finding:** The TSPEC Section 5.1 specifies a sentinel `WheelCandidateReport` with `recommended_strike_range=[0.0, 0.0]` when structured output fails. Section 3.3 defines `recommended_strike_range` with `min_length=2, max_length=2` but no value constraint. The FSPEC-WHEEL-03 Business Rules state: "When `approved = False`, `recommended_strike_range` may be set to `[0.0, 0.0]` as a null sentinel — it must not be `None`." However, nothing in the schema definition enforces that `approved=False` implies `recommended_strike_range == [0.0, 0.0]`, or that `approved=True` implies the range contains positive floats. The schema allows a conforming but semantically incorrect output such as `approved=True, recommended_strike_range=[0.0, 0.0]`.

**Impact:** A PROPERTIES test for REQ-SCREEN-01 AC1 ("Report is `approved: true`") should also assert `recommended_strike_range[0] > 0.0 and recommended_strike_range[1] > 0.0`. Without a schema validator, this is a runtime contract that can only be tested through integration tests — not schema validation alone. The test level annotation in FSPEC (Unit for schema tests) implies schema-level assertability.

**Suggested resolution:** Add a Pydantic `model_validator` to `WheelCandidateReport`:
```python
@model_validator(mode='after')
def check_strike_range_when_approved(self) -> 'WheelCandidateReport':
    if self.approved and (self.recommended_strike_range[0] <= 0.0 or self.recommended_strike_range[1] <= 0.0):
        raise ValueError("approved=True requires recommended_strike_range with positive floats")
    return self
```
This makes the contract unit-testable from the schema definition alone.

---

### [TE-TSPEC-08] [Low] — `config` parameter not passed through `options_data_tools.py` `@tool` wrappers — `get_options_chain` and `get_options_greeks` rely on `get_config()` global, which cannot be overridden in tests

**TSPEC section:** Section 2.2 `options_data_tools.py` — Note at end of section

**Finding:** The TSPEC note states: "The `config` parameter is also not passed through the tool layer; it is injected at function-call time in the raw function via `get_config()` from `tradingagents/dataflows/config.py`." `get_options_chain` uses `config` to read `options_lookforward_days`; `get_options_greeks` uses `config` for `risk_free_rate_source` and `risk_free_rate_static`. Since `get_config()` reads a module-level or environment-derived config, unit tests cannot inject a test config without either patching `get_config` at the module level or setting environment variables. This is the same testability concern that REQ-NFR-05 addresses for `iv_series`.

**Impact:** The `options_lookforward_days` boundary (filter: `target_dt <= expiry_dt <= cutoff`) and the `risk_free_rate_source == "static"` path in `get_options_greeks` (REQ-DATA-03 AC7) cannot be tested via pure unit tests without module-level patching. The integration boundary between config-driven behavior and computation is blurred. This is a Low severity finding because `get_config()` patching with `unittest.mock.patch` is workable, but the TSPEC should document this as the intended test mechanism.

**Suggested resolution:** Either (a) add an optional `config: Optional[dict] = None` parameter to both raw functions (already present for `get_options_chain` and `get_options_greeks` per the TSPEC signatures — the issue is that the functions call `get_config()` when `config is None` rather than always using the parameter), and document that tests pass a config dict directly; or (b) explicitly document in PROPERTIES that config-boundary tests must use `unittest.mock.patch("tradingagents.dataflows.y_finance_options.get_config", return_value=test_config)` as the approved pattern. Option (a) is cleaner and is already partially specified in the function signatures.

---

## Approved Items

The following design decisions are well-specified from a testability perspective and require no changes:

1. **`get_iv_metrics` test seam (`iv_series`)** — The injectable `iv_series: Optional[list[float]]` parameter correctly separates the pure statistical computation from the yfinance I/O fetch. The FSPEC-WHEEL-02 acceptance tests are unit-testable with this seam. The zero-variance guard, `iv_environment` boundary values, and `iv_percentile` strict-less-than semantics are all exercisable without a network call.

2. **`_filter_csp_candidates` and `_filter_cc_candidates` as separate, named functions** — Extracting the deterministic pre-filter as a named function (`_filter_csp_candidates`, `_filter_cc_candidates`) with a clean signature (`chain_df`, `greeks_lookup`, `earnings_date`, `config`) creates a clear, independently unit-testable seam. REQ-TRADE-01 AC4a ("Filter rejects any strike whose put delta is outside [0.15, 0.25] before presenting options to the LLM") is directly testable against this function without involving the LLM or any I/O.

3. **`TriggerReason` as a `Literal` type** — Using `Literal["profit_capture", "dte_rule", "breach_rule_roll", "breach_rule_close", "earnings_rule", "analyst_update"]` enables Pydantic schema validation to assert on `trigger_reason` deterministically. REQ-LIFE-03 ACs 1–4 can all be expressed as `assert decision.trigger_reason == "..."` in unit tests without examining free-text `rationale`.

4. **`RollCheckAgent` rule priority code pattern** — The explicit `if/elif` chain (Section 5.4, `trigger_reason` assignment code pattern) with named boolean variables (`rule1_fires`, `rule2_fires`, etc.) is highly testable. Each rule can be asserted by constructing inputs that set exactly one variable to `True`.

5. **`WheelPhase(str, Enum)` design** — Declaring `WheelPhase` as `str, Enum` with lowercase string values ensures JSON-serialisability and allows `assert state["wheel_phase"] == "csp_open"` in unit tests without importing the enum. This matches the LangGraph checkpoint constraint.

6. **Atomic write pattern (`tempfile.mkstemp` + `os.replace` in same directory)** — The TSPEC correctly specifies `tempfile.mkstemp(dir=dir_path)` to ensure the temp file is on the same filesystem as the target. On Windows, `os.replace` is atomic for same-filesystem moves. Writing to `dir_path` explicitly (rather than the default temp directory) avoids cross-filesystem moves that would cause `os.replace` to fail or be non-atomic. This matches the `TradingMemoryLog` pattern at `memory.py` lines 161–163 and is correctly specified.

7. **Schema render helpers pattern** — Providing `render_wheel_candidate_report`, `render_csp_decision`, `render_cc_decision`, `render_roll_decision` as separate functions follows the existing `render_research_plan` / `render_pm_decision` pattern. Render helpers are pure functions (no I/O) and are directly unit-testable by constructing a schema instance and asserting on the output string.

8. **`WheelCandidateReport.recommended_dte_range` field constraints (`min_length=2, max_length=2`)** — Using Pydantic `Field(min_length=2, max_length=2)` on `list` fields makes length validation unit-testable from schema instantiation alone. A PROPERTIES test can assert `pytest.raises(ValidationError)` when a list with length ≠ 2 is supplied.

9. **`option_chain_fixture` in `tests/fixtures/options_fixtures.py`** — Centralising the canonical fixture as a pytest fixture factory with a defined column schema (`strike`, `bid`, `ask`, `lastPrice`, `volume`, `openInterest`, `impliedVolatility`) ensures all filter unit tests use consistent, documented data shapes. This is the correct pattern for testability.
