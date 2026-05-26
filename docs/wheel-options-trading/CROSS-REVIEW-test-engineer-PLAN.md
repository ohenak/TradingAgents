# Cross-Review: test-engineer — PLAN

**Reviewer:** test-engineer
**Document reviewed:** docs/wheel-options-trading/PLAN-wheel-options-trading.md
**Date:** 2026-05-25
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Process | **TDD order violated in every batch.** Each batch contains exactly one test task and it is always the last task in the batch, depending on all preceding implementation tasks. Batch 1: B1-T7 depends on B1-T1 through B1-T6. Batch 2: B2-T6 depends on B2-T1 through B2-T5. Batch 3: B3-T6 depends on B3-T1 through B3-T5. Batch 4: B4-T6 depends on B4-T1 through B4-T5. The PLAN's own Section 4 states tests follow TSPEC §10.2 (three-layer fallback coverage), but no test task precedes any implementation task. Test-first order is never enforced. Implementers will write code before tests, removing the TDD safety net for all four phases. | Batches 1–4, all `Bx-T(last)` tasks |
| F-02 | Medium | Local | **`STRUCTURED_OUTPUT_SENTINEL` import-not-hardcode enforcement is not assigned to any test task.** ADR-WHEEL-04 (DECISIONS doc, Consequences section) is explicit: "Tests that assert on the sentinel `rationale` value must import `STRUCTURED_OUTPUT_SENTINEL` from `structured.py` rather than using a string literal." This requirement is acknowledged in the feature-level DoD (Section 11: "`STRUCTURED_OUTPUT_SENTINEL` is imported (never hardcoded) in all four agents and in CLI display") but it is not traceable to any test task. B3-T6 covers fallback result assertions but does not call out that tests must import the constant rather than hardcode the string. No task in B2-T6 enforces the constant exists and is the source-of-truth for all test assertions. Without an explicit test that imports `STRUCTURED_OUTPUT_SENTINEL` and compares it to the string literal, a future rename or typo in the constant will silently pass all tests. | Section 11 DoD; B2-T6; B3-T6; ADR-WHEEL-04 Consequences |
| F-03 | Low | Local | **B4-T6 equity-passthrough test is not marked as `@pytest.mark.integration`.** The PLAN Section 4 defines integration tests as those using canned fixtures with mocked LLM "may write to `tmp_path`". The equity-passthrough test (PROP-ROUTE-02, ADR-WHEEL-03 invariant) requires wiring together the full graph (`setup_graph`, `ConditionalLogic`, node registration) and asserting no options-layer nodes are visited. This is a cross-module integration boundary test — it must carry the `@pytest.mark.integration` marker so it is correctly excluded from the fast unit-test CI gate. B4-T6 does not specify this marker for the equity-passthrough test case. | B4-T6; Section 4 Test Strategy |
| F-04 | Low | Local | **`wheel_phase="screening"` routing test in B4-T6 does not assert the full screening path.** B4-T6 asserts `wheel_phase="screening"` routes to `first_analyst_node`, which matches the routing table. However, ADR-WHEEL-03 specifies the screening phase is `"screening"` → first analyst node (standard pipeline + WheelAnalyst + CspAgent). The test as described only checks the router's return value, not that the downstream WheelAnalyst → CspAgent edge is reached. A complete routing-path test for `"screening"` should assert that WheelAnalyst and CspAgent nodes are registered and reachable from the screening entry point. | B4-T6; ADR-WHEEL-03 Decision table |
| F-05 | Low | Local | **Theta_daily tolerance in Batch 1 DoD is inconsistent with the TSPEC header description.** The PLAN Batch 1 DoD states `Theta_daily ≈ −0.0314 ± 0.005`. TSPEC §2.1.3 "Expected values for unit test assertion" states `Theta_put_daily ≈ −0.0314` with `±0.005` tolerance, which is correct per the formula. However, the TSPEC preamble also mentions the Hull 10e value of `−0.0327`, creating a surface-level inconsistency that could confuse the B1-T7 implementer. The PLAN should explicitly note the `−0.0314` (formula-derived) value is authoritative and `−0.0327` is a Hull 10e table approximation with different inputs, matching the TSPEC §2.1.3 note. This is already resolved in the TSPEC but not surfaced prominently in the PLAN's Batch 1 DoD or B1-T7 description, risking the implementer asserting the wrong target. | Batch 1 DoD; B1-T7; TSPEC §2.1.3 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | F-01 (TDD order): Is the intent that agents within a batch should use a test-first sub-ordering — for example, B1-T7 split into a test-stub task preceding B1-T1, with implementation tasks depending on the stub? Or is the batch design intentionally implementation-first with tests as a final verification step? The answer determines whether the PLAN needs structural revision (separate test-stub and test-verify tasks per implementation task) or a clarifying note. |
| Q-02 | F-02 (Sentinel constant enforcement): Should B3-T6 be updated to include an explicit assertion that `STRUCTURED_OUTPUT_SENTINEL` is imported from `structured.py` in each of the four agent test files — for example, `assert agent_test.SENTINEL_USED == STRUCTURED_OUTPUT_SENTINEL` or a static-analysis check via `ast.parse`? Or is the intent that this is enforced by code review only (as stated for the `WheelPhase` write-convention in ADR-WHEEL-02)? |
| Q-03 | OI-07 (tool-calling wiring, PLAN Section 8): The PLAN recommends that options agents use "direct calls to the raw functions in the factory (not via ToolNode)". If this is adopted, the B3-T6 test descriptions should be updated to reflect that `tools_options` ToolNode is only wired for WheelAnalyst, not for CspAgent, CcAgent, or RollCheckAgent. Should the test task descriptions be updated to document which agents use ToolNode vs direct function calls? |

