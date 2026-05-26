# Cross-Review — Test Engineer — REQ
# Document: REQ-wheel-options-trading.md

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Document reviewed | REQ-wheel-options-trading.md v0.1.0 |
| Recommendation | Needs revision |

---

## Summary

The REQ is well-structured and unusually precise for a first-draft requirements document: numeric thresholds, formula definitions, and Pydantic schema field lists make the majority of acceptance criteria directly automatable. The Phase 1 data-layer requirements (REQ-DATA-01 through REQ-DATA-05) are the strongest section — most ACs are concrete enough to become unit tests with mocked yfinance calls today. The Phase 3 schema ACs (REQ-TRADE-02, REQ-TRADE-04) include formula checks, which is excellent. However, five High-severity gaps exist: LLM-agent ACs that cannot be deterministically asserted, missing error and rate-limit paths, undefined observable assertions for the roll-decision agent, unspecified mock strategy for `yf.Ticker.option_chain()`, and the memory-log reflection requirement which is completely untestable as written. A further cluster of Medium and Low findings covers boundary conditions on formulae (IV Rank division-by-zero), timing precision for the 10 s NFR, and CLI output testability. These must be addressed before TSPEC and PROPERTIES can be written without ambiguity.

---

## Findings

### [TEV-REVIEW-01] High — LLM agent ACs are non-deterministic and untestable as written

**Requirement(s):** REQ-SCREEN-01 (AC2, AC3, AC4), REQ-TRADE-01 (AC1, AC2, AC3), REQ-TRADE-03 (AC2), REQ-LIFE-03 (AC1, AC2, AC3, AC4), REQ-TRADE-05 (AC1, AC2)

**Finding:** Multiple ACs are phrased as "Agent runs → Report is `approved: false` with reason X" or "Aggressive debater arguments reference Y." These ACs depend on an LLM producing a specific string or making a particular argument — outputs that vary per model, temperature, and prompt version. They cannot be turned into reliable automated regression tests without deterministic stubs.

**Impact:** Tests written directly against these ACs would be flaky by design. Regressions in agent logic (e.g., the agent stops filtering on IV Rank) would go undetected if the LLM happens to produce the right-shaped output for the wrong reasons. The test suite would give false confidence.

**Suggested resolution:** Decompose each agent AC into two layers:

1. **Unit test (deterministic):** Mock the LLM to return a fixed structured response and assert that the agent correctly routes/formats/populates the schema field (e.g., `approved=False`, `rejection_reason` non-empty). This tests the agent scaffolding, not the LLM.
2. **Prompt-content assertion (integration test, opt-in):** Assert that the prompt *sent* to the LLM contains the required data fields (IV Rank value, earnings date, etc.). This tests that the agent passes the right context, which is deterministic.

Add a note to REQ-NFR-05 specifying that agent tests must mock the LLM and assert on structured-output fields, not on free-text rationale strings.

---

### [TEV-REVIEW-02] High — No mock/stub strategy defined for `yf.Ticker.option_chain()`

**Requirement(s):** REQ-DATA-01, REQ-DATA-02, REQ-DATA-03, REQ-DATA-04, REQ-NFR-05, REQ-NFR-06

**Finding:** The REQ mandates testability via REQ-NFR-05 ("every new agent must have at least one unit test with a mocked data layer") but never defines how `yf.Ticker.option_chain()` is to be mocked, what a valid stub response shape looks like, or whether a fixture module of canned option chain DataFrames will be provided. Without this, every implementer will invent a different mock structure, producing incompatible and fragile test fixtures.

The REQ also introduces `yf.Ticker.calendar` (REQ-DATA-04) and historical IV sampling over 252 trading days (REQ-DATA-02), neither of which has a stub contract defined. The 252-day IV sampling path is particularly high-risk: if the yfinance API changes or rate-limits, the test has no safe fallback fixture.

**Impact:** Unit tests for REQ-DATA-01 through REQ-DATA-04 will either hit the live yfinance API (fragile CI) or use inconsistent mocks (coverage gaps). Integration tests will be impossible to run offline.

