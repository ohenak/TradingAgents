# Cross-Review — Software Engineer — FSPEC (v3)
# Document: FSPEC-wheel-options-trading.md v0.3.0

| Field | Value |
|---|---|
| Reviewer | Software Engineer (SE-Review) |
| Date | 2026-05-25 |
| Iteration | 3 |
| Recommendation | Approved with minor changes |

---

## Resolution Status of Prior v2 Findings

| Finding | Status | Notes |
|---|---|---|
| FSPEC-SE2-01 | Resolved | All three agent sections (FSPEC-WHEEL-04 step 11 and Business Rules, FSPEC-WHEEL-05 step 15 and Business Rules, FSPEC-WHEEL-06 step 9 and Business Rules) now specify the three-argument `bind_structured(llm, Schema, agent_name)` pattern and name `invoke_structured_or_freetext` explicitly. JSON-extraction fallback is now positioned as an agent-level step after `invoke_structured_or_freetext` returns a raw string. The `agent_name` snake_case identifiers (`'csp_agent'`, `'cc_agent'`, `'roll_check_agent'`) are given. One residual inaccuracy remains in how the structured-success path is described — see FSPEC-SE3-01 below. |
| FSPEC-SE2-02 | Resolved | `"signal_processor"` is replaced by `"wheel_cycle_summary"`. FSPEC-WHEEL-07 Actors and step 9 define `wheel_cycle_summary` as a new node with specified responsibilities (emit cycle summary, persist `WheelPosition`, write `TradingMemoryLog`, output `wheel_phase: None`, route to `END`). The FSPEC now clearly mandates adding this node to the graph. |
| FSPEC-SE2-03 | Resolved | FSPEC-WHEEL-08 resolves the conflict by using both strings: the Rich panel title is `"Wheel Suitability"` and the body always opens with the header line `## WheelCandidateReport`. Business Rules explicitly state that both strings will appear in `console.export_text()`, satisfying REQ-SCREEN-03 AC1 and FSPEC-WHEEL-08 AC1. Open Questions confirms this is closed. |
| FSPEC-SE2-04 | Resolved | FSPEC-WHEEL-07 now includes a "New AgentState Fields" table enumerating all five new fields (`wheel_phase`, `wheel_candidate_report`, `csp_decision`, `cc_decision`, `roll_decision`), with types (`Optional[str]`), writing agents, reading consumers, and serialisation rationale. FSPEC-WHEEL-09 Open Questions confirms the field names and types are closed. |
| FSPEC-SE2-05 | Resolved | FSPEC-WHEEL-09 Business Rules now specify the injection point: "after the `{market_context}` variable block and before the debate role-assignment instruction." Open Questions confirms FSPEC-SE2-05 is resolved. |
| FSPEC-SE2-06 | Resolved | FSPEC-WHEEL-03 Open Questions section now reads "None. Both items below are now closed." The ±10% near-the-money threshold is confirmed and the TSPEC carry-forward note (`near_the_money_pct` should be added to the config table with default `0.10`) is explicit. |
| FSPEC-SE2-07 | Resolved | FSPEC-WHEEL-03 Open Questions confirms midpoint DTE rounded up — `ceil((recommended_dte_low + recommended_dte_high) / 2)` calendar days — as the specified and closed formula. |

---

## New or Remaining Findings

### [FSPEC-SE3-01] Medium — `invoke_structured_or_freetext` always returns `str`; FSPEC description of the structured-success path is inaccurate

**FSPEC sections:** FSPEC-WHEEL-04 Stage 4 step 11 and Business Rules; FSPEC-WHEEL-05 Stage 4 step 15 and Business Rules; FSPEC-WHEEL-06 step 9 and Business Rules

**Finding:** All three agent sections now describe the invocation pattern as:

> "If the structured call succeeds, a validated `CspDecision` instance is returned."

The actual signature of `invoke_structured_or_freetext` in `agents/utils/structured.py` (lines 48–73) is:

```python
def invoke_structured_or_freetext(...) -> str:
```

The function always returns `str`. When the structured call succeeds, it returns `render(result)` — a rendered markdown string produced by the caller-supplied `render_fn`. When it falls back to freetext, it returns `response.content` — also a raw `str`. A validated `CspDecision` (or `CcDecision` / `RollDecision`) instance is **never** what `invoke_structured_or_freetext` returns.

As a consequence, the JSON-extraction fallback step described in all three sections — "If it fails, `invoke_structured_or_freetext` returns a raw string. The agent must then attempt JSON extraction from the raw string using `try: CspDecision.model_validate_json(raw)`" — conflates two distinct return cases:

1. Structured path succeeded → `render(result)` is returned. This string was produced by `render_fn` from an already-validated Pydantic instance. There is no JSON to extract; calling `model_validate_json` on a rendered markdown block will always fail.
2. Freetext fallback fired → `response.content` is returned. This string may contain JSON if the model produced it, and `model_validate_json` is the appropriate extraction attempt.

An implementer following the FSPEC will not be able to distinguish which path was taken from the return value alone (both return `str`). If they apply `model_validate_json` unconditionally on both paths, the rendered-markdown case will always produce the sentinel — suppressing successful structured results. If they skip JSON extraction on the assumption that a non-None return means structured success, they lose the freetext fallback recovery.

