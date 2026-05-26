# Cross-Review: test-engineer — PLAN

**Reviewer:** test-engineer
**Document reviewed:** docs/wheel-options-trading/PLAN-wheel-options-trading.md
**Date:** 2026-05-25
**Iteration:** 2

---

## Prior Findings Resolution

### F-01 (Medium) — TDD ordering: Bx-T-STUB before implementation, Bx-T-VERIFY after

**Status: Resolved.**

Every batch now follows the explicit Red → Green → Refactor cycle. Each batch header states the TDD order (e.g., `B3-T-STUB → {B3-T1 … B3-T6 in parallel} → B3-T-VERIFY`). The `Bx-T-STUB` tasks are task #0 in each batch with dependency `Batch N-1` only (not on any intra-batch implementation task). The `Bx-T-VERIFY` tasks are the final task in each batch, depending on all implementation tasks. Section 5 now contains an explicit "TDD Ordering Rule (TE-F-01)" sub-section formalising this three-phase contract. The stub tasks include correct descriptions of "failing tests / bodies raise NotImplementedError" for the Red phase. Resolution confirmed.

### F-02 (Medium) — STRUCTURED_OUTPUT_SENTINEL import enforcement in B3-T-STUB

**Status: Resolved.**

B3-T-STUB now explicitly carries the "SENTINEL IMPORT REQUIREMENT (ADR-WHEEL-04)" block: "All test stubs that will assert on the sentinel value MUST include `from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL` at the top of the test file. No test file may use a hardcoded string literal for the sentinel value at any point (stub or verify)." This is also enforced in B3-T-VERIFY's DoD: "All sentinel assertions import the constant — no hardcoded string literals in any test file." Resolution confirmed.

### F-03 (Low) — `@pytest.mark.integration` on equity-passthrough test

**Status: Resolved.**

B4-T-STUB now includes `wheel_phase=None` → equity path with `@pytest.mark.integration` as one of the named test stubs. B4-T-VERIFY explicitly states: "**Equity-passthrough test** (`PROP-ROUTE-02`) carries `@pytest.mark.integration` (TE-F-03)". The Batch 4 DoD also states: "Equity-passthrough integration test passes, marked `@pytest.mark.integration`". Section 5 Test Strategy table now lists the equity-passthrough test as requiring `@pytest.mark.integration`. Resolution confirmed.

### F-04 (Low) — Full screening-path routing test covering WheelAnalyst + CspAgent reachability

**Status: Resolved.**

B4-T-STUB now includes a stub for `wheel_phase="screening"` that asserts both the router return value and that WheelAnalyst + CspAgent nodes are registered and reachable. B4-T-VERIFY explicitly states: "**Full screening-path test** asserts `wheel_phase="screening"` → `first_analyst_node` returned AND WheelAnalyst + CspAgent nodes are registered and reachable from the screening entry point (TE-F-04, ADR-WHEEL-03)". The Batch 4 DoD includes this criterion. Resolution confirmed.

### F-05 (Low) — Theta_daily tolerance discrepancy note

**Status: Resolved.**

B1-T-VERIFY now explicitly states: "`−0.0314` is formula-derived and authoritative — Hull 10e shows `−0.0327` due to different inputs, not a target." Batch 1 DoD also contains: "The `−0.0314` value is formula-derived and authoritative; Hull 10e Table 19.1's `−0.0327` uses different inputs and is not the implementation target." Resolution confirmed.

---

## New Additions Review

### B3-T6 — Past-context injection task (REQ-LIFE-05 AC3)

The new B3-T6 task adds `_build_options_context` extension for past-cycle performance data injection into `WheelAnalyst` and `CspAgent` prompts. The corresponding test file `tests/test_past_context_injection.py` is added to B3-T-STUB and B3-T-VERIFY. Reviewed from a testability perspective below.

### DEC-PLAN-01 — CC DTE Lower Bound (28 DTE)

DEC-PLAN-01 is testable: the decision resolves an ambiguity between REQ-TRADE-03 ("21–45 DTE") and TSPEC §8.1 (`recommended_dte_low = 28`). The PLAN correctly designates `recommended_dte_low = 28` as authoritative and points B3-T3 and the B3 DoD to enforce this via the `_filter_cc_candidates` unit test. The re-evaluation mechanism (REQ v0.3.0 patch) is well-defined. No testability concern.

