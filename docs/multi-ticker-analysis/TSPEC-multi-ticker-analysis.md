# TSPEC — Multi-Ticker Sequential Analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | SE-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-29 |
| **Upstream** | REQ → FSPEC → **TSPEC** |
| **Downstream** | DECISIONS, PLAN, PROPERTIES, IMPL |
| **Cross-Reviews** | — |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

---

## 1. Overview

This TSPEC specifies the implementation of multi-ticker sequential analysis across three layers:

1. **Library layer** — `_detect_asset_type()`, `BatchTickerResult`, `TradingAgentsGraph.propagate_many()`
2. **CLI layer** — `parse_tickers_input()`, `MessageBuffer.reset()`, `build_batch_summary()`, `batch_run_loop()`, refactored `analyze` command with `--tickers` flag
3. **Test layer** — unit tests for pure functions, integration tests at CLI/graph boundaries

The implementation is entirely additive within the library layer. The CLI layer requires targeted refactoring of `run_analysis()` to extract the ticker-specific per-iteration work.

---

## 2. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Language | Python 3.10+ | Existing project constraint |
| CLI framework | Typer (existing) | `--tickers` flag added to existing `analyze` command |
| Display | Rich (existing) | Live context, table, panel — all already imported |
| Data models | Python `dataclasses` | Lightweight, no external dep; consistent with existing `WheelPosition` pattern |
| Test framework | pytest (existing) | `conftest.py` fixtures, `typer.testing.CliRunner` already in use |

No new dependencies required.

---

## 3. New and Modified Files

### New files

| File | Purpose |
|---|---|
| `tradingagents/graph/batch.py` | `BatchTickerResult` public dataclass |
| `cli/batch.py` | `BatchTickerRecord`, `build_batch_summary()`, `batch_run_loop()` |
| `tests/test_parse_tickers_input.py` | Unit tests for `parse_tickers_input()` |
| `tests/test_message_buffer_reset.py` | Unit tests for `MessageBuffer.reset()` |
| `tests/test_build_batch_summary.py` | Unit tests for `build_batch_summary()` |
| `tests/test_batch_run_loop.py` | Integration tests for `batch_run_loop()` |
| `tests/test_propagate_many.py` | Unit tests for `TradingAgentsGraph.propagate_many()` |
| `tests/test_detect_asset_type_internal.py` | Unit tests for `_detect_asset_type()` |
| `tests/test_analyze_command_batch.py` | CLI integration tests for `analyze --tickers` |

### Modified files

| File | Change |
|---|---|
| `tradingagents/dataflows/utils.py` | Add `CRYPTO_SUFFIXES`, `_detect_asset_type()` |
| `tradingagents/graph/trading_graph.py` | Add `propagate_many()`, import `BatchTickerResult` |
| `cli/utils.py` | Add `parse_tickers_input()` |
| `cli/main.py` | Add `MessageBuffer.reset()`, add `--tickers` option to `analyze`, refactor `run_analysis()` to accept `ticker` as parameter, extract `_run_single_ticker()`, add batch dispatch |

---

## 4. Data Models

### 4.1 `BatchTickerResult` — public API type

**File:** `tradingagents/graph/batch.py`

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class BatchTickerResult:
    """Public return type for propagate_many(). One record per ticker."""
    ticker: str
    state: Optional[dict]     # final_state dict; None on failure
    decision: Optional[str]   # process_signal output; None on failure
    error: Optional[Exception] # caught Exception; None on success
```

### 4.2 `BatchTickerRecord` — internal CLI type

**File:** `cli/batch.py`

```python
from dataclasses import dataclass

@dataclass
class BatchTickerRecord:
    """Internal CLI-layer record for a successfully completed ticker analysis.
    Distinct from BatchTickerResult (public API type in tradingagents/).
    """
    ticker: str
    final_state: dict
    decision: str
