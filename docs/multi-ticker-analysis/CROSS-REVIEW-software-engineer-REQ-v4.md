# Cross-Review: software-engineer — REQ

**Reviewer:** software-engineer
**Document reviewed:** docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md
**Date:** 2026-05-27
**Iteration:** 4

---

## v3 Finding Resolution

All three v3 findings are resolved in v0.4.0:
- F-01 ✅ (High) `propagate_many(tickers, date, asset_types=None)` — library-internal CRYPTO_SUFFIXES detection, no CLI import. §3 Assumptions documents boundary + relocation. AC4/AC5 added.
- F-02 ✅ (Medium) BATCH-06 description covers `None`/absent `wheel_candidate_report` alongside malformed-JSON fallback.
- F-03 ✅ (Low) No REQ change required; TSPEC will handle spy pattern note.

---

## Findings

| ID | Severity | Scope | Finding | Section ref |
|----|----------|-------|---------|-------------|
| F-01 | Low | Local | REQ-BATCH-02 AC1 still references `detect_asset_type()` by name: "asset type is determined per ticker by `detect_asset_type()`". After the boundary resolution in v0.4.0, the CLI now calls the library-internal function (not `detect_asset_type()` from `cli/utils.py`). The AC wording should say "the library-internal asset type detection function" to match the resolved boundary. Minor consistency issue only. | REQ-BATCH-02 |
| F-02 | Low | Local | REQ-API-01 description says "the caller is responsible for ensuring list length matches `tickers`" but does not specify the error behaviour when lengths differ (e.g. `propagate_many(["AAPL","MSFT"], "2026-05-27", asset_types=["stock"])` — 2 tickers, 1 type). Should specify: raises `ValueError` with a descriptive message. Without this, TSPEC cannot prescribe the validation behaviour and two different implementations would both satisfy the REQ. | REQ-API-01 |

---

## Questions

None remaining.

---

## Positive Observations

- v0.4.0 resolves all prior High and Medium findings cleanly. The `asset_types=None` design is the right architectural choice — it keeps the library self-contained while giving callers explicit control when needed.
- AC4 and AC5 for `propagate_many` provide clear, mock-assertable coverage of both the auto-detection path and the explicit override path.
- The BATCH-06 `None`/absent wheel report handling is now fully specified alongside the malformed-JSON fallback — no gap for the TSPEC author.
- §3 Assumptions now contains a concise, actionable boundary note that removes ambiguity from the TSPEC scope.

---

## Recommendation

**Approved with minor changes**

> No High or Medium findings. F-01 and F-02 are Low. F-01 is a one-word consistency fix; F-02 adds a single error-behaviour sentence to REQ-API-01. Both should be addressed before TSPEC authoring to ensure the implementation contract is unambiguous.
