# Cross-Review: test-engineer — DECISIONS

**Reviewer:** test-engineer
**Document reviewed:** docs/wheel-options-trading/DECISIONS-wheel-options-trading.md v0.3.0
**Date:** 2026-05-25
**Iteration:** 3

---

## Context

This is the third iteration review. The prior review (v2, `CROSS-REVIEW-test-engineer-DECISIONS-v2.md`)
raised four findings: F-01 (Medium, ADR-WHEEL-03 equity-passthrough integration test invariant
absent), F-02 (Medium, ADR-WHEEL-05 `tmp_path` isolation and integer-sort regression test absent),
F-03 (Medium, ADR-WHEEL-04 level-2 freetext-valid-JSON fallback scenario missing), and F-04 (Low,
ADR-WHEEL-04 sentinel constant declared a contract but no import-enforcement mechanism specified).

v0.3.0 fully resolves all four prior findings and introduces one new v0.3.0-specific addition
(ADR-WHEEL-01 zero-variance sentinel disclosure) that carries a minor residual testability gap.

---

## Resolution Status of Prior Findings (F-01 through F-04)

| Prior ID | Status | Notes |
|----------|--------|-------|
| F-01 | Resolved | ADR-WHEEL-03 Consequences now includes the dedicated equity-passthrough integration test invariant, with explicit PROPERTIES mandate and LangGraph regression guard framing |
| F-02 | Resolved | ADR-WHEEL-05 Consequences now includes both the `tmp_path` I/O-layer isolation requirement and the integer-sort regression test specification (cycle-10 over cycle-9 invariant); both carry "must appear in the PROPERTIES document" mandates |
| F-03 | Resolved | ADR-WHEEL-04 Test coverage bullet now specifies all three scenarios per agent — (a) structured-output success, (b) freetext-valid-JSON path, (c) total failure — with explicit statement that scenario (b) guards against silent `tradeable=False` outcomes; 12-case total documented |
| F-04 | Resolved | ADR-WHEEL-04 Sentinel constant enforcement bullet now requires `STRUCTURED_OUTPUT_SENTINEL` to be defined in `structured.py` and imported by all four agents, the CLI display layer, and all test assertions — import-time mutation detection is fully specified |

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | ADR-WHEEL-01 zero-variance disclosure note string `'IV range is flat — rank set to neutral 50'` is specified verbatim but not elevated to a named constant, leaving it vulnerable to accidental mutation that silently breaks verbatim-surface assertions | ADR-WHEEL-01 Consequences — Zero-variance sentinel disclosure |
| F-02 | Low | Local | Q-02 from v2 (bare JSON vs markdown-fenced JSON on the freetext path) is only partially addressed: the test coverage bullet now says "valid bare JSON string" but the Decision section step 3 still does not state whether agents must strip markdown fences before calling `model_validate_json` | ADR-WHEEL-04 Decision step 3; Consequences — Test coverage |
| F-03 | Low | Local | Q-03 from v2 (multiple `status="open"` files for the same ticker) remains unaddressed: the Consequences section documents orphan file risk but does not specify the return behaviour or error condition when `load_latest_open_position` finds more than one open-status file for the same ticker | ADR-WHEEL-05 Consequences |

---

## Finding Detail

### F-01 — Low — ADR-WHEEL-01 zero-variance disclosure note string lacks constant-enforcement

**New in v0.3.0.** The Zero-variance sentinel disclosure bullet (ADR-WHEEL-01 Consequences) states
that the formatted report string includes the note `'IV range is flat — rank set to neutral 50'` and
that the CLI output and `WheelCandidateReport.iv_assessment` field must surface this note
"verbatim when it is present."

The verbatim requirement implies a string equality check in tests. However, unlike the
`STRUCTURED_OUTPUT_SENTINEL` constant (ADR-WHEEL-04), there is no analogous requirement to define
this note string as a named constant. Any test asserting verbatim presence, and the CLI display
layer checking for it, will hardcode the string literal `'IV range is flat — rank set to neutral 50'`
— the same mutation risk that motivated F-04 in the prior review.

If the string changes in `get_iv_metrics` without a corresponding change in the CLI layer and the
test assertions, the disclosure requirement will silently stop working: the zero-variance sentinel
will produce `iv_environment = "normal"` with no warning, and no test will catch it.

**Suggested addition:** Add to the zero-variance sentinel disclosure bullet: "The note string
`'IV range is flat — rank set to neutral 50'` must be defined as a module-level constant (e.g.,
`IV_FLAT_NOTE` in the same module as `get_iv_metrics`). The CLI surface check and any test
asserting verbatim presence must import `IV_FLAT_NOTE` rather than hardcoding the string literal,
for the same mutation-safety reasons as `STRUCTURED_OUTPUT_SENTINEL`."

---

### F-02 — Low — ADR-WHEEL-04 step 3 still silent on markdown-fence stripping

**Q-02 from v2 partially addressed.** The test coverage bullet now specifies "(b) freetext fallback
succeeds — mock `invoke_structured_or_freetext` to return a **valid bare JSON string**." The word
"bare" implicitly restricts scenario (b) to clean JSON. However, the Decision section step 3 still
reads: "The agent calls `Schema.model_validate_json(raw_str)` on the returned string." It does not
state whether `raw_str` may be markdown-fenced (e.g., ` ```json\n{...}\n``` `) and, if so, whether
the agent must strip the fences before calling `model_validate_json`. This omission has a direct
test consequence: if the freetext LLM path returns fenced JSON and the agent does not strip fences,
`model_validate_json` raises `ValidationError`, the sentinel is returned, and scenario (b)'s test
(which uses bare JSON) passes — masking the real failure mode.