```

---

## 5. Module Specifications

### 5.1 `tradingagents/dataflows/utils.py` — additions

**`CRYPTO_SUFFIXES`** (module constant):
```python
CRYPTO_SUFFIXES: tuple[str, ...] = ("-USD", "-USDT", "-USDC", "-BTC", "-ETH")
```
Must be kept in sync with `cli/utils.py`'s `CRYPTO_SUFFIXES`. Both live independently in their respective layers; no cross-layer import.

**`_detect_asset_type(ticker: str) -> str`**:
- Strip and uppercase `ticker`
- Return `"crypto"` if it ends with any element of `CRYPTO_SUFFIXES`
- Return `"stock"` otherwise
- No side effects; pure function
- Does NOT import from `cli/`

### 5.2 `tradingagents/graph/trading_graph.py` — `propagate_many`

**Signature:**
```python
def propagate_many(
    self,
    tickers: list[str],
    date: str,
    asset_types: list[str] | None = None,
) -> list[BatchTickerResult]:
```

**Algorithm:**
1. If `asset_types is not None` and `len(asset_types) != len(tickers)` → raise `ValueError(f"asset_types length {len(asset_types)} != tickers length {len(tickers)}")`
2. `results: list[BatchTickerResult] = []`
3. For each `(i, ticker)` in `enumerate(tickers)`:
   - `asset_type = asset_types[i] if asset_types else _detect_asset_type(ticker)`
   - `try: state, decision = self.propagate(ticker, date, asset_type=asset_type)`
   - `results.append(BatchTickerResult(ticker=ticker, state=state, decision=decision, error=None))`
   - `except Exception as e: results.append(BatchTickerResult(ticker=ticker, state=None, decision=None, error=e))`
   - `KeyboardInterrupt` and `SystemExit` are NOT caught; they propagate
4. Return `results`

**Import:** `from tradingagents.dataflows.utils import _detect_asset_type`
**Import:** `from tradingagents.graph.batch import BatchTickerResult`

### 5.3 `cli/utils.py` — `parse_tickers_input`

**Signature:** `def parse_tickers_input(csv_string: str) -> list[str]`

**Algorithm:**
1. Split `csv_string` on `","` 
2. For each token: call `normalize_ticker_symbol(token.strip())`; discard empty results after strip
3. Deduplicate preserving first-occurrence order (use `dict.fromkeys()` pattern)
4. Return the resulting list (may be empty)

**Contract:**
- Pure function; no I/O, no side effects
- `parse_tickers_input("")` → `[]`
- `parse_tickers_input("  ")` → `[]`
- `parse_tickers_input("NVDA,AAPL,NVDA")` → `["NVDA", "AAPL"]`
- `parse_tickers_input(" nvda , AAPL , nvda ")` → `["NVDA", "AAPL"]`

### 5.4 `cli/main.py` — `MessageBuffer.reset()`

**Purpose:** Fully restore the MessageBuffer to its pre-`init_for_analysis` state so it can be reused for the next ticker without state bleed.

**Implementation:**

`MessageBuffer.__init__` must store a reference to the three original (un-patched) method objects before they can be replaced by `run_analysis`'s decorators:

```python
def __init__(self, max_length=100):
    # ... existing fields ...
    # Store originals for reset()
    self._orig_add_message = self.__class__.add_message
    self._orig_add_tool_call = self.__class__.add_tool_call
    self._orig_update_report_section = self.__class__.update_report_section
```

`reset()`:
```python
def reset(self) -> None:
    """Reset all per-analysis state for batch mode reuse."""
    self.messages.clear()
    self.tool_calls.clear()
    self._processed_message_ids.clear()
    self.agent_status = {}
    self.current_report = None
    self.final_report = None
    self.current_agent = None
    self.report_sections = {}
    self.selected_analysts = []
    # Restore original (pre-decorator) methods using instance-level __dict__ deletion
    # (instance attribute takes precedence over class attribute; deleting it restores
    # the class-level method for subsequent calls)
    for attr in ("add_message", "add_tool_call", "update_report_section"):
        self.__dict__.pop(attr, None)
