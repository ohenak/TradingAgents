# Cross-Review — Software Engineer — REQ (v2)
# Document: REQ-wheel-options-trading.md v0.2.0

| Field | Value |
|---|---|
| Reviewer | Software Engineer (SE-Review) |
| Date | 2026-05-25 |
| Document reviewed | REQ-wheel-options-trading.md v0.2.0 |
| Iteration | 2 |
| Recommendation | Approved with minor changes |

---

## Resolution Status of Prior Findings

| Finding | Status | Notes |
|---|---|---|
| SEV-REVIEW-01 | Resolved | A3 and REQ-DATA-02 now fully commit to the OHLCV realised-volatility proxy. The formula, flat-range sentinel, and rationale are all clearly documented. The `iv_series` injectable parameter closes the test seam. |
| SEV-REVIEW-02 | Resolved | REQ-LIFE-01 now mandates `class WheelPhase(str, Enum)` with explicit lowercase string values, and `AgentState` stores the phase as `Optional[str]`. Both the enum declaration and the storage type are correct. |
| SEV-REVIEW-03 | Resolved | REQ-LIFE-01 now includes an Architecture Note specifying the `START → wheel_router` preamble conditional edge, the `ConditionalLogic.route_wheel_phase()` method, and the passthrough behaviour for `wheel_phase is None`. The implementation path is unambiguous. |
| SEV-REVIEW-04 | Resolved | REQ-DATA-05 now mandates the `"options_data"` category in `TOOLS_CATEGORIES`, requires `VENDOR_METHODS` registration with yfinance + Alpha Vantage stub entries, and explicitly states that `@tool` wrappers must call `route_to_vendor()` and must not import `y_finance.py` directly. |
| SEV-REVIEW-05 | Resolved | REQ-SCREEN-02 now uses `list[float]` and `list[int]` with `Field(min_length=2, max_length=2)` for both range fields. The Note explaining the reason (LLM provider JSON schema compatibility and LangGraph checkpoint serialisation) is present. |
| SEV-REVIEW-06 | Resolved | REQ-DATA-02 dependency is now `None`. The description explicitly states that the OHLCV path uses `Ticker.history()` close prices, not `get_options_chain`. The 252-call anti-pattern is no longer implied. |
| SEV-REVIEW-07 | Resolved | REQ-TRADE-05 ACs are now prompt-content assertions: AC1 checks that the prompt string contains the serialised `CspDecision` fields `mid_premium` and `probability_of_profit`; AC2 checks that the Conservative debater's prompt contains the `earnings_date` string. Both are deterministic. |
| SEV-REVIEW-08 | Resolved | REQ-DATA-03 now specifies `^IRX` as the primary source (with division-by-100 parsing noted), fallback to `config["wheel"]["risk_free_rate_static"]`, and AC7 covering the unavailability path. Section 7 lists both `risk_free_rate_source` and `risk_free_rate_static` as config keys. |
| SEV-REVIEW-09 | Resolved | REQ-SCREEN-01 dependency table now includes `REQ-DATA-03`, and the description explicitly states that `WheelAnalyst` calls `get_options_greeks` to compute a Delta-anchored `recommended_strike_range`. |
| SEV-REVIEW-10 | Resolved | REQ-LIFE-02 now specifies `{positions_dir}/{ticker}-cycle-{cycle_number}.json` as the file path, mandates the atomic temp-file + rename pattern matching `TradingMemoryLog`, and `positions_dir` is listed in Section 7 as a config key. |
| SEV-REVIEW-11 | Resolved | REQ-DATA-01 AC3 now correctly references `config["data_vendors"]["options_data"]`. |
| SEV-REVIEW-12 | Resolved | Section 7 now provides a complete table with env var names, types, and the `TRADINGAGENTS_WHEEL_{UPPER_SNAKE_CASE_KEY}` naming convention, and REQ-NFR-03 explicitly requires entries in `_ENV_OVERRIDES`. |
| SEV-REVIEW-13 | Resolved | REQ-TRADE-02 and REQ-LIFE-02 both now state "DTE is always calendar days; annualisation uses 365" in their descriptions. |
| SEV-REVIEW-14 | Resolved | REQ-DATA-04 description now correctly reads: "`within_options_cycle` is `True` if the next earnings date falls on or before the front-month expiration date", with the logical test `earnings_date <= expiration_date` explicit. |

---

## New or Remaining Findings

### [SEV-REVIEW2-01] Medium — `_apply_env_overrides` does not support nested config keys; `TRADINGAGENTS_WHEEL_*` env vars will silently have no effect

**Requirement(s):** REQ-NFR-03, Section 7

