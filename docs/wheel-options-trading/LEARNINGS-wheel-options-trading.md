# LEARNINGS — wheel-options-trading

| Field | Detail |
|---|---|
| Feature | wheel-options-trading |
| REQ | docs/wheel-options-trading/REQ-wheel-options-trading.md |
| Date Completed | 2026-05-26 |
| Total Iterations | REQ: 2, FSPEC: 3, TSPEC: 2, DECISIONS: 3, PLAN: 3, PROPERTIES: 2, IMPL: 3 |
| Upstream | REQ → FSPEC → TSPEC → DECISIONS → PLAN → PROPERTIES → IMPL |
| Harvested from | CROSS-REVIEW-software-engineer-REQ.md, CROSS-REVIEW-test-engineer-REQ.md, CROSS-REVIEW-software-engineer-REQ-v2.md, CROSS-REVIEW-test-engineer-REQ-v2.md, CROSS-REVIEW-software-engineer-FSPEC.md, CROSS-REVIEW-test-engineer-FSPEC.md, CROSS-REVIEW-software-engineer-FSPEC-v2.md, CROSS-REVIEW-test-engineer-FSPEC-v2.md, CROSS-REVIEW-software-engineer-FSPEC-v3.md, CROSS-REVIEW-product-manager-TSPEC.md, CROSS-REVIEW-test-engineer-TSPEC.md, CROSS-REVIEW-product-manager-TSPEC-v2.md, CROSS-REVIEW-test-engineer-TSPEC-v2.md, CROSS-REVIEW-product-manager-DECISIONS.md, CROSS-REVIEW-test-engineer-DECISIONS.md, CROSS-REVIEW-product-manager-DECISIONS-v2.md, CROSS-REVIEW-test-engineer-DECISIONS-v2.md, CROSS-REVIEW-product-manager-DECISIONS-v3.md, CROSS-REVIEW-test-engineer-DECISIONS-v3.md, CROSS-REVIEW-product-manager-PLAN.md, CROSS-REVIEW-test-engineer-PLAN.md, CROSS-REVIEW-product-manager-PLAN-v2.md, CROSS-REVIEW-test-engineer-PLAN-v2.md, CROSS-REVIEW-product-manager-PLAN-v3.md, CROSS-REVIEW-test-engineer-PLAN-v3.md, CROSS-REVIEW-product-manager-PROPERTIES.md, CROSS-REVIEW-software-engineer-PROPERTIES.md, CROSS-REVIEW-product-manager-PROPERTIES-v2.md, CROSS-REVIEW-software-engineer-PROPERTIES-v2.md, CROSS-REVIEW-product-manager-IMPLEMENTATION.md, CROSS-REVIEW-test-engineer-IMPLEMENTATION.md, CROSS-REVIEW-product-manager-IMPLEMENTATION-v2.md, CROSS-REVIEW-test-engineer-IMPLEMENTATION-v2.md, CROSS-REVIEW-product-manager-IMPLEMENTATION-v3.md, CROSS-REVIEW-test-engineer-IMPLEMENTATION-v3.md |

---

## 1. Non-Convergences

Review loops that required three or more iterations to reach approval.

| Phase | Reviewer | Issue | Resolution | Iteration Count |
|---|---|---|---|---|
| FSPEC | software-engineer | `route_to_vendor` signature wrong; `structured.py` fallback paths missing; Rule 5 lacked state-access mechanism; `bind_structured` shown with wrong arg count | Corrected in v2 (signatures, node names); v3 introduced the key insight that `invoke_structured_or_freetext` always returns `str` not Schema | 3 |
| DECISIONS | test-engineer | ADR-WHEEL-04 (3-level LLM fallback) lacked test requirements for level-2 freetext-valid-JSON scenario; `STRUCTURED_OUTPUT_SENTINEL` needed module-level constant and import enforcement test | Added level-2 test scenario and `test_sentinel_enforcement.py` using `ast.parse`/`ast.walk`; approved v3 with 3 Low residuals | 3 |
| PLAN | product-manager | REQ v0.3.0 not produced before PLAN; CC DTE ambiguity unresolved in FSPEC; `past_context` injection (REQ-LIFE-05 AC3) untraced in task graph | v2 added REQ v0.3.0, resolved DTE via FSPEC amendment, added traceability to AC3 | 3 |
| PLAN | test-engineer | TDD ordering violated in every batch (single test task always last); `STRUCTURED_OUTPUT_SENTINEL` import enforcement absent from all test tasks; negative `_build_options_context` test stub missing in v2 | v3 restructured batches with `Bx-T-STUB` before implementation tasks and `Bx-T-VERIFY` after | 3 |
| IMPL | product-manager | Rule 5 returned ROLL instead of CLOSE (AC4 defect — tests passed because they mirrored defective code); `_build_options_context` fully implemented but never called (dead code); `csp_agent` wired as orphan node | v2 fixed Rule 5 + wired `_build_options_context`; v3 confirmed all P0/P1 satisfied | 3 |