**Suggested addition:** Add one sentence to Decision step 3: "If `raw_str` begins with a markdown
code fence (`` ```json `` or `` ``` ``), the agent must strip the fence and closing delimiter before
calling `model_validate_json`. Test scenario (b) must include one parametrised sub-case with a
fenced input to cover this branch."

---

### F-03 — Low — ADR-WHEEL-05 does not specify behaviour for multiple concurrent open positions

**Q-03 from v2 unaddressed.** The Consequences section documents that `load_latest_open_position`
skips `status="cycle_complete"` positions and returns the latest `status="open"` position. It does
not specify behaviour when two or more files for the same ticker both have `status="open"` — a
realistic edge case when a graph crash occurred after writing cycle N's file but before updating
cycle N-1's status to `cycle_complete`.

Without a specified behaviour (return the highest-cycle open file, raise `WheelStateError`, log a
warning), the PROPERTIES author cannot write a deterministic test for this case, and the
implementation is free to return either file silently.

**Suggested addition:** Add to ADR-WHEEL-05 Consequences: "When `load_latest_open_position` finds
multiple `status='open'` files for the same ticker, it returns the one with the highest integer
cycle number and emits a `WARNING`-level log entry listing the conflicting files (or, if a stricter
contract is preferred, raises `WheelStateError`). This behaviour must be specified in TSPEC Section
9.2 and covered by a dedicated PROPERTIES test. Leaving it unspecified creates an untestable
ambiguity at the boundary most likely to be reached by orphan-file accumulation."

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | ADR-WHEEL-04 Test coverage bullet specifies 12 fallback test cases across "four wheel agents." Are all four agents confirmed to be WheelAnalyst, CspAgent, CcAgent, and RollCheckAgent? The Decision section step 4 specifies sentinel values for CspAgent, CcAgent, and RollCheckAgent but does not list a sentinel value for WheelAnalyst (which uses `deep_think_llm`). If WheelAnalyst produces a `WheelCandidateReport`, its sentinel `tradeable=False` value should be explicitly enumerated alongside the others. |

---

## Positive Observations

- **All four prior findings fully resolved.** Every required change from v2 was implemented
  precisely and with the correct level of specificity. The equity-passthrough integration test
  invariant (ADR-WHEEL-03), the `tmp_path` I/O-layer isolation requirement (ADR-WHEEL-05), the
  integer-sort regression test specification (ADR-WHEEL-05), the three-scenario test coverage
  including level-2 freetext-valid-JSON (ADR-WHEEL-04), and the `STRUCTURED_OUTPUT_SENTINEL`
  import-enforcement requirement (ADR-WHEEL-04) are all present and correctly specified.

- **ADR-WHEEL-01 zero-variance sentinel disclosure (new in v0.3.0, substantively correct):** The
  addition of the zero-variance sentinel disclosure requirement is a correct and important testability
  consequence of the realised-vol proxy decision. The requirement that the CLI surface the note
  "verbatim when it is present" and trace it to REQ-DATA-02, REQ-SCREEN-01, and REQ-SCREEN-02 gives
  the PROPERTIES author concrete anchors. The disclosure of the approval-without-valid-data risk
  (`iv_rank = 50` passes Criterion 1) is precise and testable.

- **ADR-WHEEL-04 Test coverage bullet (12-case enumeration, complete):** The three-scenario
  enumeration with level-2 explicitly identified as "the guard against the agent silently treating a
  valid freetext JSON response as a total failure" is exactly the right framing. The addition of
  `STRUCTURED_OUTPUT_SENTINEL` as the required assertion target (rather than a string literal) makes
  the test both mutation-safe and self-documenting.

- **ADR-WHEEL-05 tmp_path and integer-sort bullets (well-scoped):** The distinction between
  "I/O-layer functions require `tmp_path`-isolated tests" and "agent-level unit tests use the
  `_position_loader` injectable" correctly identifies two separate test isolation strategies at two
  levels of the call stack. Both bullets carry explicit "must appear in the PROPERTIES document"
  directives.

- **ADR-WHEEL-03 equity-passthrough invariant (well-framed):** The new Consequences bullet
  correctly names the specific output fields (`wheel_phase` remains `None`, no options-layer tools
  invoked, `market_report` / `sentiment_report` functionally equivalent), giving the PROPERTIES
  author enough detail to write the test without consulting the TSPEC for the field list.

---

## Recommendation

**Approved with minor changes**

All three findings are Low severity. The document is ready to serve as PLAN input. The three Low
findings are additive and localised:

1. **ADR-WHEEL-01 Consequences:** Add constant-enforcement language for the zero-variance note
   string `'IV range is flat — rank set to neutral 50'` (F-01).
2. **ADR-WHEEL-04 Decision step 3:** Add one sentence specifying markdown-fence stripping
   behaviour and a parametrised sub-case for test scenario (b) (F-02).
3. **ADR-WHEEL-05 Consequences:** Add specified behaviour for multiple concurrent `status="open"`
   files and the associated PROPERTIES test requirement (F-03).

These may be addressed in the same pass as PLAN authoring, or in a DECISIONS v0.3.1 patch.
Q-01 (WheelAnalyst sentinel value enumeration) should be clarified before the PLAN's test task
table is written.