**Suggested resolution:**

- Add a requirement (or a note under REQ-NFR-05) specifying that a canonical pytest fixture `option_chain_fixture(ticker, expiry)` must be provided in `tests/fixtures/options_fixtures.py`, returning a `pd.DataFrame` with the exact columns expected by the data layer.
- Specify the minimum stub shape for `yf.Ticker.calendar` (a dict with an `Earnings Date` key, or `None`).
- Require that `get_iv_metrics` accepts an injectable `iv_series` parameter or a seam for overriding historical data retrieval, so unit tests can pass in a fixed 252-element list.

---

### [TEV-REVIEW-03] High — Error and exception paths are incompletely specified

**Requirement(s):** REQ-DATA-01 (AC2), REQ-DATA-03 (AC3), REQ-DATA-04 (AC3), REQ-NFR-06

**Finding:** REQ-NFR-06 states that data fetch failures must return a graceful error string, but the following failure modes have no AC at all:

- **yfinance rate limit / HTTP 429:** No defined return value. Should this return a specific error string, a sentinel, or retry?
- **yfinance `option_chain()` returns an empty DataFrame** (valid ticker but no options listed): REQ-DATA-01 AC2 covers "no available options" but does not distinguish between an empty chain and a network error — these should produce different observable outputs.
- **IV Rank denominator is zero** (`max_IV_52w == min_IV_52w`, i.e., IV was flat for a year): REQ-DATA-02 has no AC for this divide-by-zero path. The formula in Assumption A3 is undefined when the range is zero.
- **BSM with negative time-to-expiry** (e.g., expiry is in the past by 1 day, not 0 DTE): REQ-DATA-03 AC3 covers 0 DTE but not negative DTE, which also produces a math domain error in `sqrt(T)`.
- **`get_options_greeks` with IV = 0** (some far OTM strikes report zero IV): No AC covers the BSM formula behaviour when `sigma = 0`.
- **`within_options_cycle` flag in REQ-DATA-04 AC2** is asserted to be `True` when "earnings is 10 days away and expiration is 30 days away" — but the definition of `within_options_cycle` in the description says "if any front-month expiration falls on or after the earnings date," which is the opposite condition. This is a contradiction in the AC.

**Impact:** Implementers will make different choices for all undefined paths. Tests will not cover crash-causing inputs. The `within_options_cycle` contradiction will produce a broken implementation that passes its own incorrectly-specified tests.

**Suggested resolution:**

- Add ACs to REQ-DATA-01 for: (a) yfinance HTTP error → returns `"Error fetching options chain for {ticker}: {error}"`, (b) empty chain DataFrame → returns `"No options chain available for {ticker}"` (keep distinct from network error).
- Add AC to REQ-DATA-02 for: IV range is zero → returns IV Rank = 50 (or `"Insufficient IV variance to compute rank"`) rather than `NaN` or `ZeroDivisionError`.
- Add ACs to REQ-DATA-03 for: negative DTE → same error as 0 DTE; IV = 0 → returns `"Cannot compute Greeks: implied volatility is zero for strike {strike}"`.
- Fix REQ-DATA-04 AC2: clarify that `within_options_cycle = True` means the earnings date falls *within* the options cycle window (i.e., earnings < expiry), so a 10-day earnings date with a 30-day expiry means the earnings event happens *before* expiry, and the flag should be `True`. Rewrite the AC text to remove ambiguity.

---

### [TEV-REVIEW-04] High — REQ-LIFE-03 (RollCheckAgent) ACs are not deterministically testable

**Requirement(s):** REQ-LIFE-03 (AC1, AC2, AC3, AC4), REQ-LIFE-04

**Finding:** The RollCheckAgent rules (profit capture, DTE, breach, earnings, analyst update) are each individually rule-based and therefore testable — but the ACs conflate the rule-firing logic with the LLM's choice of rationale string. For example:

