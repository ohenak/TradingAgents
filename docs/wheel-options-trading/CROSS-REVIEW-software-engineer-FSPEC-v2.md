# Cross-Review — Software Engineer — FSPEC (v2)
# Document: FSPEC-wheel-options-trading.md v0.2.0

| Field | Value |
|---|---|
| Reviewer | Software Engineer (SE-Review) |
| Date | 2026-05-25 |
| Iteration | 2 |
| Recommendation | Needs revision |

---

## Resolution Status of Prior Findings

| Finding | Status | Notes |
|---|---|---|
| FSPEC-SE-01 | Resolved | Step 2 now correctly shows `route_to_vendor("get_options_chain", ...)` with no category argument. Business Rules add `TOOLS_CATEGORIES` registration requirement. Error contract (wrappers catch `ValueError`/`RuntimeError`) is now accurate. |
| FSPEC-SE-02 | Partially resolved | All three agent sections now mandate `bind_structured` from `structured.py`. However the call signature shown conflicts with the actual implementation (see FSPEC-SE2-01 below). |
| FSPEC-SE-03 | Resolved | Rule 5 mechanism is fully specified: `WheelPosition.prior_analyst_bias: Optional[str]`, written at end of each RollCheckAgent run, compared against current run's `AgentState.investment_plan` extraction. |
| FSPEC-SE-04 | Resolved | Business Rule added: agent verifies `options_lookforward_days >= recommended_dte_high` and uses `max(options_lookforward_days, recommended_dte_high + 7)` if not. Open Question carry-forward to TSPEC author noted. |
| FSPEC-SE-05 | Resolved | `route_wheel_phase()` return values fully enumerated as a table. `ConditionalLogic` construction requires injected first-analyst-node name at `setup_graph()` time. |
| FSPEC-SE-06 | Resolved | FSPEC-WHEEL-08 (CLI panel) and FSPEC-WHEEL-09 (risk debate injection) are now present and cover REQ-SCREEN-03 and REQ-TRADE-05. |
| FSPEC-SE-07 | Resolved | "No rule fires" aliasing to `"profit_capture"` is now explicitly documented in Business Rules with a note that downstream test assertions must be consistent with the aliasing. |
| FSPEC-SE-08 | Resolved | Criterion 5 now reads from `AgentState.investment_plan` / `ResearchPlan.recommendation` Literal (`Buy`, `Overweight`, `Hold`, `Underweight`, `Sell`). Free-text majority-vote branch removed. |
| FSPEC-SE-09 | Resolved | The below-cost-basis branch is unambiguous: if strikes ≥ cost basis exist, LLM is called with warning note; if no such strike exists, `tradeable=False` and LLM is not called. |
| FSPEC-SE-10 | Resolved | Open question closed: "Resolved: strict less-than per REQ-DATA-02 formula." |
| FSPEC-SE-11 | Not resolved | `AgentState` extension fields are still not enumerated in FSPEC-WHEEL-07. FSPEC-WHEEL-09 references `csp_decision` and `cc_decision` as state fields but defers their definition to an Open Question. See FSPEC-SE2-04. |
| FSPEC-SE-12 | Resolved | `"cycle_complete"` reset is now unambiguous: written to output state, graph terminates normally, next `invoke()` call starts in `"screening"`. No loop-back edge. |

---

## New or Remaining Findings

### [FSPEC-SE2-01] High — `bind_structured` call signature and fallback behaviour conflict with the actual `structured.py` implementation

**FSPEC sections:** FSPEC-WHEEL-04 Stage 4 step 11 and Business Rules; FSPEC-WHEEL-05 Stage 4 step 15 and Business Rules; FSPEC-WHEEL-06 step 9 and Business Rules

**Finding:** The v0.2.0 text mandates that each agent use `bind_structured(llm, CspDecision)` (or `CcDecision` / `RollDecision`) from `structured.py`. The actual signature in `structured.py` (line 31) is:

```python
def bind_structured(llm: Any, schema: type[T], agent_name: str) -> Optional[Any]:
```

