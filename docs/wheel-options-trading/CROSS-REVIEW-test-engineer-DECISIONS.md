# Cross-Review — Test Engineer — DECISIONS
# Document: DECISIONS-wheel-options-trading.md v0.1.0

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Recommendation | Needs revision |

---

## Summary

Five ADRs reviewed against TSPEC v0.2.0. Two ADRs are missing their Re-evaluation Trigger section
entirely (ADR-WHEEL-03, ADR-WHEEL-05). Two more have triggers that are too vague to act on as
monitoring or test conditions (ADR-WHEEL-01, ADR-WHEEL-02). Consequences sections across multiple
ADRs omit testing implications that will directly affect the PROPERTIES document: the sentinel
detection requirement (ADR-WHEEL-04) is the one well-documented exception. The TSPEC's test seams
are generally well-designed and cover the key execution paths, but the ADRs do not cross-reference
them or explain what test invariants the chosen approach imposes. Four findings require attention
before the DECISIONS document is used as input to PLAN authoring.

---

## Findings

### [TE-DECISIONS-01] High — ADR-WHEEL-03 is missing its Re-evaluation Trigger section entirely

**ADR:** ADR-WHEEL-03

**Finding:** ADR-WHEEL-03 (Shared Graph vs Sub-graphs) has no Re-evaluation Trigger section. Every
other ADR in this document includes one. The absence means there is no documented condition under
which the architectural choice to graft a preamble conditional edge onto the shared `StateGraph`
would be revisited. This matters for testing because the chosen approach locks in a specific
assumption: that `route_wheel_phase()` returning `self.first_analyst_node` is a transparent
pass-through. If a future graph refactor renames nodes or changes the `START` edge topology, there
is no guidance on when to reconsider the architecture. A missing trigger also means there is no
integration-test property anchored to a measurable re-evaluation condition.

Separately, the Consequences section does not state what the testability contract is: specifically,
that an integration test must assert `wheel_phase=None` produces an output state identical to the
pre-feature equity-only graph output (REQ-NFR-01). Without this documented in the ADR, the
PROPERTIES author has no ADR-level backing for this required property.

**Suggested resolution:** Add a Re-evaluation Trigger: "If LangGraph changes the `START` edge
semantics, conditional edge return-value routing, or `StateGraph.compile()` validation in a way
that rejects the preamble pattern, or if the equity pass-through integration test fails after any
LangGraph version bump." Also add to Consequences: "An integration test must assert that when
`wheel_phase is None`, the final `AgentState` output fields (`market_report`, `sentiment_report`,
etc.) are byte-for-byte identical to the equity-only baseline. This property is the primary guard
against regression on REQ-NFR-01."

---

### [TE-DECISIONS-02] High — ADR-WHEEL-05 is missing its Re-evaluation Trigger section and omits test-isolation implications in Consequences

**ADR:** ADR-WHEEL-05

**Finding:** ADR-WHEEL-05 (Per-Cycle JSON Files) has no Re-evaluation Trigger section. There is also
a consequential gap in the Consequences section: it does not document the test-isolation requirement
that unit tests for `save_wheel_position`, `load_wheel_position`, `load_latest_open_position`, and
all three consumers (`CcAgent`, `RollCheckAgent`, `route_wheel_phase`) must use a temporary
directory (e.g., `tmp_path` from pytest) — never the production `positions_dir`. Without this
documented in the ADR, individual test authors may inadvertently write to the real positions
directory, producing test pollution that persists across runs.

The Consequences section also does not mention the integer-sort invariant that the TE cross-review
of TSPEC v0.1.0 (TE-TSPEC-04) identified as a High-severity bug and TSPEC v0.2.0 fixed. The ADR
says "Lexicographic sort silently breaks at cycle >= 10" and documents the fix, but the Consequences
section does not state that a regression test for cycle numbers >= 10 is a required property of the
chosen approach. This is the kind of precisely observable test condition that should be documented at
the ADR level.

**Suggested resolution:** Add a Re-evaluation Trigger: "If the position directory grows to a scale
where globbing all per-ticker JSON files becomes measurably slow (e.g., > 500 cycle files, or
`load_latest_open_position` exceeds 100ms on commodity hardware), or if the codebase introduces
multi-ticker concurrent analysis that makes the single-file-per-cycle isolation insufficient."