- AC1: "Returns `HOLD` with rationale 'at 50% profit captured; DTE sufficient to hold'" — the rationale string is an LLM output.
- AC3: "Returns `ROLL` (roll down/out) or `CLOSE` with explicit rationale" — the AC accepts either action. This is under-constrained: it cannot fail.

Additionally, AC3 states the agent returns either `ROLL` or `CLOSE` for a 15% breach, but neither the REQ description nor the AC specifies the *observable decision criterion* that distinguishes these two outcomes. Two engineers implementing this rule would produce different results.

**Impact:** AC3 as written can never fail as a test because both outcomes are accepted. The rule disambiguating `ROLL` vs. `CLOSE` on breach is missing, so the integration can never be regression-tested. AC1 and AC4 rationale assertions will be flaky.

**Suggested resolution:**

- For AC3: Define the decision criterion. For example: "If `current_value_pct_of_premium ≥ 50` (position has retained value), return `ROLL`; if `< 50` (deep loss), return `CLOSE`." Then write AC3 as two separate ACs — one for each branch with a fixed input.
- For all rationale ACs: change the assertion to check the `trigger_reason` field of `RollDecision` (which is in the schema) rather than the free-text `rationale` field. `trigger_reason` should be drawn from an enum of rule names so it is deterministically testable.
- Add a `trigger_reason` enum to REQ-LIFE-04 (e.g., `"profit_capture"`, `"dte_rule"`, `"breach_rule"`, `"earnings_rule"`, `"analyst_update"`).

---

### [TEV-REVIEW-05] High — REQ-LIFE-05 LLM reflection AC is untestable

**Requirement(s):** REQ-LIFE-05 (AC2, AC3)

**Finding:** AC2 asserts "LLM reflection notes the loss and contributing conditions." There is no observable proxy for this: the LLM's reflection is free text. AC3 asserts that `past_context` "includes prior cycle summary" — this is testable by checking that the summary string is present in the prompt, but the REQ does not specify what fields from `WheelPosition` must appear in the summary (ticker? cycle P&L? annualised return?).

**Impact:** AC2 cannot be automated at all. AC3 can only be tested by asserting on whatever text the implementer happened to include, with no correctness guarantee.

**Suggested resolution:**

- Remove AC2 or replace it with a testable proxy: "When `cycle_pnl < 0`, the memory log entry's `notes` field is non-empty" — the content is LLM-generated but its *presence* is testable.
- For AC3: specify the required fields: "`past_context` must contain the ticker, `cycle_pnl` formatted to 2 decimal places, and `cycle_annualised_return_pct`." This makes the assertion deterministic regardless of LLM prose.
- Add an AC1 for AC-level schema testing: "Memory log entry for a completed cycle contains all fields from `WheelPosition` with `cycle_pnl` and `cycle_annualised_return_pct` non-null."

---

### [TEV-REVIEW-06] Medium — REQ-NFR-02 latency requirement has no specified measurement method

**Requirement(s):** REQ-NFR-02

**Finding:** "Options chain fetch must complete within 10 seconds for any US equity ticker." This is a performance requirement but specifies neither: (a) measurement conditions (cold cache, warm cache, CI network, local network?); (b) what the measured interval is (entire `get_options_chain()` call including parsing? just the `yf.Ticker.option_chain()` HTTP call?); (c) percentile (p50? p95? worst case?); (d) whether this applies in CI with a mocked network (meaningless) or only in integration tests against the live API.

**Impact:** Without these parameters, any implementation that passes a single manual timing check on a developer's machine will be declared compliant. The requirement cannot be regressed automatically in CI.

**Suggested resolution:** Rewrite as: "The `get_options_chain()` function, measured from call entry to return of the formatted string, must complete within 10 seconds at p95 on a live yfinance network call (integration test, not mocked). In unit tests (mocked), no timing constraint applies. A pytest `integration` mark test using `pytest-benchmark` or `time.perf_counter` must assert this." If the 10 s target cannot be externally validated in CI (no live API access), either remove the automated assertion requirement or relax to a manual benchmark note.

---

