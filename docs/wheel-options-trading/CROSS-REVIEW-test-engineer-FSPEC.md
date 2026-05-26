# Cross-Review — Test Engineer — FSPEC
# Document: FSPEC-wheel-options-trading.md v0.1.0

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Document reviewed | FSPEC-wheel-options-trading.md v0.1.0 |
| Recommendation | Needs revision |

---

## Summary

The FSPEC is well-structured and identifies the correct test seam in FSPEC-WHEEL-02 (`iv_series` injectable parameter). However, six issues require revision before this document can serve as the basis for PROPERTIES authoring:

1. Two business rules (WheelAnalyst Criterion 5 and RollCheckAgent Rule 5) have no defined test seam, making them untestable without live LLMs and live state.
2. Acceptance tests for deterministic filter boundaries (delta inclusivity, IV rank thresholds, breach threshold, deep-OTM boundary) are absent, leaving the most precisely specified rules unverified.
3. All "Who: Agent" acceptance tests leave test level unspecified — it is unclear whether these are unit tests with mocked LLMs, integration tests, or e2e tests, which blocks the TE from selecting the right fixture strategy.
4. Three acceptance tests assert on `tradeable=True` with strike populated but the strike is selected by the LLM — these ACs are not deterministically verifiable without mocking.
5. The `rationale` field (present on all output schemas) is never asserted in any AC, creating a gap: tests will never catch a schema that omits `rationale` or populates it with `None`.
6. Several edge-case branches specified in the flow sections have no corresponding acceptance test.

---

## Findings

### [FSPEC-TE-01] High — WheelAnalyst Criterion 5 (analyst consensus) has no test seam

**FSPEC section:** FSPEC-WHEEL-03, step 6; Business Rules
**Finding:** Criterion 5 reads the overall analyst consensus from the "Portfolio Manager's most recent `PortfolioDecision` signal, or if not yet available, by majority vote across the four analyst reports." No injectable seam or mock-friendly interface is defined for this criterion. The four analyst reports are free-text or complex LangChain messages; majority vote extraction logic from them is LLM-dependent in practice. The FSPEC Open Questions section itself admits the "exact signal extraction logic from existing analyst report schemas" is unresolved.
**Impact:** There is no way to write a deterministic unit test for Criterion 5 without resolving how the consensus signal is extracted. Any test for a multi-criterion failure that includes Criterion 5 cannot be reliably reproduced without either a live LLM or a precisely specified signal field. AC REQ-SCREEN-01 AC4 (bull/bear debate concluded with Sell rating) is currently unverifiable.
**Suggested resolution:** Add a business rule stating that `analyst_bias` must be derived from a specific, structured field (e.g., `PortfolioDecision.signal` Literal, or an `overall_signal: Literal["Buy","Hold","Sell"]` field on each analyst report). Document the exact extraction rule so it can be exercised with a dict fixture. If the extraction requires LLM judgment, define a thin structured extraction step whose output is a Literal — that step is the unit under test, not the prose report.

---

### [FSPEC-TE-02] High — RollCheckAgent Rule 5 (analyst_update) has no test seam for prior-run state

**FSPEC section:** FSPEC-WHEEL-06, step 5 (Rule 5); Open Questions
**Finding:** Rule 5 fires when "the latest analyst consensus has changed from bullish (prior run) to bearish (current run)." This requires comparing the current consensus to a value stored from a previous invocation. The FSPEC Open Questions section explicitly acknowledges this storage mechanism is undefined ("SE author must specify how the prior consensus is stored and retrieved — e.g., in `WheelPosition.notes`, a separate state field, or the memory log"). Without a defined storage field, there is no way to construct a test fixture that exercises the bullish→bearish transition.
**Impact:** The acceptance test for REQ-LIFE-03 AC4 ("Analyst consensus changed from bullish to bearish") cannot be written as a unit or integration test. A test would require either two sequential full-graph invocations or a mock for an undefined storage interface. Regression coverage for Rule 5 is zero until this is resolved.
**Suggested resolution:** Add a business rule specifying the exact storage location and format of the prior analyst consensus (e.g., `WheelPosition.prior_analyst_bias: Literal["bullish", "neutral", "bearish"] | None`). The rule evaluation then becomes: `prior_analyst_bias == "bullish" and current_analyst_bias == "bearish"`. This is a deterministic boolean that can be tested with a simple `WheelPosition` fixture.

