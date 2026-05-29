# PLAN — Multi-Ticker Sequential Analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | SE-Author (Claude Code) |
| **Version** | 0.2.0 |
| **Created** | 2026-05-29 |
| **Upstream** | REQ → FSPEC → TSPEC → DECISIONS → **PLAN** |
| **Downstream** | PROPERTIES, IMPL |
| **Cross-Reviews** | — |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

---

## Summary

Add multi-ticker sequential analysis to TradingAgents:
- `--tickers` CLI flag and CSV prompt input for batch mode
- Sequential per-ticker execution loop with error isolation
- Post-run summary table with wheel/standard mode decision extraction
- `propagate_many()` Python API method
- Underlying pure functions and types extracted for testability

Four phases ordered by dependency. Each phase opens with failing tests (🔴) before any implementation.

---

## Status Key

| Symbol | Meaning |
|---|---|
| ⬚ | Not Started |
| 🔴 | Red — test written, failing |
| 🟢 | Green — minimum implementation passes test |
| 🔵 | Refactored — clean, all tests pass |
| ✅ | Done — merged, CI green |

---

## Phase 1 — Library Layer

**Scope:** Pure library additions with no CLI dependencies. All new; no existing code modified except `tradingagents/dataflows/utils.py` and `tradingagents/graph/trading_graph.py`.

**Dependencies:** None.

| # | Task | Test File | Source File | Status |
|---|---|---|---|---|
| 1.1 | Write failing tests for `_detect_asset_type()` (5 cases + CRYPTO_SUFFIXES sync) | `tests/test_detect_asset_type_internal.py` | — | ⬚ |
| 1.2 | Implement `CRYPTO_SUFFIXES` constant and `_detect_asset_type()` in `tradingagents/dataflows/utils.py` | `tests/test_detect_asset_type_internal.py` | `tradingagents/dataflows/utils.py` | ⬚ |
| 1.3 | Refactor `_detect_asset_type()` | `tests/test_detect_asset_type_internal.py` | `tradingagents/dataflows/utils.py` | ⬚ |
| 1.4 | Write failing tests for `BatchTickerResult` dataclass (field types, None defaults) | `tests/test_propagate_many.py` | — | ⬚ |
| 1.5 | Implement `BatchTickerResult` dataclass in `tradingagents/graph/batch.py` | `tests/test_propagate_many.py` | `tradingagents/graph/batch.py` | ⬚ |
| 1.6 | Write failing tests for `propagate_many()` (all 7 cases: empty, all-succeed, one-fail, asset_types mismatch, asset_types=None detection, explicit override, mixed explicit, KI propagation) | `tests/test_propagate_many.py` | — | ⬚ |
| 1.7 | Implement `propagate_many()` on `TradingAgentsGraph` | `tests/test_propagate_many.py` | `tradingagents/graph/trading_graph.py` | ⬚ |
| 1.8 | Refactor `propagate_many()` | `tests/test_propagate_many.py` | `tradingagents/graph/trading_graph.py` | ⬚ |

**Phase 1 exit criteria:** All `tests/test_detect_asset_type_internal.py` and `tests/test_propagate_many.py` tests green. No CLI files touched.

---

## Phase 2 — CLI Pure Functions

**Scope:** Pure functions and a new data type in the CLI layer. No I/O, no side effects, fully unit-testable.

**Dependencies:** Phase 1 complete (imports `BatchTickerRecord` shape is defined here for TSPEC clarity, but `cli/batch.py` itself has no library dependencies beyond standard library).

| # | Task | Test File | Source File | Status |
|---|---|---|---|---|
| 2.1 | Write failing tests for `parse_tickers_input()` (5 cases) | `tests/test_parse_tickers_input.py` | — | ⬚ |
| 2.2 | Implement `parse_tickers_input()` in `cli/utils.py` | `tests/test_parse_tickers_input.py` | `cli/utils.py` | ⬚ |
| 2.3 | Refactor `parse_tickers_input()` | `tests/test_parse_tickers_input.py` | `cli/utils.py` | ⬚ |
| 2.4 | Write failing tests for `MessageBuffer.reset()` (2 cases: post-patch reset, fresh-buffer no-op) | `tests/test_message_buffer_reset.py` | — | ⬚ |
| 2.5 | Implement `MessageBuffer.reset()` in `cli/main.py` using `__dict__.pop` pattern | `tests/test_message_buffer_reset.py` | `cli/main.py` | ⬚ |
| 2.6 | Refactor `MessageBuffer.reset()` | `tests/test_message_buffer_reset.py` | `cli/main.py` | ⬚ |
| 2.7 | Write failing test for `BatchTickerRecord` field types (construct with ticker/final_state/decision; assert field access) | `tests/test_build_batch_summary.py` | — | ⬚ |
| 2.8 | Implement `BatchTickerRecord` dataclass in `cli/batch.py` | `tests/test_build_batch_summary.py` | `cli/batch.py` | ⬚ |
| 2.9 | Write failing tests for `build_batch_summary()` (11 cases: all-success-standard, one-failed, all-failed, all-success-exit-0, wheel-approved, wheel-rejected, wheel-None, wheel-malformed-JSON, standard-first-line-skip-blanks, 75-char-truncation, row-order-preserved) | `tests/test_build_batch_summary.py` | — | ⬚ |
| 2.10 | Implement `build_batch_summary()` in `cli/batch.py` | `tests/test_build_batch_summary.py` | `cli/batch.py` | ⬚ |
| 2.11 | Refactor `build_batch_summary()` | `tests/test_build_batch_summary.py` | `cli/batch.py` | ⬚ |