### [TEV-REVIEW-07] Medium — REQ-SCREEN-01 liquidity filter criteria use a combined AC that hides individual rule failures

**Requirement(s):** REQ-SCREEN-01 (AC1, AC2, AC3, AC4)

**Finding:** AC1 requires "all five criteria are met" and asserts `approved: true`. There are no ACs for the liquidity criteria individually: minimum OI ≥ 100 and bid/ask spread ≤ 10%. This means a bug where the liquidity filter is broken (accepts OI = 0 strikes) would not be caught by any AC, because AC1 tests the happy path and the failure ACs only cover IV Rank (AC2), earnings (AC3), and analyst consensus (AC4).

**Impact:** The liquidity filter can be entirely omitted from the implementation and all ACs would still pass.

**Suggested resolution:** Add two ACs:
- AC6: "Given a chain where all near-the-money strikes have OI < 100, report is `approved: false` with reason 'Insufficient liquidity'."
- AC7: "Given a chain where all near-the-money strikes have bid/ask spread > 10% of mid, report is `approved: false` with reason 'Chain spread too wide'."

Also add an AC for price affordability (the `max_wheel_stock_price` check): AC8: "Given stock price $600 with `max_wheel_stock_price=500`, report is `approved: false`."

---

### [TEV-REVIEW-08] Medium — REQ-TRADE-01 AC4 is redundant with REQ-SCREEN-01 and not independently testable

**Requirement(s):** REQ-TRADE-01 (AC4)

**Finding:** AC4 states "target delta range is `[0.15, 0.25]` in config → strike selected has put delta in [0.15, 0.25]." This AC depends on: (a) the CspAgent calling `get_options_greeks` for each candidate strike, (b) the LLM selecting the strike from the returned Greeks, (c) the options chain fixture having at least one strike in the delta range. This is a multi-layer integration test disguised as a single AC and will fail non-deterministically if the LLM ignores the delta guidance.

**Impact:** If the LLM selects a strike outside the delta range because the prompt does not enforce it, this AC fails — but the root cause is prompt design, not a code bug. A unit test cannot distinguish the two.

**Suggested resolution:** Split into two ACs: (a) A unit test asserting that the *filter function* (not the LLM) correctly rejects strikes outside the configured delta range from the candidate set before it is presented to the LLM; (b) an integration AC that the final `CspDecision.delta` is within the configured range (accepting that this requires an LLM call and should be marked `@pytest.mark.integration`).

---

### [TEV-REVIEW-09] Medium — REQ-LIFE-02 `cycle_annualised_return_pct` formula is not specified

**Requirement(s):** REQ-LIFE-02 (AC3)

**Finding:** AC3 specifies `cycle_pnl = (145 − 140 + 4.30) × 100 = 930` — the P&L formula is clear and testable. However, `cycle_annualised_return_pct` is not given a formula, even though it appears in both the schema and the AC. Without the formula, two implementers will compute different values (annualised yield on cost basis vs. on strike vs. on max cash required), and there is no way to write a regression test for it.

**Impact:** `cycle_annualised_return_pct` will be meaningless as a comparable metric and cannot be validated by automated tests.

**Suggested resolution:** Add the formula explicitly to REQ-LIFE-02, analogous to Assumption A3. For example: `cycle_annualised_return_pct = (cycle_pnl / (csp_strike × 100)) × (365 / cycle_duration_days) × 100`. Then add an AC that checks a known-input/known-output pair.

---

### [TEV-REVIEW-10] Medium — REQ-SCREEN-03 and REQ-LIFE-06 CLI ACs require human visual inspection

**Requirement(s):** REQ-SCREEN-03 (AC1, AC2, AC3), REQ-LIFE-06 (AC1, AC2, AC3)

**Finding:** All CLI ACs describe visible UI states ("section is visible in the report panel," "shown in red / warning colour," "Both positions are displayed"). None specify a programmatic assertion strategy. Rich console output is not directly assertable without capturing stdout and parsing ANSI escape codes or Rich markup.

