# PROPERTIES — Multi-Ticker Sequential Analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | TE-Author (Claude Code) |
| **Version** | 0.2.0 |
| **Created** | 2026-05-29 |
| **Upstream** | REQ → FSPEC → TSPEC → PLAN → **PROPERTIES** |
| **Downstream** | IMPL tests |
| **Cross-Reviews** | `CROSS-REVIEW-product-manager-PROPERTIES.md`, `CROSS-REVIEW-software-engineer-PROPERTIES.md` |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

Project-level constraints from DECISIONS-multi-ticker-analysis.md:
- DEC-MULTI-01: library layer must not import from CLI → PROP-NEG-01 enforces this.
- DEC-MULTI-02: `MessageBuffer.reset()` via `__dict__.pop` → PROP-SAVE-04 tests the observable outcome.

---

## Property List

### Category: Functional — Input Parsing (Unit)

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-INPUT-01 | `parse_tickers_input("")` must return `[]` | Unit | REQ-BATCH-01 AC5; TSPEC §5.3 |
| PROP-INPUT-02 | `parse_tickers_input("  ")` must return `[]` | Unit | REQ-BATCH-01 AC5 |
| PROP-INPUT-03 | `parse_tickers_input("AAPL")` must return `["AAPL"]` | Unit | REQ-BATCH-01 AC1 |
| PROP-INPUT-04 | `parse_tickers_input(" nvda , AAPL , nvda ")` must return `["NVDA","AAPL"]` — whitespace stripped, uppercased, first-occurrence dedup | Unit | REQ-BATCH-01 AC1, AC4; TSPEC §5.3 |
| PROP-INPUT-05 | `parse_tickers_input("CNC.TO,BTC-USD")` must return `["CNC.TO","BTC-USD"]` — exchange suffixes and crypto suffixes preserved | Unit | REQ-BATCH-01 AC1, AC6 |
| PROP-INPUT-06 | `parse_tickers_input("NVDA,AAPL,NVDA")` must deduplicate to `["NVDA","AAPL"]` — first-occurrence order | Unit | REQ-BATCH-01 AC4 |

---

### Category: Functional — Asset Type Detection (Unit)

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-ASSET-01 | `_detect_asset_type("BTC-USD")` must return `"crypto"` | Unit | REQ-BATCH-01 AC6; TSPEC §5.1 |
| PROP-ASSET-02 | `_detect_asset_type("ETH-USDT")` must return `"crypto"` | Unit | TSPEC §5.1 |
| PROP-ASSET-03 | `_detect_asset_type("AAPL")` must return `"stock"` | Unit | TSPEC §5.1 |
| PROP-ASSET-04 | `_detect_asset_type("CNC.TO")` must return `"stock"` — exchange suffix is not a crypto suffix | Unit | TSPEC §5.1 |
| PROP-ASSET-05 | `_detect_asset_type("  btc-usd  ")` must return `"crypto"` — strip+uppercase applied | Unit | TSPEC §5.1 |

---

### Category: Contract — Cross-Layer Consistency (Unit)

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-CONTRACT-01 | `cli.utils.CRYPTO_SUFFIXES` must equal `tradingagents.dataflows.utils.CRYPTO_SUFFIXES` | Unit | DEC-MULTI-01; TSPEC §5.1 |

---

### Category: Functional — MessageBuffer Reset (Unit)

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-RESET-01 | After `reset()`, `message_buffer.messages` must be empty | Unit | REQ-BATCH-05; TSPEC §5.4 |
| PROP-RESET-02 | After `reset()`, `message_buffer._processed_message_ids` must be empty | Unit | REQ-BATCH-05; TSPEC §5.4 |
| PROP-RESET-03 | After `reset()`, `message_buffer.agent_status` must be `{}` | Unit | REQ-BATCH-05; TSPEC §5.4 |
| PROP-RESET-04 | After `reset()`, the instance-level `add_message` attribute must not exist (class method restored) | Unit | REQ-BATCH-05; TSPEC §5.4; DEC-MULTI-02 |
| PROP-RESET-05 | `reset()` on a fresh (un-patched) buffer must not raise and must leave all fields at their default empty state | Unit | TSPEC §5.4 |

---