Three arguments are required. The FSPEC omits `agent_name` entirely. Any agent implemented to the FSPEC call form will raise a `TypeError` at construction time.

Beyond the argument count, the fallback behaviour specified in all three sections — "if the structured call fails and the free-text fallback also fails to produce a parseable schema instance (via JSON extraction)" — does not exist in `structured.py`. The actual `invoke_structured_or_freetext` function (lines 48–73) falls back to `plain_llm.invoke(prompt).content`, which returns a raw string. There is no JSON extraction step on the free-text fallback. If the structured call fails, the function returns the LLM's raw string — which is not a `CspDecision` / `CcDecision` / `RollDecision` instance. The FSPEC's implied assertion that the fallback "produces a parseable schema instance via JSON extraction" is a feature that does not exist and must either be implemented in `structured.py` or in each agent.

Additionally, the FSPEC does not reference `invoke_structured_or_freetext` at all. An implementer reading only the FSPEC will call `bind_structured` at construction time and then have no specified invocation pattern — `bind_structured` returns a structured LLM wrapper, not a result. The invocation step is entirely missing.

**Impact:** Any implementation that exactly follows the FSPEC will fail at construction time (wrong arg count). Beyond that, the fallback JSON-extraction step will not exist unless added by the implementer, meaning schema validation failures will silently produce raw strings instead of `tradeable=False` sentinel instances, violating the specified safe-degradation contract.

**Suggested resolution:** Replace the current `bind_structured`-only references with the two-call pattern used by existing agents: (1) `bind_structured(llm, Schema, agent_name)` at construction time; (2) `invoke_structured_or_freetext(structured_llm, plain_llm, prompt, render, agent_name)` at invocation time. Specify what the `render` function returns for each schema (a serialised JSON string or a formatted markdown block). Explicitly state where JSON extraction from the free-text fallback is expected to occur: either it is a new capability to be added to `structured.py`, or each agent must implement a `parse_schema_from_string(raw: str, schema: type[T]) -> T | None` step after `invoke_structured_or_freetext` returns.

---

### [FSPEC-SE2-02] High — `"signal_processor"` is not an existing graph node; router return value for `cycle_complete` will fail at graph build time

**FSPEC section:** FSPEC-WHEEL-07, Business Rules (`route_wheel_phase()` return values) and step 9

**Finding:** The `route_wheel_phase()` return value table specifies:

> `wheel_phase == "cycle_complete"` → `"signal_processor"`

The current `setup_graph()` in `graph/setup.py` registers no node named `"signal_processor"`. The terminal node is `"Portfolio Manager"`, which connects to `END` via a plain edge (line 155). LangGraph's `add_conditional_edges` validates that every string returned by the routing function is a registered node or the `END` sentinel. Returning `"signal_processor"` for an unregistered node will raise a `ValueError` at graph-compile time (`workflow.compile()`), preventing the graph from starting.

**Impact:** The `"cycle_complete"` branch cannot be exercised at all until this node exists or the return value is changed to a valid node name. This is a blocking implementation gap — the state machine defined in FSPEC-WHEEL-07 cannot be wired into the existing graph without a decision on what node `"cycle_complete"` routes to.

**Suggested resolution:** The FSPEC must specify one of: (a) a new `"wheel_cycle_summary"` node (with its own node-creation function) that emits the cycle summary and resets `wheel_phase`, with `route_wheel_phase()` returning its registered name; (b) routing `cycle_complete` directly to `"Portfolio Manager"` (the current terminal node) with a pre-existing summary emission handled elsewhere; or (c) routing to `END` directly (the LangGraph sentinel, not a node string) if the cycle summary is emitted as part of the state transition itself. Option (a) is architecturally cleanest and consistent with the FSPEC's stated intent that a summary is emitted and the memory log written. The node name in the return value table and in `add_conditional_edges` must agree.

---

### [FSPEC-SE2-03] Medium — FSPEC-WHEEL-08 panel title string conflict leaves REQ-SCREEN-03 AC1 unverifiable

**FSPEC section:** FSPEC-WHEEL-08, Acceptance Tests AC1 and Open Questions

