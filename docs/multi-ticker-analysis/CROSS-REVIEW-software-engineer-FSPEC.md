# Cross-Review: software-engineer — FSPEC

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/FSPEC-multi-ticker-analysis.md
**Date:** 2026-05-28
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | High | Local | FSPEC-BATCH-02 is silent on the two interactive post-analysis prompts in the existing `run_analysis()`. After the Live context closes, the current code prompts (a) "Save report? (Y/n)" with a path prompt, and (b) "Display full report on screen? (Y/n)". In batch mode, both prompts would block execution between tickers, requiring user input for every ticker. The FSPEC must explicitly state that both prompts are suppressed in batch mode: auto-save always occurs to `results/{TICKER}/{DATE}/` (already covered by REQ-BATCH-05), and `display_complete_report()` is either suppressed or replaced with a fixed condensed output per ticker. This is a product UX decision that engineers must not interpret independently. | FSPEC-BATCH-02 |
| F-02 | High | Local | FSPEC-BATCH-02 does not address the Rich `Live` context manager. The existing flow wraps the entire streaming analysis in `with Live(layout, refresh_per_second=4):`. In batch mode, this context must be entered and exited **per ticker** — if a single Live context spans the whole batch, the layout will not reset between tickers and display state will bleed across runs. The FSPEC must specify: the Live context is entered at the start of each ticker's analysis (before streaming begins) and exited after streaming completes; the layout is re-created or reset between tickers. | FSPEC-BATCH-02, Step 3 |
| F-03 | Medium | Local | FSPEC-BATCH-02 Step 3 omits `graph.process_signal(decision)`. In the existing `run_analysis()`, `graph.process_signal(final_state["final_trade_decision"])` is called immediately after streaming completes (line 1261 in cli/main.py). This call stores the decision in the memory log and enables cross-ticker learning injection on subsequent runs for the same ticker. In batch mode, this must be called per ticker after each successful `propagate()`. The FSPEC flow must include this call — without it, the memory log will not accumulate batch run decisions, breaking the existing learning persistence feature. | FSPEC-BATCH-02, Step 3 |
| F-04 | Low | Local | FSPEC-BATCH-02 says "record (ticker, final_state, decision) as SUCCESS" but does not define the `batch_results` data structure that FSPEC-BATCH-03 consumes. The structure is implied (list of tuples or objects), but the FSPEC should name what is being accumulated — e.g. "append `BatchTickerRecord(ticker, final_state, decision)` to `batch_results`". This avoids the TSPEC author inventing a different structure that FSPEC-BATCH-03 cannot consume. | FSPEC-BATCH-02, Step 4; FSPEC-BATCH-03 |
| F-05 | Low | Local | FSPEC-BATCH-02 AT3 says "`results/TICKER2/` may or may not exist" after an OSError during save. This is imprecise — `save_report_to_disk()` creates the directory before writing files, so the directory will typically exist even when an OSError occurs mid-write (e.g. disk-full during file write). The FSPEC should say "the results directory may be partially populated" rather than "may or may not exist" to avoid a test asserting the wrong condition. | FSPEC-BATCH-02, AT3 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For F-01: should `display_complete_report()` be called per ticker in batch mode (producing full output for each ticker before moving to the next), or should full report display be suppressed entirely in batch mode (only the summary table is shown at the end)? |
| Q-02 | Is `graph.process_signal()` the correct call to persist to the memory log in batch mode, or is there a separate mechanism for batch runs? |

---

## Positive Observations

- FSPEC-BATCH-03 decision tree is thorough: the wheel vs. standard mode branching, None/absent/malformed JSON handling, and empty-vs-N/A distinction are all business rules that would otherwise vary by implementation. This is exactly the right level of precision for an FSPEC.
- The `sys.exit` call placement (after table is printed) is correctly specified in BR-08 — this prevents the common bug of exiting before the table renders.
- FSPEC-BATCH-01 correctly defers the blank `--tickers` flag behaviour to OQ-F-01 rather than inventing one.
- BR-06 in FSPEC-BATCH-02 correctly names the library-internal detection function (`_detect_asset_type(ticker)` in `tradingagents/`), consistent with the REQ-API-01 boundary decision.
- The single-ticker bypass (FSPEC-BATCH-01 BR-04 → FSPEC-BATCH-03 BR-01) is consistently specified across both FSPECs.

---

## Recommendation

**Needs revision**

> F-01 (interactive prompts block batch loop) and F-02 (Live context per-ticker) are High findings that describe missing business rules engineers cannot infer. F-01 in particular is a PM-owned UX decision: suppress both prompts in batch mode, or show condensed output between tickers? F-03 is Medium: `graph.process_signal()` must be placed in the execution flow to preserve the memory log feature. F-04 and F-05 are Low. All High and Medium findings must be addressed before TSPEC authoring.