```

**Rationale for `__dict__.pop`:** The decorators in `run_analysis()` assign to `message_buffer.add_message = ...` (instance attribute, shadows the class method). Deleting the instance attribute restores the class-level method without needing to store originals explicitly.

### 5.5 `cli/main.py` — `analyze` command refactoring

#### New `--tickers` option

```python
@app.command()
def analyze(
    checkpoint: bool = typer.Option(False, "--checkpoint", ...),
    clear_checkpoints: bool = typer.Option(False, "--clear-checkpoints", ...),
    tickers: Optional[str] = typer.Option(
        None,
        "--tickers",
        help="Comma-separated list of ticker symbols to analyze sequentially. "
             "Skips the interactive ticker prompt.",
    ),
):
```

#### `analyze` command flow (updated)

```python
# 1. Resolve tickers from flag or interactive prompt
if tickers is not None:
    ordered_tickers = parse_tickers_input(tickers)
    if not ordered_tickers:
        raise typer.BadParameter(
            "Error: --tickers requires at least one valid ticker symbol.",
            param_hint="'--tickers'",
        )
else:
    raw = get_ticker()           # existing interactive prompt
    ordered_tickers = parse_tickers_input(raw) if "," in raw else [raw]

# 2. Route single vs batch
if len(ordered_tickers) == 1:
    run_analysis(ticker=ordered_tickers[0], checkpoint=checkpoint)  # existing flow
else:
    run_batch_analysis(ordered_tickers, checkpoint=checkpoint)
```

**Note:** `typer.BadParameter` causes Typer to print the message and exit with code 2.

#### `run_analysis()` refactoring

`run_analysis()` is refactored to accept `ticker: str` as a required parameter (extracted from `selections`):

```python
def run_analysis(ticker: str, checkpoint: bool = False) -> None:
```

All references to `selections["ticker"]` inside `run_analysis()` are replaced with the `ticker` parameter. The interactive ticker prompt (`get_ticker()`) is moved to the `analyze` command dispatcher. The post-analysis interactive save prompt and display prompt are retained for single-ticker mode. The function signature change is backward-compatible within the codebase since the only caller is `analyze()`.

### 5.6 `cli/batch.py` — `batch_run_loop` and `build_batch_summary`

#### `batch_run_loop`

```python
def batch_run_loop(
    ordered_tickers: list[str],
    config: dict,
    graph: TradingAgentsGraph,
    selections: dict,
    checkpoint: bool = False,
) -> tuple[dict[str, BatchTickerRecord], list[str]]:
    """Run analysis for each ticker in order. Returns (batch_results, failed_tickers)."""
```

**Per-ticker steps** (see FSPEC-BATCH-02 for full pseudocode):
1. `console.print(f"[{i}/{N}] Analyzing {ticker} on {date}")`
2. `asset_type = _detect_asset_type(ticker).value`  (convert to AssetType enum string)
3. Create `results_dir = Path(config["results_dir"]) / ticker / date`; `results_dir.mkdir(...)`
4. `stats_handler = StatsCallbackHandler()`
5. `message_buffer.reset()`
6. Re-bind decorators (same 3 closures as current `run_analysis()`) closing over this ticker's `results_dir`
7. `message_buffer.init_for_analysis(pipeline_analyst_keys)`
8. `layout = create_layout()`
9. `with Live(layout, refresh_per_second=4):`
   - Stream graph and update display (reuse existing streaming logic extracted to `_stream_analysis()`)
   - On `propagate()` success: `graph.process_signal(decision)` (non-fatal), print `"✓ {ticker} complete"`, save via `save_report_to_disk()`
   - `batch_results[ticker] = BatchTickerRecord(...)`
10. Error handling per FSPEC-BATCH-02 BR-01/BR-02

**Note:** The streaming + display logic inside `run_analysis()` is extracted to `_stream_analysis(ticker, date, asset_type, graph, config, selections, ...)` which both single-ticker and batch modes call.

#### `build_batch_summary`

```python
def build_batch_summary(
    batch_results: dict[str, BatchTickerRecord],
    failed_tickers: list[str],
    selected_analyst_keys: list[str],
    ordered_tickers: list[str],
) -> tuple[Table, int]:
    """Build the Rich summary Table and determine exit code.
    
    Returns (table, exit_code) where exit_code is 0 or 1.
    Pure function — no I/O.
    """