**Finding:** The existing `_apply_env_overrides()` function in `default_config.py` iterates over `_ENV_OVERRIDES` and writes each resolved value to `config[key]` — a flat top-level assignment. The new wheel config keys all live under `config["wheel"]` (a nested dict), but `_ENV_OVERRIDES` only supports top-level key paths (e.g., `config["llm_provider"]`, `config["max_debate_rounds"]`). If the implementer adds entries such as `"TRADINGAGENTS_WHEEL_MIN_IV_RANK": "min_iv_rank"` without modifying `_apply_env_overrides`, the override will write `config["min_iv_rank"] = 25` at the top level — leaving `config["wheel"]["min_iv_rank"]` unchanged and the env var silently ignored.

**Impact:** REQ-NFR-03 requires all wheel thresholds to be overridable via env vars. If this structural mismatch is not addressed in the TSPEC, the env-var override feature will appear to work in developer tests (where overrides are applied to the flat test config) but fail in production where the nested config is read.

**Suggested resolution:** The TSPEC must extend `_apply_env_overrides` (or add a companion `_apply_nested_env_overrides`) to support dot-path key resolution (e.g., `"wheel.min_iv_rank"`). Alternatively, each `TRADINGAGENTS_WHEEL_*` var can be read with `os.getenv()` inline when constructing the `"wheel"` sub-dict — matching the pattern already used for `TRADINGAGENTS_RESULTS_DIR` and `TRADINGAGENTS_CACHE_DIR` in `DEFAULT_CONFIG`. The REQ should explicitly note this architectural constraint so the TSPEC author does not assume the current flat `_apply_env_overrides` is sufficient.

---

### [SEV-REVIEW2-02] Medium — REQ-LIFE-01 AC5 specifies `WheelStateError` but no definition or module location is given

**Requirement(s):** REQ-LIFE-01 (AC5)

**Finding:** AC5 states: "Graph raises `WheelStateError` exception" when `wheel_phase="cc_open"` but no `WheelPosition` with `cc_strike` exists. `WheelStateError` is a named custom exception that does not exist anywhere in the codebase. The REQ does not specify where it should be defined (a new `tradingagents/agents/options/exceptions.py`? inline in `graph/setup.py`?), what its base class is, or what information it carries. Without this, the TSPEC author will either invent a location (risking architectural inconsistency) or use a generic `RuntimeError` (losing the deterministic AC assertion).

**Impact:** Medium — the AC is testable only if the exception class is importable from a known, stable location. If two engineers place it in different modules, any test that catches `WheelStateError` by import path will fail.

**Suggested resolution:** Add a note to REQ-LIFE-01 specifying the exception's module path (e.g., `tradingagents/agents/options/exceptions.py`), base class (`ValueError` or `RuntimeError`), and the minimum information it must carry (phase name, ticker). This is a one-line decision that removes implementation ambiguity.

---

### [SEV-REVIEW2-03] Low — REQ-DATA-02 `iv_percentile` edge-case formula is ambiguous when `current_vol` equals the maximum in the lookback

**Requirement(s):** REQ-DATA-02

**Finding:** The formula defines `iv_percentile = (days where realised_vol < current_vol) / total_days × 100` using a strict less-than comparison. When `current_vol` equals the maximum realised vol in the lookback window (i.e., today is at the 100th percentile), the formula returns `(total_days - 1) / total_days × 100` — approximately 99.6% for a 252-day window — rather than 100. This is technically correct behaviour for a strict empirical CDF, but it is subtly inconsistent with the `iv_rank` formula which would return exactly 100 in the same situation. A test that computes both metrics on a series where `current_vol == max_vol` will observe `iv_rank == 100` and `iv_percentile ≈ 99.6`, which may surprise the test author and create a fragile assertion.

**Impact:** Low — the formula is implementable as written. The inconsistency is a documentation gap, not a blocking defect.

**Suggested resolution:** Add a sentence to the REQ-DATA-02 formula block: "When `current_vol == max_vol_lookback`, `iv_percentile` uses strict less-than and will be approximately `(total_days − 1) / total_days × 100` rather than 100. This is expected behaviour and tests should not assert `iv_percentile == 100` in this case."

---

### [SEV-REVIEW2-04] Low — `within_options_cycle` in REQ-DATA-04 references a `front-month expiration date` that is not an input to the function

**Requirement(s):** REQ-DATA-04

**Finding:** REQ-DATA-04's description was revised to correctly state: "`within_options_cycle` is `True` if the next earnings date falls on or before the front-month expiration date." However, the function signature `get_next_earnings_date(ticker, curr_date)` does not accept an `expiration_date` parameter. The "front-month expiration date" is undefined in the function's scope. AC2 illustrates the calculation with specific values (earnings 10 days away, expiration 30 days away), but it is unclear whether the function (a) always looks up the nearest available expiration from the options chain internally, (b) uses a fixed `dte_to_roll` config value as a proxy, or (c) requires an `expiration_date` parameter to be added. Without this, two implementers will produce incompatible implementations: one that hardcodes 30 DTE as the "front-month", another that calls `get_options_chain` internally.