Add to Consequences: "All unit tests for `save_wheel_position`, `load_latest_open_position`, and
consuming agents must write to a `tmp_path`-isolated directory. The `_position_loader` injectable
(TE-TSPEC-06) eliminates filesystem access for agent-level unit tests entirely. A dedicated
regression test must assert that `load_latest_open_position` returns cycle 10 and not cycle 9 when
both exist (integer sort invariant, TE-TSPEC-04)."

---

### [TE-DECISIONS-03] Medium — ADR-WHEEL-01 re-evaluation trigger is not observable or actionable

**ADR:** ADR-WHEEL-01

**Finding:** The re-evaluation trigger states: "If a no-cost historical IV source becomes available
via yfinance or as a free API, the proxy should be replaced with true historical implied volatility."
This is a passive watch condition with no concrete detection mechanism. As written, no monitoring
alert, scheduled check, or periodic review can determine when this trigger has fired. A trigger
that relies on a team member happening to notice a new yfinance feature or free API will be missed
in practice.

For testing, this matters because the `iv_series` test seam (TSPEC Section 2.1.2) is designed to
bypass the yfinance OHLCV fetch and exercise the pure statistical computation. If the data source
changes from realised-vol to true implied vol, the seam must also change — but without a clear
trigger condition tied to an observable event, the update may be delayed or incomplete.

**Suggested resolution:** Rewrite the trigger as: "Re-evaluate when `yf.Ticker.option_chain()` adds
a `date` parameter to its public API (detectable by inspecting the yfinance changelog in CI on each
dependency version bump), or when a free historical IV API (e.g., CBOE Datashop free tier,
Polygon.io free plan) appears in the project's approved-vendors list. Gate yfinance version upgrades
with a CI check that asserts `yf.Ticker.option_chain` signature has not changed. The `iv_series`
test seam must be updated simultaneously with any data-source change."

---

### [TE-DECISIONS-04] Medium — ADR-WHEEL-02 re-evaluation trigger is not observable; Consequences omit the unknown-value test requirement

**ADR:** ADR-WHEEL-02

**Finding:** The re-evaluation trigger states: "If a future LangGraph release adds first-class
support for `str`-enum typed fields in TypedDicts with guaranteed JSON-safe checkpointing." This
cannot be detected automatically: there is no CI step, changelog watch, or test assertion that
would fire when this LangGraph capability becomes available. The trigger also has no guidance on
how to verify the new capability is working correctly before switching the field type.

More critically for testing, the Consequences section documents the misspelling risk and the
`WheelPhase` convention but does not state that the unknown-value fallback path in
`route_wheel_phase()` must be covered by a dedicated test property. ADR-WHEEL-02 justifies the
`Optional[str]` choice partly on the grounds that "explicit fallback in `route_wheel_phase()`
covers unknown values" — but if this fallback is not verified by an automated test, the safety-net
argument is unsubstantiated. The TSPEC (Section 6.2) specifies the fallback behaviour but does not
elevate it to a required test seam at the ADR level.

The Consequences section also does not note that tests asserting `state["wheel_phase"] == "csp_open"`
(the literal-string pattern the ADR recommends) must be reviewed whenever a `WheelPhase` constant
is renamed, since the type system will not catch the mismatch.

**Suggested resolution:** Add to Re-evaluation Trigger: "Monitor LangGraph release notes for
`TypedDict` enum support in each version upgrade (add a checklist item to the dependency-upgrade
runbook). Verify by compiling a test graph with an `Optional[WheelPhase]`-typed AgentState field
and confirming the checkpointer round-trips it without error." Add to Consequences: "A test property
must assert that `route_wheel_phase({'wheel_phase': 'totally_unknown_value', ...})` returns the
first analyst node name and emits exactly one `WARNING`-level log entry. This is the only automated
guard for the unknown-value safety net."

---

### [TE-DECISIONS-05] Low — ADR-WHEEL-04 Consequences omit the multi-level sentinel detection test requirement

**ADR:** ADR-WHEEL-04

**Finding:** The Consequences section correctly notes that "PROPERTIES tests must verify the
sentinel path is exercised and that the returned state is detectable (non-empty `rationale`
field)." This is the best-documented test consequence among all five ADRs. However, it stops short
of specifying that the three distinct failure levels must each be independently tested:

