# FSPEC — Multi-Ticker Sequential Analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-28 |
| **Upstream** | REQ → **FSPEC** |
| **Downstream** | TSPEC, PROPERTIES |
| **Cross-Reviews** | — |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2026-05-28 | Initial draft |

---

## Scope

This FSPEC covers three behaviorally complex flows that engineers must not interpret independently:

| FSPEC ID | Title | Linked REQ |
|---|---|---|
| FSPEC-BATCH-01 | Batch Input and Shared Configuration Setup | REQ-BATCH-01, REQ-BATCH-02 |
| FSPEC-BATCH-02 | Per-Ticker Execution Loop | REQ-BATCH-03, REQ-BATCH-04, REQ-BATCH-05, REQ-NFR-02 |
| FSPEC-BATCH-03 | Post-Run Summary Table Decision Logic | REQ-BATCH-06 |

Not FSPECed (sufficient REQ detail, no multi-step branching for PM to resolve):
- REQ-API-01 (`propagate_many` — linear contract with typed signature)
- REQ-NFR-01 (regression test — test infrastructure concern, not a product flow)

---

## FSPEC-BATCH-01 — Batch Input and Shared Configuration Setup

**Linked requirements:** REQ-BATCH-01, REQ-BATCH-02

### Behavioral Flow

```
START: user runs `tradingagents analyze [--tickers CSV]`
        │
        ▼
Step 1: Ticker Resolution
  ├── IF --tickers flag present
  │     └── Parse flag value as comma-separated string
  │           → skip interactive ticker prompt entirely
  └── IF no --tickers flag
        └── Display interactive ticker prompt
              ├── IF blank/empty input → show validation error, re-prompt (loop)
              └── IF non-empty input → accept value
        ↓
  Split on comma → strip whitespace from each token
  Apply normalize_ticker_symbol() to each token
  Deduplicate: retain first occurrence, discard subsequent duplicates
  ↓
  Result: ordered_tickers = [TICKER_1, TICKER_2, …] (unique, normalised)
        │
        ├── IF len(ordered_tickers) == 1
        │     → SINGLE-TICKER PATH: behave identically to pre-feature flow
        │       (no batch loop, no summary table, no progress headers)
        │
        └── IF len(ordered_tickers) > 1
              → BATCH PATH: continue to Step 2

Step 2: Shared Configuration Prompts
  Display shared config prompts ONCE (same prompts as current single-ticker flow):
    - Output language
    - LLM provider
    - Deep-think model
    - Quick-think model
    - Analysis date
    - Analyst selection
    - Research depth
  Collect all responses → config dict
  ↓
  Initialise TradingAgentsGraph ONCE using config dict
  (Graph is reused for all tickers; not re-initialised per ticker)
  ↓
  → Proceed to FSPEC-BATCH-02 (per-ticker execution loop)
```

### Business Rules

| ID | Rule |
|---|---|
| BR-01 | `--tickers` flag takes absolute precedence; the interactive prompt is never shown if the flag is present, even if the flag value is malformed |
| BR-02 | Normalisation via `normalize_ticker_symbol()` is applied to every token from both input paths; exchange suffixes (`.TO`, `.T`, `.HK`) are preserved |
| BR-03 | Deduplication is first-occurrence order: `NVDA,AAPL,NVDA` → `[NVDA, AAPL]` |
| BR-04 | A single-token result (after dedup) routes to the existing single-ticker flow unchanged; no batch infrastructure is activated |
| BR-05 | `TradingAgentsGraph` is constructed exactly once after all config prompts complete; it is not constructed per ticker |

### Edge Cases

| Scenario | Behaviour |
|---|---|
| `--tickers` value is all-blank (e.g. `--tickers "  "`) | After normalisation, zero tokens remain → treat as empty input → show validation error, prompt interactively OR exit with usage error. Engineers must decide which; flag for TSPEC. |
| `--tickers` produces a single unique ticker after dedup | Route to single-ticker path (BR-04) |
| Batch contains both stock and crypto (e.g. `AAPL,BTC-USD`) | Accept cross-type batches; asset type is NOT detected at this step — it is detected per ticker inside the loop (FSPEC-BATCH-02) |
| User selects "Wheel Analyst" without any standard analysts | Apply the existing auto-fallback (all four standard analysts added with a warning); this behaviour is unchanged |