**Finding:** The FSPEC specifies the panel title as `"Wheel Suitability"`, but the acceptance test for REQ-SCREEN-03 AC1 asserts:

> `console.export_text()` contains `"Wheel Suitability"` (panel title) and `"IV Rank"`.

However, the Open Questions section in FSPEC-WHEEL-08 explicitly flags this conflict:

> "SE author should confirm the exact title string and whether it should match `'WheelCandidateReport'` verbatim (per REQ-SCREEN-03 AC1 which checks for `'WheelCandidateReport'` in output)."

This means the AC was written to pass on the FSPEC's own panel title (`"Wheel Suitability"`), but the upstream REQ-SCREEN-03 AC1 asserts on a different string (`"WheelCandidateReport"`). The FSPEC's AC1 text has been silently rewritten to match the FSPEC's design rather than the REQ's acceptance criterion. This is a traceability break: a test that passes the FSPEC's AC1 will fail the REQ's AC1.

**Impact:** PROPERTIES authors writing tests to REQ-SCREEN-03 AC1 will assert on `"WheelCandidateReport"` (the REQ's wording). Tests will fail unless the implementation includes this string in the output (e.g., as a subtitle, body header, or schema dump). This is a hidden PM/SE contract gap that will surface as a test failure in the nightly run.

**Suggested resolution:** The Open Question must be closed before TSPEC authoring. Either: (a) change the panel title to `"WheelCandidateReport"` to match the REQ assertion verbatim; (b) update REQ-SCREEN-03 AC1 to assert on `"Wheel Suitability"` (requires REQ rev); or (c) specify that both strings appear in the output (panel title is `"Wheel Suitability"` and the body includes a header line `"WheelCandidateReport"`). The FSPEC AC1 must reflect whichever string the implementation is expected to produce so that TE-authored tests pass against REQ.

---

### [FSPEC-SE2-04] Medium — `AgentState` extension fields remain unspecified; FSPEC-WHEEL-09 introduces new field references without resolution

**FSPEC section:** FSPEC-WHEEL-07 Business Rules; FSPEC-WHEEL-09 Input/Output and Open Questions

**Finding:** FSPEC-SE-11 from the prior review identified that new `AgentState` fields needed to be enumerated. In v0.2.0:

- FSPEC-WHEEL-07 still does not list the new `AgentState` fields (only `wheel_phase: Optional[str]` is mentioned by name in one business rule; the structured-result fields are not enumerated).
- FSPEC-WHEEL-09 references `csp_decision` and `cc_decision` as `AgentState` fields (serialised JSON strings) but immediately defers their definition to the SE author in the Open Questions section: "SE author must confirm these field names and their types (raw JSON string vs Pydantic instance) match the state layout defined in FSPEC-WHEEL-07."

The result is that the inter-node state contract — which fields exist, what their types are, who writes them, and who reads them — is unresolved in the FSPEC. FSPEC-WHEEL-09's prompt assembler reads `state["csp_decision"]` or `state["cc_decision"]`, but there is no specification of who writes these fields, in what format, or whether they are `Optional[str]` or `Optional[dict]`. Similarly, `WheelCandidateReport` must transit the state from WheelAnalyst to the CLI layer, but its state field name is not given.

**Impact:** TSPEC and PROPERTIES authors will each make independent assumptions about field names and types. Inconsistent assumptions will produce import-time or runtime `KeyError` / `TypeError` failures in the graph. This is the same risk flagged in FSPEC-SE-11 and it remains unmitigated.

**Suggested resolution:** Add a state-extension table to FSPEC-WHEEL-07 (or a dedicated sub-section) enumerating all new `AgentState` fields introduced by the wheel feature. At minimum: `wheel_phase: Optional[str]`, `wheel_candidate_report: Optional[str]` (serialised JSON from WheelAnalyst), `csp_decision: Optional[str]` (serialised JSON from CspAgent), `cc_decision: Optional[str]` (serialised JSON from CcAgent), `roll_decision: Optional[str]` (serialised JSON from RollCheckAgent). Confirm type (raw JSON string) and writing agent for each field. Close the Open Question in FSPEC-WHEEL-09 once this table is written.

---

### [FSPEC-SE2-05] Medium — FSPEC-WHEEL-09 `{options_context}` injection point in debate prompts is deferred to SE author — a PM-scoped decision

**FSPEC section:** FSPEC-WHEEL-09, Behavioural Flow step 2 and Open Questions

**Finding:** The FSPEC specifies that `{options_context}` is inserted "at a defined injection point in the existing debate prompt template" but defers specifying where in the template this injection point is to the SE author:

> "SE author must specify where in the prompt structure this injection point is placed (e.g., after the standard market context block, before the debate instructions)."

Where the options context appears in the debate prompt directly affects LLM behaviour — if placed before the debate instructions, debaters will weight it heavily; if placed after the market context and before their role definition, it influences the framing. This is a functional decision about how the risk debate incorporates options data, which is PM scope. Deferring it to the SE author causes the SE (TSPEC author) to make a product-level decision that may conflict with PM intent and cannot be captured in PROPERTIES test assertions (because the test checks string presence, not position).

**Impact:** If SE and PM have different mental models of where the injection occurs (e.g., SE puts it at the end as an appendix, PM expects it to precede the debate question), the debate agents may reason differently than intended and the functional spec's intent is violated without any test catching it. REQ-TRADE-05 AC1 and AC2 test string presence in the assembled prompt, not injection position.

**Suggested resolution:** The PM must specify the injection point location (at least to the level of: "after the existing `{market_context}` variable block, before the debate role assignment instruction"). This is a one-line addition that prevents a class of silent functional defects.

---

### [FSPEC-SE2-06] Low — FSPEC-WHEEL-03 Open Question on "±10% near-the-money" threshold remains unresolved in v0.2.0

**FSPEC section:** FSPEC-WHEEL-03, Open Questions

**Finding:** The Open Questions section of FSPEC-WHEEL-03 still reads:

> "Criterion 2 boundary — what counts as 'near-the-money'? This FSPEC uses ±10% of spot price as the definition. SE author must confirm or adjust this threshold."

This question was present in v0.1.0 and is not resolved in v0.2.0. The ±10% definition is used as-is in the behavioural flow (step 3: "within 10% of current spot price") but remains flagged as a question requiring SE confirmation. If this threshold is incorrect for the target options universe (e.g., high-priced stocks where near-ATM strikes are clustered within 1–2%), it produces the wrong liquidity assessment.

**Impact:** Low — the value is used consistently within the FSPEC and is implementable. However, the unresolved flag creates uncertainty for TSPEC authors about whether the threshold may change.

**Suggested resolution:** Close the open question by either confirming the ±10% value or adjusting it. If the value is provisional and expected to be configurable, add `near_the_money_pct` to the config table and document the default.

---

### [FSPEC-SE2-07] Low — FSPEC-WHEEL-03 Criterion 3 midpoint DTE calculation open question remains unresolved

**FSPEC section:** FSPEC-WHEEL-03, Open Questions

**Finding:** The second Open Question in FSPEC-WHEEL-03 reads:

> "Criterion 3 target expiration calculation: This FSPEC uses the midpoint DTE rounded up. SE author may prefer the lower bound (`recommended_dte_low`) as a more conservative anchor. Clarification needed."

This question was present in v0.1.0 and is not resolved in v0.2.0. The behavioural flow at step 4 implements the midpoint: `(recommended_dte_low + recommended_dte_high) / 2` rounded up. The open question flags that this choice is provisional.

**Impact:** Low — the FSPEC is implementable as written. However, the unresolved flag means TSPEC authors cannot rely on the midpoint formula being stable. If the anchor changes to `recommended_dte_low`, the earnings-clearance buffer calculation changes, potentially inverting Criterion 3 pass/fail for borderline earnings dates.

**Suggested resolution:** Close the open question by choosing one formula. The midpoint is a valid and conservative choice for a 28–45 DTE window; unless there is a specific reason to prefer the lower bound, close with "midpoint DTE, rounded up, as specified in step 4."

---

## Summary

v0.2.0 resolves the majority of the prior SE review findings, including the critical routing call contract (FSPEC-SE-01), the Rule 5 state mechanism (FSPEC-SE-03), the `route_wheel_phase()` return type (FSPEC-SE-05), the two missing FSPEC sections (FSPEC-SE-06), and the below-cost-basis contradiction (FSPEC-SE-09). The document is materially improved.

Two new High-severity issues block implementation. FSPEC-SE2-01 reports that the `bind_structured` call signature shown in all three agent sections omits the required `agent_name` argument, the `invoke_structured_or_freetext` invocation pattern is absent entirely, and the specified JSON-extraction fallback does not exist in `structured.py` — meaning an implementation written to the FSPEC will fail at construction time and silently misbehave on schema failures. FSPEC-SE2-02 reports that the `"signal_processor"` node returned by `route_wheel_phase()` for `cycle_complete` is not registered in the current graph, which will cause `workflow.compile()` to raise a `ValueError` before the graph can execute.

Two Medium issues require PM decisions that are currently deferred to SE: FSPEC-SE2-03 (the panel title string that conflicts between FSPEC-WHEEL-08 and REQ-SCREEN-03 AC1) and FSPEC-SE2-05 (the `{options_context}` injection point location in the debate prompt templates). FSPEC-SE2-04 carries forward the unresolved `AgentState` field enumeration from FSPEC-SE-11.

Three Low issues (FSPEC-SE2-06, FSPEC-SE2-07) are carry-forward open questions from v0.1.0 that should be closed to prevent TSPEC uncertainty.

The document should not proceed to TSPEC authoring until FSPEC-SE2-01 and FSPEC-SE2-02 are resolved.

---

## Approved Items

- **FSPEC-WHEEL-01 routing contract (v0.2.0):** The corrected `route_to_vendor("method_name", ...)` call pattern, the `TOOLS_CATEGORIES` registration rule, and the error-catch contract at the tool-wrapper layer are all accurate and implementable.
- **FSPEC-WHEEL-02 IV computation (unchanged from v0.1.0):** Fully implementable; the injectable test seam, zero-variance guard, boundary annotations, and output field table remain correct.
- **FSPEC-WHEEL-03 Criteria 1–4 and Criterion 5 mechanism:** Criterion 5 is now specified via `ResearchPlan.recommendation` Literal, which provides a deterministic test seam. The multi-criterion failure concatenation, sentinel `[0.0, 0.0]` for rejected strike range, and `analyst_bias` string values are clearly specified.
- **FSPEC-WHEEL-04 and FSPEC-WHEEL-05 deterministic filter formulas and progressive relaxation:** The five financial formulas are correct and unambiguous. The progressive relaxation ordering (C → B → A-fallback) is correctly specified. The below-cost-basis branch resolution in FSPEC-WHEEL-05 is now consistent.
- **FSPEC-WHEEL-06 Rule 5 mechanism and multi-rule priority:** `WheelPosition.prior_analyst_bias` storage, update timing, and the `prior_bullish AND current_bearish` firing condition are fully specified and testable. The six-level priority order (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1) and the `"profit_capture"` aliasing are explicitly documented.
- **FSPEC-WHEEL-07 phase transition table, guard table, and router return values:** The transition table, required-data guards, `WheelStateError` messages, and the full `route_wheel_phase()` return value enumeration are complete and accurate (subject to FSPEC-SE2-02 resolution for the `cycle_complete` target node).
- **FSPEC-WHEEL-08 CLI display (structure):** The field list, approval styling, panel insertion point, and Rich test-harness pattern are clearly specified and match existing CLI conventions.
- **FSPEC-WHEEL-09 options context injection (structure):** The field list for `options_context`, `CspDecision` vs `CcDecision` branching, and the equity-only suppression rule are well specified. The injection point location remains an open question.
- **TE findings resolution:** Test level annotations added to all ACs, `rationale` schema-contract tests added to all four agent sections, boundary-value ACs added for filter inclusivity and IV rank thresholds, and progressive relaxation ACs added for relaxation attempts 9a and 9b. These collectively close all FSPEC-TE findings that were in scope for PM/FSPEC action.
