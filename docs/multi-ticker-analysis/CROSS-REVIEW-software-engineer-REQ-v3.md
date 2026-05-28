# Cross-Review: software-engineer — REQ

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 3

---

## v2 Finding Resolution

All five v2 findings are resolved in v0.3.0:
- F-01 ✅ BATCH-06 trigger changed to `"wheel" in selected_analyst_keys`
- F-02 ✅ API-01 description specifies `detect_asset_type()` per ticker + AC4 added
- F-03 ✅ BATCH-03 AC1 uses `call_args_list` exact equality
- F-04 ✅ BATCH-02 AC1 uses "the single TradingAgentsGraph instance"
- F-05 ✅ BATCH-05 AC1 uses call-count assertion on `propagate`

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | High | Cross-Feature | `detect_asset_type()` lives in `cli/utils.py` (CLI layer). REQ-API-01 mandates that `TradingAgentsGraph.propagate_many()` (in `tradingagents/graph/trading_graph.py`, library layer) calls it. This creates an import from library → CLI, inverting the dependency direction: the library would depend on the CLI. The correct fix is one of: (a) move `detect_asset_type()` to `tradingagents/` (e.g., `tradingagents/dataflows/utils.py`) and import it from there in both CLI and `propagate_many`; or (b) make `propagate_many` accept an optional `asset_types: list[str] | None = None` parameter, leaving asset-type detection to the caller (CLI passes it; scripts that call the API directly pass `None` to trigger auto-detection via a library-internal function). The REQ must resolve this boundary before TSPEC can prescribe the correct implementation. | REQ-API-01; §3 Assumptions |
| F-02 | Medium | Local | REQ-BATCH-06 does not handle the case where wheel was selected (`"wheel" in selected_analyst_keys`) but `wheel_candidate_report` is `None` or absent in `final_state`. `AgentState.wheel_candidate_report` is typed `Optional[str]`; it is `None` when the WheelAnalyst did not run or failed silently. The existing malformed-JSON fallback (`N/A` / `Success`) applies to parsing failures on a non-None value, not to a `None` value. Add a sentence: "If `wheel_candidate_report` is `None` or absent in state, the **Decision** cell shows `N/A` and **Status** remains `Success`." | REQ-BATCH-06 |
| F-03 | Low | Local | REQ-BATCH-05 AC1 intermediate-state assertion ("when `save_report_to_disk()` is invoked for AAPL, `propagate` call count for MSFT is 0") requires intercepting `save_report_to_disk()` with a side effect to inspect `propagate.call_count` mid-execution. This is testable but requires a spy/`side_effect` on `save_report_to_disk`, which is non-trivial. TSPEC should note this pattern explicitly. No REQ change needed; flagging for TSPEC awareness. | REQ-BATCH-05 |

---

## Questions

| ID | Question |
|----|---------|
| Q-01 | For F-01 resolution option (b): if the caller passes `asset_types=None`, should `propagate_many` use a library-internal detection function (duplicating CRYPTO_SUFFIXES logic), or should the REQ mandate moving `detect_asset_type` to the library? Moving it is cleaner but is a refactor affecting CLI imports. |

---

## Positive Observations

- v0.3.0 is in excellent shape. All prior High and Medium findings are resolved cleanly.
- The `BatchTickerResult` dataclass contract, `call_args_list` strict ordering, and `[FAILED] TICKER: ExceptionClass` format are all precisely implementable.
- The wheel decision trigger using `selected_analyst_keys` is architecturally correct — it avoids relying on transient state key presence.
- REQ-API-01 AC4 with `detect_asset_type` mock inspection is a clean, testable criterion.
- The malformed-JSON fallback in BATCH-06 prevents a display-path crash after a successful batch — good defensive specification.

---

## Recommendation

**Needs revision**

> F-01 is High: it exposes an import boundary inversion that makes REQ-API-01 unimplementable as written without an architectural decision the REQ must make. F-02 is Medium: the None/absent `wheel_candidate_report` case is a one-line fix in the description. Both must be addressed. F-03 is Low and requires no REQ change.
