# Cross-Review: test-engineer — PLAN

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/PLAN-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | Task 2.7 (`BatchTickerRecord` dataclass) has `—` in the Test File column and the note "no test — tested implicitly by Phase 3". This violates TDD: production code must be preceded by a failing test. Phase 3 tests (3.1) come after task 2.7 in the plan, so the dataclass exists without a test from tasks 2.1 through 2.7. Fix: add a task 2.7a — "Write failing test for `BatchTickerRecord` field types" in `tests/test_build_batch_summary.py` (constructing a `BatchTickerRecord` with known fields and asserting field access). This 3-line test satisfies TDD without adding a new test file. | Phase 2, task 2.7 |
| F-02 | Low | Local | Task 3.6 (update `get_ticker()` prompt text) is listed before task 3.7 (write failing tests for `analyze` command). This puts an implementation task before its test. Fix: swap order — 3.6 should become 3.7, and the current 3.7 becomes 3.6. The test for the new prompt text (e.g., assert "comma-separated" in CliRunner output) should be written as a failing test before the prompt text is changed. | Phase 3, tasks 3.6–3.7 |

---

## Questions

None.

---

## Positive Observations

- TDD order is correctly enforced for all other task groups: 1.1 (test) → 1.2 (impl) → 1.3 (refactor); 1.4 → 1.5; 1.6 → 1.7 → 1.8; 2.1 → 2.2 → 2.3; 2.4 → 2.5 → 2.6; 2.8 → 2.9 → 2.10; 3.1 → 3.2/3.3 → 3.4 → 3.5.
- Integration test boundary coverage is sound: `test_batch_run_loop.py` covers the CLI→library boundary with mocked `propagate`; `test_analyze_command_batch.py` covers the CLI command dispatch; `test_regression_single_ticker.py` covers the unchanged single-ticker path.
- The `cli.batch.Live` no-op patch requirement is carried from the TSPEC into the PLAN (task 3.1 description), ensuring the headless-pytest issue is addressed at the plan level.
- Phase exit criteria are precise and verifiable: specific test files are named, and "full test suite passes" is stated at Phase 3 exit.
- Definition of Done includes the boundary check (`tradingagents/` imports nothing from `cli/`) — this is directly testable as a module-level import assertion.
- The 4-phase structure correctly isolates the most complex refactoring (Phase 3) from the testable pure functions (Phase 2), minimising integration risk.

---

## Recommendation

**Needs revision**

> F-01 (Medium): task 2.7 must have a preceding test task added (2.7a). F-02 (Low): tasks 3.6 and 3.7 must be swapped to restore TDD order. Both are small, mechanical fixes.