**Impact:** Low in isolation, but the field feeds REQ-SCREEN-01's earnings clearance check (criterion 3), so an incorrect implementation here propagates into every wheel candidate approval decision.

**Suggested resolution:** Add `expiration_date: str` as an optional parameter to `get_next_earnings_date(ticker, curr_date, expiration_date: Optional[str] = None)`. When provided, compute `within_options_cycle` against that date. When omitted, use the nearest options expiration from `get_options_chain()` or a config default. Document the resolution in the function signature within the REQ.

---

## Summary

The PM's v0.2.0 revision is thorough and correct. All 14 prior findings from the iteration 1 review have been resolved, several with notably precise additions (the `iv_series` injectable parameter, the Architecture Note for graph integration, the explicit `route_to_vendor()` mandate in REQ-DATA-05, and the full Section 7 config table). The document is now implementable end-to-end.

Two medium findings are raised as new issues: the `_apply_env_overrides` flat-key structural incompatibility with the nested `config["wheel"]` dict (SEV-REVIEW2-01) must be addressed in the TSPEC before the env-var override feature can be considered delivered; and the missing definition of `WheelStateError`'s module location (SEV-REVIEW2-02) should be resolved to prevent architectural fragmentation. Both are resolvable within the TSPEC without requiring further REQ revision.

Two low findings are raised for documentation precision: the `iv_percentile` edge-case at the maximum (SEV-REVIEW2-03) and the undefined `expiration_date` scope in `get_next_earnings_date` (SEV-REVIEW2-04). Neither blocks implementation, but both will surface as test-writing questions during PROPERTIES.

**Overall recommendation:** Approved with minor changes. The document can proceed to FSPEC and TSPEC. SEV-REVIEW2-01 must be captured as a TSPEC constraint. SEV-REVIEW2-02 through SEV-REVIEW2-04 may be resolved in the TSPEC without returning to REQ.

---

## Approved Items

All items approved in iteration 1 remain approved. The following v0.2.0 additions are additionally approved:

- **Assumption A3 (revised) and REQ-DATA-02:** The realised-volatility proxy approach is correctly specified, the formula is unambiguous for the non-degenerate case, and the flat-range sentinel (`iv_rank = 50`, note in report) is a pragmatic and testable fallback. The `iv_series` injectable parameter cleanly closes the test seam without leaking test concerns into production paths.
- **REQ-DATA-02 `iv_environment` field and thresholds:** The `Literal["elevated", "normal", "compressed"]` tri-state with explicit cutoffs (≥ 50 / 25–49 / < 25) is deterministically testable and correctly replaces the prior free-text AC assertions identified as TEV-REVIEW-12.
- **REQ-DATA-03 (revised risk-free rate):** The `^IRX` primary / static fallback pattern with explicit percentage-to-decimal parsing note and AC7 for unavailability is well-specified and implementable.
- **REQ-DATA-05 (revised module placement):** The `"options_data"` category mandate, `VENDOR_METHODS` registration requirement, and `route_to_vendor()` mandate are architecturally correct and consistent with the existing codebase pattern verified in `interface.py`.
- **REQ-LIFE-01 Architecture Note:** The `START → wheel_router → existing first node` preamble pattern with `ConditionalLogic.route_wheel_phase()` is the correct low-risk integration approach. The passthrough for `wheel_phase is None` preserves the equity pipeline unchanged and is consistent with REQ-NFR-01.
- **REQ-LIFE-02 position file storage:** The `{positions_dir}/{ticker}-cycle-{cycle_number}.json` path with atomic write mandate eliminates the concurrent-write risk identified in SEV-REVIEW-10.
- **REQ-SCREEN-02 list fields:** The `list[float]` with `Field(min_length=2, max_length=2)` pattern is the correct fix and will survive both LLM provider schema generation and LangGraph checkpoint serialisation.
- **REQ-TRADE-05 ACs (revised):** Prompt-content assertions on the assembled prompt string are deterministic and compatible with the existing `structured.py` wrapper pattern. The revised ACs are testable without an LLM call.
- **Section 7 Configuration table:** Complete, with correct env var names, types, and the naming convention documented. The `positions_dir`, `risk_free_rate_source`, and `risk_free_rate_static` entries are all present.
- **REQ-NFR-05 (revised):** The additions mandating LLM mocking in agent unit tests, the `option_chain_fixture` canonical fixture, and the `iv_series` injectable parameter collectively define a coherent, consistent test strategy across all four phases.
