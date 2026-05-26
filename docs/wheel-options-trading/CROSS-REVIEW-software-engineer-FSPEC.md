# Cross-Review — Software Engineer — FSPEC
# Document: FSPEC-wheel-options-trading.md v0.1.0

| Field | Value |
|---|---|
| Reviewer | Software Engineer (SE-Review) |
| Date | 2026-05-25 |
| Document reviewed | FSPEC-wheel-options-trading.md v0.1.0 |
| Recommendation | Needs revision |

---

## Summary

The FSPEC is well-structured and covers the seven behavioural areas described in its overview. The flows for IV computation (FSPEC-WHEEL-02), suitability screening (FSPEC-WHEEL-03), and the state machine (FSPEC-WHEEL-07) are the most complete and implementable sections. However, three High-severity issues block implementation: the routing contract in FSPEC-WHEEL-01 conflicts materially with the actual `route_to_vendor()` signature in `interface.py`; the `structured.py` fallback path is missing from the LLM-call flows in FSPEC-WHEEL-04 through FSPEC-WHEEL-06; and the Rule 5 analyst-update detection in FSPEC-WHEEL-06 has no specified mechanism for accessing prior-run state, making implementation impossible without a design decision. Seven Medium-severity issues cover ambiguous filter preconditions, missing schema fields, a broken `no-rule-fires` default, and unresolved open questions that create rework risk. These must be resolved before TSPEC authoring begins.

---

## Findings

### [FSPEC-SE-01] High — `route_to_vendor()` call contract is incompatible with the actual implementation

**FSPEC section:** FSPEC-WHEEL-01, step 2

**Finding:** The flow describes calling `route_to_vendor()` with a `category` key as the first argument and a `method_name` as the second: `route_to_vendor("options_data", "get_options_chain", ...)`. However, the actual signature in `interface.py` (line 134) is `route_to_vendor(method: str, *args, **kwargs)` — it takes only the method name and derives the category internally via `get_category_for_method(method)`. The category is not passed by the caller at all. Additionally, the existing implementation raises `ValueError` (not `RuntimeError`) when a method is not in `VENDOR_METHODS` (line 141), and raises `RuntimeError` only when no vendor is available after the fallback chain is exhausted (line 162). There is no code path that returns `"Unknown options_data vendor: {vendor}"` as a string — `get_vendor()` returns `"default"` for unknown keys and the fallback chain proceeds. The FSPEC's error contract ("returns an error string, does not raise") is inconsistent with the actual behaviour ("raises `RuntimeError`").

**Impact:** Any `options_data_tools.py` implementation written to the FSPEC call pattern will fail at runtime with a `TypeError` on the wrong argument count. The stated error-return contract will also not hold — exceptions will propagate to calling agents, violating REQ-NFR-06.

**Suggested resolution:** Revise step 2 to show `route_to_vendor("get_options_chain", ...)` with no category argument. Add a new business rule explaining that the new category `"options_data"` must be registered in `TOOLS_CATEGORIES` (following the pattern of `"core_stock_apis"`) so that `get_category_for_method()` resolves it. Revise the error contract to state that `options_data_tools.py` wrappers must catch `ValueError` and `RuntimeError` from `route_to_vendor()` and convert them to error strings before returning to the agent, satisfying REQ-NFR-06 at the tool-wrapper layer rather than inside the router.

---

### [FSPEC-SE-02] High — `structured.py` fallback path not specified for LLM-decision agents

**FSPEC section:** FSPEC-WHEEL-04 Stage 4, FSPEC-WHEEL-05 Stage 4, FSPEC-WHEEL-06 steps 5–6

**Finding:** The flows for `CspAgent`, `CcAgent`, and `RollCheckAgent` all describe calling the LLM and validating the output against a schema, but none reference the `invoke_structured_or_freetext()` pattern from `structured.py`. The existing codebase uses `bind_structured(llm, schema, agent_name)` at agent-creation time and `invoke_structured_or_freetext(structured_llm, plain_llm, prompt, render, agent_name)` at invocation time. The FSPEC's schema-validation-retry logic (e.g., FSPEC-WHEEL-04 step 12: "retry once; if the second attempt fails, return `tradeable = False`") conflicts with `structured.py`'s own fallback: `structured.py` retries once as free text on failure, and its output is a rendered string — not a Pydantic instance — making downstream validation against `CspDecision`/`CcDecision` schemas non-trivial. There is no description of how the rendered string from the free-text fallback is parsed back into a schema instance.