---

## Positive Observations

- Every batch has an explicit Definition of Done table that directly names the required test outputs (e.g., Batch 1 DoD calls out the BSM numeric verification test, zero-variance guard test, and all-unit-tests-pass with no network calls). This gives the implementer clear, measurable acceptance criteria.
- The 12 structured-output fallback test cases (PROP-FALLBACK-01 through PROP-FALLBACK-12) are correctly assigned to B3-T6 with explicit per-agent decomposition (3 scenarios × 4 agents), matching the ADR-WHEEL-04 test coverage mandate exactly.
- The equity-passthrough integration test (ADR-WHEEL-03 invariant, PROP-ROUTE-02) is explicitly tasked in B4-T6 with precise assertions: `wheel_phase=None` → first analyst node, no options nodes visited, output fields unchanged. This is the primary regression guard for LangGraph version bumps.
- The integer-sort regression test (PROP-POSN-01, ADR-WHEEL-05) is explicitly tasked in B2-T6 with precise inputs (cycle-10 and cycle-9 both present in `tmp_path`) and expected output (cycle-10 returned).
- The zero-variance sentinel disclosure test (ADR-WHEEL-01) is tasked in B1-T7 with the exact input (`iv_series=[0.20]*100`) and expected output string (`"IV range is flat — rank set to neutral 50"`), and appears in the Batch 1 DoD.
- Test seam parameters (`_spot_price`, `_risk_free_rate`, `_sigma` in B1-T7; `_position_loader` in B2-T6, B3-T6) are listed in both the implementation task descriptions and the corresponding test task, ensuring the seams are visible to the implementer and test author simultaneously.
- Section 3 (DECISIONS carry-forward notes for implementers) is a valuable addition: it collects all five ADR binding constraints with implementation-specific language, reducing the risk that implementers miss a decision constraint buried in the DECISIONS document.
- The `cycle_annualised_return_pct` discrepancy note (Section 9) provides the correct value (33.21%), the authoritative source (TSPEC §9.4), and a required code comment for the test, which is the correct pattern for carrying a known numeric correction into implementation.

---

## Recommendation

**Needs revision**

### What must change before approval

**F-01 (High urgency, TDD order):** The single-test-task-at-batch-end pattern must be addressed. The minimum-viable fix is to split each batch's test task into two tasks: (a) a *test-stub* task that creates the test file with failing tests (written before the implementation) and (b) a *test-verify* task placed after the implementation tasks that runs the tests and verifies they pass. Alternatively, interleave test tasks with implementation tasks so that each implementation task is preceded by its corresponding test stub task. The current structure will result in implementation-first development across all 23 production files.

**F-02 (Sentinel import enforcement):** Add an explicit test requirement to B3-T6 (or a dedicated sub-task) that asserts `STRUCTURED_OUTPUT_SENTINEL` is imported from `structured.py` in each agent test file and that the sentinel assertions use the imported constant, not a hardcoded string literal. This can be a simple static check (e.g., `ast.parse` on the test source) or an assertion on the module-level import, but it must be a named test task so it is not silently omitted.
