# DECISIONS — multi-ticker-analysis

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | SE-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-29 |
| **Upstream** | REQ → FSPEC → TSPEC → **DECISIONS** |
| **Downstream** | PLAN, PROPERTIES, IMPL |
| **Cross-Reviews** | — |
| **LEARNINGS** | `docs/multi-ticker-analysis/LEARNINGS-multi-ticker-analysis.md` |

No project-level `docs/_decisions/DECISIONS-*.md` files exist; nothing to contradict.

---

## DEC-MULTI-01: Library-internal asset type detection

**Context:** `TradingAgentsGraph.propagate_many()` lives in the library layer (`tradingagents/graph/trading_graph.py`) and needs per-ticker asset type detection (stock vs crypto) to call `propagate(ticker, date, asset_type=...)` correctly. The only existing detection function, `detect_asset_type()`, lives in `cli/utils.py` — the CLI layer. The library must not import from the CLI.

**Decision:** Add `asset_types: list[str] | None = None` parameter to `propagate_many()`. When `None`, a new library-internal `_detect_asset_type()` in `tradingagents/dataflows/utils.py` performs suffix-based detection using a local `CRYPTO_SUFFIXES` constant. When provided, the caller's values are used directly. The CLI always passes `None`; script callers may pass explicit types.

**Alternatives considered:**
- **Option A — move `detect_asset_type()` to `tradingagents/`** — rejected because it changes the location of a public CLI utility, requiring updates to all CLI importers; it also creates a harder-to-discover coupling between CLI utility tests and the library module.
- **Option B — duplicate CRYPTO_SUFFIXES logic in library-internal function** (CHOSEN) — the function is 3 lines; the duplication risk is low and isolated to one constant. Divergence is a re-evaluation trigger.

**Constraints that forced this shape:** REQ §3 Assumptions explicitly states: "The library layer (`TradingAgentsGraph`) must not import from the CLI." This is a hard architectural boundary, not an engineering preference.

**Reversibility:** Easy — if CRYPTO_SUFFIXES diverges between layers, or if a future feature needs the same detection outside the CLI, Option A (move to `tradingagents/`) can be adopted. The `asset_types` parameter remains backward-compatible regardless.

**Re-evaluation triggers:**
- `CRYPTO_SUFFIXES` in `cli/utils.py` and `tradingagents/dataflows/utils.py` diverge (indicates the two-copy approach is failing)
- A third caller (e.g., portfolio management) needs asset type detection and importing from `tradingagents/` becomes the natural choice

---

## DEC-MULTI-02: `MessageBuffer.reset()` via instance `__dict__` deletion

**Context:** `run_analysis()` monkey-patches three `MessageBuffer` methods (`add_message`, `add_tool_call`, `update_report_section`) by assigning closures that capture per-ticker file paths to the instance. In batch mode, these closures must be removed between tickers so the next ticker's paths are captured correctly. `reset()` must restore the unpatched class methods.

**Decision:** In `reset()`, delete the instance-level attributes using `self.__dict__.pop(attr, None)` for each of the three method names. Python's attribute lookup falls back to the class after the instance attribute is removed, automatically restoring the class-level method without needing to store or restore originals explicitly.

**Alternatives considered:**
- **Option A — store originals in `__init__`**: `self._orig_add_message = self.__class__.add_message` in `__init__`, then restore in `reset()` — rejected because `__init__` would need to know about a decorator pattern defined hundreds of lines away in `run_analysis()`. This creates invisible coupling: a future refactor of `run_analysis()` decorators would silently leave stale originals in `__init__`.
- **Option B — `__dict__.pop` pattern** (CHOSEN) — exploits standard Python attribute resolution. No coupling between `__init__` and `run_analysis()`. `reset()` is self-contained: it removes anything patched onto the instance without needing to know what was there.

**Constraints that forced this shape:** The monkey-patching pattern in `run_analysis()` predates this feature and cannot be changed as part of this feature's scope. Any `reset()` implementation must work with the existing patching mechanism.

**Reversibility:** Easy — if `MessageBuffer` is refactored to accept file paths via constructor or dependency injection (removing the monkey-patching entirely), `reset()` simply clears the data fields and the `__dict__.pop` calls become no-ops or can be removed.

**Re-evaluation triggers:**
- `MessageBuffer` is refactored to accept `log_file` and `report_dir` as constructor or `init_for_analysis()` parameters
- A fourth method is monkey-patched by `run_analysis()` (must be added to `reset()` manually)
- Python version introduces a change to instance attribute lookup that breaks the `__dict__.pop` pattern (extremely unlikely)