### Category: Functional — Summary Table Logic (Unit)

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-TABLE-01 | `build_batch_summary` must return a table with rows in the same order as `ordered_tickers` | Unit | REQ-BATCH-06 BR-07; FSPEC-BATCH-03 |
| PROP-TABLE-02 | A ticker in `failed_tickers` must produce a row with empty Decision and Status `"Failed"` | Unit | REQ-BATCH-06 AC2; FSPEC-BATCH-03 |
| PROP-TABLE-03 | When `"wheel"` in `selected_analyst_keys` and `wheel_candidate_report` parses with `approved=True`, Decision must be `"Approved"` and Status `"Success"` | Unit | REQ-BATCH-06 AC4; FSPEC-BATCH-03 |
| PROP-TABLE-04 | When `"wheel"` in `selected_analyst_keys` and `wheel_candidate_report` parses with `approved=False`, Decision must be `"Rejected"` | Unit | REQ-BATCH-06 AC4 |
| PROP-TABLE-05 | When `"wheel"` in `selected_analyst_keys` and `wheel_candidate_report` is `None`, Decision must be `"N/A"` and Status `"Success"` | Unit | REQ-BATCH-06; FSPEC-BATCH-03 BR-03 |
| PROP-TABLE-06 | When `"wheel"` in `selected_analyst_keys` and `wheel_candidate_report` is malformed JSON, Decision must be `"N/A"` and Status `"Success"` | Unit | REQ-BATCH-06 AC4 |
| PROP-TABLE-07 | In standard mode, Decision must be the first non-empty line of `final_trade_decision`, truncated to 50 characters | Unit | REQ-BATCH-06 AC1; FSPEC-BATCH-03 BR-04 |
| PROP-TABLE-08 | In standard mode, if `final_trade_decision` is empty or all blank lines, Decision must be empty string (not `"N/A"`) | Unit | REQ-BATCH-06; FSPEC-BATCH-03 BR-05 |
| PROP-TABLE-09 | `build_batch_summary` must return exit code `1` when `failed_tickers` is non-empty | Unit | REQ-BATCH-04 AC2; FSPEC-BATCH-03 BR-08 |
| PROP-TABLE-10 | `build_batch_summary` must return exit code `0` when `failed_tickers` is empty | Unit | REQ-BATCH-04 AC3; FSPEC-BATCH-03 BR-08 |

---

### Category: Functional — `propagate_many` API (Unit)

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-API-01 | `propagate_many([], date)` must return `[]` and not call `propagate()` | Unit | REQ-API-01; TSPEC §5.2 |
| PROP-API-02 | `propagate_many(tickers, date)` must return `list[BatchTickerResult]` in input order | Unit | REQ-API-01 AC1 |
| PROP-API-03 | A ticker whose `propagate()` raises `Exception` must produce `BatchTickerResult(error=<exception>)` with `state=None`, `decision=None` | Unit | REQ-API-01 AC2 |
| PROP-API-04 | Subsequent tickers must still be processed after one fails | Unit | REQ-API-01 AC2 |
| PROP-API-05 | `propagate_many(tickers, date, asset_types=None)` must call `_detect_asset_type(ticker)` for each ticker | Unit | REQ-API-01 AC4; TSPEC §5.2 |
| PROP-API-06 | `propagate_many(tickers, date, asset_types=["stock","crypto"])` must pass the explicit types to `propagate()` without calling internal detection | Unit | REQ-API-01 AC5 |
| PROP-API-07 | `propagate_many` with `len(asset_types) != len(tickers)` must raise `ValueError` | Unit | REQ-API-01; TSPEC §5.2 |

---

### Category: Integration — Batch Execution Loop

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-LOOP-01 | When `propagate()` raises `ValueError` for one ticker, `[FAILED] TICKER: ValueError` must be printed and the next ticker must be analyzed | Integration | REQ-BATCH-04 AC1; FSPEC-BATCH-02 |
| PROP-LOOP-02 | When `save_report_to_disk()` raises `OSError` for one ticker, that ticker must appear in `failed_tickers` and the next ticker must proceed | Integration | REQ-BATCH-05 AC3; FSPEC-BATCH-02 |
| PROP-LOOP-03 | When all tickers fail, `batch_results` must be empty and `failed_tickers` must contain all tickers | Integration | REQ-BATCH-04 AC4; FSPEC-BATCH-02 |
| PROP-LOOP-04 | `propagate()` calls must appear in `call_args_list` in the exact order of `ordered_tickers` — strict sequential ordering | Integration | REQ-BATCH-03 AC1; FSPEC-BATCH-02 |
| PROP-LOOP-05 | `message_buffer.reset()` must be called before each ticker's `propagate()` call. Verified by patching `cli.batch.message_buffer` with a `MagicMock()` and asserting `mock_buffer.reset.call_count == len(ordered_tickers)` with each reset preceding its corresponding `propagate()` call | Integration | REQ-BATCH-05; FSPEC-BATCH-02 BR-04 |
| PROP-LOOP-06 | `graph.process_signal()` raising `Exception` must not mark the ticker as failed — ticker must still appear in `batch_results` as Success | Integration | FSPEC-BATCH-02 Step 3a |
| PROP-LOOP-07 | The progress header `[N/TOTAL] Analyzing TICKER on DATE` must appear in output before that ticker's analysis output | Integration | REQ-NFR-02 AC1; FSPEC-BATCH-02 BR-03 |

---