**Impact:** REQ-NFR-04 requires all decision schemas to use the existing `structured.py` wrapper. Without specifying how the FSPEC flows interact with `structured.py`'s retry/fallback mechanism, the implementer must design this behaviour ad hoc, producing inconsistent behaviour across the three agents and potentially double-counting retry attempts.

**Suggested resolution:** Add a business rule to each affected section: "LLM invocation must use `invoke_structured_or_freetext()` from `structured.py`. If the structured call fails and the free-text fallback also fails to produce a parseable schema instance (via JSON extraction), return `tradeable = False` / `action = "HOLD"` with the appropriate rejection reason. The `structured.py` internal retry is considered the first retry; no additional retry is performed at the agent level." Remove the standalone "retry once" language in the FSPEC and replace it with a reference to this pattern.

---

### [FSPEC-SE-03] High — Rule 5 (analyst update) in RollCheckAgent has no specified state access mechanism

**FSPEC section:** FSPEC-WHEEL-06, Rule 5

**Finding:** Rule 5 states "If the latest analyst consensus has changed from bullish (prior run) to bearish (current run)," but provides no specification for where the prior-run consensus is stored or how it is retrieved. The open question at the end of FSPEC-WHEEL-06 acknowledges this gap but does not provide options. The FSPEC says "e.g., in `WheelPosition.notes`, a separate state field, or the memory log" — these three options are architecturally different: `WheelPosition.notes` is a free-text string not suitable for structured retrieval; a separate state field requires extending `AgentState`; the memory log format (a markdown file parsed by `TradingMemoryLog`) does not have a `consensus` field at all. Without a decision on this, implementation cannot begin.

**Impact:** Rule 5 cannot be implemented. If the implementer chooses a mechanism not considered by the TSPEC author, it may conflict with the position tracker schema, `AgentState` field requirements, or the memory log format.

**Suggested resolution:** Close this open question in the FSPEC. The recommended resolution is: add a `prior_analyst_bias: Optional[str]` field to `WheelPosition` (storing `"bullish"`, `"neutral"`, or `"bearish"` as written at the close of each run), and read it at the start of `RollCheckAgent`. The `RollCheckAgent` compares the current `analyst_bias` from the incoming analyst reports against `WheelPosition.prior_analyst_bias`. Update the `WheelPosition` record at the end of each `RollCheckAgent` run regardless of action taken.

---

### [FSPEC-SE-04] Medium — `get_options_chain` is called without an expiry filter in FSPEC-WHEEL-03 and FSPEC-WHEEL-04, but the DTE window is required

**FSPEC section:** FSPEC-WHEEL-03 step 3, FSPEC-WHEEL-04 step 3

**Finding:** FSPEC-WHEEL-03 step 3 says `get_options_chain(ticker, curr_date)` — no expiry argument. FSPEC-WHEEL-04 step 3 says the same. But the DTE-window filter (28–45 days) is applied in Stage 2 using the data already fetched. The tool signature (from FSPEC-WHEEL-01) accepts an optional `expiry_date` parameter but no `dte_window` or `lookforward_days` parameter — it returns all expirations within `options_lookforward_days` (default 90 days). This means the agent fetches up to 90 days of chains and then filters down to 28–45 days in code. This is consistent but unstated — implementers reading step 3 may call with no arguments and not realise the 90-day window is the raw fetch scope. More critically, REQ-DATA-01 defines the lookforward window as configurable via `options_lookforward_days`, but this config key does not appear in REQ Section 7 (the config table). The FSPEC does not reference how to ensure 90 days ≥ `recommended_dte_high` when `recommended_dte_high` is changed from the default 45.

**Impact:** If `options_lookforward_days` is set below `recommended_dte_high`, the chain fetch returns no expirations in the target DTE window and every trade resolves to `tradeable = False`. This is a silent misconfiguration with no runtime error.

**Suggested resolution:** Add a business rule in FSPEC-WHEEL-04: "Before calling `get_options_chain`, the agent must verify that `options_lookforward_days >= recommended_dte_high`. If not, the fetch must use `max(options_lookforward_days, recommended_dte_high + 7)` as the effective lookforward." Also add `options_lookforward_days` to the configuration table in REQ Section 7.

---

### [FSPEC-SE-05] Medium — `route_wheel_phase()` return type conflicts with LangGraph conditional edge API

**FSPEC section:** FSPEC-WHEEL-07, Behavioural Flow — Router