### DEC-PLAN-02 — Phase Transitions Automated by Agents

DEC-PLAN-02 is testable: the six transition rows are deterministic (based on observable output fields like `CspDecision.tradeable`, `RollDecision.action`, `called_away`). B4-T-STUB lists test stubs for five of the six non-None phase transitions (`wheel_phase="screening"`, `"stock_owned"`, `"cc_open"` missing position, `"invalid_phase"`, `"cycle_complete"`). The `"csp_open"` routing branch is covered by the `WheelStateError` guard test. B4-T-VERIFY and the Batch 4 DoD require all routing branches to be tested. No testability concern.

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | **B3-T6 past-context injection lacks a negative / equity-passthrough test stub.** The `test_past_context_injection.py` file is named in B3-T-STUB but the stub description only mentions the multi-cycle positive scenario: `_build_options_context` output contains `cycle_pnl` and `cycle_annualised_return_pct` when `WheelPosition.cycle_history` contains a prior cycle. The equity-only path (`wheel_phase is None`, or `cycle_history` is empty / no prior cycle) is not named as a required test stub. REQ-LIFE-05 AC3 is the positive assertion only. However, the TSPEC §5.5 `_build_options_context` function explicitly returns `""` when no options state is present, and the B3 DoD does not include a named item for the zero-history path. Without an explicit negative test — asserting that `_build_options_context` returns no `Past Cycle Performance` section when `cycle_history` is empty or absent — the boundary between first cycle and subsequent cycle behaviour is unverified. A future regression where past-context is accidentally injected into the first cycle would not be caught. | B3-T-STUB description; B3-T-VERIFY; Batch 3 DoD |
| F-02 | Low | Local | **B3-T6 does not specify the injectable `_position_loader` test seam for `_build_options_context`.** B3-T3 (CcAgent) and B3-T4 (RollCheckAgent) both carry an explicit `_position_loader` injectable per ADR-WHEEL-05. B3-T6 extends `_build_options_context` to read `WheelPosition.cycle_history`, which also requires filesystem I/O. The B3-T6 task description states the function "reads `WheelPosition` via the same `_position_loader` injectable used by CcAgent and RollCheckAgent" — but the test stub description in B3-T-STUB does not list `test_past_context_injection.py` as requiring a `_position_loader` injectable. The Batch 3 DoD does not include an item confirming that past-context injection unit tests inject a `_position_loader` and do not write to the real `positions_dir`. Without this, implementers may rely on real filesystem access, violating ADR-WHEEL-05's unit test isolation invariant. | B3-T-STUB description; B3-T6 task description; ADR-WHEEL-05; Section 5 ADR test invariants table |
| F-03 | Low | Local | **B4-T-STUB does not name a test stub for the `csp_open` → `stock_owned` transition (DEC-PLAN-02, automated by RollCheckAgent).** The routing stubs listed in B4-T-STUB cover `wheel_phase` values `None`, `"cc_open"` (no-position guard), `"invalid_phase"`, `"screening"`, `"stock_owned"`, and `"cycle_complete"`. The transition from `"csp_open"` phase (RollCheckAgent detects assignment, sets `"stock_owned"`) is handled in B3-T4 (RollCheckAgent) but the corresponding graph-level integration routing test for `wheel_phase="csp_open"` is absent from B4-T-STUB. DEC-PLAN-02 lists `csp_open → stock_owned` as an automated transition; B4-T2 implements the routing for this branch; B4-T-VERIFY should confirm it. The omission creates a gap: the routing test table in B4-T-STUB describes the router's behaviour for six non-None phases (per DEC-PLAN-02 + TSPEC), but the `"csp_open"` routing branch (which returns `roll_check_agent`) is not explicitly named as a test stub. | B4-T-STUB description; DEC-PLAN-02 transitions table; B4-T2 description |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | B3-T6 states `_build_options_context` reads `WheelPosition` via the same `_position_loader` injectable used by CcAgent and RollCheckAgent. Should `_build_options_context` accept `_position_loader` as a keyword-only argument (mirroring the CcAgent and RollCheckAgent pattern), or will it obtain the loader from the agent's closure? The choice affects whether the test file can inject a mock loader without patching. |
| Q-02 | DEC-PLAN-02 states the `cycle_complete → None` transition is triggered by `wheel_cycle_summary` returning `{"wheel_phase": None}`. Should B4-T-STUB include a stub for `wheel_phase="cycle_complete"` routing to `wheel_cycle_summary` and assert the returned state contains `wheel_phase=None`? The current B4-T-STUB lists `"cycle_complete"` as a routing stub but B4-T-VERIFY and the Batch 4 DoD do not explicitly name the `None`-reset assertion as a required pass criterion. |