**Impact:** Medium. The agents' degradation contract — structured success → rendered string in state, structured failure + JSON extraction success → validated instance, structured failure + JSON extraction failure → sentinel — cannot be correctly implemented from the FSPEC as written without understanding the underlying `structured.py` behaviour. An implementer who reads only the FSPEC will write incorrect control flow for the structured-success branch.

**Suggested resolution:** Replace "a validated `CspDecision` instance is returned" with the accurate description: "`invoke_structured_or_freetext` always returns a `str`. On the structured path it returns the result of `render_fn(validated_instance)` (a formatted string for state storage). On the freetext fallback path it returns the LLM's raw string, which may contain JSON. The agent should apply `Schema.model_validate_json(raw)` only when the freetext path is taken." Since the agent cannot distinguish the paths from the return value alone, the recommended implementation pattern is to first try `model_validate_json` on the returned string; if that succeeds, use the parsed instance; if it fails, use the rendered string as a plain text result and record the sentinel `Schema(tradeable=False, rationale='Structured output failed — safe fallback applied.')` only when both the structured call and freetext-JSON-extraction fail. This pattern should be specified uniformly across all three agent sections and in the Business Rules.

---

## Summary

v0.3.0 fully resolves all six prior v2 findings. The two High findings (FSPEC-SE2-01, FSPEC-SE2-02) are addressed: the `bind_structured` / `invoke_structured_or_freetext` two-call pattern is now correct and complete in all three agent sections, and `"signal_processor"` is replaced by the new `"wheel_cycle_summary"` node with full specification. The two Medium findings (FSPEC-SE2-03, FSPEC-SE2-04) are resolved: the panel title conflict is closed with a dual-string solution, and all new `AgentState` fields are enumerated in FSPEC-WHEEL-07. Both Low findings (FSPEC-SE2-05, FSPEC-SE2-06, FSPEC-SE2-07) are closed with explicit answers.

One new Medium issue (FSPEC-SE3-01) is raised: the description of `invoke_structured_or_freetext`'s structured-success return value is incorrect in all three agent sections. The function always returns `str`, never a Pydantic instance, and the FSPEC's current phrasing will lead to incorrect control flow in the agent implementations unless corrected. The correction is a targeted wording change in three places and does not require restructuring any other part of the FSPEC.

The document is otherwise in excellent shape. No blocking issues remain. The correction in FSPEC-SE3-01 can be applied as a v0.3.1 patch concurrent with TSPEC authoring, as it does not change any agent behaviour — only the prose description of the invocation pattern.

---

## Approved Items

- **FSPEC-WHEEL-01 routing contract:** The corrected `route_to_vendor("method_name", ...)` call pattern, `TOOLS_CATEGORIES` registration rule, `"options_data"` category key, and error-catch contract at the tool-wrapper layer are accurate and implementable.
- **FSPEC-WHEEL-02 IV computation:** The injectable test seam, zero-variance guard, boundary annotations, strict less-than percentile formula, and output field table are all correct and testable.
- **FSPEC-WHEEL-03 suitability decision flow:** Criteria 1–5 are fully specified, all-criteria evaluation (no short-circuit) is stated, multi-failure `rejection_reason` concatenation is specified, and both prior open questions (near-the-money ±10% and midpoint DTE) are closed.
- **FSPEC-WHEEL-04 and FSPEC-WHEEL-05 deterministic filters, progressive relaxation, and yield formulas:** Financial formulas are correct. Relaxation order (C → B → A-fallback for CSP; D → C → fallback for CC), earnings hard block, and below-cost-basis branch are all unambiguous.
- **FSPEC-WHEEL-06 rule evaluation, priority order, and Rule 5 mechanism:** All five rules, priority order (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1), `"profit_capture"` aliasing, `WheelPosition.prior_analyst_bias` storage/update, and the six `Literal` trigger reason values are precisely specified.
- **FSPEC-WHEEL-07 phase state machine:** New `AgentState` fields table is complete and typed. Phase definitions, transition table, guard table, `WheelStateError` messages, and `route_wheel_phase()` return value enumeration are accurate. The `"wheel_cycle_summary"` node specification is clear and consistent with the rest of the FSPEC.
- **FSPEC-WHEEL-08 CLI display:** Dual-string solution (`"Wheel Suitability"` as panel title + `## WheelCandidateReport` as body header) cleanly satisfies both the FSPEC AC and REQ-SCREEN-03 AC1. Field layout, approval styling, and display guard are clearly specified.
- **FSPEC-WHEEL-09 options context injection:** Injection point location (after `{market_context}`, before role-assignment instruction), field lists for `CspDecision` and `CcDecision` context blocks, equity-mode suppression, and state field references are all closed and consistent with the `AgentState` table in FSPEC-WHEEL-07.
- **`bind_structured` / `invoke_structured_or_freetext` call pattern (construction and invocation steps):** Three-argument construction, `agent_name` snake_case identifiers, and the two-step invocation structure are now correctly specified. Subject only to the prose correction in FSPEC-SE3-01.