**Finding:** The FSPEC says `route_wheel_phase()` returns "a node name string directing the `StateGraph` to the appropriate next node." LangGraph's `add_conditional_edges()` method requires the routing function to return either a string matching a node name (when routing to a single target) or a key matching the `conditional_edge_mapping` dict supplied to `add_conditional_edges`. The existing `ConditionalLogic` methods (e.g., `should_continue_market`) return node-name strings directly, and `add_conditional_edges` is called with a list of possible targets. However, for `route_wheel_phase()`, the router must return different first-node names depending on the phase (`"screening"` routes to the first analyst node, `"csp_open"` routes to `RollCheckAgent`, etc.). The existing `setup_graph()` calls `workflow.add_edge(START, plan.specs[0].agent_node)` — a plain edge, not a conditional one. The FSPEC says to replace this with `START → wheel_router` as a preamble conditional edge, but does not specify the `conditional_edge_mapping` dict or how the `None` phase (equity-only path) determines which analyst node to route to when the analyst plan is built dynamically by `build_analyst_execution_plan()`.

**Impact:** The implementer cannot wire the conditional edge without knowing the exhaustive set of possible return values and how to register them. When `wheel_phase = None`, the router must return `plan.specs[0].agent_node` — a value that is dynamically determined at graph-build time and not known statically. This is an architectural gap that may require refactoring how `setup_graph()` passes the analyst plan to `ConditionalLogic`.

**Suggested resolution:** Specify that `ConditionalLogic` must be constructed with a reference to the first analyst node name (set during `setup_graph()`) or that `route_wheel_phase()` accepts the analyst plan as a parameter. Provide the `add_conditional_edges` call signature showing the full mapping dict with all five phase values plus `None`. Confirm that the FSPEC's intent is to use a string-keyed mapping rather than direct node-name returns to handle the dynamic first-analyst-node case.

---

### [FSPEC-SE-06] Medium — `WheelCandidateReport` has no FSPEC coverage for `REQ-SCREEN-03` (CLI) and `REQ-TRADE-05` (risk debate adaptation)

**FSPEC section:** (gap — no FSPEC section covers REQ-SCREEN-03 or REQ-TRADE-05)

**Finding:** REQ-SCREEN-03 requires CLI integration showing the `WheelCandidateReport` in a Rich panel, and REQ-TRADE-05 requires the risk debate agents to receive `CspDecision`/`CcDecision` context in their prompts. Neither requirement has a corresponding FSPEC section. REQ-SCREEN-03 AC1–AC3 and REQ-TRADE-05 AC1–AC3 have no FSPEC acceptance test coverage. The FSPEC overview states it covers the "seven areas of behavioural complexity" but both of these are areas where engineering decisions are needed: what Rich panel layout is specified, and exactly how the risk debate prompt is assembled (which fields, which format).

**Impact:** TSPEC and PROPERTIES authors will have no functional specification to reference for these two requirements, forcing them to make design decisions that the PM should have specified. This breaks the PDLC pipeline and creates rework risk when those decisions conflict with PM intent.

**Suggested resolution:** Add FSPEC-WHEEL-08 covering CLI display behaviour for the WheelCandidateReport panel (field list, layout, colour scheme for approved/rejected). Add FSPEC-WHEEL-09 covering risk debate prompt assembly when `CspDecision`/`CcDecision` are available, specifying which fields are included and how the context string is formatted.

---

### [FSPEC-SE-07] Medium — `no rule fires` default in RollCheckAgent produces wrong `trigger_reason`

**FSPEC section:** FSPEC-WHEEL-06, step 6 (multi-rule firing) and Edge Cases

**Finding:** The "no rule fires" default is specified as `action = "HOLD"`, `trigger_reason = "profit_capture"`. However, `"profit_capture"` is the trigger reason for Rule 1 (profit target hit). When no rule fires, the position is within normal parameters — it has not reached the profit target, it is not near DTE, and there is no breach or analyst change. Returning `trigger_reason = "profit_capture"` when Rule 1 did not fire is factually incorrect and will cause test failures: a test that checks "no rule fires → HOLD" will pass the action check but fail if it additionally asserts on the semantics of `trigger_reason`. Furthermore, the `RollDecision` schema defines `trigger_reason` as a `Literal` with exactly six values and `"profit_capture"` is the only `HOLD`-associated value, so there is no clean `"no_rule"` value available.

**Impact:** Tests asserting `trigger_reason == "profit_capture"` when profit target was not reached will be semantically misleading. REQ-LIFE-03 AC1 specifies `action = "HOLD"` with `trigger_reason = "profit_capture"` only when "premium is at 50% of received value" (i.e., Rule 1 fired). The no-rule-fires default will produce the same output as a genuine Rule 1 trigger, making it impossible to distinguish the two cases programmatically.