---

## Positive Observations

- All five prior TE findings (F-01 through F-05) are fully resolved with precise, verifiable language in the task descriptions, stub listings, verify task requirements, and batch DoD items. The resolution quality is high — each fix names the exact test assertion required, not just a general direction.
- The new TDD Ordering Rule section (Section 5, "TE-F-01") is a clean formalisation of the Red → Green → Refactor cycle as a batch-level contract. The batch headers now state the ordering explicitly, making it mechanically enforceable by the `se-implement` skill.
- The sentinel import requirement is propagated correctly to three separate enforcement points: B3-T-STUB (import at stub-time), B3-T-VERIFY (no hardcoded literals at verify-time), and the feature-level DoD (Section 12). This layered enforcement is the right pattern.
- DEC-PLAN-01 and DEC-PLAN-02 are well-structured decisions with observable test invariants. DEC-PLAN-01 maps directly to a named DoD item (`CcAgent _filter_cc_candidates uses recommended_dte_low = 28`). DEC-PLAN-02 maps directly to the B4-T-STUB routing stubs and the B4-T-VERIFY assertions.
- B3-T6 correctly identifies that the past-context injection test belongs to a dedicated file (`test_past_context_injection.py`) rather than being merged into `test_risk_debate_injection.py`, keeping the two cross-cutting concerns (debate injection vs. lifecycle history injection) independently testable.
- The re-evaluation triggers in DEC-PLAN-01 and DEC-PLAN-02 are observable from tests or CI: DEC-PLAN-01's trigger is a REQ-level patch (external signal); DEC-PLAN-02's trigger would be a change in the `wheel_phase` assignment semantics (testable via the routing invariants in B4-T-VERIFY).
- The PREREQUISITE GATE (Section 2) is a sound pre-condition for test authoring: it prevents PROPERTIES authors from writing tests against REQ v0.2.0 values that have known numeric errors (33.25% vs 33.21%) or missing config keys.

---

## Recommendation

**Needs revision**

### What must change before approval

**F-01 (Medium — must fix):** B3-T-STUB must be updated to name an explicit negative test stub for `_build_options_context` in `tests/test_past_context_injection.py`: when `WheelPosition.cycle_history` is empty (or `WheelPosition` is absent), the function returns a string containing no `Past Cycle Performance` section. The Batch 3 DoD must include a corresponding item: "Past-context injection negative test passes: `_build_options_context` returns no past-cycle section when `cycle_history` is empty or position is absent (first-cycle / equity-only path)." This is required to close the boundary gap for REQ-LIFE-05 AC3 — without a negative assertion, a regression that injects stale or zero-valued past-context into first-cycle prompts would be undetected.

**F-02 (Low — address before B3-T-STUB authoring):** Add to the B3-T-STUB description: "`test_past_context_injection.py` stubs inject a `_position_loader` callable (not the real filesystem loader) per ADR-WHEEL-05." Add to the Batch 3 DoD: "Past-context injection unit tests inject `_position_loader`; no test in `test_past_context_injection.py` writes to the real `positions_dir`."

**F-03 (Low — address before B4-T-STUB authoring):** Add `wheel_phase="csp_open"` → `roll_check_agent` as an explicit named test stub in the B4-T-STUB routing test list, and add a corresponding pass criterion to B4-T-VERIFY and the Batch 4 DoD.
