# REQ — Multi-Ticker Sequential Analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.5.0 |
| **Created** | 2026-05-27 |
| **Upstream** | Conversation context (user request) → **REQ** |
| **Downstream** | FSPEC, TSPEC, PROPERTIES |
| **Cross-Reviews** | `CROSS-REVIEW-software-engineer-REQ.md`, `CROSS-REVIEW-test-engineer-REQ.md`, `CROSS-REVIEW-software-engineer-REQ-v2.md`, `CROSS-REVIEW-test-engineer-REQ-v2.md`, `CROSS-REVIEW-software-engineer-REQ-v3.md`, `CROSS-REVIEW-test-engineer-REQ-v3.md` |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.5.0 | 2026-05-27 | Final Low-finding cleanup: BATCH-02 AC1 detect_asset_type reference (SE-F-01/TE-F-02); API-01 asset_types length mismatch ValueError (SE-F-02); API-01 AC2 mock Given clause (TE-F-01) |
| 0.4.0 | 2026-05-27 | Address SE and TE cross-review v3 findings: API-01 propagate_many gains optional asset_types parameter resolving library→CLI import boundary (SE-F-01); BATCH-06 None/absent wheel_candidate_report case added (SE-F-02); API-01 AC3 mock Given clause (TE-F-01); BATCH-04 AC2 failure summary clarified as BATCH-06 table (TE-F-02); §3 Assumptions updated with CRYPTO_SUFFIXES relocation note |
| 0.3.0 | 2026-05-27 | Address SE and TE cross-review v2 findings: BATCH-06 wheel trigger changed to analyst-selection not state-presence (SE-F-01); API-01 detect_asset_type per ticker added (SE-F-02); BATCH-01 AC6 rewritten as mock-assertable propagate args (TE-F-01); BATCH-06 AC4 malformed-JSON fallback added (TE-F-02); BATCH-03 AC1 strict call_args_list ordering (SE-F-03); BATCH-02 AC1 single-init wording (SE-F-04); BATCH-05 AC1 timing wording (SE-F-05); BATCH-06 AC1 truncation clarified (TE-F-03); NFR-01 baseline-test creation note (TE-F-04); BATCH-04 AC5 KI test mechanism (TE-F-05); API-01 AC3 propagate return index (TE-F-06) |
| 0.2.0 | 2026-05-27 | Address SE and TE cross-review v1 findings: specify per-ticker asset type detection (SE-F-03); acknowledge run_analysis refactoring scope (SE-F-02); add message_buffer decorator-rebinding requirement (SE-F-01); add normalize_ticker_symbol reference (TE-F-03); rewrite BATCH-03 ACs as mock-order assertions (TE-F-02, SE-F-04); resolve API-01 return type to BatchTickerResult (SE-F-05, TE-F-08); tighten BATCH-04 exception scope and exit codes (SE-F-06, TE-F-04, TE-F-05); specify BATCH-05 AC2 test mechanism (TE-F-06); specify BATCH-06 decision source field (TE-F-07); rewrite NFR-01 with concrete regression test criterion (SE-F-07, TE-F-01); fix NFR-02 format string (TE-F-10); add all-failure scenario (TE-F-11); add first-occurrence dedup order (TE-F-09); address low findings SE-F-08/F-10 |
| 0.1.0 | 2026-05-27 | Initial draft |

---

## 1. Problem Statement

TradingAgents currently analyzes one ticker per CLI invocation. A user who wants to screen five wheel candidates must re-launch the CLI five times, re-entering their LLM provider, date, analyst selection, and research depth on each run. This is slow, error-prone (mismatched settings across runs), and makes batch watchlist screening impractical.

The gap: no mechanism exists to pass a list of tickers and have the system analyze them sequentially under a single, consistent configuration.

---

## 2. User Stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | Wheel options trader | Provide a list of ticker symbols at once | I can screen my entire watchlist without re-entering settings for each ticker |
| US-02 | Quantitative researcher | Have all tickers analyzed under identical settings (LLM, date, analysts) | I can compare results on a level playing field |
| US-03 | Trader | See a consolidated summary table after all tickers complete | I can compare decisions and key metrics across tickers at a glance |
| US-04 | Trader | Have a failed ticker logged and skipped | A single bad ticker (e.g. delisted, no options data) does not abort the remaining batch |
| US-05 | Trader | Have each ticker's full report auto-saved to disk as it completes | I don't lose earlier results if a later ticker fails or I close the terminal |
| US-06 | Developer | Call a convenience method on the Python API with a list of tickers | I can embed batch analysis in scripts and notebooks without writing my own loop |

