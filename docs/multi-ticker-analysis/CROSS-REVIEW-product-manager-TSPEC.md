# Cross-Review: product-manager — TSPEC

**Reviewer:** product-manager
**Document reviewed:** docs/multi-ticker-analysis/TSPEC-multi-ticker-analysis.md
**Date:** 2026-05-29
**Iteration:** 1

---

## Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-01 | Low | Local | The TSPEC §5.5 does not mention updating the `get_ticker()` prompt text. Currently it reads "Enter the exact ticker symbol to analyze..." (singular). REQ-BATCH-01 AC1 requires that the existing ticker prompt accepts CSV input — users entering `AAPL, MSFT, NVDA` must understand this is valid. The prompt text (and its box title "Step 1: Ticker Symbol") should be updated to indicate multi-ticker CSV input is accepted. Without this, AC1's UX goal ("without re-entering settings for each ticker") is technically met but the prompt misleads users about what they can type. | REQ-BATCH-01 AC1 |
| F-02 | Low | Local | TSPEC §5.5 `analyze` command flow handles the interactive path as `raw = get_ticker()` then `parse_tickers_input(raw) if "," in raw else [raw]`. The `else [raw]` path bypasses `parse_tickers_input()`, which means `normalize_ticker_symbol()` is not called again — this is fine because `get_ticker()` already normalizes. However, the TSPEC should make this dependency explicit so the `run_analysis()` refactor doesn't accidentally double-normalize. | REQ-BATCH-01 AC3; REQ-NFR-01 |

---

## Questions

None — all open questions from the REQ (OQ-01 through OQ-03) remain deferred, which is correct.

---

## Positive Observations

- All 9 requirements (P0 and P1) are present in the traceability table (§8) with named components. No P0 or P1 requirement is silently omitted.
- REQ-NFR-01 (no regressions) is explicitly covered by both the `run_analysis(ticker=...)` refactor and a dedicated regression test file — this is the right approach for a high-risk refactor.
- The single-ticker routing (§5.5 `len(ordered_tickers) == 1` → `run_analysis()`) correctly preserves the existing interactive save/display prompts for single-ticker users per REQ-BATCH-05/REQ-NFR-01.
- REQ-BATCH-04 exit codes (0 vs 1) are correctly implemented: `build_batch_summary` returns exit code and `raise SystemExit(exit_code)` is called after printing the table — consistent with REQ-BATCH-04 BR-08 (exit code determined after table is printed).
- The `--tickers "   "` → `typer.BadParameter` → exit code 2 correctly handles the FSPEC-BATCH-01 edge case.
- REQ-API-01 (P2) is implemented — no P2 feature is left out, which is a bonus.

---

## Recommendation

**Approved with minor changes**

> No High or Medium findings. F-01 (prompt text update) and F-02 (normalization dependency note) are Low and should be addressed in the TSPEC before PLAN authoring. All P0 and P1 requirements are accurately traced and no out-of-scope behavior is introduced.
