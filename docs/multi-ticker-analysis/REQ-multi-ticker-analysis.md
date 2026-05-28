# REQ — Multi-Ticker Sequential Analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-27 |
| **Upstream** | Conversation context (user request) → **REQ** |
| **Downstream** | FSPEC, TSPEC, PROPERTIES |
| **Cross-Reviews** | — |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
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
- CLI: comma-separated ticker input at the existing ticker prompt, OR a `--tickers` flag accepting a comma-separated list
- CLI: single shared configuration (LLM provider, model, analysis date, analyst selection, research depth, language) applied to all tickers in the batch
- Sequential execution: one ticker completes fully before the next begins
- Per-ticker auto-save to disk immediately after each analysis completes (existing save flow reused)
- Error isolation: a ticker that raises an unhandled exception is logged with its error message; the batch continues
- Post-run summary table printed to the terminal once all tickers have been processed
- Python API: `propagate_many(tickers, date)` convenience method returning a list of `(state, decision)` tuples

### Out of Scope
- Parallel or concurrent analysis of multiple tickers
- Per-ticker overrides of LLM provider, date, or analyst selection within a single batch run
- Cross-ticker portfolio optimisation, correlation analysis, or position sizing
- Streaming partial results to a file during the run (results saved ticker-by-ticker, not streamed)
- A dedicated batch config file format (YAML/JSON watchlist input)

### Assumptions
- The existing `TradingAgentsGraph` and `propagate()` are reused without modification per ticker; this feature is a loop wrapper, not a graph change.
- The existing per-ticker auto-save path (`results/{ticker}/{date}/`) is sufficient; no new directory structure is required.
- Rate limits and API costs are the user's responsibility; no automatic throttling or cost-cap is added.
- A batch of one ticker behaves identically to the current single-ticker flow.

---

## 4. Requirements

### Domain: CLI Batch Input (REQ-BATCH)

---

#### REQ-BATCH-01 — Multi-ticker input at the CLI

**Description:** The CLI `analyze` command accepts multiple ticker symbols in a single invocation. The user may enter a comma-separated list at the existing ticker prompt, or pass `--tickers AAPL,MSFT,NVDA` as a flag. Both forms are equivalent.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | the CLI is launched with `tradingagents analyze` | the user enters `AAPL, MSFT, NVDA` at the ticker prompt (spaces optional) | the system normalises to `["AAPL", "MSFT", "NVDA"]` and processes all three |
| AC2 | Trader | the CLI is launched with `tradingagents analyze --tickers AAPL,MSFT,NVDA` | the command starts | the ticker prompt is skipped and the batch list is taken from the flag |
| AC3 | Trader | a single ticker is entered (no comma) | any entry method | behaviour is identical to the current single-ticker flow |
| AC4 | Trader | the ticker list contains duplicates (e.g. `AAPL,AAPL`) | the command starts | duplicates are removed and each unique ticker is analysed once |
| AC5 | Trader | an empty string or blank input is provided | the user submits the ticker prompt | the existing validation error is shown and the prompt is re-displayed |

**Dependencies:** None

---

#### REQ-BATCH-02 — Shared configuration across all tickers

**Description:** All configuration choices made during the setup prompts (LLM provider, model, analysis date, analyst selection, research depth, output language) apply uniformly to every ticker in the batch. The user is prompted once; no per-ticker prompts appear.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-02

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of three tickers is configured with `anthropic` provider and `2026-05-27` date | all three analyses run | each ticker's graph is initialised with the same provider, model, date, and analyst set |
| AC2 | Trader | a batch run is in progress | the second ticker begins | no configuration prompts are re-displayed; the loop advances automatically |

**Dependencies:** REQ-BATCH-01

---

#### REQ-BATCH-03 — Sequential execution

**Description:** Tickers are analysed one at a time in the order provided. The next ticker begins only after the current ticker's analysis (including save and display) is fully complete.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01, US-02

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of `["AAPL", "MSFT"]` is running | AAPL's analysis is streaming | MSFT's analysis has not started |
| AC2 | Trader | AAPL's analysis completes | the batch loop advances | MSFT begins immediately without user interaction |
| AC3 | Trader | a batch of N tickers runs | all complete | total wall time ≥ sum of individual run times (no parallelism) |

**Dependencies:** REQ-BATCH-01, REQ-BATCH-02

---

#### REQ-BATCH-04 — Error isolation

