# Cross-Review: test-engineer — REQ

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | High | Local | REQ-NFR-01 AC1 has no verifiable comparison method. "All prompts, output panels, and save paths are identical" cannot be automated without specifying a baseline and comparison strategy (e.g., snapshot of questionary call sequence, Rich output diff, or path-structure assertion). Without this, the regression requirement is a manual-only check — it is not a testable acceptance criterion. Must specify the regression test approach: snapshot of prompt call order, parameterised test sharing a helper with the current single-ticker path, or explicit integration test that asserts the same save-path format. | REQ-NFR-01 |
| F-02 | High | Local | REQ-BATCH-03 AC1 ("MSFT's analysis has not started while AAPL is streaming") is untestable as written. There is no observable state that distinguishes "has not started" from "has started but not yet visible" in an automated test without timing assertions (flaky). Must replace with a mock-order assertion: "given a mock `propagate()`, assert that `propagate("MSFT", …)` is not called until `propagate("AAPL", …)` has returned". | REQ-BATCH-03 |
| F-03 | High | Local | REQ-BATCH-01 AC1 normalisation is underspecified. The REQ says the system "normalises to `["AAPL", "MSFT", "NVDA"]`" but does not state whether this uses the existing `normalize_ticker_symbol()` function (which handles exchange suffixes like `CNC.TO`) or new logic. If it uses the existing function, a unit test can assert on its output. If it is new logic, the normalisation rules must be stated explicitly: strip whitespace, uppercase, preserve dots/exchange suffixes? Without this, AC1 cannot be implemented as a deterministic unit test. | REQ-BATCH-01 |
| F-04 | Medium | Local | REQ-BATCH-04 AC2 specifies "non-zero exit code" but not which code. `typer.testing.CliRunner` captures `result.exit_code`. Tests must assert a specific value (e.g., `exit_code == 1`) or at minimum assert `exit_code != 0`. The vague "non-zero" allows exit code `2` (Typer's usage error) to satisfy the criterion even when the failure reason is a ticker error, not a usage error. Specify `exit_code == 1` for partial batch failure. | REQ-BATCH-04 |
| F-05 | Medium | Local | REQ-BATCH-04 AC1 — "marked as failed" is not observable in isolation. The failure state representation is unspecified: is it a Rich console print, a structured object, an entry in the summary table? Without a defined observable output (e.g., "the string `[FAILED] BADTICKER: <error class>` is printed to stdout"), a test cannot assert on it. | REQ-BATCH-04 |
| F-06 | Medium | Local | REQ-BATCH-05 AC2 ("batch run is interrupted after the second of three tickers") has no specified test mechanism. "Interrupted" is ambiguous: is this a `KeyboardInterrupt`, a mid-run process kill, or a controlled exception injection? The only reliably testable approach is exception injection: mock `propagate()` to raise on the third ticker call, then assert disk state. The REQ should specify this as the intended verification method. | REQ-BATCH-05 |
| F-07 | Medium | Local | REQ-BATCH-06 — "final decision" column content is unspecified for testability. The source field (`final_trade_decision` from graph state vs. `graph.process_signal()` output) is not stated. These produce different string representations. Tests asserting on the summary table content cannot be written without knowing which field is extracted and whether it is truncated, normalized (e.g., first line only), or raw. | REQ-BATCH-06 |
| F-08 | Medium | Local | REQ-API-01 return type conflict makes AC2 untestable. The description says errors are in "a separate errors dict" but the ACs only reference `(ticker, None, None)` tuples. A test cannot assert `result[1] == (ticker, None, None)` and also `errors["BADTICKER"] == <exception>` without knowing the method signature. The SE cross-review also flags this as F-05. Both issues must be resolved together. | REQ-API-01 |
| F-09 | Low | Local | REQ-BATCH-01 AC4 (duplicate removal) does not specify whether insertion order is preserved. A batch of `["NVDA", "AAPL", "NVDA"]` should deduplicate to `["NVDA", "AAPL"]` (first-occurrence order) or `["AAPL", "NVDA"]` (sorted)? Order affects the sequential execution sequence and must be deterministic for tests. | REQ-BATCH-01 |
| F-10 | Low | Local | REQ-NFR-02 AC1 uses "such as" (`[3/5] Analyzing GOOGL on 2026-05-27`), which is not a testable specification. A test must match against an exact format or a documented regex. Replace "such as" with an exact format string or regexp: e.g., `r"\[\d+/\d+\] Analyzing \w+ on \d{4}-\d{2}-\d{2}"`. | REQ-NFR-02 |
| F-11 | Low | Local | Missing negative scenario: all tickers fail. REQ-BATCH-04 addresses partial failure but not total failure. When every ticker raises an exception, does the summary table still print? Does the exit code differ from partial failure? This edge case needs at least one acceptance criterion. | REQ-BATCH-04 |
| F-12 | Low | Cross-Feature | The `message_buffer` module-level singleton and its monkey-patched method decorators make test isolation difficult — a state leak between test cases that invoke CLI-level batch logic. This is a broader testability constraint that affects any future CLI feature using the singleton. Worth recording as a cross-feature constraint: CLI module-level singletons should expose a reset/factory method for test isolation. | §3 Assumptions |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | Is `typer.testing.CliRunner` the intended test harness for `--tickers` flag and batch loop tests, or is the intent to test the batch loop logic in isolation (extracted function, not CLI entry point)? The answer determines whether tests are CLI-level or unit-level. |
| Q-02 | For REQ-BATCH-06 wheel mode (AC4), is "Approved/Rejected" derived from `WheelCandidateReport.approved`, or from a string in the final trade decision? Specifying the source field is needed to write an assertion. |
| Q-03 | Should per-ticker test isolation (message_buffer reset, decorator re-binding) be the responsibility of the batch loop implementation, or should a test fixture handle it? This decision affects TSPEC test strategy. |

---

## Positive Observations

- The existing `typer.testing.CliRunner` pattern in `tests/test_cli_wheel.py` is well-suited for testing the `--tickers` flag and the post-run summary table output. No new test infrastructure is needed for CLI-level tests.
- REQ-API-01 AC3 (single-ticker equivalence) is a clean and implementable regression guard for `propagate_many()`.
- REQ-BATCH-04 AC3 (exit code 0 on all success) is precise and immediately testable via `CliRunner.invoke`.
- The out-of-scope exclusion of parallel execution eliminates the need for thread-safety tests, significantly narrowing test surface.
- The `_dummy_api_keys` autouse fixture in `conftest.py` means batch-loop unit tests will not require real API credentials.

---

## Recommendation

**Needs revision**

> F-01, F-02, and F-03 are High findings that make core acceptance criteria of REQ-NFR-01, REQ-BATCH-03, and REQ-BATCH-01 untestable as written. F-04 through F-08 are Medium findings covering exit code precision, observable failure state, interruption test mechanism, summary table source field, and API return type. All High and Medium findings must be addressed before TSPEC authoring can produce a sound test strategy.