---

## 3. Scope

### In Scope
- CLI: comma-separated ticker input at the existing ticker prompt, OR a `--tickers` flag accepting a comma-separated list; the flag takes precedence and skips the interactive prompt
- CLI: single shared configuration (LLM provider, model, analysis date, analyst selection, research depth, language) applied to all tickers in the batch
- Per-ticker asset type detection using `detect_asset_type()` for each ticker individually; cross-type batches (e.g. stocks + crypto in the same batch) are supported
- Sequential execution: one ticker completes fully before the next begins
- Per-ticker auto-save to disk immediately after each analysis completes (existing save flow reused)
- Error isolation: only `Exception` subclasses are caught and isolated per ticker; `KeyboardInterrupt` and `SystemExit` always propagate
- Post-run summary table printed to the terminal once all tickers have been processed
- Python API: `propagate_many(tickers, date)` convenience method returning a list of `BatchTickerResult` objects

### Out of Scope
- Parallel or concurrent analysis of multiple tickers
- Per-ticker overrides of LLM provider, date, or analyst selection within a single batch run
- Cross-ticker portfolio optimisation, correlation analysis, or position sizing
- Streaming partial results to a file during the run (results saved ticker-by-ticker, not streamed)
- A dedicated batch config file format (YAML/JSON watchlist input)

### Assumptions
- **Graph reuse:** `TradingAgentsGraph` is initialised once before the batch loop; `propagate()` is called once per ticker. No graph recompilation occurs between tickers. This is architecturally sound: `propagate()` creates a fresh `AgentState` per call and does not mutate graph topology.
- **Refactoring scope:** The current `run_analysis()` function in `cli/main.py` has `selections["ticker"]` wired into results directory creation, log file paths, spinner text, and graph initialisation. Implementing batch mode requires extracting ticker as a per-iteration parameter rather than a single selection value. This refactoring of `run_analysis()` is explicitly in scope for this feature.
- **Message buffer rebinding:** The `message_buffer` in `cli/main.py` has its `add_message`, `add_tool_call`, and `update_report_section` methods monkey-patched with closures that capture per-ticker `log_file` and `report_dir` paths. The batch loop must re-bind these decorators for each ticker using that ticker's results directory. The `_processed_message_ids` set and all per-analysis state on the buffer must be cleared between tickers.
- **Stats handler scope:** A new `StatsCallbackHandler` is created per ticker. Stats are displayed after each individual ticker's analysis completes, not aggregated across the batch.
- **Asset type detection boundary:** `detect_asset_type()` currently lives in `cli/utils.py` (CLI layer). `TradingAgentsGraph` (library layer) must not import from the CLI. A lightweight internal detection function using the same `CRYPTO_SUFFIXES` logic will be added to `tradingagents/` (e.g., `tradingagents/dataflows/utils.py`) as part of this feature. The CLI will continue using its own copy; both functions share the same CRYPTO_SUFFIXES constant but live in separate layers.
- The existing per-ticker auto-save path (`results/{TICKER}/{DATE}/`) is sufficient; no new directory structure is required.
- Rate limits and API costs are the user's responsibility; no automatic throttling or cost-cap is added.
- A batch of one ticker behaves identically to the current single-ticker flow.

---

## 4. Requirements

### Domain: CLI Batch Input (REQ-BATCH)

---

#### REQ-BATCH-01 — Multi-ticker input at the CLI

**Description:** The CLI `analyze` command accepts multiple ticker symbols in a single invocation. The user may enter a comma-separated list at the existing ticker prompt, or pass `--tickers AAPL,MSFT,NVDA` as a flag. When `--tickers` is present the interactive ticker prompt is skipped. Each symbol is normalised using the existing `normalize_ticker_symbol()` function (strips whitespace, uppercases, preserves exchange suffixes such as `.TO`, `.T`, `.HK`). Deduplication preserves first-occurrence order.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | the CLI is launched with `tradingagents analyze` | the user enters `AAPL, MSFT, NVDA` at the ticker prompt (spaces optional) | `normalize_ticker_symbol()` is called on each token; the resolved list is `["AAPL", "MSFT", "NVDA"]` |
| AC2 | Trader | the CLI is launched with `tradingagents analyze --tickers AAPL,MSFT,NVDA` | the command starts | the interactive ticker prompt is not displayed; the batch list is `["AAPL", "MSFT", "NVDA"]` |
| AC3 | Trader | a single ticker is entered (no comma, no `--tickers` flag) | any entry method | behaviour is identical to the current single-ticker flow |
| AC4 | Trader | the ticker list contains duplicates (e.g. `NVDA,AAPL,NVDA`) | the command starts | duplicates are removed preserving first-occurrence order: `["NVDA", "AAPL"]`; each unique ticker is analysed once |
| AC5 | Trader | an empty string or blank input is provided | the user submits the ticker prompt | the existing validation error is shown and the prompt is re-displayed |
| AC6 | Trader | a batch contains both a stock (`AAPL`) and a crypto token (`BTC-USD`) and `propagate()` is mocked | the batch executes | the CLI calls the library-internal asset type detection per ticker; `propagate('AAPL', …, asset_type='stock')` and `propagate('BTC-USD', …, asset_type='crypto')` are called, verified by mock call inspection |

