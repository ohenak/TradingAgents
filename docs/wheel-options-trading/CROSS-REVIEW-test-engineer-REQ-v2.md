# Cross-Review — Test Engineer — REQ (v2)
# Document: REQ-wheel-options-trading.md v0.2.0

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Document reviewed | REQ-wheel-options-trading.md v0.2.0 |
| Iteration | 2 |
| Recommendation | Approved with minor changes |

---

## Resolution Status of Prior Findings

| Finding | Status | Notes |
|---|---|---|
| TEV-REVIEW-01 | Resolved | REQ-NFR-05 now mandates LLM mocking and structured-field assertions. REQ-SCREEN-01, REQ-TRADE-03, REQ-TRADE-05, and REQ-LIFE-03 descriptions all carry matching test-strategy notes. |
| TEV-REVIEW-02 | Resolved | REQ-NFR-05 now specifies `option_chain_fixture(ticker, expiry)` in `tests/fixtures/options_fixtures.py`. REQ-DATA-02 description defines the injectable `iv_series: Optional[list[float]]` parameter explicitly. |
| TEV-REVIEW-03 | Resolved | REQ-DATA-01 adds AC5 (HTTP error) and AC6 (empty DataFrame, distinct from AC2). REQ-DATA-02 adds AC5 (zero-variance → rank 50 with flat-range note). REQ-DATA-03 adds AC5 (negative DTE), AC6 (IV=0), and AC7 (^IRX unavailable). REQ-DATA-04 AC2 rewritten with unambiguous `earnings_date <= expiration_date` semantics. |
| TEV-REVIEW-04 | Resolved | REQ-LIFE-03 splits the breach rule into AC3a (`current_value_pct_of_premium >= 50` → ROLL) and AC3b (`< 50` → CLOSE). REQ-LIFE-04 adds `trigger_reason` as a six-value Literal enum. Tests are directed to assert on `trigger_reason`. |
| TEV-REVIEW-05 | Resolved | REQ-LIFE-05 AC2 replaced with testable proxy (`notes` field non-empty when `cycle_pnl < 0`). AC3 now specifies required fields for `past_context` (ticker, `cycle_pnl` to 2dp, `cycle_annualised_return_pct`). AC4 added for full `WheelPosition` field presence check. |
| TEV-REVIEW-06 | Resolved | REQ-NFR-02 now specifies measurement point (call entry to return), percentile (p95), test marker (`integration`), and excludes mocked unit tests from the constraint. |
| TEV-REVIEW-07 | Resolved | REQ-SCREEN-01 adds AC6 (OI < 100 → rejected with "Insufficient liquidity"), AC7 (spread > 10% → rejected with "Chain spread too wide"), and AC8 (price > max_wheel_stock_price → rejected). |
| TEV-REVIEW-08 | Resolved | REQ-TRADE-01 splits the original AC4 into AC4a (unit test on the deterministic filter function with mocked LLM) and AC4b (integration test asserting `CspDecision.delta` is within range, marked `@pytest.mark.integration`). |
| TEV-REVIEW-09 | Resolved | REQ-LIFE-02 now includes the explicit formula `cycle_annualised_return_pct = (cycle_pnl / (csp_strike × shares_held)) × (365 / cycle_duration_days) × 100` in the description. AC3a added with a concrete numeric example and expected output. |
| TEV-REVIEW-10 | Resolved | REQ-SCREEN-03 and REQ-LIFE-06 both carry test-strategy notes specifying `console.export_text()` and `Console(file=StringIO())`. All CLI ACs now reference `console.export_text()` output as the observable. |
| TEV-REVIEW-11 | Resolved | REQ-LIFE-01 adds AC5 (`cc_open` with no matching `WheelPosition` → `WheelStateError`) and AC6 (unknown `wheel_phase` value → equity-only fallback with warning). |
| TEV-REVIEW-12 | Resolved | `get_iv_metrics` now returns a structured object with `iv_environment: Literal["elevated", "normal", "compressed"]`. REQ-DATA-02 AC3 and AC4 assert on this enum field directly. |
| TEV-REVIEW-13 | Resolved | REQ-DATA-01 description now specifies "inclusive boundary `expiry_date <= target_date + timedelta(days=options_lookforward_days)` anchored to `target_date`" in calendar days. |
| TEV-REVIEW-14 | Resolved | REQ-TRADE-02 AC1 rewritten as "All numeric fields other than `delta` and `theta` are non-negative; `delta` is in (−1, 0); `theta` is ≤ 0." |
| TEV-REVIEW-15 | Resolved | REQ-LIFE-02 specifies `{config["wheel"]["positions_dir"]}/{ticker}-cycle-{cycle_number}.json` as the file path. Atomic temp-file + rename write pattern is required. AC4 references this exact pattern. |
| TEV-REVIEW-16 | Resolved | Section 7 now includes a complete table mapping every config key to its env var name, type, and description. REQ-NFR-03 now states the naming convention explicitly. |