1. Structured call succeeds — Pydantic instance returned via render path (happy path).
2. Structured call fails, freetext fallback returns valid JSON — `model_validate_json` succeeds
   on the raw string.
3. Both paths fail — sentinel returned.

TSPEC Section 10.2 documents the correct parsing pattern and warns that `model_validate_json` on
a rendered-markdown string is expected to fail (the rendered string is not JSON). Without a test
that explicitly exercises level 2 (freetext path returns valid JSON that parses successfully), the
parsing logic in each of the four agents may silently treat a valid freetext JSON response as a
total failure and return the sentinel, resulting in unnecessary `tradeable=False` outcomes that are
invisible without this specific test coverage.

Additionally, the rejected alternative "JSON-mode prompt only" was discarded as "fragile," but it
would have been equally testable (mock the LLM to return a JSON string, assert the parse succeeds).
The test cost of the chosen three-layer approach — specifically the need to mock three distinct LLM
response types — should be documented so the PROPERTIES author knows to write three parametrised
test cases per agent rather than one.

**Suggested resolution:** Add to Consequences: "The three-layer fallback requires three independent
test scenarios per agent: (a) structured-output success (mock `bind_structured` to return a valid
Pydantic instance via the render path); (b) freetext fallback succeeds (mock the freetext LLM to
return a valid JSON string, assert `model_validate_json` parses it and no sentinel is emitted);
(c) total failure (mock both paths to return unparseable content, assert the sentinel is returned
with `tradeable=False`/`action='HOLD'` and `rationale` is non-empty). The three parametrised
scenarios apply to each of the four wheel agents, totalling 12 required sentinel/fallback test
cases."

---

## Approved Items

**ADR-WHEEL-01 — Test seam design:** The `iv_series: Optional[list[float]]` injectable parameter
on `get_iv_metrics` is a well-designed test seam. It cleanly separates the pure statistical
computation (IV Rank, IV Percentile, `iv_environment` derivation) from the yfinance OHLCV fetch.
The boundary condition documented in Consequences (`iv_percentile` approaches but does not reach
100 when `current_vol == max_vol_lookback`) is a correctly specified test invariant. The zero-variance
sentinel producing `iv_rank = 50` with a populated note string is deterministic and testable.

**ADR-WHEEL-01 — Chosen approach testability vs rejected alternatives:** None of the rejected
alternatives (252-call historical IV, third-party feeds, VIX proxy) would have been more testable
than the chosen realised-vol proxy. All would have required mocking an even larger external surface.
The chosen approach correctly concentrates the test seam at the statistical computation boundary.

**ADR-WHEEL-02 — Literal-string test simplification:** The decision to test against literal string
values (`assert state["wheel_phase"] == "csp_open"`) without importing the enum is a pragmatic
simplification that reduces test coupling to the enum class definition. This is a reasonable
trade-off and consistent with how the rest of the codebase tests `AgentState` string fields.

**ADR-WHEEL-03 — `WheelStateError` testability:** The decision to raise `WheelStateError` (a
`ValueError` subclass) on illegal phase transitions (e.g., `wheel_phase="csp_open"` with no open
position) is a correct and testable design. The exception type is concrete, importable, and
distinct from general `ValueError`, enabling precise `pytest.raises(WheelStateError)` assertions.

**ADR-WHEEL-04 — Sentinel detectability:** Specifying a non-empty `rationale` field as the sentinel
detection mechanism is a well-chosen testable invariant. The `rationale` field is always-populated
in all four schemas (including the sentinel), making it unambiguous as a diagnostic signal. The
choice of `tradeable=False` / `action="HOLD"` as sentinel values — documented as exempt from
field-range constraints — correctly avoids Pydantic validation failures on the sentinel itself.

**ADR-WHEEL-05 — `_position_loader` injectable:** The decision to inject `_position_loader` as a
keyword-only callable in `create_cc_agent` (TE-TSPEC-06) is directly traceable to the chosen
per-cycle JSON file approach. It eliminates filesystem dependency from agent-level unit tests
entirely, which is the correct test isolation strategy for a filesystem-backed state store.