---

### [FSPEC-TE-03] High — Three "Who: Agent" acceptance tests assert on LLM-selected strike fields

**FSPEC section:** FSPEC-WHEEL-04 AC1 (CspAgent tradeable=True, strike populated); FSPEC-WHEEL-05 AC1 (CcAgent, strike >= 140.0); FSPEC-WHEEL-05 AC4 (strike_above_cost_basis validated)
**Finding:** These ACs are tagged "Who: Agent" and require running the agent end-to-end. The assertions include `strike` being populated, `annualised_yield_pct >= min_annualised_yield_pct`, and `strike >= 140.0`. The strike value is selected by the LLM in Stage 4 of each flow. Without a mocked LLM constrained to a fixed response, these assertions are non-deterministic — the LLM might select any strike from the filtered candidate list.
**Impact:** If implemented as written, these tests will be flaky unless the LLM is mocked. The FSPEC does not specify whether "Who: Agent" means a full e2e run with a real LLM, or an integration test with `FakeChatModel` returning a scripted response. This ambiguity means the TE cannot write a reliable pass/fail assertion.
**Suggested resolution:** Split each of these ACs into two: (a) a unit/integration test that verifies the deterministic pre-filter produces a candidate set where all entries satisfy the yield/delta constraint (LLM mocked with `FakeChatModel` to return the first candidate), and (b) a contract test that verifies the `CspDecision`/`CcDecision` schema is valid regardless of which candidate was selected. The formula-correctness assertion (FSPEC-WHEEL-04 AC5) is already well-framed as "Who: System" and should serve as the model.

---

### [FSPEC-TE-04] Medium — No acceptance test covers the IV rank boundary values (25 and 50)

**FSPEC section:** FSPEC-WHEEL-02, step 9; Business Rules
**Finding:** The FSPEC precisely specifies that `iv_rank == 25` maps to `"normal"` and `iv_rank == 50` maps to `"elevated"`. These are exact boundary values with documented intent. The existing acceptance tests cover `iv_rank >= 50` (elevated) and `iv_rank < 25` (compressed), but there is no AC for `iv_rank == 25` (boundary of normal), `iv_rank == 49.999` (just below elevated), or `iv_rank == 50` (boundary of elevated). There is also no AC for `iv_rank` in the range [25, 50) → `"normal"`.
**Impact:** The boundary at 25 (normal vs compressed) is exercised by no AC. An off-by-one implementation (`> 25` instead of `>= 25`) would pass all existing ACs.
**Suggested resolution:** Add unit-level ACs using the `iv_series` test seam:
- `iv_rank == 25.0` → `iv_environment == "normal"` (injectable series)
- `iv_rank == 50.0` → `iv_environment == "elevated"` (injectable series)
- `iv_rank == 24.9` → `iv_environment == "compressed"` (injectable series)
These can be produced exactly by crafting an `iv_series` where `current_vol`, `min_vol`, and `max_vol` are chosen to produce the desired rank.

---

### [FSPEC-TE-05] Medium — No acceptance test covers Filter A delta boundary inclusivity

**FSPEC section:** FSPEC-WHEEL-04, step 6; FSPEC-WHEEL-05, step 10; Business Rules
**Finding:** Both the CSP and CC filter specifications state delta range boundaries are inclusive (`target_csp_delta_low <= abs(delta) <= target_csp_delta_high`). The FSPEC-WHEEL-04 AC that covers Filter A (AC4, "Who: System") only checks that strikes outside [0.15, 0.25] are rejected — it does not test that a strike with `abs(delta) == 0.15` (lower boundary) or `abs(delta) == 0.25` (upper boundary) is retained.
**Impact:** An implementation using strict inequality (`< target_csp_delta_low`) would pass all existing ACs but incorrectly reject boundary strikes. Given that delta values from yfinance are floating-point and may land exactly on the configured boundary, this is a realistic defect scenario.
**Suggested resolution:** Add a unit test (mocked chain, mocked Greeks) for each filter: one candidate with `abs(delta) == target_csp_delta_low` must survive Filter A; one with `abs(delta) == target_csp_delta_high` must survive Filter A. Same pattern for CC Filter B.