---

## 2. Cross-Feature Patterns

Findings with Scope = Cross-Feature that point to constraints applying beyond this feature.

| Finding | Suggested Promotion Target |
|---|---|
| **[DOMAIN: api-data] yfinance provides no historical IV time series.** `option_chain()` is a point-in-time snapshot. Any feature needing IV Rank/Percentile must use a realised-volatility proxy (30-day rolling std of log returns). Surfacing this as "IV Rank" without disclosure is misleading; document the proxy in both ADR and UI copy. Discovered at REQ phase (SEV-REVIEW-01) and formalised in ADR-WHEEL-02. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add yfinance IV limitation; `docs/_decisions/` — reference ADR-WHEEL-02 pattern for future options features |
| **[DOMAIN: api-data] `^IRX` (risk-free rate) returns percentage not decimal.** `yfinance.Ticker("^IRX").history()` returns e.g. `5.25`, not `0.0525`. Any BSM or derivative formula must divide by 100. Also: `^IRX` can return an empty frame; a static fallback rate is required. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add `^IRX` percentage-not-decimal note and empty-frame guard requirement |
| **[DOMAIN: langgraph] `AgentState` fields that hold domain enums must be typed `Optional[str]`, not `Optional[DomainEnum]`.** LangGraph's JSON checkpointer cannot serialise raw Pydantic Enum instances stored in state. The Enum itself must be defined as `class MyEnum(str, Enum)` with lowercase string values; the TypedDict field must be `Optional[str]`. Discovered at REQ phase (SEV-REVIEW-02) and reinforced throughout FSPEC/TSPEC reviews. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add LangGraph state serialisation rules: (1) `(str, Enum)` pattern; (2) TypedDict fields as `Optional[str]` not `Optional[Enum]`; (3) no raw Pydantic model instances in state |
| **[DOMAIN: langgraph] `tuple` fields are not JSON-serialisable in LangGraph state.** Pydantic model fields typed as `tuple[float, float]` cause checkpointer failures. Use `list[float]` with `Field(min_length=2, max_length=2)` instead. Discovered at REQ phase (SEV-REVIEW-05). | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add: "No tuple fields in LangGraph-persisted Pydantic schemas; use bounded list[float]" |
| **[DOMAIN: llm-structured-output] `invoke_structured_or_freetext` always returns `str`, never a Pydantic instance.** The `structured.py` wrapper contract: `bind_structured(llm, Schema, agent_name)` takes three arguments; `invoke_structured_or_freetext(bound_llm, messages, Schema)` returns `str`. The calling agent is responsible for `Schema.model_validate_json(result)`. Any agent that assigns the return value to a typed Pydantic variable without `model_validate_json` will fail at runtime. Discovered at FSPEC v3 (FSPEC-SE3-01). | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add structured-output invocation contract; update LLM-agent authoring guidelines |
| **[DOMAIN: llm-structured-output] `bind_structured(llm, Schema, agent_name)` takes three arguments.** FSPEC v1/v2 showed only two — omitting the `agent_name` string caused binding failures. This is a silent API contract that must be enforced by code example in any authoring guide. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add `bind_structured` 3-arg signature note |
| **[DOMAIN: llm-structured-output] `STRUCTURED_OUTPUT_SENTINEL` must be a module-level constant, imported everywhere, never hardcoded.** Hardcoding the sentinel string in tests or agents breaks when the constant changes. Enforcement: `test_sentinel_enforcement.py` using `ast.parse`/`ast.walk` to assert no string literal matches the sentinel value across all agent modules. This pattern should be required for every feature that uses the 3-level fallback. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add sentinel import-enforcement requirement; add `ast.parse`/`ast.walk` enforcement test pattern to test authoring guide |
| **[DOMAIN: pdlc-process] TSPEC default values that differ from REQ §7 must produce a REQ amendment, not a silent override.** `near_the_money_pct` (TSPEC: 0.10, REQ: 0.05) and `options_lookforward_days` (TSPEC: 90, REQ: 45) diverged silently — TSPEC comment labelled them "TSPEC extensions" but REQ §7 had already specified them with different values. This propagated into implementation bugs caught only at IMPL review. The rule: any TSPEC default that differs from an existing REQ default must trigger a REQ amendment at TSPEC time, not a comment. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — add: "TSPEC defaults diverging from REQ §7 require a REQ amendment, not a TSPEC comment"; update TSPEC review checklist |