**Dependencies:** None

---

#### REQ-BATCH-02 — Shared configuration across all tickers

**Description:** All configuration choices made during the setup prompts (LLM provider, model, analysis date, analyst selection, research depth, output language) apply uniformly to every ticker in the batch. Asset type is the sole per-ticker value — it is detected automatically per ticker and is not a user-configurable shared setting. The user is prompted for shared settings once; no per-ticker configuration prompts appear.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-02

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of three tickers is configured with `anthropic` provider and `2026-05-27` date | all three analyses run | the single `TradingAgentsGraph` instance (initialised once before the loop) is used for all three `propagate()` calls with the same provider, model, date, and analyst set; asset type is determined per ticker by the library-internal asset type detection function |
| AC2 | Trader | a batch run is in progress | the second ticker begins | no configuration prompts are re-displayed; the loop advances automatically |

**Dependencies:** REQ-BATCH-01

---

#### REQ-BATCH-03 — Sequential execution

**Description:** Tickers are analysed one at a time in the order provided. The next ticker's `propagate()` call must not be made until the current ticker's `propagate()` call has returned. This is a strict ordering constraint, not a timing assertion.

**Design constraint:** The batch loop must not invoke `propagate(ticker_N)` until `propagate(ticker_{N-1})` has returned. Verified by mock call order, not by wall-clock timing.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01, US-02

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | `propagate()` is mocked and a batch of `["AAPL", "MSFT"]` executes | the batch completes | `mock.call_args_list == [call("AAPL", …), call("MSFT", …)]` — exact equality on the full call list confirms AAPL was called first and MSFT second with no interleaving |
| AC2 | Trader | AAPL's `propagate()` call returns | the batch loop advances | MSFT's `propagate()` is called immediately in the same thread without user interaction |

**Dependencies:** REQ-BATCH-01, REQ-BATCH-02

---

#### REQ-BATCH-04 — Error isolation

**Description:** If a ticker's analysis raises an `Exception` subclass, it is caught, and a failure line is printed to the terminal in the format `[FAILED] {TICKER}: {ExceptionClassName}`. The batch continues with the next ticker. `KeyboardInterrupt` and `SystemExit` are not caught and always propagate immediately, aborting the batch.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-04

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of `["AAPL", "BADTICKER", "NVDA"]` is running and `propagate("BADTICKER", …)` raises `ValueError` | the exception is raised | the string `[FAILED] BADTICKER: ValueError` is printed to the terminal, and `propagate("NVDA", …)` is subsequently called |
| AC2 | Trader | one or more tickers fail | the batch completes | the CLI exits with exit code `1`; the post-run summary table (REQ-BATCH-06) serves as the failure summary — failed tickers appear as rows with `Failed` in the **Status** column |
| AC3 | Trader | all tickers succeed | the batch completes | the CLI exits with exit code `0` |
| AC4 | Trader | all tickers in the batch fail | the batch completes | the CLI exits with exit code `1`; the summary table is still printed with all rows showing `Failed`; no partial results are suppressed |
| AC5 | Trader | `propagate("AAPL", …)` raises `KeyboardInterrupt` | the exception is raised | the batch loop does not catch it; the process exits immediately without printing `[FAILED]`. Verified via `pytest.raises(KeyboardInterrupt)` on the batch loop function directly, not via `CliRunner` (which suppresses `KeyboardInterrupt`). |

**Dependencies:** REQ-BATCH-01, REQ-BATCH-03

---

#### REQ-BATCH-05 — Per-ticker auto-save