---

### [FSPEC-TE-06] Medium — No acceptance test for Rule 3 breach threshold boundary and Rule 4 deep-OTM boundary

**FSPEC section:** FSPEC-WHEEL-06, Rule 3 and Rule 4; Business Rules
**Finding:** The FSPEC specifies two precise exclusive/inclusive boundaries:
- Rule 3 breach: fires when `spot_price <= csp_strike × 0.85` (exact 15% threshold).
- Rule 4 deep-OTM: does NOT fire when `abs(current_delta) < 0.10`; DOES fire when `abs(current_delta) >= 0.10`.

The existing ACs for Rule 3 (AC3a, AC3b) use "stock dropped >= 15% below CSP strike" without testing the exact boundary (`spot_price == csp_strike × 0.85`). There is no AC for Rule 4's deep-OTM boundary at exactly `abs(delta) == 0.10`.
**Impact:** An implementation that uses `< 0.85` instead of `<= 0.85` for Rule 3, or `<= 0.10` instead of `< 0.10` for the deep-OTM check, would pass all current ACs.
**Suggested resolution:** Add boundary unit tests:
- Rule 3: `spot_price = csp_strike * 0.85` → Rule 3 fires (boundary inclusive). `spot_price = csp_strike * 0.851` → Rule 3 does not fire.
- Rule 4 deep-OTM: `abs(current_delta) = 0.10` → NOT deep OTM → Rule 4 fires (earnings within DTE). `abs(current_delta) = 0.09` → deep OTM → Rule 4 does not fire.

---

### [FSPEC-TE-07] Medium — All "Who: Agent" ACs are missing test level specification

**FSPEC section:** All six FSPEC sections (acceptance tests throughout)
**Finding:** The acceptance tests use three "Who" labels — "Agent", "System", and "Developer" — but none of these maps to a standard test level (unit / integration / e2e / smoke). "Who: Agent" appears on ACs that require the full agent invocation (e.g., WheelAnalyst runs, CspAgent runs, RollCheckAgent runs). It is ambiguous whether these mean:
- Unit tests with all data tools mocked and LLM replaced by `FakeChatModel`
- Integration tests with mocked yfinance but real LangChain graph execution
- End-to-end smoke tests with live yfinance and a real LLM

The codebase uses pytest markers `unit`, `integration`, and `smoke`. Without test level assignment, the TE cannot determine which marker to apply, which fixtures to build, or whether the test belongs in the fast CI gate or a slower nightly run.
**Impact:** PROPERTIES authoring will require the TE to make undocumented assumptions about test level for every "Who: Agent" AC. If those assumptions differ from the implementer's expectations, tests will either be too slow for the CI gate or too shallow to catch regressions.
**Suggested resolution:** Add a test level annotation to each AC. Suggested mapping: ACs that test deterministic rule logic (filters, formula correctness, schema field values) → `unit`. ACs that require the full agent flow with mocked LLM and mocked data tools → `integration`. ACs that run in a real LangGraph graph invocation with live tools → `smoke`. At minimum, mark each AC with `[unit]`, `[integration]`, or `[smoke]`.

---

### [FSPEC-TE-08] Medium — Progressive relaxation branches in FSPEC-WHEEL-04 and FSPEC-WHEEL-05 have no acceptance tests

**FSPEC section:** FSPEC-WHEEL-04, steps 9a–9d; FSPEC-WHEEL-05, steps 13a–13d
**Finding:** The CSP progressive relaxation defines four named branches: yield_filter_relaxed (9a), earnings_filter_relaxed (9b), nearest-Delta fallback (9c), and earnings hard block (9d). The CC flow defines the same structure. The ACs cover only the nearest-Delta fallback (9c / AC2) and the earnings hard block (9d / AC3). Relaxation attempts 9a and 9b have no corresponding acceptance test.
**Impact:** The relaxation logic in steps 9a and 9b is non-trivial: it changes which filters are active and adds notes to the output. There is no AC verifying that (a) the `yield_filter_relaxed` note appears in the output when only Filter C is dropped, (b) the `earnings_filter_relaxed` note appears when Filters B and C are both dropped, or (c) relaxed candidates are still presented to the LLM rather than the system returning `tradeable=False` prematurely.
**Suggested resolution:** Add ACs for each relaxation attempt:
- "Given: all strikes pass A and B but fail C (yield too low) — When: filter runs — Then: `tradeable=True` and output contains `yield_filter_relaxed` note."
- "Given: all strikes pass A but fail B and C — When: filter runs — Then: `tradeable=True` and output contains `earnings_filter_relaxed` note."
These can be unit tests with a mocked chain and mocked Greeks.