### Acceptance Tests

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AT1 | Trader | `tradingagents analyze --tickers AAPL,MSFT` | command starts | ticker prompt is not shown; `ordered_tickers == ["AAPL", "MSFT"]`; config prompts appear once |
| AT2 | Trader | interactive prompt receives ` nvda , AAPL , nvda ` | user submits | `ordered_tickers == ["NVDA", "AAPL"]` (normalised, deduped first-occurrence) |
| AT3 | Trader | single ticker `AAPL` entered (no comma) | command proceeds | no batch loop; behaviour identical to pre-feature single-ticker flow |
| AT4 | Trader | `tradingagents analyze --tickers AAPL` | command starts | single-token result after dedup → single-ticker path activated |
| AT5 | Trader | `tradingagents analyze` and user submits blank | prompt displayed | validation error shown; prompt re-displayed without advancing |

### Open Questions

| # | Question |
|---|---|
| OQ-F-01 | What is the exact behaviour when `--tickers "  "` (all-blank flag value) is provided? Options: (a) show interactive prompt, (b) exit with a usage error message. |

---

## FSPEC-BATCH-02 — Per-Ticker Execution Loop

**Linked requirements:** REQ-BATCH-03, REQ-BATCH-04, REQ-BATCH-05, REQ-NFR-02

### Behavioral Flow

```
INPUT: ordered_tickers (N ≥ 2), config, graph (TradingAgentsGraph instance)
       failed_tickers = []
        │
        ▼
FOR EACH ticker at index i (1-based) in ordered_tickers:

  Step 1: Progress Header
    Print: "[{i}/{N}] Analyzing {ticker} on {DATE}"
    ↓
  Step 2: Setup Per-Ticker State
    Detect asset_type = library_internal_detect(ticker)
    Create fresh StatsCallbackHandler for this ticker
    Create results directory: results/{TICKER}/{DATE}/
    Re-bind message_buffer decorators to this ticker's log_file and report_dir
    Clear message_buffer._processed_message_ids and all per-analysis state
    ↓
  Step 3: Execute Analysis
    TRY:
      final_state, decision = graph.propagate(ticker, date, asset_type=asset_type)
      ↓
      Step 4: Save Report (inside try block)
        TRY:
          save_report_to_disk(final_state, ticker, results_dir)
          record (ticker, final_state, decision) as SUCCESS
        EXCEPT OSError:
          print: "[FAILED] {ticker}: OSError"
          record ticker as FAILED
          append ticker to failed_tickers
          CONTINUE to next ticker
    ↓
    EXCEPT KeyboardInterrupt:
      DO NOT CATCH → propagate immediately (batch aborts, no [FAILED] printed)
    ↓
    EXCEPT SystemExit:
      DO NOT CATCH → propagate immediately
    ↓
    EXCEPT Exception as e:
      print: "[FAILED] {ticker}: {type(e).__name__}"
      record ticker as FAILED
      append ticker to failed_tickers
      CONTINUE to next ticker  ← loop continues with next ticker

END FOR
        │
        ▼
→ Proceed to FSPEC-BATCH-03 (summary table) with batch_results and failed_tickers
→ Exit code: 0 if failed_tickers is empty, else 1
```

### Business Rules

| ID | Rule |
|---|---|
| BR-01 | Only `Exception` subclasses are caught per ticker; `KeyboardInterrupt` and `SystemExit` always propagate |
| BR-02 | Save failure (`OSError`) is treated identically to analysis failure: ticker is marked FAILED, `[FAILED]` line is printed, loop continues |
| BR-03 | Progress header `[N/TOTAL] Analyzing TICKER on DATE` is printed **before** any analysis output for that ticker |
| BR-04 | `message_buffer` must be fully reset per ticker: decorators rebound to the new ticker's paths, `_processed_message_ids` cleared, per-analysis state cleared |
| BR-05 | A new `StatsCallbackHandler` is created per ticker; stats are displayed at the end of each individual ticker's analysis, not accumulated |
| BR-06 | Library-internal asset type detection (`_detect_asset_type(ticker)` in `tradingagents/`) is called per ticker in the loop; CLI layer's `detect_asset_type()` is **not** called here |