**Phase 2 exit criteria:** All `tests/test_parse_tickers_input.py`, `tests/test_message_buffer_reset.py`, and `tests/test_build_batch_summary.py` tests green (11 tasks). No change to `run_analysis()` or `analyze` command.

---

## Phase 3 — CLI Batch Execution

**Scope:** The execution loop, `run_analysis()` refactoring, and the updated `analyze` command. This phase has the most integration surface.

**Dependencies:** Phase 1 and Phase 2 complete.

| # | Task | Test File | Source File | Status |
|---|---|---|---|---|
| 3.1 | Write failing tests for `batch_run_loop()` (6 cases: partial-fail, OSError-save, all-fail, KI-propagation, process_signal-non-fatal, progress-header `[N/TOTAL] Analyzing TICKER on DATE` for REQ-NFR-02) with `cli.batch.Live` patched as no-op | `tests/test_batch_run_loop.py` | — | ⬚ |
| 3.2 | Refactor `run_analysis()` in `cli/main.py` to accept `ticker: str` parameter; move `get_ticker()` call to `analyze` dispatcher | `tests/test_batch_run_loop.py` | `cli/main.py` | ⬚ |
| 3.3 | Extract `_stream_analysis()` helper from `run_analysis()` for reuse by both single-ticker and batch paths | `tests/test_batch_run_loop.py` | `cli/main.py` | ⬚ |
| 3.4 | Implement `batch_run_loop()` in `cli/batch.py` | `tests/test_batch_run_loop.py` | `cli/batch.py` | ⬚ |
| 3.5 | Refactor `batch_run_loop()` | `tests/test_batch_run_loop.py` | `cli/batch.py` | ⬚ |
| 3.6 | Write failing tests for `analyze` command: `--tickers` flag, blank-flag exit-2, single-ticker routing, interactive CSV routing, KI propagation, new prompt-text assertion | `tests/test_analyze_command_batch.py` | — | ⬚ |
| 3.7 | Update `get_ticker()` prompt text in `cli/utils.py` to indicate CSV input; add `--tickers` option to `analyze` command; implement single-vs-batch dispatch | `tests/test_analyze_command_batch.py` | `cli/utils.py`, `cli/main.py` | ⬚ |
| 3.8 | Implement `run_batch_analysis()` orchestrator in `cli/main.py` (calls `batch_run_loop`, `build_batch_summary`, `raise SystemExit`) | `tests/test_analyze_command_batch.py` | `cli/main.py` | ⬚ |
| 3.9 | Refactor Phase 3 changes | `tests/test_analyze_command_batch.py` | `cli/main.py`, `cli/batch.py` | ⬚ |

**Phase 3 exit criteria:** All `tests/test_batch_run_loop.py` and `tests/test_analyze_command_batch.py` tests green. Full test suite passes (no regressions).

---

## Phase 4 — Regression and Integration

**Scope:** Single-ticker regression test (REQ-NFR-01) and CRYPTO_SUFFIXES cross-layer consistency test (TE reviewer note). No new production code.

**Dependencies:** Phase 3 complete.

| # | Task | Test File | Source File | Status |
|---|---|---|---|---|
| 4.1 | Write single-ticker regression test: CliRunner + mocked propagate; assert questionary call sequence (8 calls), results path format, Rich panel title set for `["market","news"]` analyst set | `tests/test_regression_single_ticker.py` | — | ⬚ |
| 4.2 | Verify regression test passes (no production changes expected; failure = regression) | `tests/test_regression_single_ticker.py` | *(none — test only)* | ⬚ |
| 4.3 | Add CRYPTO_SUFFIXES cross-layer consistency test: `assert cli.utils.CRYPTO_SUFFIXES == tradingagents.dataflows.utils.CRYPTO_SUFFIXES` | `tests/test_detect_asset_type_internal.py` | — | ⬚ |
| 4.4 | Run full test suite; confirm all tests green, no new warnings | *(all test files)* | *(none)* | ⬚ |

**Phase 4 exit criteria:** All tests green including regression. `pytest --tb=short` exits 0.

---

## Dependency Notes

```
Phase 1 (library)
  └── Phase 2 (CLI pure functions)
        └── Phase 3 (CLI batch execution)
              └── Phase 4 (regression + consistency)
```

Within each phase, test tasks (Red) always precede implementation tasks (Green → Refactor).

---

## Integration Points

| Component | Phase | Notes |
|---|---|---|
| `tradingagents/dataflows/utils.py` | 1 | Additive only; existing functions untouched |
| `tradingagents/graph/trading_graph.py` | 1 | Additive method; no existing method signatures change |
| `cli/utils.py` | 2, 3 | `parse_tickers_input()` added; `get_ticker()` prompt text updated |
| `cli/main.py :: MessageBuffer` | 2 | `reset()` method added; `__init__` unchanged |
| `cli/main.py :: run_analysis()` | 3 | Signature change: `ticker: str` required param; ticker resolution moved out |
| `cli/main.py :: analyze()` | 3 | `--tickers` option added; dispatch logic added |
| `cli/batch.py` | 2, 3 | New file; no existing code depends on it before this feature |

---

## Definition of Done

- [ ] All 4 phases complete (⬚ → ✅)
- [ ] `pytest` exits 0 with no failures or errors
- [ ] No regressions in existing tests (full suite green)
- [ ] `ruff check` passes (no lint errors in new/modified files)
- [ ] CRYPTO_SUFFIXES consistency test in `test_detect_asset_type_internal.py`
- [ ] Single-ticker regression test in `test_regression_single_ticker.py` passes
- [ ] `tradingagents/` layer imports nothing from `cli/` (boundary preserved)