---

### [FSPEC-TE-09] Medium — Simultaneous multi-rule firing (Rules 1+2 and others) has only one AC and it is in the edge cases section, not the AC list

**FSPEC section:** FSPEC-WHEEL-06, edge cases ("Both Rule 1 and Rule 2 fire"); Business Rules (priority order)
**Finding:** The FSPEC defines a six-level priority order (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1) for multi-rule firing. The only multi-rule scenario tested in the AC list is the implicit Rule 1+2 conflict mentioned in the edge cases section — and even that is documented as an edge case description, not as a formal AC. Combinations such as Rule 3 + Rule 2 (breach AND DTE approaching), Rule 4 + Rule 2 (earnings AND DTE), and Rule 5 + Rule 3 (analyst update AND breach) have no ACs.
**Impact:** The priority ordering is a core business rule. Without ACs for multi-rule scenarios, an implementation that evaluates rules in wrong order or that short-circuits on first firing would pass all existing ACs.
**Suggested resolution:** Add unit-level ACs for at least:
- Rule 3 fires simultaneously with Rule 2: final action must be from Rule 3 (higher priority).
- Rule 5 fires simultaneously with Rule 4: final action must be `CLOSE` with `trigger_reason == "analyst_update"` (Rule 5 > Rule 4).
- Rule 1 fires simultaneously with Rule 2: final action must be `ROLL` with `trigger_reason == "dte_rule"` (this case is described in edge cases but should be a formal AC).
These are pure unit tests on the rule-evaluation function with mocked inputs.

---

### [FSPEC-TE-10] Medium — `rationale` field schema correctness is not verified by any AC

**FSPEC section:** FSPEC-WHEEL-03 Output table; FSPEC-WHEEL-04 Output; FSPEC-WHEEL-05 Output; FSPEC-WHEEL-06 Output table
**Finding:** Every output schema (`WheelCandidateReport`, `CspDecision`, `CcDecision`, `RollDecision`) includes a `rationale: str` field marked "Always" populated. No acceptance test asserts that this field is non-None, non-empty, or of type `str` when the agent runs. Tests that check `approved`, `tradeable`, `action`, and `trigger_reason` will not catch a schema implementation that defines `rationale` as `Optional[str]` or that returns `None` for `rationale` in rejection paths.
**Impact:** The field will be green in schema validation but could silently be empty or absent in practice, breaking downstream consumers that display rationale text.
**Suggested resolution:** Add a low-scope schema contract AC to each agent section: "Given: any terminal output from the agent — When: `rationale` field is read — Then: it is a non-empty string." This is trivially verifiable in the same unit test that checks other schema fields.

---

### [FSPEC-TE-11] Low — `get_iv_metrics` AC1 does not specify that yfinance must be mocked

**FSPEC section:** FSPEC-WHEEL-02, AC1
**Finding:** AC1 is "Given: A valid ticker with 252+ trading days of OHLCV history — When: `get_iv_metrics(ticker, curr_date)` is called — Then: Returned dict contains `iv_rank` and `iv_percentile` in [0, 100] with no NaN values." This AC does not use the `iv_series` injectable seam. As written, it requires a live yfinance call (or an unspecified mock of `yf.Ticker.history()`). The test will be non-deterministic (network-dependent) unless the test fixture is specified.
**Impact:** If implemented as a unit test without explicit mocking instructions, it will be classified as integration or smoke, making it too slow for the fast CI gate and dependent on network availability.
**Suggested resolution:** Replace or supplement AC1 with a test that uses the `iv_series` seam (e.g., inject a known 252-element series), or explicitly annotate AC1 as `[smoke]` to signal that network access is required and it belongs in the nightly run, not the unit gate.

---

### [FSPEC-TE-12] Low — FSPEC-WHEEL-03 AC for `approved=True` does not verify `recommended_strike_range` is non-sentinel