**Description:** Each ticker's full analysis report is saved to disk immediately after its `propagate()` call returns and before the next ticker begins. The save path follows the existing convention: `results/{TICKER}/{DATE}/`. The message_buffer decorators are rebound to this directory before the ticker's analysis starts.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-05

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of `["AAPL", "MSFT"]` runs with `propagate()` mocked to return a valid `final_state` | AAPL's mock returns | `results/AAPL/{DATE}/` contains the saved report; when `save_report_to_disk()` is invoked for AAPL, `propagate` has been called exactly once (for AAPL only, call count for MSFT is 0) |
| AC2 | Trader | a batch of `["AAPL", "MSFT", "NVDA"]` is run with `propagate()` mocked to raise `Exception` on the third call | the third call raises | `results/AAPL/{DATE}/` and `results/MSFT/{DATE}/` exist on disk; `results/NVDA/{DATE}/` does not |
| AC3 | Trader | `save_report_to_disk()` raises an `OSError` for one ticker (e.g. disk full) | the save fails | the error is caught and treated as a non-fatal batch failure (same behaviour as REQ-BATCH-04 AC1); the batch continues |

**Dependencies:** REQ-BATCH-03, REQ-BATCH-04

---

#### REQ-BATCH-06 — Post-run summary table

**Description:** After all tickers in the batch have been processed, a summary table is printed to the terminal. The table has one row per ticker with columns: **Ticker**, **Decision**, **Status**. The **Decision** value is extracted from the `final_trade_decision` key of the graph's final state dict; the first non-empty line of that string is used, truncated to 50 characters if longer. For batch runs where `"wheel"` was included in the analyst selection (`"wheel" in selected_analyst_keys`), the **Decision** value is instead `Approved` or `Rejected` derived from `WheelCandidateReport.approved` parsed from the `wheel_candidate_report` state field. If `wheel_candidate_report` is `None` or absent in state, or if `WheelCandidateReport.model_validate_json()` raises during parsing (malformed JSON), the **Decision** cell shows `N/A` and **Status** remains `Success`. Failed tickers show an empty **Decision** and `Failed` in **Status**.

No summary table is printed for a single-ticker invocation.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-03

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of three tickers completes with all succeeding | the last ticker finishes | a table with three rows is printed; each row has the ticker symbol, the first non-empty line of `final_trade_decision` truncated to 50 characters if longer, and `Success` |
| AC2 | Trader | one ticker in the batch failed | the summary is printed | the failed ticker's row shows `Failed` in **Status** and an empty **Decision** cell |
| AC3 | Trader | a single-ticker invocation runs | it completes | no summary table is printed; the existing per-ticker output is unchanged |
| AC4 | Trader | `"wheel"` was included in the analyst selection for this batch run | the batch summary is printed | the **Decision** column shows `Approved` (if `WheelCandidateReport.approved == True`) or `Rejected` (if `False`); if `model_validate_json()` raises, **Decision** shows `N/A` and **Status** shows `Success` |

**Dependencies:** REQ-BATCH-03, REQ-BATCH-04

---

### Domain: Python API (REQ-API)

---

#### REQ-API-01 — `propagate_many` convenience method

**Description:** `TradingAgentsGraph` exposes a `propagate_many(tickers, date, asset_types=None)` method where `asset_types: list[str] | None`. When `asset_types` is `None` (the default), the method calls a library-internal detection function in `tradingagents/` per ticker to determine asset type (stock or crypto) using `CRYPTO_SUFFIXES` suffix matching — no import from the CLI layer. When `asset_types` is provided as a list, those values are used directly (the caller is responsible for ensuring list length matches `tickers`; if lengths differ, `ValueError` is raised with a descriptive message). The CLI passes `None` to trigger auto-detection; script callers may pass explicit types. For each ticker, `propagate(ticker, date, asset_type=detected_or_provided_type)` is called. Returns a `list[BatchTickerResult]` in input order. `BatchTickerResult` is a dataclass with fields: `ticker: str`, `state: dict | None`, `decision: str | None`, `error: Exception | None`. On success: `state` and `decision` are populated, `error` is `None`. On failure: `state` and `decision` are `None`, `error` holds the caught exception. Only `Exception` subclasses are caught; `KeyboardInterrupt` and `SystemExit` propagate.

