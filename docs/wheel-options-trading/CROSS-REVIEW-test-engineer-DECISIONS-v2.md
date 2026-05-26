# Cross-Review: test-engineer — DECISIONS

**Reviewer:** test-engineer
**Document reviewed:** docs/wheel-options-trading/DECISIONS-wheel-options-trading.md v0.2.0
**Date:** 2026-05-25
**Iteration:** 2

---

## Context

This is the second iteration review. The prior review (v1, `CROSS-REVIEW-test-engineer-DECISIONS.md`)
raised five findings: two High (TE-DECISIONS-01: ADR-WHEEL-03 missing Re-evaluation Trigger;
TE-DECISIONS-02: ADR-WHEEL-05 missing Re-evaluation Trigger and test isolation implications), two
Medium (TE-DECISIONS-03: ADR-WHEEL-01 trigger not observable; TE-DECISIONS-04: ADR-WHEEL-02 trigger
not observable and missing unknown-value test requirement), and one Low (TE-DECISIONS-05:
ADR-WHEEL-04 missing three-level fallback test requirement).

v0.2.0 addresses all five findings in part. Two findings are fully resolved; three are partially
resolved with residual gaps documented below.

---

## Resolution Status of Prior Findings

| Prior ID | Status | Notes |
|----------|--------|-------|
| TE-DECISIONS-01 | Partial | Re-evaluation trigger added (resolved); equity-passthrough integration test invariant still absent from Consequences |
| TE-DECISIONS-02 | Partial | Re-evaluation trigger added and `_position_loader` injectable documented (resolved); `tmp_path` isolation requirement and integer-sort regression test specification still absent from Consequences |
| TE-DECISIONS-03 | Resolved | Re-evaluation trigger rewritten with automated >20-percentile-point threshold, specific benchmark tickers, and manual yfinance changelog condition |
| TE-DECISIONS-04 | Resolved | Trigger updated with LangGraph runbook checklist item and test-graph verification step; Consequences now include the explicit unknown-value unit test requirement |
| TE-DECISIONS-05 | Partial | Test coverage bullet added for sentinel (level 3); level 2 (freetext path returns valid JSON that parses successfully) still absent |

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | ADR-WHEEL-03 Consequences still missing the equity-passthrough integration test invariant required by REQ-NFR-01 | ADR-WHEEL-03 Consequences |
| F-02 | Medium | Local | ADR-WHEEL-05 Consequences still missing the `tmp_path` isolation requirement and integer-sort regression test specification | ADR-WHEEL-05 Consequences |
| F-03 | Medium | Local | ADR-WHEEL-04 test coverage note omits level-2 fallback scenario (freetext path returns valid JSON), leaving a silent-sentinel risk uncovered | ADR-WHEEL-04 Consequences — Test coverage |
| F-04 | Low | Local | ADR-WHEEL-04 sentinel marker string is declared a contract but no test mechanism is specified to detect accidental mutation of the string | ADR-WHEEL-04 Consequences — Distinguishability |

---

## Finding Detail

### F-01 — Medium — ADR-WHEEL-03 Consequences still missing equity-passthrough integration test invariant

**Prior finding:** TE-DECISIONS-01 (High) called for a Consequences bullet requiring an integration
test asserting that when `wheel_phase is None`, the final `AgentState` output fields (`market_report`,
`sentiment_report`, etc.) are identical to the equity-only baseline — the primary automated guard
for REQ-NFR-01.

