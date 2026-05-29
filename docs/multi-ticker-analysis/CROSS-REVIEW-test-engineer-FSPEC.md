# Cross-Review: test-engineer — FSPEC

**Reviewer:** test-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-28
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Medium | Local | FSPEC-BATCH-01 ATs do not specify how interactive prompts are simulated in tests. AT2 says "interactive prompt receives ` nvda , AAPL , nvda `" but gives no test mechanism. The two viable approaches are: (a) `CliRunner.invoke(app, [], input="nvda, AAPL, nvda\n...")` — passes stdin to the Typer app; (b) mock `questionary.text().ask` to return the string. These produce different code coverage and catch different failure modes. The FSPEC must specify which approach is canonical so all AT tests use the same path, and so the TSPEC can prescribe it. | FSPEC-BATCH-01, AT2, AT5 |
| F-02 | Medium | Local | FSPEC-BATCH-02 does not address test isolation for the `message_buffer` module-level singleton. The flow specifies that the buffer must be fully reset per ticker (BR-04), but tests of the batch loop that exercise this reset will fail or produce false positives if a previous test left the singleton in a modified state. The FSPEC must specify that a reset/factory mechanism for `message_buffer` is required for test isolation — either a `reset()` method or a factory function that tests can call in setUp/teardown. Without this, TSPEC authors will independently invent incompatible approaches. | FSPEC-BATCH-02, BR-04 |
| F-03 | Low | Local | FSPEC-BATCH-02 AT1 says "`propagate('BADTICKER')` raises `ValueError`" without specifying how `propagate` is mocked. The AT should say "with `graph.propagate` mocked to raise `ValueError` when called with 'BADTICKER'". Without this, test authors may mock at different levels (module-level patch vs. instance mock), which affects isolation. | FSPEC-BATCH-02, AT1 |
| F-04 | Low | Local | FSPEC-BATCH-02 AT3 says "`save_report_to_disk()` raises `OSError` on ticker 2" without specifying the injection mechanism. The AT should specify: "with `save_report_to_disk` mocked to raise `OSError` on the second call" (using `side_effect` list on the mock). Without this, tests may use file-system-based approaches (creating a read-only path) which are platform-dependent and brittle. | FSPEC-BATCH-02, AT3 |
| F-05 | Low | Local | FSPEC-BATCH-03's decision logic (BR-01 through BR-08) is defined purely as a flow inside the CLI command. For the acceptance tests (AT1 through AT9) to be runnable at unit level — without invoking the full CLI, questionary prompts, Rich Live context, and `propagate()` — the table-building and decision logic must be extractable as a pure function. The FSPEC should add a note that the summary table logic must be implemented as a standalone function receiving `batch_results`, `failed_tickers`, `selected_analyst_keys`, and `N` as inputs, so it can be unit tested independently. | FSPEC-BATCH-03 |
| F-06 | Low | Local | OQ-F-01 (blank `--tickers` flag) is unresolved, leaving a decision branch without a testable acceptance criterion. AT5 covers the interactive-prompt blank case but there is no AT for the `--tickers "  "` flag case. Until OQ-F-01 is resolved (option a: fall through to interactive prompt; option b: exit with usage error), the corresponding AT cannot be written. Flag for resolution before TSPEC authoring. | FSPEC-BATCH-01, OQ-F-01 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For F-01: should the canonical test mechanism for interactive prompts be `CliRunner(mix_stderr=False)` with a pre-built `input` string, or `unittest.mock.patch` of `questionary`? Choosing one avoids divergence between test authors. |
| Q-02 | For F-05: should the summary table function signature be decided in the FSPEC or deferred to TSPEC? |

---

## Positive Observations

- FSPEC-BATCH-03 decision tree is complete — all branches (wheel vs. standard, None/absent/malformed, failed/succeeded, N==1 vs. N>1) are distinct enough to map to separate test cases without further disambiguation.
- AT8 and AT9 (exit codes 1 and 0) are immediately testable via `CliRunner.exit_code`; this is the correct test mechanism.
- FSPEC-BATCH-02 AT2 (`KeyboardInterrupt` propagation) correctly identifies `pytest.raises(KeyboardInterrupt)` on the batch loop function as the test mechanism (consistent with REQ-BATCH-04 AC5), not CliRunner which suppresses KI.
- FSPEC-BATCH-03 BR-05 (empty `final_trade_decision` → empty cell, not N/A) is a subtle distinction that would otherwise vary by implementation; documenting it explicitly enables a precise unit test.
- AT4 in FSPEC-BATCH-02 specifies the progress header regex pattern — directly usable in `assert re.search(pattern, output)`.

---

## Recommendation

**Needs revision**

> F-01 and F-02 are Medium findings that affect test isolation and AT implementability. F-01 (interactive prompt simulation mechanism) must be resolved so the TSPEC can prescribe a consistent approach. F-02 (message_buffer reset for test isolation) must be specified so TSPEC authors don't invent incompatible solutions. F-03 through F-06 are Low and should be addressed before TSPEC authoring to keep ATs precise enough to implement directly.