### Category: Integration — `analyze` Command

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-CLI-01 | `tradingagents analyze --tickers AAPL,MSFT` must not display the interactive ticker prompt | Integration | REQ-BATCH-01 AC2; FSPEC-BATCH-01 BR-01 |
| PROP-CLI-02 | `tradingagents analyze --tickers "   "` must exit with code 2 and print the usage error message | Integration | REQ-BATCH-01; FSPEC-BATCH-01 edge case |
| PROP-CLI-03 | A single-ticker invocation (no comma, no `--tickers`) must route to the existing `run_analysis()` path | Integration | REQ-BATCH-01 AC3; FSPEC-BATCH-01 BR-04 |
| PROP-CLI-04 | An interactive CSV input `"NVDA, AAPL, NVDA"` at the ticker prompt must result in a batch run for `["NVDA","AAPL"]`. Verified by mocking `propagate()` and asserting `propagate.call_args_list == [call("NVDA", ...), call("AAPL", ...)]` | Integration | REQ-BATCH-01 AC1, AC4 |
| PROP-CLI-05 | Config prompts (language, provider, model, date, analysts, depth) must appear exactly once for any batch size | Integration | REQ-BATCH-02 AC1, AC2 |

---

### Category: Integration — Regression

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-REG-01 | Single-ticker analysis via the updated `analyze` command must invoke the same questionary prompt sequence (8 prompts: ticker, language, provider, deep-model, quick-model, date, analysts, depth) as before the feature shipped | Integration | REQ-NFR-01 AC1; TSPEC §7.3 |
| PROP-REG-02 | Single-ticker analysis must produce a results directory at `results/TICKER/DATE/` matching the pre-feature path format | Integration | REQ-NFR-01 AC1 |
| PROP-REG-03 | Single-ticker analysis must render the same set of Rich panel titles as before the feature shipped (for the same analyst selection) | Integration | REQ-NFR-01 AC1 |

---

### Category: Negative Properties

| ID | Property | Test Level | REQ / TSPEC ref |
|---|---|---|---|
| PROP-NEG-01 | `tradingagents` library modules must NOT import from `cli/` at any level. Verified by an `ast`-based static import scan on all `.py` files under `tradingagents/`: assert no `from cli` or `import cli` statement exists in any module | Unit (import check) | DEC-MULTI-01; REQ §3 Assumptions |
| PROP-NEG-02 | `batch_run_loop` must NOT catch `KeyboardInterrupt` — it must propagate immediately | Integration | REQ-BATCH-04 AC5; FSPEC-BATCH-02 BR-01 |
| PROP-NEG-03 | `propagate_many` must NOT catch `KeyboardInterrupt` — it must propagate immediately | Unit | REQ-API-01; TSPEC §5.2 |
| PROP-NEG-04 | The summary table must NOT be printed for a single-ticker invocation | Integration | REQ-BATCH-06 AC3; FSPEC-BATCH-03 BR-01 |
| PROP-NEG-05 | The "Save report?" and "Display full report?" interactive prompts must NOT appear during batch mode | Integration | FSPEC-BATCH-02 BR-07 |
| PROP-NEG-06 | In standard mode, `build_batch_summary` must NOT use `"N/A"` when `final_trade_decision` is absent or blank — empty string is the correct value | Unit | FSPEC-BATCH-03 BR-05 |

---

## Coverage Matrix

| Requirement | Properties | All ACs covered? |
|---|---|---|
| REQ-BATCH-01 (P0) | PROP-INPUT-01–06, PROP-CLI-01–04 | ✅ |
| REQ-BATCH-02 (P0) | PROP-CLI-05 | ✅ |
| REQ-BATCH-03 (P0) | PROP-LOOP-04 | ✅ |
| REQ-BATCH-04 (P1) | PROP-LOOP-01, PROP-LOOP-03, PROP-TABLE-09, PROP-TABLE-10, PROP-NEG-02 | ✅ |
| REQ-BATCH-05 (P1) | PROP-LOOP-02, PROP-LOOP-05, PROP-RESET-01–05 | ✅ |
| REQ-BATCH-06 (P1) | PROP-TABLE-01–10, PROP-NEG-04 | ✅ |
| REQ-API-01 (P2) | PROP-API-01–07, PROP-NEG-03 | ✅ |
| REQ-NFR-01 (P0) | PROP-REG-01–03 | ✅ |
| REQ-NFR-02 (P1) | PROP-LOOP-07 | ✅ |
| DEC-MULTI-01 (boundary) | PROP-CONTRACT-01, PROP-ASSET-01–05, PROP-NEG-01 | ✅ |
| DEC-MULTI-02 (reset) | PROP-RESET-04 | ✅ |

**Total properties:** 43 (20 Unit, 16 Integration, 6 Negative, 1 Contract)
**Gaps:** None identified.