**Priority:** P2
**Phase:** 1
**Source user stories:** US-06

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Developer | `ta.propagate_many(["AAPL", "MSFT"], "2026-05-27")` is called with `propagate()` mocked | the call completes | a list of two `BatchTickerResult` objects is returned in input order; both have `error=None` and non-None `state` and `decision` |
| AC2 | Developer | `propagate_many(["AAPL", "BADTICKER"], "2026-05-27")` is called with `propagate("BADTICKER", …)` mocked to raise `ValueError` and `propagate("AAPL", …)` mocked to succeed | the call completes | the BADTICKER result has `state=None`, `decision=None`, `error=<ValueError instance>`; the AAPL result is populated normally |
| AC3 | Developer | `ta.propagate_many(["AAPL"], "2026-05-27")` is called with `propagate()` mocked to return a deterministic `(state, decision)` tuple | it completes | `result[0].decision == ta.propagate("AAPL", "2026-05-27")[1]` — the second element of the mocked `propagate()`'s `(final_state, decision)` return tuple |
| AC4 | Developer | `ta.propagate_many(["AAPL", "BTC-USD"], "2026-05-27")` is called with `asset_types=None` and `propagate()` mocked | it completes | the library-internal detection function determines `asset_type="stock"` for AAPL and `asset_type="crypto"` for BTC-USD; `propagate("AAPL", …, asset_type="stock")` and `propagate("BTC-USD", …, asset_type="crypto")` are called with those types |
| AC5 | Developer | `ta.propagate_many(["AAPL"], "2026-05-27", asset_types=["crypto"])` is called with `propagate()` mocked | it completes | `propagate("AAPL", …, asset_type="crypto")` is called with the explicitly provided type, bypassing internal detection |

**Dependencies:** None (wraps existing `propagate`)

---

### Domain: Non-Functional Requirements (REQ-NFR)

---

#### REQ-NFR-01 — No regressions on single-ticker flow

**Description:** The existing single-ticker interactive flow must behave identically before and after this feature ships. No prompts, display output, save paths, or graph behaviour may change for single-ticker invocations. Regression is verified by a parameterised integration test that exercises both the pre-feature single-ticker path and the post-feature single-ticker path through the same helper, asserting on: (a) the sequence of `questionary` prompt calls (mocked), (b) the results directory path format `results/{TICKER}/{DATE}/`, and (c) the set of Rich panel titles rendered to the console. This baseline integration test is created as part of this feature's test suite — it does not pre-exist and must be established before the feature is considered complete.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | `propagate()` and `questionary` are mocked; a single ticker `AAPL` is analysed via the updated CLI | analysis completes | the ordered list of `questionary` prompt call names, the resolved results path `results/AAPL/{DATE}/`, and the set of Rich panel titles are identical to those asserted in the pre-feature baseline integration test |

**Dependencies:** REQ-BATCH-01

---

#### REQ-NFR-02 — Progress indication between tickers

**Description:** The terminal must clearly indicate which ticker is currently being analysed and how many remain. The header format is exactly: `[{N}/{TOTAL}] Analyzing {TICKER} on {DATE}` where `N` is the 1-based index, `TOTAL` is the total ticker count, `TICKER` is the normalised symbol, and `DATE` is the analysis date in `YYYY-MM-DD` format. This line is printed before the analysis output for that ticker.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-01, US-04

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of five tickers is running and `propagate()` is mocked | the third ticker begins | the terminal output contains the string `[3/5] Analyzing {TICKER} on {DATE}` matching the pattern `\[\d+/\d+\] Analyzing \S+ on \d{4}-\d{2}-\d{2}` before that ticker's analysis output |

**Dependencies:** REQ-BATCH-03

---

## 5. Dependency Map

```
REQ-BATCH-01 (multi-ticker input)
  └── REQ-BATCH-02 (shared config)
        └── REQ-BATCH-03 (sequential execution)
              ├── REQ-BATCH-04 (error isolation)
              │     └── REQ-BATCH-05 (per-ticker save)
              └── REQ-BATCH-06 (summary table)
                    └── REQ-BATCH-04

REQ-API-01 (propagate_many) — independent, wraps propagate()

REQ-NFR-01 — cross-cuts all BATCH reqs
REQ-NFR-02 — depends on REQ-BATCH-03
```

---

## 6. Open Questions

| # | Question | Impact | Owner |
|---|---|---|---|
| OQ-01 | Should `--tickers` accept a path to a text file (one ticker per line) as an alternative input form? | Scope — adds file-input parsing | User |
| OQ-02 | Should the summary table include per-ticker wall-clock duration? | P2 UX nicety — low effort | User |
| OQ-03 | For wheel mode batches, should the summary table include IV Rank alongside Approved/Rejected? | Scope of REQ-BATCH-06 AC4 | User |