---

## 3. Rejected Proposals

Things considered and explicitly not done, where the reason matters for future work.

| Proposal | Rejected By | Rationale | Reusable for future features? |
|---|---|---|---|
| Use `^IRX` live rate with no fallback | software-engineer (REQ review) | `^IRX` can return empty frame; BSM formula cannot accept NaN risk-free rate; static fallback (e.g. 0.05) required | Yes — any feature using `^IRX` must include this fallback |
| Store `WheelPhase` as `Optional[WheelPhase]` in `AgentState` TypedDict | software-engineer (REQ review) | LangGraph JSON checkpointer cannot serialise raw Enum in state; must use `Optional[str]` | Yes — applies to all future LangGraph state fields holding domain enums |
| Use `tuple[float, float]` for IV range/bounds in Pydantic schemas | software-engineer (REQ review) | Not JSON-serialisable in LangGraph checkpointer | Yes — use `list[float]` with `Field(min_length=2, max_length=2)` |
| Real IV rank from historical option chain data via yfinance | ADR-WHEEL-02 (DECISIONS phase) | yfinance `option_chain()` is a snapshot; no historical series available without paid data vendor | Yes — document in data-layer constraints for any options feature |
| Full LangGraph compiled-graph integration test for equity passthrough (PROP-ROUTE-01/09) in v0.3.0 | test-engineer (IMPL v2/v3) | LangGraph integration harness not yet available; deferred to GAP-06 in PROPERTIES §10 with PROP-ROUTE-01-INT placeholder | Yes — when LangGraph harness is available, activate deferred integration property tests |
| Assert `PROP-SCREEN-13` (wheel_analyst node absent when not in selected_analysts) via compiled graph | test-engineer (IMPL v3) | Same harness gap as GAP-06; Low severity because routing is covered structurally | Yes — add alongside PROP-ROUTE-01-INT when harness is available |

---

## 4. Process Learnings

Signals about how the workflow should evolve, plus domain-specific rules derived from this feature.

### [DOMAIN: pdlc-process] TDD ordering must be enforced at PLAN level, not left to batch authors.

**What was discovered:** Every PLAN v1 batch placed the single test task last, after all implementation tasks. This is the opposite of TDD: implementation ran without a failing test gate, and integration gaps (PROP-TRADE-08/09) were not caught until late IMPL reviews.

**Why it matters:** A test task placed last is a QA formality, not a gate. When the test is written after the implementation, it tends to test the implementation as-built rather than the requirement as-specified — this is exactly how the Rule 5 ROLL/CLOSE defect and the `_build_options_context` dead-code issue survived to IMPL v2.

**Rule for future features:** Each batch in the PLAN must follow the structure: `Bx-T-STUB` (write failing tests first) → implementation tasks → `Bx-T-VERIFY` (confirm all tests pass). The PLAN reviewer must reject any batch that places the test task after implementation tasks.

---

### [DOMAIN: pdlc-process] Dead-code risk: PLAN must explicitly name call sites for every utility function.

