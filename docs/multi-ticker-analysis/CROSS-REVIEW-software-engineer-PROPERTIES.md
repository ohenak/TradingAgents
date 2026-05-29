# Cross-Review: software-engineer — PROPERTIES

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/PROPERTIES-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | PROP-CLI-04 says an interactive CSV input "must result in a batch run for `["NVDA","AAPL"]`" but doesn't specify the observable verification mechanism. "Results in a batch run" is ambiguous — the test must assert `propagate.call_args_list == [call("NVDA", ...), call("AAPL", ...)]` via a mocked `propagate()`. Add the verification note so the property is directly implementable. | PROP-CLI-04 |
| F-02 | Low | Local | PROP-NEG-01 ("library modules must NOT import from `cli/`") is classified as "Unit (import check)" but doesn't specify the test mechanism. Two options: (a) `ast.walk` static import scan on each `tradingagents/` module, or (b) `pytest` import assertion using `importlib`. The PROPERTIES should specify which approach is canonical so all implementations agree. | PROP-NEG-01 |
| F-03 | Low | Local | PROP-LOOP-05 ("message_buffer.reset() must be called before each ticker's propagate() call") requires observing calls to a method on a module-level singleton. The property should note that the test patches `cli.batch.message_buffer` with a `MagicMock()` (or patches `cli.batch.message_buffer.reset` specifically) to track call count and ordering. Without this note, implementers may choose incompatible mock targets. | PROP-LOOP-05 |

---

## Questions

None.

---

## Positive Observations

- All 43 properties are technically implementable with the existing pytest + CliRunner + MagicMock infrastructure. No new test tooling is needed.
- Test level assignments are correct throughout: pure functions (INPUT, ASSET, RESET, TABLE, API) at Unit; batch loop and CLI command at Integration. No E2E tests are specified — the pyramid is well-shaped.
- PROP-CONTRACT-01 (CRYPTO_SUFFIXES cross-layer consistency) is the correct observable for DEC-MULTI-01's drift re-evaluation trigger — a direct equality assertion between two module-level constants.
- PROP-RESET-04 ("instance-level `add_message` attribute must not exist after reset") directly tests the `__dict__.pop` pattern from DEC-MULTI-02 without relying on implementation internals.
- PROP-NEG-02 (KI not caught by batch_run_loop) and PROP-NEG-03 (KI not caught by propagate_many) are both testable via `pytest.raises(KeyboardInterrupt)` on the respective functions — correctly classified as Integration and Unit respectively.
- PROP-TABLE-07 through PROP-TABLE-10 cover the wheel mode decision branches completely, including all four cases (approved, rejected, None, malformed) — each is a distinct test case.
- The integration boundary between CLI and library is properly covered: PROP-CLI-01–05 cover the `analyze` command dispatch, while PROP-LOOP-01–07 cover `batch_run_loop` with mocked `propagate()`.

---

## Recommendation

**Approved with minor changes**

> No High or Medium findings. F-01 through F-03 are Low and should be addressed before implementation to prevent ambiguous test implementations. All properties are technically sound and testable.