**What v0.2.0 addressed:** A Re-evaluation Trigger section was added ("If LangGraph changes the
`START` edge semantics..."). A Consequences bullet documents the single-ticker constraint and notes
that "The single-ticker constraint is verified implicitly by all existing PROPERTIES tests." This
does not address the equity-passthrough invariant.

**Residual gap:** The Consequences section still contains no statement that a dedicated integration
test must assert `wheel_phase=None` produces output state functionally equivalent to the pre-feature
equity-only path. The Re-evaluation Trigger now says "if the equity pass-through integration test
fails after any LangGraph version bump" — which implies such a test exists — but the Consequences
section never requires it to be written. The PROPERTIES author has no ADR-level backing to include
this as a required property.

Without this test, a regression that silently changes equity-path behaviour under `wheel_phase=None`
would go undetected. REQ-NFR-01 requires the existing equity pipeline to be entirely unaffected.
The only reliable automated guard for this requirement is a differential integration test comparing
pre- and post-feature graph output for a `wheel_phase=None` invocation.

**Required change:** Add to ADR-WHEEL-03 Consequences: "A dedicated integration test must assert
that when `wheel_phase is None`, the final `AgentState` output fields produced by the
`wheel_router → first_analyst_node` path are functionally equivalent to the output fields produced
by the equity-only graph with no preamble router (REQ-NFR-01). This property must appear in the
PROPERTIES document and is the primary regression guard for LangGraph version bumps that affect
`START` edge semantics."

---

### F-02 — Medium — ADR-WHEEL-05 Consequences still missing `tmp_path` isolation requirement and integer-sort regression test specification

**Prior finding:** TE-DECISIONS-02 (High) called for two additions to the Consequences section:
(a) all unit tests for filesystem-touching functions must use a `tmp_path`-isolated directory;
(b) a dedicated regression test must assert that `load_latest_open_position` returns cycle 10, not
cycle 9, when both exist (integer sort invariant, originally TE-TSPEC-04).

**What v0.2.0 addressed:** A Re-evaluation Trigger section was added (performance threshold and
multi-ticker concurrent-analysis condition). The Consequences section now documents that
`CcAgent`, `RollCheckAgent`, and `ConditionalLogic.route_wheel_phase()` each accept an injectable
`_position_loader` callable for unit-test isolation. The orphan file risk is also now documented.

**Residual gap:** The Consequences section still does not state:

1. That unit tests for `save_wheel_position`, `load_wheel_position`, and `load_latest_open_position`
   itself (the I/O functions, not just their consumers) must use a `tmp_path`-scoped directory and
   must never write to the production `positions_dir`. The injectable eliminates filesystem access
   at the agent level, but the I/O layer functions still require `tmp_path` discipline. Without a
   documented requirement, individual test authors may write to the real positions directory.

2. That a regression test asserting the integer-sort invariant (cycle 10 returned over cycle 9
   when both are present) is a required property of the chosen implementation. The Decision section
   correctly documents the bug and fix ("Lexicographic sort silently breaks at cycle ≥ 10"), but
   the Consequences section does not mandate the regression test. The PROPERTIES author has no
   ADR-level directive to include this property.

**Required changes:**

Add to ADR-WHEEL-05 Consequences: "Unit tests for the I/O layer functions (`save_wheel_position`,
`load_wheel_position`, `load_latest_open_position`) must use a pytest `tmp_path`-scoped directory
and must not write to the configured `positions_dir`. The `_position_loader` injectable covers
agent-level unit tests; the I/O-layer functions require separate `tmp_path`-isolated tests."

Add to ADR-WHEEL-05 Consequences: "A dedicated regression test must assert that
`load_latest_open_position` returns the cycle-10 position file and not the cycle-9 file when both
are present in the positions directory (integer sort invariant). This test is the primary guard
against re-introducing lexicographic sort order, which silently produces the wrong result at
cycle ≥ 10 (TE-TSPEC-04). This property must appear in the PROPERTIES document."

---

### F-03 — Medium — ADR-WHEEL-04 test coverage note omits level-2 fallback scenario

**Prior finding:** TE-DECISIONS-05 (Low) called for three independently-tested failure levels per
agent: (a) structured-output success; (b) freetext fallback returns valid JSON that `model_validate_json`
parses successfully; (c) total failure returns sentinel. The concern: without level-2 coverage, the
agent's `model_validate_json` call could silently treat a valid freetext JSON response as
unparseable and return the sentinel, producing unnecessary `tradeable=False` outcomes invisible
without this specific coverage.