**Impact:** These ACs have no clear automated test path. Without a defined approach, they will either be omitted from the test suite (leaving the CLI untested) or manually verified (not regression-safe).

**Suggested resolution:** Add to each CLI AC a testable proxy. Options in ascending effort:
1. Capture `console.export_text()` (Rich supports this) and assert on the presence of key strings (e.g., `"WheelCandidateReport"`, `"IV Rank"`, `"No open wheel positions"`).
2. Add a `--json` flag to the CLI (if planned) whose output is machine-readable.
3. Explicitly note that CLI display tests use `CliRunner` from Typer/Click with Rich's `Console(file=...)` injection and assert on `stdout` text.

The REQ should specify which approach is expected so TSPEC can design the CLI with testability in mind.

---

### [TEV-REVIEW-11] Medium — REQ-LIFE-01 state machine ACs do not cover illegal phase transitions

**Requirement(s):** REQ-LIFE-01 (AC1 through AC4)

**Finding:** The state machine ACs cover the happy-path routing for each valid phase. There are no ACs for illegal or unexpected transitions: What happens if `wheel_phase=CC_OPEN` but `WheelPosition.cc_strike` is `None`? What if `CYCLE_COMPLETE` is triggered before `assignment_date` is set? What if the graph receives an unknown `WheelPhase` value?

**Impact:** The state machine implementation can silently enter an invalid state, producing undefined behaviour (e.g., `NoneType` errors mid-graph) with no test catching it.

**Suggested resolution:** Add at minimum two negative ACs:
- AC5: "If `wheel_phase=CC_OPEN` but no `WheelPosition` exists in state, the graph raises a `WheelStateError` (a defined exception, not a generic `KeyError`)."
- AC6: "An unknown `wheel_phase` value causes the graph to fall back to the equity-only path and log a warning."

---

### [TEV-REVIEW-12] Medium — REQ-DATA-02 AC3/AC4 plain-English assertions are unverifiable

**Requirement(s):** REQ-DATA-02 (AC3, AC4)

**Finding:** AC3 asserts "plain-English assessment uses language indicating elevated IV" and AC4 asserts "warns that IV is compressed." These are human-readable outputs from the tool function — the exact wording is unspecified. A test asserting `"elevated" in output` would pass even if the output was `"IV is not elevated."` A test asserting on the full string would be brittle to prompt changes.

**Impact:** These ACs cannot be safely automated. Any string-match will either be too strict (breaking on rephrasing) or too loose (missing inverted negations).

**Suggested resolution:** Replace AC3/AC4 with a structured-output approach: `get_iv_metrics` should return an object (or parseable dict) containing an `iv_environment` enum field: `"elevated"` (Rank ≥ 50), `"normal"` (25–49), `"compressed"` (< 25). The plain-English text is derived from this field. Tests then assert `result.iv_environment == "elevated"`, which is deterministic. Alternatively, if free-text is required, add a machine-readable `iv_rank_quartile: int` field (1–4) alongside the plain-English text, and test that.

---

### [TEV-REVIEW-13] Low — REQ-DATA-01 "within 90 days" look-ahead window boundary is ambiguous

**Requirement(s):** REQ-DATA-01 (AC1, description)