**Suggested resolution:** Either (a) add a seventh `trigger_reason` Literal value `"no_trigger"` for the no-rule-fires default (requires updating REQ-LIFE-04 schema), or (b) specify that the no-rule-fires default also sets `trigger_reason = "profit_capture"` and explicitly accept this aliasing in the schema documentation with a note that `"profit_capture"` covers both "Rule 1 fired" and "no rule fired, position is within normal parameters." Document the choice in REQ-LIFE-04 so downstream test assertions are consistent. Option (b) is the lower-change path.

---

### [FSPEC-SE-08] Medium — `WheelAnalyst` Criterion 5 consensus source is underspecified for the common case

**FSPEC section:** FSPEC-WHEEL-03, step 6

**Finding:** The FSPEC specifies that when the Portfolio Manager's `PortfolioDecision` is not available, the consensus is determined by "majority vote across the four analyst reports." The existing `AgentState` stores analyst outputs as plain strings (`market_report`, `sentiment_report`, `news_report`, `fundamentals_report`) — there is no structured signal field on these reports. Extracting a Buy/Hold/Sell signal from a free-text report string requires either string parsing (fragile) or an additional LLM call (introduces latency and token cost). The `WheelAnalyst` runs after the existing four analysts but before the Bull/Bear debate and Portfolio Manager, so `PortfolioDecision` is never available when `WheelAnalyst` runs. The "PM decision available" branch is therefore dead code in the normal flow.

**Impact:** The implementer must decide how to extract consensus from free-text analyst reports, risking inconsistent results and test failures. If an LLM call is used, REQ-NFR-04 and TSPEC authors will need to account for additional latency and provider cost. The dead-code branch for `PortfolioDecision` wastes specification space and may confuse implementers.

**Suggested resolution:** Remove the `PortfolioDecision` branch — it does not apply when `WheelAnalyst` runs. Specify exactly how consensus is extracted from the four report strings: either (a) the `WheelAnalyst` LLM prompt includes the four reports and asks it to determine overall bias as part of its structured output (cleanest approach, no extra call), or (b) parse for a signal keyword using `parse_rating()` from `tradingagents/agents/utils/rating.py` (already present in the codebase). Specify which approach is required.

---

### [FSPEC-SE-09] Medium — `CcAgent` below-cost-basis branch is internally contradictory

**FSPEC section:** FSPEC-WHEEL-05, step 4a and Business Rules

**Finding:** Step 4a states: "Populate `CcDecision` with `tradeable = False` (or `tradeable = True` with strong warning at LLM's discretion — see Business Rules). Skip to Stage 4 (LLM selection is still invoked, but with the warning note in the prompt)." The business rules then say: "When `spot_price < cost_basis`, the result is always `tradeable = False` with a non-empty `rejection_reason` noting the below-cost-basis risk. The LLM is not called in this branch." These two statements directly contradict each other: the flow says the LLM is still invoked with a warning; the business rules say the LLM is not called. The acceptance test (AC2) and the edge case table both follow the business rule (`tradeable = False`, LLM not called), but the flow step says otherwise.

**Impact:** Implementers reading the flow will invoke the LLM; implementers reading the business rules will not. The acceptance test will pass for one approach and fail for the other. This is a clear implementation fork with no way to resolve without PM clarification.

**Suggested resolution:** Remove the parenthetical in step 4a and replace it with the unambiguous wording from the business rules: "Return `CcDecision` with `tradeable = False` and `rejection_reason` noting below-cost-basis risk. The LLM is not called." The open question in the section already flags this decision; it must be resolved before TSPEC authoring. The FSPEC should choose one path and delete the other.

---

### [FSPEC-SE-10] Low — `iv_percentile` open question is already answered by the REQ

**FSPEC section:** FSPEC-WHEEL-02, Open Questions

**Finding:** The open question asks whether `iv_percentile` uses strict-less-than (`< current_vol`) or less-than-or-equal (`<= current_vol`). REQ-DATA-02 (v0.2.0) specifies the formula as `(days where realised_vol < current_vol) / total_days × 100` — strict less-than. The FSPEC already restates this formula in step 8: "count of days in series where realised_vol < current_vol." The open question is already answered in the REQ and in the FSPEC's own body.

**Impact:** Low — no implementation ambiguity. The open question may cause reviewers to spend time on a non-issue.

**Suggested resolution:** Close the open question with: "Resolved: strict less-than per REQ-DATA-02 formula. Boundary day (where realised_vol == current_vol) is not counted in the percentile."

---

### [FSPEC-SE-11] Low — `AgentState` extension not specified; new fields are described implicitly