**What was discovered:** `_build_options_context` was fully and correctly implemented in `agent_utils.py` but was never called by the three risk debate agents or the Portfolio Manager (REQ-TRADE-05). The PLAN listed a task to implement the function but did not list the four call sites (aggressive_debator, conservative_debator, neutral_debator, portfolio_manager) as explicit sub-tasks. The dead-code defect survived to IMPL v2 (first PM review to catch it).

**Why it matters:** A utility function with no call sites satisfies its implementation task but not its requirement. The gap is invisible to unit tests because the function's own tests pass.

**Rule for future features:** When the PLAN includes a task to implement a utility/helper, it must include a separate sub-task or checklist item naming every call site that must invoke it. PROPERTIES should include a property asserting the function is reachable from the calling agents (not just that it returns correct output in isolation).

---

### [DOMAIN: pdlc-process] Orphan node risk: graph wiring must be verified as a PLAN-level checklist item.

**What was discovered:** `csp_agent` was implemented and unit-tested but had no outgoing graph edge — it was an orphan node. The graph-wiring task in the PLAN did not enumerate every node's required edges. Caught only at IMPL review (F-04).

**Why it matters:** LangGraph silently accepts an orphan node; it simply becomes a dead end. No runtime error surfaces this. Unit tests of the node function pass normally. Only a graph-structure inspection or an end-to-end flow test reveals the missing edge.

**Rule for future features:** The PLAN must include an explicit graph-wiring checklist that enumerates: for each node, the outgoing edge(s) and the conditions/predicates that route to them. The PROPERTIES document should include a PROP-ROUTE-* property for each node asserting reachability from the graph entry point.

---

### [DOMAIN: pdlc-process] Late-cycle codebase review (PM at IMPL) catches the most severe integration defects.

**What was discovered:** The two most severe IMPL findings — Rule 5 returning ROLL instead of CLOSE (AC4 defect), and `csp_agent` as orphan node — were both caught by the PM codebase review at IMPL v1, not by unit tests. The unit tests passed because they tested the defective implementation, not the requirement. The `_build_options_context` dead-code defect was caught at IMPL v2.

**Why it matters:** Tests can only catch defects that the test author anticipated. When tests are written after implementation (or written to match implementation rather than REQ), they validate the code not the requirement. The IMPL codebase review provides a human-level requirement-vs-implementation comparison that automated tests cannot substitute for.

**Rule for future features:** The PM and SE IMPL cross-reviews should explicitly check: (1) for each REQ acceptance criterion, trace to the implementation line that satisfies it; (2) for each utility function, verify at least one call site exists in the production path; (3) for each LangGraph node, verify at least one outgoing edge connects it to the downstream flow or END.

---

### [DOMAIN: pdlc-process] Test authors must write tests against the REQ, not the implementation.

**What was discovered:** At IMPL v2, `test_rule5_beats_rule2` and `test_rule5_beats_rule1` both asserted `action == "ROLL"` — matching the defective implementation. All 512 tests passed. The defect was invisible to CI. The PM caught it only by reading `_resolve_priority` against REQ-LIFE-03 AC4.

**Why it matters:** A test suite that mirrors a defective implementation provides false confidence. This is the canonical failure mode of "test after" workflows. It is not merely a process inefficiency — it actively hides correctness bugs.

**Rule for future features:** Test stubs (`Bx-T-STUB`) must be written from the REQ acceptance criteria, with the expected value sourced from the REQ, before the implementation exists. Test reviewers should audit at least the P0 ACs by comparing test assertions against REQ text, not against implementation source.

---

### [DOMAIN: testing] Boundary tests must use values that make the boundary condition reachable.

**What was discovered:** `test_rule4_boundary_exclusive_at_0_10` used `earnings_within_cycle=False`, making Rule 4 unreachable regardless of delta value. The assertion `rule4 is False` passed vacuously — it would have passed even if the deep-OTM threshold were wrong. Caught at IMPL v1 (F-04). Also: PROP-LIFE-10 in the PROPERTIES document had an inversion error (stated `abs_delta == 0.10` fires Rule 4; implementation correctly uses `abs_delta < 0.10`), which was only caught because the boundary test was audited.

