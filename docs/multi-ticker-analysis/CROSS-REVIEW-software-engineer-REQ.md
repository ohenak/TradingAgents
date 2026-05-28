# Cross-Review: software-engineer — REQ

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | High | Local | `message_buffer` monkey-patching creates a per-ticker file-pointer leak. In `run_analysis()` (cli/main.py lines 1094–1096), the buffer's three methods are replaced with closures that capture `log_file` and `report_dir` — paths tied to `selections["ticker"]`. In batch mode the first ticker's decorators remain attached when the second ticker starts, causing all log and report writes for ticker N to land in ticker 1's directory. The REQ must require that the message_buffer decorator bindings are reset per ticker. | §3 Assumptions; REQ-BATCH-05 |
| F-02 | High | Local | `selections["ticker"]` is a scalar wired deeply into `run_analysis()`. It appears at lines 1051 (results dir), 1106, 1125, 1131, and implicitly in `save_report_to_disk()`. The REQ §3 Assumptions says the feature is "a loop wrapper, not a graph change", but the CLI ticker binding is not a shallow wrapper seam — it is load-bearing inside the function. The REQ must explicitly acknowledge this refactoring scope or its feasibility assumption is false. | §3 Assumptions; REQ-BATCH-01 |
| F-03 | High | Local | Mixed asset types in a single batch are unspecified. `detect_asset_type(ticker)` is called once per ticker today, but REQ-BATCH-02 says "shared configuration … applied uniformly to every ticker". Asset type is per-ticker, not shared config. A batch of `["AAPL","BTC-USD"]` must either (a) detect asset type per ticker silently, or (b) reject cross-type batches. Neither is addressed. Without a decision, REQ-BATCH-01 AC1 acceptance criteria are incomplete. | REQ-BATCH-01, REQ-BATCH-02 |
| F-04 | Medium | Local | REQ-BATCH-03 AC3 ("total wall time ≥ sum of individual run times") is non-deterministic and cannot be asserted in an automated test — LLM API latency is variable. This is an architectural invariant, not a measurable acceptance criterion. Restate as a design constraint: "the batch loop must not invoke the next ticker's analysis until the current one has returned". | REQ-BATCH-03 |
| F-05 | Medium | Local | REQ-API-01 return type is ambiguous. The description says errors are stored in "a separate errors dict", but the ACs reference only `(ticker, None, None)` tuples; the errors dict is never returned or referenced in any AC. The method signature must be resolved: either return `(results_list, errors_dict)` or encode the error in the tuple. | REQ-API-01 |
| F-06 | Medium | Local | REQ-BATCH-04 exception scope is underspecified. "Unhandled exception" does not address: (a) `KeyboardInterrupt` / `SystemExit` — these must propagate, not be swallowed; (b) exceptions raised during the save step vs. during graph execution; (c) whether a `BaseException` or only `Exception` is caught. An overly broad `except BaseException` would mask Ctrl+C, making a long batch uninterruptible. | REQ-BATCH-04 |
| F-07 | Medium | Local | REQ-NFR-01 AC1 is under-specified. "All prompts, output panels, and save paths are identical" cannot be verified without specifying a reference baseline or comparison method. Add a concrete testable criterion: e.g., "the sequence of questionary prompts shown, the Rich panel titles rendered, and the results directory path for a single-ticker invocation are byte-for-byte equivalent to the pre-feature baseline captured in a snapshot test." | REQ-NFR-01 |
| F-08 | Low | Local | `StatsCallbackHandler` scope in batch mode is unspecified. Currently one handler is created per `run_analysis()` invocation and its stats are displayed at the end. In batch mode, should stats be per-ticker (reset between tickers) or cumulative? The post-run summary table (REQ-BATCH-06) does not mention LLM/tool-call counts. Clarify expected scope. | REQ-BATCH-06 |
| F-09 | Low | Cross-Feature | Graph initialisation is expensive (LLM client creation, tool node wiring, LangGraph compilation — approx. 1–3 s per init). The REQ §3 Assumptions correctly states the graph is reused across tickers. However, this is an implicit architectural constraint that applies beyond this feature: any future feature that re-initialises the graph per ticker in a loop will incur the same cost. Worth recording as a domain constraint. | §3 Assumptions |
| F-10 | Low | Local | `_processed_message_ids` set on `message_buffer` is never cleared between tickers. For a 10-ticker batch the set accumulates ~10× the IDs. This is not a correctness bug (new ticker graph nodes produce new UUIDs) but is a memory accumulation. Specify whether the set should be cleared on buffer reset. | REQ-BATCH-01 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | Should `propagate_many()` accept an `asset_type` per ticker, or a single shared `asset_type`? The current `propagate(ticker, date, asset_type)` signature accepts it per call. |
| Q-02 | Is the `--tickers` flag intended to coexist with the existing interactive ticker prompt (prompt used if flag absent), or should it replace the prompt entirely in non-interactive mode? |
| Q-03 | For the post-run summary table (REQ-BATCH-06), is the "final decision" extracted from `final_trade_decision` in state, or from `graph.process_signal()` output? The two are not always the same string. |

---

## Positive Observations

- The assumption that `TradingAgentsGraph` is initialised once and `propagate()` called per ticker is architecturally sound: `propagate()` is stateless with respect to graph topology, and `_run_graph()` creates fresh `AgentState` per call. No graph re-compilation is needed.
- REQ-BATCH-04 correctly calls out non-zero exit code on any failure — this is the correct UNIX convention and enables CI pipeline integration.
- The out-of-scope list is precise and prevents scope creep: parallel execution, per-ticker config overrides, and cross-ticker analysis are all explicitly excluded.
- REQ-API-01's single-ticker equivalence criterion (AC3) is a clean regression guard for the Python API layer.

---

## Recommendation

**Needs revision**

> F-01 and F-02 are High findings that affect correctness and feasibility of the core loop. F-03 is High and leaves the most common multi-asset-type scenario (stocks + crypto) unspecified. F-04 through F-07 are Medium findings that make acceptance criteria untestable or method contracts ambiguous. All High and Medium findings must be addressed before proceeding to FSPEC.
