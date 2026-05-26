# Cross-Review — Product Manager — TSPEC
# Document: TSPEC-wheel-options-trading.md v0.1.0

| Field | Value |
|---|---|
| Reviewer | Product Manager (PM-Review) |
| Date | 2026-05-25 |
| Document reviewed | TSPEC-wheel-options-trading.md v0.1.0 |
| Recommendation | Needs revision |

---

## Summary

The TSPEC is structurally sound and demonstrates thorough coverage of the REQ and FSPEC. The module map is complete, all four Phase 1 data functions are specified with correct signatures and error handling, all five Pydantic schemas match their REQ definitions, the five-criterion WheelAnalyst evaluation is correctly reproduced, the three-stage CSP/CC filter pipelines faithfully implement the FSPEC, and the five-rule roll/hold/close logic with priority resolution is correctly specified. Config Section 8 is comprehensive and all inline comments are present.

However, four medium-severity and three low-severity findings require author attention before the TSPEC is approved for PLAN handoff:

- Two config keys added by the TSPEC (`near_the_money_pct`, `options_lookforward_days`) are not in REQ Section 7 and have no corresponding REQ-NFR-03 env var entries — these must either be added to the REQ or justified as TSPEC-only additions.
- `within_options_cycle` is deferred from `get_next_earnings_date` to the calling agent, contrary to the REQ-DATA-04 contract.
- A numeric discrepancy in the `cycle_annualised_return_pct` worked example (TSPEC says ~33.21%; REQ-LIFE-02 AC3a says ~33.25%).
- `WheelPosition` adds `csp_open_date` and `prior_analyst_bias` fields not in the REQ-LIFE-02 schema definition — these are functionally necessary but represent an undocumented schema extension that PROPERTIES must cover.

---

## Findings

### [PM-TSPEC-01] Medium — `get_next_earnings_date` does not return `within_options_cycle` flag

**Requirement(s):** REQ-DATA-04 (AC1, AC2)

**Finding:** REQ-DATA-04 states: "It returns the next scheduled earnings date after `curr_date`, the number of calendar days until that date, and a flag `within_options_cycle: bool`." AC1 specifies the function returns all three values; AC2 specifies the flag is `True` when earnings falls within the option's remaining life.

The TSPEC (Section 2.1.4) explicitly defers `within_options_cycle` computation to the calling agent: "this field is set by the calling agent, not by this function. The function returns `earnings_date_str`, `days_until`, and notes that the caller must compute `within_options_cycle` from `earnings_date <= expiration_date`."

This means the function's output string does not contain `within_options_cycle`, making REQ-DATA-04 AC1 and AC2 unverifiable against the raw function output.

**Impact:** REQ-DATA-04 AC1 — the function does not return `within_options_cycle`. REQ-DATA-04 AC2 — the flag cannot be tested at the function level as the REQ specifies; a calling-agent test would need to substitute. PROPERTIES will also need to be written against agent-level behaviour, not tool-level.

**Suggested resolution:** Either (a) restore `within_options_cycle` to the `get_next_earnings_date` return value (requires passing the target expiration date as a parameter — e.g., `expiry_date: Optional[str] = None` defaulting to the front-month expiration), or (b) formally amend REQ-DATA-04 to move the `within_options_cycle` computation responsibility to the calling agent and note that AC1/AC2 are verified at the agent level. Option (b) requires a REQ version bump.

---

### [PM-TSPEC-02] Medium — Two TSPEC config keys (`near_the_money_pct`, `options_lookforward_days`) are absent from REQ Section 7

**Requirement(s):** REQ-NFR-03, REQ-NFR-07

**Finding:** The TSPEC Section 8.1 specifies 18 `config["wheel"]` keys — two more than the 17 listed in REQ Section 7:

1. `near_the_money_pct` (default: `0.10`) — not in REQ Section 7; added per FSPEC-WHEEL-03 open question closure.
2. `options_lookforward_days` (default: `90`) — not in REQ Section 7; carried forward from an FSPEC-WHEEL-04 open question noting it was missing from REQ.