**Finding:** The description says "all available expiration dates within a configurable look-ahead window (default: 90 days)" but AC1 asserts on "all expirations within 90 days" without specifying whether the boundary is inclusive or exclusive, whether "90 days" is calendar days or trading days, and what the anchor date is (today's date or `target_date`).

**Impact:** Two implementers will compute different sets of returned expirations for a borderline expiry exactly 90 days out.

**Suggested resolution:** Specify: "Expirations are included if `expiry_date <= target_date + timedelta(days=options_lookforward_days)` (inclusive, calendar days). The anchor is `target_date`, not today."

---

### [TEV-REVIEW-14] Low — REQ-TRADE-02 AC1 "all numeric fields non-negative" conflicts with delta definition

**Requirement(s):** REQ-TRADE-02 (AC1)

**Finding:** AC1 asserts "all numeric fields are non-negative" but the schema defines `delta: float` as a put delta (negative value), explicitly commented "put delta (negative value)." These two constraints are mutually contradictory.

**Impact:** A correct implementation that stores `delta = -0.25` will fail AC1. An incorrect implementation that stores `delta = 0.25` will pass AC1 but violate the schema comment.

**Suggested resolution:** Rewrite AC1 as: "All numeric fields other than `delta` and `theta` are non-negative; `delta` is in (−1, 0); `theta` is ≤ 0."

---

### [TEV-REVIEW-15] Low — REQ-LIFE-02 AC4 "keyed by `{ticker}-cycle-{N}`" does not specify the storage mechanism

**Requirement(s):** REQ-LIFE-02 (AC4)

**Finding:** AC4 says "each position file is keyed by `{ticker}-cycle-{N}`" but the description says positions are "persisted (as JSON) alongside the memory log" without specifying the file path pattern, directory, or whether this is one file per position or one file containing all positions keyed by a dict.

**Impact:** Implementers will produce different file layouts, making integration tests (which must locate and read the position file) fragile.

**Suggested resolution:** Specify the exact file path: e.g., `{config["memory_log_dir"]}/{ticker}-cycle-{cycle_number}.json`. Add an AC that the file is created at this path after the first phase transition.

---

### [TEV-REVIEW-16] Low — REQ-NFR-03 env var naming convention is not specified

**Requirement(s):** REQ-NFR-03

**Finding:** "Overridable via `TRADINGAGENTS_WHEEL_*` env vars" — the `*` is not expanded. No AC specifies what the complete env var names are, their types, or their parsing rules (e.g., is `TRADINGAGENTS_WHEEL_MIN_IV_RANK=25` an int? Does `TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_LOW=0.20` parse as float?).

**Impact:** Without a defined list, integration tests for config override (like `test_env_overrides.py` in the existing suite) cannot be written, and implementers will invent different naming schemes.

**Suggested resolution:** Add a table in Section 7 mapping each config key to its env var name, type, and example, matching the style of the existing `test_env_overrides.py` tests. At minimum, provide the naming pattern rule: `TRADINGAGENTS_WHEEL_{UPPER_SNAKE_CASE_KEY}`.

---

## Approved Items

The following aspects of the REQ are well-specified from a testing perspective and can proceed to TSPEC/PROPERTIES without changes:

- **REQ-DATA-01 AC1, AC4** — concrete inputs, concrete output structure assertions (columns named). Directly automatable with mocked `yf.Ticker.option_chain()`.
- **REQ-DATA-03 AC2** — ATM put delta range (−0.55, −0.45) is a precise numeric assertion with no LLM dependency.
- **REQ-DATA-03 AC3** — 0 DTE error path is clearly specified with an exact error string.
- **REQ-DATA-03 AC4** — Invalid `option_type` validation is clear and automatable.
- **REQ-SCREEN-02 (all ACs)** — Pydantic schema validation tests are fully specifiable from the schema definition alone.
- **REQ-TRADE-02 AC2, AC3** — Field presence check and formula match are both deterministic and testable.
- **REQ-TRADE-04 AC1** — `strike_above_cost_basis` derivation from `strike >= cost_basis` is a simple boolean computation test.
- **REQ-LIFE-02 AC1, AC2, AC3** — P&L arithmetic is fully specified with concrete example values. These are the best-written ACs in the document.
- **REQ-LIFE-01 AC1 through AC4** — Phase routing ACs are graph topology tests, not LLM output tests; automatable via LangGraph state inspection with mocked nodes.
- **REQ-NFR-01** — Backwards compatibility: automatable by running the full existing test suite with `wheel_phase=None` and asserting no regressions.
- **REQ-NFR-05** — The self-referential testability requirement is appropriate (though incomplete — see TEV-REVIEW-01 and TEV-REVIEW-02).
- **Section 7 configuration table** — All threshold defaults are numerically precise and can be verified by a single test loading `default_config.py` and asserting each key value.