---

## New or Remaining Findings

---

### [TEV2-REVIEW-01] Medium — `get_next_earnings_date` does not accept an expiry date but `within_options_cycle` flag requires one

**Requirement(s):** REQ-DATA-04

**Finding:** The function signature is `get_next_earnings_date(ticker, curr_date)`. The clarified description says `within_options_cycle` is `True` if `earnings_date <= expiration_date` — meaning the comparison requires a specific expiration date. The function signature has no `expiry_date` parameter. The description gives no indication of what expiration date the implementation should use: the nearest available front-month expiration? The one returned by `get_options_chain`? A caller-supplied value?

AC2 demonstrates the use case ("earnings is 10 days away and the next expiration is 30 days away") but the "next expiration" is caller context that cannot be derived from the ticker and `curr_date` alone without an additional yfinance call inside the function. If the function internally calls `yf.Ticker.options` (the list of available expirations) to find the front-month expiry, that behaviour must be specified so it can be mocked and tested. If the caller is expected to pass the expiration date, the function signature must be updated.

**Impact:** Implementers will make conflicting choices. If the function picks an internal front-month expiry, AC2 is only verifiable if the test controls what `Ticker.options` returns (requiring an additional mock surface not defined in REQ-NFR-05's fixture specification). If the function signature stays as-is, AC2 cannot be satisfied with a deterministic test — the "30-day expiry" in AC2 has no origin.

**Suggested resolution:** Either (a) update the signature to `get_next_earnings_date(ticker, curr_date, expiry_date: Optional[str] = None)` with the rule "when `expiry_date` is None, use the nearest listed expiration from `yf.Ticker.options`" and specify what the stub returns for `Ticker.options` in the fixture, or (b) remove `within_options_cycle` from this function and compute it in `WheelAnalyst` / `CspAgent` using the expiry date that those agents already have in context.

---

### [TEV2-REVIEW-02] Medium — REQ-LIFE-03 AC1 boundary condition conflicts with the profit-capture rule description

**Requirement(s):** REQ-LIFE-03 (AC1), REQ-LIFE-03 (Description rule 1)

**Finding:** The description for rule 1 says: "If current contract value has declined to ≤ `take_profit_pct` (default: 50%) of premium received, recommend `ROLL` or `HOLD`." AC1 specifies the input as "Premium at 50% of received value, DTE = 30" and asserts `action="HOLD"`. AC1 therefore places the boundary case (exactly 50%) as a `HOLD`, but the description's rule is satisfied by either `ROLL` or `HOLD`. This means:

1. AC1 asserts one specific outcome (`HOLD`) for a condition where the description permits two (`ROLL` or `HOLD`). Any implementation that returns `ROLL` at exactly 50% would correctly satisfy the rule description but fail AC1.
2. The secondary condition that disambiguates `HOLD` from `ROLL` within the profit-capture rule (i.e., which sub-condition triggers each action) is not stated anywhere in the REQ.

**Impact:** Two compliant implementations of rule 1 will produce different outputs for the same input. AC1 will either be wrong (rejecting a valid `ROLL`) or under-constrained. Regression tests built on AC1 will be implementation-specific rather than requirements-derived.

**Suggested resolution:** Make AC1 internally consistent with the description by either: (a) adding the disambiguating sub-condition to rule 1 (e.g., "if DTE > `dte_to_roll`, return `HOLD`; otherwise return `ROLL`") and rewriting AC1 to reflect this (input: 50% value + DTE 30 > 21 → `HOLD` with `trigger_reason="profit_capture"`), or (b) changing AC1's input to a clearly unambiguous case (e.g., 40% value + DTE 30 → `HOLD`) and adding a second AC for the boundary.

---

### [TEV2-REVIEW-03] Medium — REQ-LIFE-03 earnings rule (rule 4) has no acceptance criterion

**Requirement(s):** REQ-LIFE-03 (Description rule 4)

**Finding:** The description defines five decision rules for `RollCheckAgent`: profit capture, DTE, breach (split into two sub-cases), earnings, and analyst update. The `trigger_reason` Literal in REQ-LIFE-04 includes `"earnings_rule"`. However, there is no AC for the earnings rule. The five ACs cover: profit capture (AC1), DTE (AC2), breach_roll (AC3a), breach_close (AC3b), and analyst update (AC4). The earnings rule — "If an earnings date falls within the remaining DTE, recommend `CLOSE` unless the position is deep OTM" — has no corresponding AC.

Additionally, the description's qualifier "unless the position is deep OTM" is itself undefined: "deep OTM" has no numeric threshold, making the earnings rule partially unspecifiable even if an AC were added.

**Impact:** The earnings rule will either be omitted from the implementation (no AC will catch the omission) or implemented with an arbitrary OTM threshold that is not regression-testable. The `trigger_reason="earnings_rule"` enum value exists in REQ-LIFE-04 but has no path through which a test can exercise it.

**Suggested resolution:** Add an AC for the earnings rule: e.g., "Given an earnings date 10 days away and DTE = 25, and the position is not deep OTM, `RollCheckAgent` returns `action="CLOSE"` with `trigger_reason="earnings_rule"`." Also define "deep OTM" with a numeric threshold (e.g., `current_delta_abs < 0.05`) so the qualifier in the rule is implementable and testable.

---

### [TEV2-REVIEW-04] Low — REQ-DATA-02 AC5 does not assert on `iv_percentile` in the flat-range edge case

**Requirement(s):** REQ-DATA-02 (AC5, Description)

**Finding:** The description states: "When `max_vol_lookback == min_vol_lookback` (zero variance): `iv_rank = 50`, `iv_percentile = 50`, and the report includes the note `'IV range is flat — rank set to neutral 50'`." AC5 asserts only that `iv_rank = 50` and that the report string contains the note. The `iv_percentile = 50` override is specified in the description but not verified by any AC.

Given that `iv_percentile` uses a strict `<` comparison (`days where realised_vol < current_vol`), in the zero-variance case all historical values equal the current value, so the raw formula would yield `iv_percentile = 0`, not 50. The flat-range override must apply to both fields, but the AC only guards one.

**Impact:** A correct implementation of the description will set `iv_percentile = 50` on flat ranges; an incorrect implementation that only overrides `iv_rank` will pass all ACs while returning `iv_percentile = 0`, which would incorrectly drive `iv_environment = "compressed"` from `iv_percentile` if any downstream consumer uses that field.

**Suggested resolution:** Extend AC5 to assert: `iv_rank = 50` AND `iv_percentile = 50` AND report string contains `"IV range is flat — rank set to neutral 50"`.

---

### [TEV2-REVIEW-05] Low — REQ-TRADE-01 AC2 note placement not mapped to a schema field

**Requirement(s):** REQ-TRADE-01 (AC2), REQ-TRADE-02

**Finding:** AC2 states: "Returns the closest acceptable strike with a note `'No strike matches Delta target; nearest available: {delta}'`." When `tradeable=True` (which this case implies — the trade proceeds with the nearest strike), the `CspDecision` schema (REQ-TRADE-02) has no field for advisory notes other than `rationale: str`. If this note appears in `rationale`, the AC is testing a free-text LLM field, reverting to the non-deterministic pattern prohibited by the now-resolved TEV-REVIEW-01. If it's intended to be deterministic, a dedicated schema field (e.g., `delta_fallback_note: Optional[str]`) is needed.

**Impact:** The note from AC2 has no home in the schema. A test for AC2 either asserts on the LLM-generated `rationale` (fragile) or cannot be written at all. This is a minor gap but it introduces a non-deterministic assertion into an otherwise deterministic section.

**Suggested resolution:** Either (a) add `delta_fallback_note: Optional[str]` to `CspDecision` — populated deterministically by the filter function when no exact match is found — and update AC2 to assert on this field, or (b) change AC2's assertion to check `CspDecision.delta` is within a widened range rather than a string note.

---

### [TEV2-REVIEW-06] Low — REQ-LIFE-02 AC3a numeric example has a small arithmetic imprecision

**Requirement(s):** REQ-LIFE-02 (AC3a)

**Finding:** AC3a states: `cycle_pnl=930`, `csp_strike=140`, `shares_held=100`, `cycle_duration_days=73` → `cycle_annualised_return_pct` is approximately `33.25%`. Applying the specified formula: `(930 / (140 × 100)) × (365 / 73) × 100 = (930 / 14000) × 5.0 × 100 = 0.066429 × 500 = 33.21%`. The document states `33.25%`, a difference of 0.04 percentage points. While this is small, it is incorrect as stated, and if a test asserts `abs(result − 33.25) < 0.01` it will fail against a correct implementation.

**Impact:** Low — a test author who copies the expected value from the AC verbatim will write a failing test for a correct implementation. The formula is unambiguous; only the stated result is wrong.

**Suggested resolution:** Correct the expected value in AC3a to `33.21%` (or specify a tolerance of ±0.05% if rounding conventions allow). Alternatively state "approximately 33.2%" and specify the tolerance explicitly.

---

### [TEV2-REVIEW-07] Low — REQ-SCREEN-01 AC6/AC7 rejection_reason string containment creates fragile assertion if field is LLM-generated

**Requirement(s):** REQ-SCREEN-01 (AC6, AC7), REQ-SCREEN-02

**Finding:** AC6 asserts `rejection_reason` contains `"Insufficient liquidity"` and AC7 asserts it contains `"Chain spread too wide"`. The `WheelCandidateReport` schema (REQ-SCREEN-02) defines `rejection_reason: Optional[str]` without specifying whether this field is populated by the deterministic pre-LLM filter or by the LLM's structured-output response. If the field is LLM-generated, string containment assertions are fragile (the LLM may paraphrase). If it is pre-LLM (set in the filter logic before the model is called), the assertion is reliable.

**Impact:** If `rejection_reason` is LLM-generated, AC6 and AC7 introduce the same non-determinism pattern that TEV-REVIEW-01 identified and v0.2.0 purportedly resolved. The REQ currently gives no indication of which path applies.

**Suggested resolution:** Specify in REQ-SCREEN-01 or REQ-SCREEN-02 that `rejection_reason` for filter-based rejections (liquidity, spread, price, IV rank) is set deterministically by the pre-LLM screening function (not by the LLM). The LLM is only called when all filter criteria pass and the agent must assess qualitative suitability. This design keeps the string-containment assertions reliable and is consistent with the unit-test-over-mock-LLM pattern mandated by REQ-NFR-05.

---

### [TEV2-REVIEW-08] Low — REQ-DATA-03 AC7 covers ^IRX unavailability but no AC covers `risk_free_rate_source="static"` explicit configuration

**Requirement(s):** REQ-DATA-03 (AC7), Section 7

**Finding:** AC7 covers the fallback path when `^IRX` is unavailable. However, `risk_free_rate_source` can also be explicitly set to `"static"` (see Section 7 config table). There is no AC that tests the explicitly static path: given `risk_free_rate_source="static"`, tool must use `risk_free_rate_static` directly without attempting a `^IRX` fetch. Without this AC, an implementation that always attempts the live fetch first (ignoring the `"static"` setting) will pass all ACs while violating the config contract.

**Impact:** Low — the static path is likely implemented correctly alongside the fallback path, but it is not regression-guarded.

**Suggested resolution:** Add an AC: "Given `config["wheel"]["risk_free_rate_source"] = "static"`, `get_options_greeks` uses `risk_free_rate_static` without calling `yf.Ticker("^IRX")` and the output includes the note `'using static risk-free rate'`." The "without calling" assertion can be verified by mocking `yf.Ticker` and asserting it was not invoked with `"^IRX"`.

---

## Summary

All sixteen findings from the v0.1.0 cross-review have been fully resolved in v0.2.0. The revision is a substantial improvement: the injectable `iv_series` parameter closes the main unit-test seam gap; the `trigger_reason` Literal enum makes `RollCheckAgent` fully regression-testable; the split of REQ-TRADE-01 AC4 into a deterministic filter unit test and a marked integration test is the correct decomposition; and the `console.export_text()` test strategy for CLI ACs is the right approach.

Eight new findings are identified in v0.2.0, none of which is High severity. Two are Medium: the missing `expiry_date` parameter in `get_next_earnings_date` (which makes `within_options_cycle` untestable without an unspecified additional mock surface) and the internally inconsistent AC1 for `RollCheckAgent`'s profit-capture rule (which will reject valid implementations). Three are Low and concern minor gaps: the missing AC for the `RollCheckAgent` earnings rule, the `iv_percentile` not asserted in the flat-range edge case, and the `CspDecision` note field having no schema home. The remaining three Lows are minor numeric and specification hygiene items.

The document is recommended for approval with minor changes addressing the two Medium findings before TSPEC authoring begins. The six Low findings can be resolved in TSPEC or PROPERTIES without blocking progress.

---

## Approved Items

The following aspects of REQ v0.2.0 are well-specified and can proceed to TSPEC/PROPERTIES without changes:

- **REQ-DATA-01 (all ACs including AC5, AC6):** Error-path ACs are now complete and use distinct, non-overlapping return strings. AC5 (network error) and AC6 (empty DataFrame) are distinguishable and automatable.
- **REQ-DATA-02 AC1–AC4:** The `iv_environment` Literal field makes AC3 and AC4 deterministically testable. The injectable `iv_series` parameter closes the main unit-test seam.
- **REQ-DATA-03 AC1–AC6:** Greeks ACs are concrete and cover all known numeric edge cases (0 DTE, negative DTE, IV=0, ATM Delta range). BSM formula boundary conditions are now fully enumerated.
- **REQ-SCREEN-01 AC1–AC8 (with caveat in TEV2-REVIEW-07):** The addition of AC6, AC7, AC8 for liquidity, spread, and price filters closes the coverage gap from TEV-REVIEW-07.
- **REQ-SCREEN-02 (all ACs):** Pydantic schema validation tests remain straightforwardly specifiable. The `list[float]` + `Field(min_length=2, max_length=2)` fix from the SE review is present and correct.
- **REQ-SCREEN-03 and REQ-LIFE-06 (CLI ACs):** `console.export_text()` + `Console(file=StringIO())` is the right and standard approach for Rich output testing. All CLI ACs now have a deterministic observable.
- **REQ-TRADE-01 AC4a / AC4b split:** This is the correct decomposition — deterministic filter unit test plus a separately marked integration test. No other AC in the document handles LLM non-determinism more cleanly.
- **REQ-TRADE-02 AC1 (revised), AC2, AC3:** The delta/theta sign convention fix is correct. The `annualised_yield_pct` formula check (within 0.01%) is the right precision tolerance.
- **REQ-TRADE-05 (all ACs):** Prompt-content assertions (serialised `CspDecision` fields present in the prompt string) are deterministic and correctly scope what is verifiable without an LLM call.
- **REQ-LIFE-01 AC1–AC6:** Phase routing ACs are now complete including the two negative-path ACs (AC5, AC6). These are graph topology tests automatable via LangGraph state inspection with mocked nodes.
- **REQ-LIFE-02 AC1–AC4 plus formula and AC3a:** The formula is now explicit and AC3a provides a concrete numeric anchor. Atomic write pattern and file path convention are specified.
- **REQ-LIFE-03 AC2, AC3a, AC3b, AC4:** DTE rule and breach rule ACs are now deterministically testable via `trigger_reason`. The ROLL/CLOSE disambiguation on breach is correctly handled by the `current_value_pct_of_premium` threshold.
- **REQ-LIFE-04 (all fields):** The `trigger_reason` Literal enum with six named values makes every rule path individually regression-testable without LLM output dependency.
- **REQ-LIFE-05 AC1, AC2 (revised), AC3 (revised), AC4:** All ACs are now testable — presence of `notes` field, specific field content in `past_context`, and full schema presence.
- **REQ-NFR-01 through REQ-NFR-07:** All NFRs are now measurable or otherwise actionable. REQ-NFR-02 now specifies measurement conditions unambiguously. REQ-NFR-05 is now a complete testability contract.
- **Section 7 (Configuration Keys):** Complete env var table with types and defaults. All 17 keys are covered with naming convention explicitly stated. The `positions_dir` key for atomic position file writes is correctly scoped under `config["wheel"]`.