### Edge Cases

| Scenario | Behaviour |
|---|---|
| First ticker fails | `[FAILED]` printed; loop continues from second ticker; no state carried over |
| All tickers fail | Loop completes; all tickers recorded as FAILED; summary table still printed; exit code 1 |
| `propagate()` raises `KeyboardInterrupt` | Propagates immediately; batch aborts at that point; no summary table; no `[FAILED]` line; partial disk saves are preserved for completed tickers |
| `propagate()` succeeds but `save_report_to_disk()` raises `OSError` | Ticker recorded as FAILED; `[FAILED] TICKER: OSError` printed; loop continues; analysis result is discarded for that ticker |
| Batch of exactly one ticker (after upstream dedup) | This case is blocked upstream (FSPEC-BATCH-01 BR-04 routes it to single-ticker flow); this loop never executes for N=1 |

### Acceptance Tests

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AT1 | Trader | batch `["AAPL", "BADTICKER", "NVDA"]`; `propagate("BADTICKER")` raises `ValueError` | loop executes | `[FAILED] BADTICKER: ValueError` printed; `propagate("NVDA")` subsequently called; NVDA succeeds |
| AT2 | Trader | `propagate("AAPL")` raises `KeyboardInterrupt` | exception raised | no `[FAILED]` line printed; loop does not catch; batch aborts |
| AT3 | Trader | batch of 3; `save_report_to_disk()` raises `OSError` on ticker 2 | save fails | `[FAILED] TICKER2: OSError` printed; ticker 3 analysis proceeds; `results/TICKER2/` may or may not exist |
| AT4 | Trader | batch of 5 tickers; third begins | progress header printed | output contains `[3/5] Analyzing {TICKER} on {DATE}` matching `\[\d+/\d+\] Analyzing \S+ on \d{4}-\d{2}-\d{2}` |
| AT5 | Trader | all 3 tickers fail | batch completes | summary table printed with 3 `Failed` rows; exit code 1 |

---

## FSPEC-BATCH-03 — Post-Run Summary Table Decision Logic

**Linked requirements:** REQ-BATCH-06

### Behavioral Flow

```
INPUT: N (total tickers), batch_results list, failed_tickers list,
       selected_analyst_keys (from config), wheel_mode = ("wheel" in selected_analyst_keys)
        │
        ├── IF N == 1 (single-ticker path) → DO NOT PRINT TABLE → END
        │
        └── IF N > 1 (batch path):

  Build table rows (one per ticker, in original input order):

  FOR EACH ticker result in batch_results:

    ├── IF ticker in failed_tickers:
    │     row = {Ticker: ticker, Decision: "", Status: "Failed"}
    │
    └── IF ticker succeeded:
          ├── IF wheel_mode == True:
          │     TRY:
          │       report_raw = final_state.get("wheel_candidate_report")
          │       IF report_raw is None or absent:
          │         decision_cell = "N/A"
          │       ELSE:
          │         report = WheelCandidateReport.model_validate_json(report_raw)
          │         decision_cell = "Approved" if report.approved else "Rejected"
          │     EXCEPT (ValidationError, JSONDecodeError, any Exception):
          │       decision_cell = "N/A"
          │     row = {Ticker: ticker, Decision: decision_cell, Status: "Success"}
          │
          └── IF wheel_mode == False (standard mode):
                raw_decision = final_state.get("final_trade_decision", "")
                first_line = first non-empty line of raw_decision
                            (split on "\n", find first line where line.strip() != "")
                decision_cell = first_line[:50]  (truncate to 50 chars if longer)
                IF no non-empty line found: decision_cell = ""
                row = {Ticker: ticker, Decision: decision_cell, Status: "Success"}

  END FOR

  Print Rich table with columns: Ticker | Decision | Status
  (one row per ticker in input order)

  Determine exit code:
    IF failed_tickers is empty → sys.exit(0)
    ELSE → sys.exit(1)

END
```