**Description:** If a ticker's analysis raises an unhandled exception, the error is caught, logged to the terminal with the ticker symbol and error message, and the batch continues with the next ticker. The exit code reflects whether any ticker failed.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-04

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of `["AAPL", "BADTICKER", "NVDA"]` is running | `BADTICKER` raises an exception | `BADTICKER` is marked as failed, the error is printed, and `NVDA` begins |
| AC2 | Trader | one or more tickers fail | the batch completes | the CLI exits with a non-zero exit code and prints a failure summary |
| AC3 | Trader | all tickers succeed | the batch completes | the CLI exits with code 0 |

**Dependencies:** REQ-BATCH-01, REQ-BATCH-03

---

#### REQ-BATCH-05 — Per-ticker auto-save

**Description:** Each ticker's full analysis report is saved to disk immediately after its analysis completes, before the next ticker begins. The save path follows the existing convention: `results/{TICKER}/{DATE}/`.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-05

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of `["AAPL", "MSFT"]` runs | AAPL completes | `results/AAPL/{DATE}/` contains the saved report before MSFT begins |
| AC2 | Trader | a batch run is interrupted after the second of three tickers | the user checks disk | reports for the first two tickers are present; the third is absent |
| AC3 | Trader | save fails for one ticker (e.g. disk full) | the batch continues | the save failure is logged and treated as a non-fatal error (same as REQ-BATCH-04) |

**Dependencies:** REQ-BATCH-03, REQ-BATCH-04

---

#### REQ-BATCH-06 — Post-run summary table

**Description:** After all tickers in the batch have been processed, a summary table is printed to the terminal. The table shows one row per ticker with: ticker symbol, final decision (Buy/Hold/Sell or wheel approval status), and status (success/failed).

**Priority:** P1
**Phase:** 1
**Source user stories:** US-03

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of three tickers completes with all succeeding | the last ticker finishes | a table with three rows is printed, one per ticker, with symbol, decision, and "Success" |
| AC2 | Trader | one ticker in the batch failed | the summary is printed | the failed ticker's row shows "Failed" and the error class; decision cell is blank |
| AC3 | Trader | a single-ticker invocation runs | it completes | no summary table is printed (single-ticker flow is unchanged) |
| AC4 | Trader | wheel mode is active | the batch summary is printed | the wheel approval verdict (Approved/Rejected) is shown in the decision column instead of Buy/Hold/Sell |

**Dependencies:** REQ-BATCH-03, REQ-BATCH-04

---

### Domain: Python API (REQ-API)

---

#### REQ-API-01 — `propagate_many` convenience method

**Description:** `TradingAgentsGraph` exposes a `propagate_many(tickers, date)` method that iterates over the ticker list, calls `propagate()` for each, collects results, and returns a list of `(ticker, state, decision)` tuples. Errors per ticker are caught and represented as `(ticker, None, None)` with the exception stored in a separate errors dict.

**Priority:** P2
**Phase:** 1
**Source user stories:** US-06

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Developer | `ta.propagate_many(["AAPL", "MSFT"], "2026-05-27")` is called | the call completes | a list of two `(ticker, state, decision)` tuples is returned in input order |
| AC2 | Developer | one ticker raises an exception inside `propagate()` | `propagate_many` continues | the failing ticker's tuple is `(ticker, None, None)`; subsequent tickers still run |
| AC3 | Developer | `propagate_many(["AAPL"], "2026-05-27")` is called with a single ticker | it completes | result is equivalent to calling `propagate("AAPL", "2026-05-27")` directly |

**Dependencies:** None (wraps existing `propagate`)

---

### Domain: Non-Functional Requirements (REQ-NFR)

---

#### REQ-NFR-01 — No regressions on single-ticker flow

**Description:** The existing single-ticker interactive flow must behave identically before and after this feature ships. No prompts, display output, save paths, or graph behaviour may change for single-ticker invocations.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a user enters a single ticker (no comma) via the existing prompt | analysis completes | all prompts, output panels, and save paths are identical to the pre-feature behaviour |

**Dependencies:** REQ-BATCH-01

---

#### REQ-NFR-02 — Progress indication between tickers

**Description:** The terminal must clearly indicate which ticker is currently being analysed and how many remain (e.g. `[2/5] Analyzing MSFT…`), so the user knows the batch is progressing and hasn't stalled.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-01, US-04

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a batch of five tickers is running | the third ticker begins | the terminal prints a header such as `[3/5] Analyzing GOOGL on 2026-05-27` before the analysis output |

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
| OQ-03 | For wheel mode batches, should the summary table include IV Rank and approved/rejected alongside the decision? | Scope of REQ-BATCH-06 AC4 | User |
| OQ-04 | Should a `--tickers-file` flag be a P1 or remain out of scope for this phase? | Phase boundary | User |