**What v0.2.0 addressed:** The Test coverage bullet now states: "The TSPEC specifies that the
three-layer fallback is verified by unit tests that mock `invoke_structured_or_freetext` to return
an unparseable string, then assert the agent returns the sentinel." The Distinguishability bullet
correctly documents the sentinel marker string and its role. The re-evaluation trigger mentions
sentinel firing rate monitoring.

**Residual gap:** The test coverage bullet specifies only the total-failure scenario (level 3:
unparseable string → sentinel). Levels 1 and 2 are not mentioned. Level 2 is the critical omission:
if no test exercises the path where `invoke_structured_or_freetext` returns a valid JSON string and
`model_validate_json` successfully parses it, the parsing logic in each of the four agents could
silently fail (e.g., the returned string is a markdown-wrapped JSON blob rather than bare JSON) and
return the sentinel on every freetext-path invocation. This failure mode is invisible: the agent
returns `tradeable=False`, the user sees a genuine-looking decline, and no error is raised.

The Decision section (step 3) specifies that agents call `Schema.model_validate_json(raw_str)` and
that "on `ValidationError`, proceeds to step 4." It does not state what constitutes a well-formed
`raw_str` on the freetext path, nor whether the agent strips markdown fences before attempting to
parse. Without a test that feeds a known-valid JSON string through `model_validate_json` and asserts
success (no sentinel), this ambiguity cannot be caught in CI.

**Required change:** Replace or augment the Test coverage bullet with: "The three-layer fallback
requires three independent test scenarios per agent: (a) structured-output success — mock
`invoke_structured_or_freetext` to return a valid Pydantic-rendered instance (or simulate the
structured path); (b) freetext fallback succeeds — mock the return value to a valid JSON string
matching the schema, assert `model_validate_json` parses it and the sentinel is NOT returned; (c)
total failure — mock both paths to return unparseable content, assert the sentinel is returned with
`tradeable=False`/`action='HOLD'` and a non-empty `rationale`. These three scenarios apply to each
of the four wheel agents (12 test cases total). Scenario (b) is the guard against the agent
treating a valid freetext JSON response as a parse failure."

---

### F-04 — Low — ADR-WHEEL-04 sentinel marker string declared a contract without a test enforcement mechanism

**ADR:** ADR-WHEEL-04 Consequences — Distinguishability

**Finding:** The Consequences section states: "This sentinel marker string (`'Structured output
failed — safe fallback applied.'`) is a contract — it must not be changed without updating all
consuming code." This is a correct and important observation. However, the ADR does not specify
any automated mechanism to detect accidental mutation of this string. Code review convention is
the only stated guard ("must not be changed"), which carries the same type-safety limitation that
ADR-WHEEL-02 documents for `wheel_phase` misspellings: a typo or refactor that renames the string
will silently break the CLI display layer's ability to detect and highlight sentinel results.

If the sentinel marker string changes without updating the CLI display layer, users will see the
sentinel `tradeable=False` result without the "distinct warning style" required by the Consequences
section. This is a testability gap: there is no PROPERTIES property anchored to the exact string
value, and no test that asserts the CLI display renders sentinel results differently.

**Suggested addition:** Add to Consequences: "A constant `SENTINEL_RATIONALE = 'Structured output
failed — safe fallback applied.'` should be defined in a shared module (e.g.,
`tradingagents/agents/options/constants.py`) and imported by both the agent's sentinel construction
and the CLI display layer's detection logic. A unit test must assert that the sentinel
`rationale` field equals this constant, and that the CLI display layer applies a distinct render
style when `rationale == SENTINEL_RATIONALE`. Using a shared constant makes string mutation a
compile-time import error rather than a silent runtime divergence."

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | ADR-WHEEL-03 Re-evaluation Trigger says "if the equity pass-through integration test fails after any LangGraph version bump" — does a test with this exact property already exist in the PROPERTIES document, or is this forward-referencing a test that must be created? The Consequences section should resolve this ambiguity. |
| Q-02 | ADR-WHEEL-04 Decision step 3 says agents call `Schema.model_validate_json(raw_str)`. Is `raw_str` expected to be bare JSON, or may it be markdown-fenced JSON (e.g., ` ```json\n{...}\n``` `)? The answer determines whether the agent must strip markdown fences before parsing — which is a distinct code path that requires its own test. This should be documented in the Decision section or cross-referenced to the TSPEC. |
| Q-03 | ADR-WHEEL-05 Consequences documents that `load_latest_open_position` skips `status="cycle_complete"` positions and returns only the latest `status="open"` position. Is there a required test property for the case where multiple `status="open"` files exist for the same ticker (e.g., a crash left cycle-4 and cycle-5 both with `status="open"`)? The Consequences section does not state which is returned or whether this is an error condition. |