Both keys have inline comments (satisfying REQ-NFR-07) and both have env var entries in `_WHEEL_ENV_OVERRIDES` (satisfying REQ-NFR-03's naming convention). However, neither has a formal REQ Section 7 entry with a `Type`, `Default`, and `Description` row. This means:

- The PROPERTIES document cannot trace these keys back to a REQ requirement.
- REQ-NFR-03 specifies that thresholds be exposed in `default_config.py` "under a `wheel` key" — the implicit assumption is that the REQ Section 7 table is the authoritative list.

**Impact:** REQ-NFR-03 partially unsatisfied — two config keys exist with no REQ requirement tracing them. PROPERTIES will have no REQ IDs to cite for these keys. If a future audit checks traceability, these keys will appear as unspecified additions.

**Suggested resolution:** Add a REQ v0.3.0 patch that appends `near_the_money_pct` and `options_lookforward_days` to REQ Section 7 with full rows. Both are already justified in the FSPEC (FSPEC-WHEEL-03 and FSPEC-WHEEL-04 open questions). Alternatively, annotate the TSPEC Section 8.1 with explicit notes that these two keys are TSPEC-level additions beyond REQ scope, accepted per FSPEC closure, and add a corresponding row in the Traceability Gaps table below.

---

### [PM-TSPEC-03] Medium — `WheelPosition` model extends REQ-LIFE-02 schema with undocumented fields

**Requirement(s):** REQ-LIFE-02, REQ-NFR-05

**Finding:** The TSPEC Section 9.1 `WheelPosition` model adds two fields not present in the REQ-LIFE-02 schema definition:

1. `csp_open_date: Optional[str]` — required for the `cycle_duration_days` computation in `wheel_cycle_summary` (Section 6.3 step 2: "compute `cycle_duration_days = (call_away_date_dt - csp_open_date_dt).days`"), but absent from the REQ-LIFE-02 schema table.
2. `prior_analyst_bias: Optional[str]` — required for RollCheckAgent Rule 5 (FSPEC-WHEEL-06), absent from REQ-LIFE-02 schema.

`csp_open_date` is particularly load-bearing: without it the `cycle_annualised_return_pct` formula cannot be computed, and REQ-LIFE-02 AC3a cannot be verified. The REQ-LIFE-02 formula uses `cycle_duration_days` from "CSP open date to CC call-away date", but the REQ schema does not include the open date field needed to compute this duration.

**Impact:** REQ-LIFE-02 AC3a — the formula `(cycle_pnl / (csp_strike × shares_held)) × (365 / cycle_duration_days) × 100` requires `csp_open_date` to compute `cycle_duration_days`. Without the REQ-level field definition, PROPERTIES tests cannot be traced to a REQ row. Additionally, REQ-NFR-05 requires every schema to have a validation test; PROPERTIES must cover these two extra fields.

**Suggested resolution:** Either (a) add `csp_open_date` and `prior_analyst_bias` to the REQ-LIFE-02 schema table in a REQ v0.3.0 patch (recommended — `csp_open_date` is structurally necessary for the REQ's own formula), or (b) annotate the TSPEC to explicitly document these as TSPEC-level schema additions justified by functional necessity, so the PROPERTIES author knows to include validation tests for them.

---

### [PM-TSPEC-04] Medium — `cycle_annualised_return_pct` worked example produces a different value than REQ-LIFE-02 AC3a

**Requirement(s):** REQ-LIFE-02 (AC3a)

**Finding:** REQ-LIFE-02 AC3a states: "Value is approximately `33.25%`" for inputs `cycle_pnl=930, csp_strike=140, shares_held=100, cycle_duration_days=73`.

The TSPEC Section 9.4 works the same formula:
```
(930 / (140 × 100)) × (365 / 73) × 100
= (930 / 14000) × 5.0 × 100
≈ 33.21%
```

The TSPEC explicitly notes `≈ 33.21%`, which differs from the REQ's `≈ 33.25%`. Both are approximations but they diverge at the second decimal place, which is within the precision range a PROPERTIES test would need to specify. If an implementation test asserts the value is "approximately 33.25%", it will fail against the TSPEC's formula at the same inputs.

**Impact:** REQ-LIFE-02 AC3a — the TSPEC's worked example produces a value inconsistent with the REQ's stated expected output. A PROPERTIES author reading both documents will see contradictory numeric targets for the same formula and inputs. An implementation that correctly evaluates the formula will likely produce ~33.21%, not ~33.25%, creating a spurious test failure if the PROPERTIES test was written from the REQ directly.

**Suggested resolution:** The TSPEC formula is mathematically correct for the given inputs — the REQ's "approximately 33.25%" appears to be a rounding error in the REQ document. Recommend (a) confirming the TSPEC formula output (~33.21%) is authoritative and noting the discrepancy, then (b) issuing a REQ v0.3.0 patch to update AC3a to read "approximately 33.21%" (or widen the tolerance to "approximately 33%"), so PROPERTIES tests can be anchored to a single consistent value.

---

### [PM-TSPEC-05] Low — Risk debate options context injection (REQ-TRADE-05) is addressed in FSPEC but not elaborated in TSPEC

**Requirement(s):** REQ-TRADE-05 (AC1, AC2, AC3)

**Finding:** The TSPEC module map (Section 1.1) and AgentState Extension (Section 4) correctly set up `csp_decision` and `cc_decision` as `Optional[str]` fields in `AgentState`. The FSPEC-WHEEL-09 section fully specifies the injection logic. However, the TSPEC does not include a dedicated section for the risk debate prompt assembler modification that injects `options_context` into the debate agents' prompts.

Specifically, the TSPEC is silent on: (a) which existing file contains the debate agent prompt assembly code and will be modified; (b) what the `{options_context}` template variable injection point looks like in the existing prompt template; (c) which of the three debate agents' prompt templates needs modification.

**Impact:** REQ-TRADE-05 AC1 and AC2 — passing requires an implementation that injects `mid_premium` and `probability_of_profit` into the debate prompt. Without a TSPEC section identifying the target file and injection point, the PLAN author cannot specify this work as a discrete implementation task. There is a risk this requirement gets lost in the PLAN.

**Suggested resolution:** Add a TSPEC subsection (e.g., Section 5.5 or a new Section 11) titled "Risk Debate Options Context Injection" that identifies: (a) the existing debate agent files that will be modified, (b) the specific injection point in each debate prompt template (`after {market_context}, before role-assignment instruction` per FSPEC-WHEEL-09), and (c) confirmation that this is a file-modification task (no new files created). This gives the PLAN author a clear implementation unit to schedule.

---

### [PM-TSPEC-06] Low — Structured output sentinel for `CspDecision` uses zero/empty required fields

**Requirement(s):** REQ-TRADE-02 (AC1, AC2), REQ-NFR-04

**Finding:** The TSPEC Section 5.2 specifies the safe sentinel for structured-output total failure:

```python
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
```

REQ-TRADE-02 AC1 specifies: "All numeric fields other than `delta` and `theta` are non-negative; `delta` is in (−1, 0); `theta` is ≤ 0." The sentinel sets `delta=0.0`, which violates the AC1 constraint `delta in (−1, 0)` (exclusive boundary). Additionally, the REQ-TRADE-02 AC2 specifies that when `tradeable=True`, `strike`, `expiration_date`, and `mid_premium` are non-null — the sentinel is `tradeable=False` so AC2 does not technically apply, but downstream code reading `strike=0.0` may behave unexpectedly.

**Impact:** REQ-TRADE-02 AC1 — schema validation test would fail if run against the sentinel with `tradeable=False`. A PROPERTIES validation test written against AC1 must explicitly handle the `tradeable=False` sentinel path (validate only when `tradeable=True`). This is a minor but testability-impacting issue.

**Suggested resolution:** Add a clarifying note in the TSPEC that AC1's numeric field constraints apply only when `tradeable=True`. The sentinel with `tradeable=False` is a failure-mode value exempt from the field-range constraints. Alternatively, set `delta=-0.5` (a valid put delta value) in the sentinel to avoid the boundary violation entirely. Either approach removes the ambiguity for the PROPERTIES author.

---

### [PM-TSPEC-07] Low — CC DTE lower bound deferral creates a gap against REQ-TRADE-03

**Requirement(s):** REQ-TRADE-03 (description)

**Finding:** REQ-TRADE-03 states: "Expiration — within `recommended_dte_range`, default **21–45 DTE** (calendar days)" for CC strikes. REQ Section 7 config table only has a single shared `recommended_dte_low = 28`. The TSPEC Section 10.1 item 5 explicitly defers this discrepancy: "This TSPEC uses the shared `recommended_dte_low = 28` for both CSP and CC (following the config table). PLAN/PROPERTIES author should flag if a distinct CC lower bound is required in Phase 2."

The result is that the TSPEC specifies `recommended_dte_low = 28` for CC, while the REQ description says the CC default DTE range is "21–45". An implementation following the TSPEC will set CC minimum DTE to 28, not 21.

**Impact:** REQ-TRADE-03 description — the DTE lower bound for CC deviates from the REQ text. While this is a low-stakes discrepancy (the config is overridable per REQ-NFR-03), the PROPERTIES test for CC DTE range will need to pick a value. If PROPERTIES uses the REQ description (21), the implementation (28) will fail that test.

**Suggested resolution:** Resolve the CC DTE ambiguity at the REQ level before PLAN authoring: either (a) update REQ-TRADE-03 to say "default 28–45 DTE" consistent with the config table, or (b) add a distinct `cc_recommended_dte_low` config key (default: 21) to REQ Section 7 and the TSPEC config. Document the decision in the TSPEC so PROPERTIES has a clear anchor.

---

## Traceability Gaps

| REQ ID | Title | TSPEC Coverage | Gap |
|---|---|---|---|
| REQ-DATA-01 | Options chain retrieval tool | Section 2.1.1 — complete | None |
| REQ-DATA-02 | IV Rank and IV Percentile calculation | Section 2.1.2 — complete with full algorithm | None |
| REQ-DATA-03 | Options Greeks calculation | Section 2.1.3 — complete with BSM formulae | None |
| REQ-DATA-04 | Earnings date lookup tool | Section 2.1.4 — partial | `within_options_cycle` flag deferred to calling agent (PM-TSPEC-01) |
| REQ-DATA-05 | Options data tool registration | Section 2.2 and interface.py spec — complete | None |
| REQ-SCREEN-01 | WheelAnalyst agent | Section 5.1 — complete with five-criterion table | None |
| REQ-SCREEN-02 | WheelCandidateReport schema | Section 3.3 — complete; all fields present | None |
| REQ-SCREEN-03 | CLI integration for wheel screening | Section 7.1 — complete | None |
| REQ-TRADE-01 | CspAgent | Section 5.2 — complete with deterministic filter function | None |
| REQ-TRADE-02 | CspDecision schema | Section 3.4 — complete; all fields present | Sentinel delta=0.0 conflicts with AC1 boundary (PM-TSPEC-06, Low) |
| REQ-TRADE-03 | CcAgent | Section 5.3 — complete with four-filter pipeline | CC DTE lower bound deferred (PM-TSPEC-07, Low) |
| REQ-TRADE-04 | CcDecision schema | Section 3.5 — complete; all fields present | None |
| REQ-TRADE-05 | Risk debate adaptation | FSPEC-WHEEL-09 covered; TSPEC lacks dedicated section | No TSPEC file/injection-point specification for debate prompt modification (PM-TSPEC-05, Low) |
| REQ-LIFE-01 | WheelPhase state machine | Sections 3.1, 6.1, 6.2 — complete with full routing table | None |
| REQ-LIFE-02 | Position tracker | Section 9 — complete; adds two undocumented fields | `csp_open_date` and `prior_analyst_bias` not in REQ schema (PM-TSPEC-03, Medium) |
| REQ-LIFE-03 | RollCheckAgent | Section 5.4 — complete with priority table and code pattern | None |
| REQ-LIFE-04 | RollDecision schema | Section 3.6 — complete; all fields present | None |
| REQ-LIFE-05 | Memory log integration | Section 6.3 — complete; `past_context` format specified | None |
| REQ-LIFE-06 | Wheel portfolio summary CLI | Section 7.2 — complete with both Rich tables specified | None |
| REQ-NFR-01 | Backwards compatibility | Sections 6.1, 6.2, 7.1 — guard conditions explicit | None |
| REQ-NFR-02 | Performance (10s p95) | Not explicitly specified in TSPEC | No TSPEC assertion or implementation note for the p95 latency target on `get_options_chain`. Low risk — this is a test-level constraint but PLAN should note it. |
| REQ-NFR-03 | Configurability via env vars | Section 8.2 — `_WHEEL_ENV_OVERRIDES` complete | `near_the_money_pct` and `options_lookforward_days` env vars not in REQ Section 7 (PM-TSPEC-02, Medium) |
| REQ-NFR-04 | Structured output via structured.py | Sections 5.1–5.4 — `bind_structured` / `invoke_structured_or_freetext` pattern specified for all four agents | None |
| REQ-NFR-05 | Testability | `option_chain_fixture`, `iv_series` test seam, mocked LLM patterns — all specified | Two extra `WheelPosition` fields not traceable to REQ (PM-TSPEC-03) |
| REQ-NFR-06 | Error handling | Sections 2.1.1–2.1.4 — all catch and return graceful strings | None |
| REQ-NFR-07 | Config documentation | Section 8.1 — all 18 keys have inline comments | None |

---

## Approved Items

The following areas are reviewed and approved without findings:

- **Data layer architecture (Section 2):** All four yfinance functions correctly implement the REQ/FSPEC algorithms. The `get_iv_metrics` production path (30-day rolling vol, `sqrt(252)` annualisation, zero-variance guard, `iv_series` test seam) exactly matches FSPEC-WHEEL-02. `get_options_greeks` BSM formulae are correctly specified including calendar-day DTE, `T = dte/365`, `Theta_daily = Theta_annual/365`, and the `^IRX` fallback chain. `get_options_chain` look-ahead boundary, empty-DataFrame handling, and specific-expiry override are all correctly specified.

- **Schema completeness (Section 3):** `WheelCandidateReport`, `CspDecision`, `CcDecision`, and `RollDecision` all match the REQ schema tables field-for-field. `WheelPhase` is correctly declared as `str, Enum` for LangGraph serialisability. `TriggerReason` as a `Literal` type alias is correct. Field-level descriptions are informative and accurate.

- **AgentState extension (Section 4):** Five `Optional[str]` fields with correct naming conventions. `Annotated` pattern consistent with existing fields. Safe-access note (`state.get("wheel_phase")`) is important and correct.

- **WheelAnalyst five-criterion evaluation (Section 5.1):** Criterion ordering, simultaneous evaluation (no early exit), failure-reason accumulation, `recommended_strike_range` Delta-anchored computation and fallback, and structured output fallback sentinel all match FSPEC-WHEEL-03. The `deep_think_llm` rationale is well-argued.

- **CspAgent filter pipeline (Section 5.2):** Three-filter (A→B→C) deterministic pre-filter, progressive relaxation order (C→B→A-fallback), earnings hard-block returning `tradeable=False` without LLM call, `_filter_csp_candidates` as a unit-testable standalone function, and `options_lookforward_days` guard — all correctly specified and consistent with FSPEC-WHEEL-04.

- **CcAgent filter pipeline (Section 5.3):** Four-filter (A→B→C→D) pipeline, Filter A never relaxed, below-cost-basis branch logic (no eligible strikes → `tradeable=False`; at least one eligible strike → LLM called with warning), and derived fields all match FSPEC-WHEEL-05.

- **RollCheckAgent five rules (Section 5.4):** All five rules, firing conditions, priority resolution (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1), `trigger_reason` code pattern, `prior_analyst_bias` read/write cycle, and `quick_think_llm` rationale are correctly specified and consistent with FSPEC-WHEEL-06. The "no rule fires → `profit_capture`" aliasing is documented clearly.

- **Graph integration (Section 6):** `START → wheel_router` conditional edge replaces the direct `START → first_analyst` edge. `route_wheel_phase()` return values, `WheelStateError` guards for `csp_open` and `cc_open`, and `wheel_cycle_summary → END` terminal edge are all correct. The `"wheel" in selected_analysts` conditional for `WheelAnalyst` node registration correctly implements REQ-SCREEN-01 AC5 and REQ-NFR-01.

- **`wheel_cycle_summary` node (Section 6.3):** Correctly computes `cycle_pnl`, `cycle_annualised_return_pct`, writes `TradingMemoryLog` with `cycle_pnl` formatted to 2 decimal places (satisfying REQ-LIFE-05 AC3), and resets `wheel_phase → None`. Memory log write failure is logged without blocking the state reset.

- **`WheelPosition` atomic write pattern (Section 9.3):** `tempfile.mkstemp` + `os.replace` pattern correctly matches the `TradingMemoryLog` pattern noted in REQ-LIFE-02. `load_latest_open_position` correctly skips `cycle_complete` positions.

- **Config env override mechanism (Section 8.2):** The `_WHEEL_ENV_OVERRIDES` separate mapping and `_apply_nested_env_overrides` helper correctly handle the nested `config["wheel"]` path that the existing flat `_apply_env_overrides` cannot reach. The `_coerce` type-preserving cast approach is architecturally sound.

- **Backwards compatibility guards:** The `if "wheel" in selected_analysts` conditional, `wheel_phase is None → first_analyst_node` router path, CLI display guard (`"wheel" in selected_analysts AND state.get("wheel_candidate_report") is not None`), and REQ-NFR-01 preservation of the `"Trader" → "Aggressive Analyst"` edge when wheel is not selected are all correctly specified.

- **`scipy` dependency note (Section 10.7):** Correctly surfaced as a PLAN-level dependency decision. The `math.erfc` alternative is a reasonable option worth considering.

- **Open questions deferral (Section 10.1):** The five deferred items are appropriate PLAN-level decisions. The `csp_open → stock_owned` manual trigger mechanism and the CC DTE lower bound are the two that have the highest product impact and should be resolved before PLAN authoring begins.