### Business Rules

| ID | Rule |
|---|---|
| BR-01 | No summary table is printed when N == 1 (single-ticker path) |
| BR-02 | `wheel_mode` is determined by whether `"wheel"` is in `selected_analyst_keys` — NOT by whether `wheel_candidate_report` exists in state |
| BR-03 | In wheel mode, if `wheel_candidate_report` is `None`, absent, or unparseable (any exception during `model_validate_json()`), the Decision cell shows `N/A` and Status remains `Success` |
| BR-04 | In standard mode, the Decision value is the first non-empty line of `final_trade_decision`, truncated to 50 characters. "First non-empty line" means the first line after splitting on `\n` where `.strip() != ""` |
| BR-05 | If `final_trade_decision` is empty, absent, or contains only blank lines, the Decision cell is empty (not `N/A`) |
| BR-06 | Failed tickers always show an empty Decision cell regardless of mode |
| BR-07 | Rows appear in the same order as the original input ticker list |
| BR-08 | Exit code is determined after the table is printed: 0 if zero failures, 1 if any failure |

### Edge Cases

| Scenario | Behaviour |
|---|---|
| `wheel_mode` True but all wheel runs rejected | All rows show `Rejected`; Status is `Success` for all; exit code 0 |
| `wheel_mode` True, `wheel_candidate_report` present and valid for some tickers, `None` for others | Per-ticker: valid → Approved/Rejected; None → N/A; both show Status=Success |
| Standard mode, `final_trade_decision` is `None` | Decision cell is empty; Status is `Success` |
| Standard mode, first line of `final_trade_decision` is exactly 50 characters | No truncation; shown as-is |
| Standard mode, first line is 51 characters | Shown as 50 characters (truncated) |
| Standard mode, `final_trade_decision` is `"\n\n\nBuy\n"` | First non-empty line is `"Buy"`; Decision shows `"Buy"` |
| Mixed batch: some tickers failed, some succeeded | Failed rows: empty Decision, `Failed` Status; success rows: populated Decision, `Success` Status; table contains all rows |

### Acceptance Tests

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AT1 | Trader | batch of 3 succeeds; standard mode; `final_trade_decision = "Buy NVDA\nRationale..."` | table printed | row shows `"Buy NVDA"` in Decision (10 chars, no truncation); Status `Success` |
| AT2 | Trader | batch of 3; one ticker failed | table printed | failed ticker row: Decision empty, Status `Failed`; other rows: Decision populated, Status `Success` |
| AT3 | Trader | single-ticker invocation | analysis completes | no summary table printed |
| AT4 | Trader | wheel mode; `wheel_candidate_report` parses with `approved=True` | table printed | Decision shows `Approved`; Status `Success` |
| AT5 | Trader | wheel mode; `wheel_candidate_report` is `None` in state | table printed | Decision shows `N/A`; Status `Success` |
| AT6 | Trader | wheel mode; `wheel_candidate_report` is malformed JSON | table printed | Decision shows `N/A`; Status `Success` |
| AT7 | Trader | standard mode; `final_trade_decision` first line is 75 characters | table printed | Decision shows first 50 characters of that line |
| AT8 | Trader | all tickers fail | table printed; process exits | all rows show `Failed`; exit code is 1 |
| AT9 | Trader | all tickers succeed | table printed; process exits | all rows show `Success`; exit code is 0 |

### Open Questions

| # | Question |
|---|---|
| OQ-F-02 | Should the summary table be saved to disk (e.g., as `results/batch-summary-{DATE}.md`) in addition to being printed to the terminal? If yes, the save path and format need specifying. |
| OQ-F-03 | Should the table include a wall-clock duration column per ticker (OQ-02 from REQ)? Low effort to add; deferred pending user answer. |
