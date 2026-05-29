# Cross-Review: test-engineer — TSPEC

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/TSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | `_detect_asset_type()` return type contradiction. §5.1 specifies the function returns `str` (`"stock"` or `"crypto"`). §5.6 `batch_run_loop` step 2 calls `_detect_asset_type(ticker).value` — `.value` is an enum method; calling it on a `str` raises `AttributeError` at runtime. Any integration test of `batch_run_loop` that reaches step 2 will fail immediately. Fix: either (a) change §5.1 to return `AssetType` enum and remove `.value` in §5.6, or (b) keep the return as `str` and remove `.value` from step 2. Option (b) is simpler and consistent with `propagate(asset_type: str = "stock")`. | §5.1, §5.6 batch_run_loop step 2 |
| F-02 | Medium | Local | `batch_run_loop` test file is classified as "Integration" but §5.6 uses `with Live(layout, refresh_per_second=4):` inside the loop. Rich's `Live` renders to a terminal — in a headless pytest run it will either raise or produce no output, making assertions on console output fail. The TSPEC must specify how `Live` is handled in `test_batch_run_loop.py`: either (a) patch `cli.batch.Live` with a `MagicMock` context manager, or (b) use `Console(file=StringIO(), force_terminal=False)` so Live renders to a buffer. Without this, implementers will have to guess and may write incompatible tests. | §5.6 batch_run_loop; §7.1 |
| F-03 | Low | Local | `test_detect_asset_type_internal.py` is listed in §3 new files but §7.3 provides no test cases for it. At minimum specify: `_detect_asset_type("BTC-USD")` → `"crypto"`, `_detect_asset_type("AAPL")` → `"stock"`, `_detect_asset_type("ETH-USDT")` → `"crypto"`, `_detect_asset_type("CNC.TO")` → `"stock"`. | §3, §7.3 |
| F-04 | Low | Local | `test_propagate_many.py` is missing the empty-list edge case: `propagate_many([], date)` should return `[]` with no calls to `propagate()`. Required to confirm the loop handles the empty input without error. | §7.3 |
| F-05 | Low | Local | `test_build_batch_summary.py` is missing a test for a ticker that appears in `ordered_tickers` but is in neither `batch_results` nor `failed_tickers` (e.g., due to a bug in batch_run_loop). `batch_results[ticker]` would raise `KeyError`. Either this case should be tested as defensive handling (returns `N/A` or raises clearly), or the TSPEC should document that `ordered_tickers`, `batch_results`, and `failed_tickers` are always consistent (each ticker is in exactly one). | §5.6 build_batch_summary; §7.3 |
| F-06 | Low | Local | `test_regression_single_ticker.py` (REQ-NFR-01) describes verifying "questionary prompt sequence, results path, and Rich panel titles" are identical to a baseline, but does not specify what the known-good baseline values are. Without explicit expected values hardcoded in the test (e.g., `EXPECTED_PROMPTS = ["Step 1...", ...]`, `EXPECTED_PANEL_TITLES = {"Wheel Suitability", ...}`), the test cannot be written from the TSPEC alone. Add a §7.3 entry specifying the exact assertions for this test. | §7.3 test_regression_single_ticker.py; REQ-NFR-01 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For F-01: does `propagate(ticker, date, asset_type=...)` accept the raw string `"stock"`/`"crypto"`, or does it require the `AssetType` enum? This determines which fix is correct. |
| Q-02 | For F-05: is the invariant "each ticker is in exactly one of batch_results or failed_tickers" guaranteed by the loop structure, or should build_batch_summary be defensive? |

---

## Positive Observations

- The split between `parse_tickers_input` (unit), `build_batch_summary` (unit), and `batch_run_loop` (integration) correctly pushes the most testable logic to the lowest level. The test pyramid is well-applied.
- `MagicMock` with `side_effect` for `save_report_to_disk` OSError injection is the right approach — deterministic, portable, no filesystem dependency.
- `pytest.raises(KeyboardInterrupt)` on `batch_run_loop` directly (not CliRunner) is explicitly specified — correct given CliRunner's KI suppression.
- `MessageBuffer.reset()` via `__dict__.pop` is a clean, testable approach — the test can verify the class-method is restored by checking `type(message_buffer).add_message is message_buffer.add_message` (no instance shadow) after reset.
- All 9 REQ requirements appear in the traceability table, and every test file maps to at least one requirement. No gap in coverage at the mapping level.

---

## Recommendation

**Needs revision**

> F-01 (return type mismatch causing AttributeError) and F-02 (Live context in headless tests) are Medium findings that will cause test failures without fixes. F-03 through F-06 are Low. All must be addressed before the PLAN is authored.