**Why it matters:** Vacuous boundary tests are worse than no test — they signal that the boundary is covered when it is not. The inversion in the spec went undetected for multiple phases because no test was forcing it to be correct.

**Rule for future features:** Boundary tests for compound conditions must ensure every required condition is satisfied simultaneously. PROPERTIES reviewers should check boundary test parameters against the property's required inputs — a boundary test that cannot exercise the boundary is a finding.

---

### [DOMAIN: testing] Integer sort is required for any numbered file pattern where N >= 10.

**What was discovered:** `load_latest_open_position` used lexicographic sort on cycle filenames. Lexicographic order puts `cycle-9` after `cycle-10` (because "9" > "1"). The bug was identified at TSPEC review (TE-TSPEC-04) and a regression test `test_integer_sort_regression_cycle_10_over_cycle_9` was added to `test_wheel_position.py`.

**Why it matters:** This is a silent data corruption bug — the wrong position file is loaded, and no error is raised. It only manifests when the cycle count exceeds 9.

**Rule for future features:** Any file loading that relies on a numeric suffix in the filename must use integer sort: `key=lambda p: int(p.stem.rsplit("-cycle-", 1)[-1])` or equivalent. This must be specified in the TSPEC and have an explicit regression test asserting that cycle-10 sorts after cycle-9.

---

### [DOMAIN: testing] Injectable test seams for every external dependency must be specified at TSPEC time, not discovered at IMPL time.

**What was discovered:** Several seams were missing at TSPEC time and required remediation: `get_options_greeks` had no injectable test seam (TE-TSPEC-01); `create_roll_check_agent` and `ConditionalLogic._load_position` lacked an injectable position loader (TE-TSPEC-06-RESIDUAL). The seam pattern (`iv_series`, `_spot_price`, `_risk_free_rate`, `_sigma`, `_position_loader`, `_earnings_date`, `_front_month_expiry`) was retrofitted rather than designed in.

**Why it matters:** A function that cannot be tested without network access or filesystem side effects cannot be unit-tested. The seam gap means integration tests are required where unit tests would suffice, increasing test fragility and CI cost.

**Rule for future features:** The TSPEC must enumerate every external dependency (network call, filesystem read, LLM invocation, current-time call) and specify the injectable parameter name for each. The test-engineer TSPEC reviewer must verify completeness of the seam table before approving.

---

### [DOMAIN: options-trading] Progressive relaxation branches must have explicit acceptance criteria in the REQ.

**What was discovered:** The CSP filter pipeline has two progressive relaxation paths (`yield_filter_relaxed`, `earnings_filter_relaxed`). These paths had no ACs in the REQ (FSPEC-TE-08), no PROPERTIES entries until v2, and were not tested at integration level until the test-engineer raised PROP-SCREEN-10/11 for explicit inclusion.

**Why it matters:** A relaxation branch that is untested effectively does not exist. If the primary filter rejects all candidates, the fallback path silently fails to produce any recommendation — a correctness bug that is invisible without end-to-end coverage.

**Rule for future features:** Any multi-path filter or fallback pipeline must have explicit ACs in the REQ for each branch, including the relaxed branch. PROPERTIES must include at least one property per branch asserting the correct output when the primary path is exhausted.

---

### [DOMAIN: options-trading] Rule definitions with multiple sub-cases must explicitly name each sub-case with its output action.

**What was discovered:** Rule 3 (`breach_rule`) had two sub-cases: `breach_rule_roll → ROLL` (current value >= 50% of premium) and `breach_rule_close → CLOSE` (current value < 50% of premium). The FSPEC originally described only the roll sub-case. The LLM prompt at IMPL v2 also described only the roll sub-case (FSPEC-SE v2, PM F-NEW-03). This meant the LLM-guided output path could not produce the correct CLOSE action for deep-loss breach.

**Why it matters:** In the 3-level fallback architecture, the LLM prompt is the primary path. An incomplete prompt produces wrong output that survives Layer 1 validation because the schema is valid — only the action field is wrong. The deterministic override catches it, but that reduces the 3-level fallback to effectively 1-level for this rule.