---

## Positive Observations

- **ADR-WHEEL-01 Re-evaluation Trigger (fully resolved):** The trigger is now actionable and
  observable. The automated condition (>20 percentile point divergence against benchmark tickers
  SPY, QQQ, AAPL) is measurable, and the reference to a named regression test suite makes it
  detectable in CI. The manual condition (yfinance changelog at each dependency upgrade) is
  concrete and assignable. This is a well-formed trigger.

- **ADR-WHEEL-02 unknown-value test requirement (fully resolved):** The Consequences section now
  includes a precise, implementable test specification: pass `'invalid_phase'` as `wheel_phase`,
  assert the graph routes to the first analyst node, assert exactly one `WARNING`-level log entry.
  This is exactly the right level of detail for a PROPERTIES entry.

- **ADR-WHEEL-02 Re-evaluation Trigger (fully resolved):** The trigger now includes a runbook
  checklist item and a concrete verification step (compile a test graph with
  `Optional[WheelPhase]`-typed field and confirm checkpointer round-trips without error). This is
  both observable and actionable.

- **ADR-WHEEL-04 Distinguishability (new in v0.2.0, well-specified):** The sentinel marker string
  as a named contract and the requirement for distinct CLI warning rendering are new and correct.
  The re-evaluation trigger tied to a sentinel firing rate (>1 per 100 runs) provides a concrete
  monitoring condition.

- **ADR-WHEEL-05 Re-evaluation Trigger (fully resolved):** The trigger now includes a measurable
  performance condition (>500 cycle files or >100ms on commodity hardware) and a concurrency
  condition. Both are observable and tied to product-scale events.

- **ADR-WHEEL-05 `_position_loader` injectable (confirmed in v0.2.0):** The injectable is now
  documented in the Consequences section with its correct consumer list (`CcAgent`, `RollCheckAgent`,
  `ConditionalLogic.route_wheel_phase()`), confirming test isolation at the agent level is fully
  designed.

- **ADR-WHEEL-03 single-ticker constraint (new in v0.2.0, well-specified):** The Consequences
  bullet documenting the single-ticker constraint is clear, correctly traces to US-05/US-07, and
  notes the out-of-scope multi-ticker batch scenario. The test coverage note ("verified implicitly
  by all existing PROPERTIES tests") is acceptable for this property.

---

## Recommendation

**Needs revision**

Three Medium findings (F-01, F-02, F-03) require changes before this document is used as input
to PLAN authoring. Each finding identifies a specific missing Consequences bullet that the PROPERTIES
author will need as ADR-level backing. The changes are additive and localised; no ADR decisions
require reversal.

Minimum required changes:

1. **ADR-WHEEL-03 Consequences:** Add the equity-passthrough integration test invariant (F-01).
2. **ADR-WHEEL-05 Consequences:** Add the `tmp_path` isolation requirement for I/O-layer unit tests
   and the integer-sort regression test specification (F-02).
3. **ADR-WHEEL-04 Consequences — Test coverage bullet:** Add the three-scenario requirement with
   explicit inclusion of the level-2 freetext-valid-JSON scenario (F-03).

F-04 (Low) and the three questions may be resolved in the same pass.