**FSPEC section:** FSPEC-WHEEL-03, first AC (REQ-SCREEN-01 AC1)
**Finding:** The AC states "all five criteria are met → `WheelCandidateReport.approved == True`." When `approved=True`, the FSPEC specifies that `recommended_strike_range` must be computed via the Delta-anchored method (step 8) and must not be `[0.0, 0.0]` (the null sentinel). However the AC only checks `approved == True`; it does not verify that `recommended_strike_range != [0.0, 0.0]` and has two positive float elements. The strike range derivation (step 8) is a non-trivial sub-flow that could silently fail and fall back to `[0.0, 0.0]` even on the approved path.
**Impact:** The Delta-anchored strike range derivation (or its fallback) will have no regression coverage from the AC list.
**Suggested resolution:** Extend the `approved=True` AC: "Then: `recommended_strike_range` is a list of two positive floats, both greater than 0.0." This adds one line to the AC and covers the entire step 8 sub-flow.

---

### [FSPEC-TE-13] Low — FSPEC-WHEEL-07 state machine AC4 (phase transition) does not specify how transition is triggered

**FSPEC section:** FSPEC-WHEEL-07, AC4 (REQ-LIFE-01 AC4)
**Finding:** AC4 reads: "Given: Phase transition occurs (CSP assigned — `assignment_date` is written to `WheelPosition`) — When: State is updated — Then: `wheel_phase` in `AgentState` changes from `'csp_open'` to `'stock_owned`'." The FSPEC Open Questions section explicitly notes that the CSP assignment event may be triggered manually by the human trader (not automated). If the trigger is manual, this AC cannot be tested as an automated test — it describes a human-in-the-loop action. If it can be triggered by writing to `WheelPosition`, the AC should name the function/method that performs this write so a unit test can call it directly.
**Impact:** Without knowing the automation boundary, the test engineer cannot write this AC as either a unit or integration test. It may need to be scoped as a manual test only, which should be explicitly documented.
**Suggested resolution:** Resolve the Open Question for assignment detection before this AC is finalised. If the trigger is always manual: mark the AC as `[manual]` and exclude it from automated test plans. If there is a function that reads `WheelPosition.assignment_date` and updates `AgentState["wheel_phase"]`, name that function in the AC so it can be unit-tested directly.

---

## Approved Items

The following aspects of the FSPEC are well-specified from a testability perspective and require no changes:

- **`iv_series` injectable test seam (FSPEC-WHEEL-02):** The parameter is precisely defined, its bypass semantics are unambiguous, and the zero-variance fixture (`[0.20] * 100`) in AC5 is an exemplary unit-testable AC. All boundary notes (flat-range, shortened-lookback) are testable via this seam.
- **Vendor routing acceptance tests (FSPEC-WHEEL-01):** The Alpha Vantage stub AC ("returns `'not implemented'` — no exception") is deterministic, does not require yfinance or LLM mocking, and tests the exact error-isolation property specified in the business rules.
- **Formula ACs (FSPEC-WHEEL-04 AC5, FSPEC-WHEEL-05 AC4):** The `annualised_yield_pct` formula AC and `strike_above_cost_basis` boolean AC are both "Who: System" with deterministic assertions on computed fields. These are the correct model for all formula-correctness tests.
- **`WheelStateError` ACs (FSPEC-WHEEL-07 AC5, AC6):** The state machine error ACs are deterministic: given a specific invalid state, either an exception is raised or a fallback path is taken. Both are testable with a simple `AgentState` dict fixture and a mocked position store.
- **`rejection_reason` string content ACs (FSPEC-WHEEL-03 OI and spread ACs):** The exact substrings (`"Insufficient liquidity"`, `"Chain spread too wide"`, `"Stock price exceeds cash management limit"`) are specified and machine-checkable via `in` operator. These are well-formed deterministic ACs.
- **Earnings hard block AC (FSPEC-WHEEL-04 AC3):** Clear precondition (all expirations straddle earnings), deterministic assertion (`tradeable=False`, exact `rejection_reason` string), and the LLM is explicitly not called — making this a clean unit test.
- **Output field table completeness:** All output schemas enumerate field names, types, population conditions, and sentinel values. This gives the PROPERTIES author enough information to write schema-contract tests without reading implementation code.