**Rule for future features:** Each rule in a decision agent must name every output action it can produce, the condition that triggers each, and the exact `trigger_reason` literal. The REQ must enumerate the `trigger_reason` Literal set; the LLM prompt must match the REQ sub-cases; the PROPERTIES must have a test for each sub-case.

---

### [DOMAIN: pdlc-process] Config default deviations require a bidirectional update (TSPEC + REQ amendment), not a comment.

**What was discovered:** `near_the_money_pct` and `options_lookforward_days` appeared in REQ §7 with defaults 0.05/45. The TSPEC used 0.10/90 with an inline comment labelling them "TSPEC additions." But they were not additions — they already existed in REQ with different values. This caused a three-way contradiction (REQ / TSPEC / implementation) that was masked by weak tests (no exact-value assertion). Caught at IMPL v1 (F-01, F-02) as a High finding.

**Why it matters:** Silent overrides of REQ defaults produce bugs that are invisible until implementation review. The weak-test masking pattern (assert type only, not value) made the gap undetectable by CI.

**Rule for future features:** (1) If the TSPEC introduces a config key not in the REQ, add it to REQ §7 in the same PR. (2) If the TSPEC changes an existing REQ default, produce a REQ amendment; do not comment inline. (3) Config default tests must assert exact values, not just presence or type.

---

## 5. Open Items for Consolidation

Candidates for promotion that this harvest is not authorised to promote autonomously.

| Item | Target location | Priority | Notes |
|---|---|---|---|
| yfinance historical IV limitation (realised-vol proxy required) | `docs/_constraints/DOMAIN-CONSTRAINTS.md` | High | Any future options or volatility feature hitting yfinance will rediscover this. Should be a named constraint so SE reviewers can catch it at REQ phase. |
| `^IRX` percentage-not-decimal bug + empty-frame fallback | `docs/_constraints/DOMAIN-CONSTRAINTS.md` | High | Silent arithmetic error if not guarded. |
| LangGraph state serialisation rules: `(str, Enum)`, `Optional[str]` TypedDict fields, no Pydantic instances, no tuple fields | `docs/_constraints/DOMAIN-CONSTRAINTS.md` | High | Will affect every future LangGraph feature that models domain enums or complex types. |
| `structured.py` invocation contract: `bind_structured(llm, Schema, agent_name)` + `invoke_structured_or_freetext` returns `str`; caller must call `model_validate_json` | `docs/_constraints/DOMAIN-CONSTRAINTS.md` or LLM-agent authoring guide | High | Silent runtime failure if caller assigns return value as Pydantic instance. |
| `STRUCTURED_OUTPUT_SENTINEL` import-enforcement test pattern (`ast.parse`/`ast.walk`) | LLM-agent authoring guide or test templates | Medium | Reusable for any feature using the 3-level fallback. |
| TDD ordering enforcement: `Bx-T-STUB` → implementation → `Bx-T-VERIFY` | PLAN review checklist / `orchestrate-dev` PLAN phase guidelines | High | Structural rule that prevents the "tests mirror defective implementation" failure mode. |
| Graph wiring checklist (enumerate every node's outgoing edges in PLAN) | PLAN review checklist / PROPERTIES authoring guide | High | Orphan-node bug is silent at unit-test level and only caught by codebase review or graph-structure test. |
| PLAN must name all call sites for each utility function | PLAN review checklist | Medium | Prevents dead-code defects for utility functions implemented but never wired. |
| Integer sort required for N-indexed file patterns | `docs/_constraints/DOMAIN-CONSTRAINTS.md` or file-I/O authoring guide | Medium | Silent data corruption at N >= 10. |
| TSPEC default deviations from REQ §7 require REQ amendment | TSPEC review checklist | Medium | Prevents three-way config contradictions masked by weak tests. |
| Injectable test seam table required at TSPEC time for all external dependencies | TSPEC authoring guide / test-engineer TSPEC review checklist | Medium | Seams retrofitted at IMPL time are more disruptive and less complete. |
| Progressive relaxation branches must have explicit REQ ACs and PROPERTIES entries | REQ authoring guide / PROPERTIES review checklist | Medium | Silent fallback-path failures are undetectable without per-branch coverage. |
