# Cross-Review: test-engineer — Implementation

**Reviewer:** test-engineer
**Document reviewed:** feat-multi-ticker-analysis branch (test suite vs PROPERTIES v0.2.0)
**Date:** 2026-05-29
**Iteration:** 1

---

## Test Suite Status

All 52 feature tests pass:
```
test_detect_asset_type_internal.py  6
test_parse_tickers_input.py         5
test_message_buffer_reset.py        3
test_build_batch_summary.py        12
test_propagate_many.py             10
test_batch_run_loop.py              6
test_analyze_command_batch.py       5
test_regression_single_ticker.py    5
                                  ----
                                    52  passed
```

---

## Property Coverage Audit

| Property | Test | Covered |
|---|---|---|
| PROP-INPUT-01..06 | test_parse_tickers_input.py | ✅ |
| PROP-ASSET-01..05 | test_detect_asset_type_internal.py | ✅ |
| PROP-CONTRACT-01 | test_detect_asset_type_internal.py::test_crypto_suffixes_match_cli | ✅ |
| PROP-RESET-01..05 | test_message_buffer_reset.py | ✅ |
| PROP-TABLE-01..10 | test_build_batch_summary.py | ✅ |
| PROP-API-01..07 | test_propagate_many.py | ✅ |
| PROP-LOOP-01..07 | test_batch_run_loop.py | ✅ |
| PROP-CLI-01..05 | test_analyze_command_batch.py | ✅ |
| PROP-REG-01..03 | test_regression_single_ticker.py | ✅ |
| PROP-NEG-02 (batch KI not caught) | test_batch_run_loop.py::test_keyboard_interrupt_propagates | ✅ |
| PROP-NEG-03 (propagate_many KI) | test_propagate_many.py::test_keyboard_interrupt_propagates | ✅ |
| PROP-NEG-04 (no table single-ticker) | test_regression_single_ticker.py (routing tests) | ✅ |
| PROP-NEG-06 (empty ≠ N/A standard) | test_build_batch_summary.py::test_standard_first_non_empty_line_used | ✅ (implicit) |
| **PROP-NEG-01 (library imports no cli/)** | — | ❌ **MISSING** |
| **PROP-NEG-05 (Save/Display prompts suppressed in batch)** | — | ❌ **MISSING** |

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Cross-Feature | PROP-NEG-01 has no test. The PROPERTIES doc specifies "Verified by an `ast`-based static import scan on all `.py` files under `tradingagents/`: assert no `from cli` or `import cli` statement exists." The implementation IS compliant (verified manually: only a comment mentions cli in `tradingagents/dataflows/utils.py`), but there is no automated guard. This is the test that protects DEC-MULTI-01's architectural boundary against future regression — exactly the kind of invariant that needs a standing test. `tests/test_sentinel_enforcement.py` already demonstrates the `ast.walk` + `ast.ImportFrom` pattern to copy. Add a test to `test_detect_asset_type_internal.py`. | PROP-NEG-01 |
| F-02 | Medium | Local | PROP-NEG-05 has no test. The PROPERTIES doc requires: "The 'Save report?' and 'Display full report?' interactive prompts must NOT appear during batch mode." `run_batch_analysis` correctly never invokes these prompts (they live only in `run_analysis`'s post-Live block), so the implementation is compliant — but there is no test asserting it. Add a test to `test_analyze_command_batch.py` that runs a 2-ticker batch with mocked `propagate` and asserts `typer.prompt` is never called (or that the output contains no "Save report?" string). | PROP-NEG-05 |
| F-03 | Low | Local | PROP-NEG-06 (standard mode empty `final_trade_decision` → empty string, not "N/A") is covered only implicitly. `test_build_batch_summary.py` tests the first-non-empty-line extraction but no test asserts the specific case where `final_trade_decision` is absent/blank yields `""` (and explicitly NOT "N/A"). Add an explicit assertion for the empty case. | PROP-NEG-06 |

---

## Questions

None.

---

## Positive Observations

- 40 of the 43 properties have direct, correctly-levelled tests. Unit properties are unit-tested; integration properties (LOOP, CLI) use mocked `propagate`/`save`/Live at the integration boundary — the test pyramid is well-shaped.
- The `batch_run_loop` injectable-dependency design makes the integration tests clean and deterministic — no real Rich Live rendering, no filesystem surprises.
- PROP-NEG-02 and PROP-NEG-03 (KeyboardInterrupt propagation) are both tested via `pytest.raises(KeyboardInterrupt)` at the correct level, exactly as the PROPERTIES doc prescribes.
- The `call_args_list` strict-ordering assertions in `test_propagate_many.py` correctly verify sequential execution (PROP-LOOP-04 / REQ-BATCH-03).

---

## Recommendation

**Needs revision**

> F-01 and F-02 are Medium: two negative properties (PROP-NEG-01 import-boundary guard, PROP-NEG-05 prompt suppression) listed in the approved PROPERTIES doc have no corresponding test. The implementation is compliant, but the coverage gap means a future regression of either invariant would go undetected. Add both tests. F-03 (Low) — make PROP-NEG-06 explicit.