**FSPEC section:** FSPEC-WHEEL-07

**Finding:** The FSPEC states `AgentState["wheel_phase"]` must be added as `Optional[str]`, and business rules mention that `WheelCandidateReport`, `CspDecision`, `CcDecision`, and `RollDecision` results must be passed between nodes. However, the FSPEC does not specify which `AgentState` fields carry these outputs. In the existing graph, all inter-node results are passed via `MessagesState.messages` (a list of `AnyMessage`) or via named string fields like `market_report`. For structured output schemas to be accessible to downstream agents, they either need dedicated `AgentState` fields or must be serialised into the messages list. Without a specification, different nodes may use incompatible access patterns.

**Impact:** Medium-risk rework if the TSPEC author and implementer make different assumptions about state layout. Pydantic models stored directly in `AgentState` must be JSON-serialisable; `MessagesState` base handles this for `messages` automatically but not for custom TypedDict fields.

**Suggested resolution:** Add a brief state-extension specification to FSPEC-WHEEL-07 listing the new `AgentState` fields: `wheel_phase: Optional[str]`, `wheel_candidate_report: Optional[str]` (serialised JSON), `csp_decision: Optional[str]`, `cc_decision: Optional[str]`, `roll_decision: Optional[str]`. Using string (serialised JSON) rather than raw Pydantic instances avoids LangGraph checkpoint serialisation issues while making the inter-node contract explicit.

---

### [FSPEC-SE-12] Low — `cycle_complete` reset happens "within the same invocation" but graph has no loop-back edge for this

**FSPEC section:** FSPEC-WHEEL-07, step 9 and Open Questions

**Finding:** The FSPEC specifies that after emitting the cycle summary in `cycle_complete`, `wheel_phase` resets to `"screening"` within the same graph invocation. However, `setup_graph()` builds a `StateGraph` that ends at `Portfolio Manager → END`. There is no loop-back edge from any cycle-summary node back to the router or analyst nodes. If `cycle_complete` processing emits the summary and resets `wheel_phase` in the output state, the graph still terminates — the next `"screening"` invocation occurs on the caller's next call to `graph.invoke()`. The FSPEC's claim that the reset "happens within the same invocation" is architecturally incorrect given the current graph topology.

**Impact:** Low — the net observable behaviour (state resets to `"screening"`) is the same regardless of whether it happens within or across invocations. But the phrase "within the same invocation" may cause the TSPEC author to attempt to add a loop-back edge, which conflicts with the existing terminal `Portfolio Manager → END` topology.

**Suggested resolution:** Clarify this open question: "The `wheel_phase = 'screening'` reset is written to the output state of the `cycle_complete` node. The graph invocation terminates normally. The next `graph.invoke()` call starts in `'screening'`. No intra-invocation loop is added." This removes ambiguity without changing the end-state behaviour.

---

## Approved Items

- **FSPEC-WHEEL-02 (IV computation flow):** The step-by-step computation is precise and implementable. Branch conditions, formulas, the zero-variance guard, and the injectable test seam are all unambiguous. The output field table is complete.
- **FSPEC-WHEEL-03 Criteria 1, 2, 3, 4 (suitability screening):** The criterion ordering, simultaneous-failure behaviour, and `rejection_reason` concatenation rule are clearly specified. The sentinel `[0.0, 0.0]` for `recommended_strike_range` when `approved = False` solves the Pydantic `list[float]` constraint correctly.
- **FSPEC-WHEEL-04 and FSPEC-WHEEL-05 deterministic filter formulas:** The formulas for `annualised_yield_pct`, `max_loss`, `breakeven_price`, and `probability_of_profit` are unambiguous and match REQ-TRADE-02 AC3.
- **FSPEC-WHEEL-06 rule priority table:** The priority matrix (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1) is explicit and testable. The six `trigger_reason` literals are clearly enumerated.
- **FSPEC-WHEEL-07 phase transition table and guard table:** The transition preconditions and `WheelStateError` error messages are fully specified and map directly to REQ-LIFE-01 ACs.
- **Error string contracts across all sections:** The pattern of returning error strings rather than raising exceptions (REQ-NFR-06) is consistently applied throughout FSPEC-WHEEL-01 through FSPEC-WHEEL-06, with specific string formats given for each error case.
- **Consistency with REQ (overall):** All FSPEC acceptance tests reference specific REQ ACs, and coverage is good across the core P0 requirements. The missing FSPEC sections for REQ-SCREEN-03 and REQ-TRADE-05 are flagged in FSPEC-SE-06; the remaining P0 requirements have adequate FSPEC coverage.