```

**Algorithm:**
1. `wheel_mode = "wheel" in selected_analyst_keys`
2. `table = Table(...)` with columns Ticker, Decision, Status
3. For each `ticker` in `ordered_tickers`:
   - If `ticker in failed_tickers`: add row `(ticker, "", "Failed")`
   - Else look up `rec = batch_results[ticker]`:
     - If `wheel_mode`: try parse `rec.final_state.get("wheel_candidate_report")` → `"Approved"/"Rejected"/"N/A"`
     - Else: extract first non-empty line of `rec.final_state.get("final_trade_decision", "")[:50]`
     - Add row `(ticker, decision_cell, "Success")`
4. `exit_code = 1 if failed_tickers else 0`
5. Return `(table, exit_code)`

**Display (called by `run_batch_analysis()`):**
```python
console.print(table)
raise SystemExit(exit_code)
```

---

## 6. Error Handling

| Scenario | Handler | Behaviour |
|---|---|---|
| `--tickers` all-blank after parse | `analyze()` | `typer.BadParameter` → exit code 2 + message |
| `propagate()` raises `Exception` | `batch_run_loop()` inner `except Exception` | Print `[FAILED] TICKER: ExceptionClass`; append to `failed_tickers`; continue |
| `propagate()` raises `KeyboardInterrupt` | Not caught | Propagates; batch aborts; no `[FAILED]` line |
| `save_report_to_disk()` raises `OSError` | Inner `except OSError` in save block | Print `[FAILED] TICKER: OSError`; append to `failed_tickers`; continue |
| `graph.process_signal()` raises `Exception` | Non-fatal inner `except Exception` | Log warning; continue to save step |
| `propagate_many()` `asset_types` length mismatch | `propagate_many()` | `ValueError` with descriptive message |
| `propagate_many()` `propagate()` raises `Exception` | Per-ticker `except Exception` | `BatchTickerResult(error=e)`; KI/SystemExit propagate |

---

## 7. Test Strategy

### 7.1 Test levels

| Layer | Test level | Rationale |
|---|---|---|
| `parse_tickers_input()` | Unit | Pure function; no dependencies |
| `_detect_asset_type()` | Unit | Pure function; no dependencies |
| `MessageBuffer.reset()` | Unit | Isolated singleton state; no CLI needed |
| `build_batch_summary()` | Unit | Pure function; takes dict/list inputs |
| `propagate_many()` | Unit (mocked `propagate`) | Library boundary; no LLM calls |
| `batch_run_loop()` | Integration (mocked `graph.propagate`, `save_report_to_disk`) | Tests loop control flow + state mutations |
| `analyze --tickers` CLI | Integration (CliRunner + mocked graph) | Tests end-to-end command dispatch |
| Single-ticker regression | Integration (CliRunner) | REQ-NFR-01: pre/post-feature parity |

### 7.2 Test doubles

| Dependency | Double | Location |
|---|---|---|
| `TradingAgentsGraph.propagate` | `MagicMock` with configurable `side_effect` | Per test via `unittest.mock.patch` |
| `save_report_to_disk` | `MagicMock` with `side_effect` for OSError injection | Per test |
| `graph.process_signal` | `MagicMock` with `side_effect` for exception injection | Per test |
| `questionary` prompts | `CliRunner(input=...)` | CliRunner stdin |
| `TradingAgentsGraph.__init__` | `MagicMock` via `mock_llm_client` fixture | Existing `conftest.py` pattern |

### 7.3 Key test cases by file

**`tests/test_parse_tickers_input.py`**
- `""` → `[]`
- `"  "` → `[]`
- `"AAPL"` → `["AAPL"]`
- `" nvda , AAPL , nvda "` → `["NVDA", "AAPL"]`
- `"CNC.TO,BTC-USD"` → `["CNC.TO", "BTC-USD"]` (exchange suffix preserved)

**`tests/test_message_buffer_reset.py`**
- After `init_for_analysis()` + monkey-patch + `reset()`: all fields at default; `add_message` is the class method, not the closure
- `reset()` on fresh buffer: no-op, no error

**`tests/test_build_batch_summary.py`**
- All success, standard mode → correct Decision/Status per row
- One failed ticker → correct Failed row + correct exit code 1
- All failed → all Failed rows + exit code 1
- All success → exit code 0
- Wheel mode, `approved=True` → "Approved"
- Wheel mode, `wheel_candidate_report=None` → "N/A"
- Wheel mode, malformed JSON → "N/A"
- Standard mode, `final_trade_decision = "\n\nBuy NVDA\n"` → "Buy NVDA"
- Standard mode, 75-char first line → 50-char truncated decision
- `ordered_tickers` order preserved in table rows

**`tests/test_propagate_many.py`**
- All succeed: returns `list[BatchTickerResult]` in input order; all `error=None`
- One ticker raises `ValueError`: that result has `error=<ValueError>`, others succeed
- `asset_types` length mismatch → `ValueError`
- `asset_types=None`: `_detect_asset_type` called per ticker
- `asset_types=["crypto"]`: explicit type passed to `propagate()`; detection bypassed
- `KeyboardInterrupt` propagates (not caught)

**`tests/test_batch_run_loop.py`**
- AAPL succeeds, BADTICKER raises ValueError, NVDA succeeds: `failed_tickers == ["BADTICKER"]`, `batch_results` has AAPL and NVDA
- `save_report_to_disk` raises `OSError` on ticker 2: ticker 2 in `failed_tickers`, ticker 3 still runs
- All tickers fail: `batch_results == {}`, `failed_tickers == [all 3]`
- `propagate()` raises `KeyboardInterrupt`: `pytest.raises(KeyboardInterrupt)` on `batch_run_loop` call
- `process_signal()` raises `Exception`: ticker still in `batch_results` (Success), warning logged

**`tests/test_analyze_command_batch.py`**
- `--tickers AAPL,MSFT` (both mocked): propagate called twice in order; config prompts once
- `--tickers "   "`: exit code 2, error message printed
- `--tickers AAPL` (single): routes to `run_analysis` (single-ticker path)
- Interactive `" nvda , AAPL , nvda "` → batch with `["NVDA", "AAPL"]`
- `KeyboardInterrupt` propagates from loop: `pytest.raises(KeyboardInterrupt)` on loop function (not CliRunner)

**`tests/test_regression_single_ticker.py`** (REQ-NFR-01)
- With `propagate()` mocked, single-ticker via `CliRunner.invoke(app, ["analyze"], input=...)`: verify questionary prompt sequence, results path `results/AAPL/{DATE}/`, Rich panel titles — identical to pre-feature baseline asserted in same test

---

## 8. Requirements Traceability

| Requirement | Component |
|---|---|
| REQ-BATCH-01 | `parse_tickers_input()` in `cli/utils.py`; `--tickers` option in `analyze` |
| REQ-BATCH-02 | `run_batch_analysis()` shared config; single `TradingAgentsGraph` init |
| REQ-BATCH-03 | `batch_run_loop()` sequential `propagate()` calls |
| REQ-BATCH-04 | `batch_run_loop()` exception handling; `[FAILED]` format; exit codes |
| REQ-BATCH-05 | `batch_run_loop()` per-ticker `save_report_to_disk()`; `MessageBuffer.reset()` rebinding |
| REQ-BATCH-06 | `build_batch_summary()` in `cli/batch.py` |
| REQ-API-01 | `TradingAgentsGraph.propagate_many()` in `trading_graph.py`; `BatchTickerResult` in `batch.py` |
| REQ-NFR-01 | `run_analysis(ticker=...)` refactoring; regression integration test |
| REQ-NFR-02 | Progress header `f"[{i}/{N}] Analyzing {ticker} on {date}"` in `batch_run_loop()` |

---

## 9. Integration Points

| Existing component | Touch point | Change type |
|---|---|---|
| `cli/main.py :: MessageBuffer` | Add `reset()` method | Additive |
| `cli/main.py :: run_analysis()` | Accept `ticker: str` param; remove internal ticker resolution | Refactor |
| `cli/main.py :: analyze()` | Add `--tickers` option; dispatch to batch or single | Additive |
| `cli/utils.py :: normalize_ticker_symbol` | Called by `parse_tickers_input()` | Read-only |
| `cli/utils.py :: CRYPTO_SUFFIXES` | Referenced by `cli/utils.py` only; NOT imported by library | Read-only |
| `tradingagents/dataflows/utils.py` | Add library-internal `CRYPTO_SUFFIXES`, `_detect_asset_type()` | Additive |
| `tradingagents/graph/trading_graph.py` | Add `propagate_many()`; import `BatchTickerResult`, `_detect_asset_type` | Additive |
| `tradingagents/graph/analyst_execution.py` | `build_analyst_execution_plan()` called per ticker in batch loop | Read-only |
