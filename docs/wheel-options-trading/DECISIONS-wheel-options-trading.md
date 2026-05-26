# DECISIONS — Wheel Options Trading

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | SE-Author (Claude Code) |
| **Version** | 0.2.0 |
| **Created** | 2026-05-25 |
| **Upstream** | TSPEC-wheel-options-trading.md v0.2.0 → **DECISIONS** |
| **Downstream** | PLAN, future CONSOLIDATE-LEARNINGS |
| **Cross-Reviews** | CROSS-REVIEW-product-manager-DECISIONS.md, CROSS-REVIEW-test-engineer-DECISIONS.md |
| **LEARNINGS** | `docs/wheel-options-trading/LEARNINGS-wheel-options-trading.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.2.0 | 2026-05-25 | Address PM/TE cross-review: accuracy labelling, product justifications, single-ticker constraint, sentinel distinguishability, orphan file risk, test coverage notes |
| 0.1.0 | 2026-05-25 | Initial draft — five ADRs extracted from REQ, FSPEC, TSPEC, and cross-review trail |

---

## ADR-WHEEL-01: IV Rank Data Source — Realised Volatility Proxy vs Implied Volatility History

| Field | Value |
|---|---|
| **Status** | Decided |
| **Date** | 2026-05-25 |
| **Deciders** | SE-Author, PM-Author, SE-Review, TE-Review |

### Context

REQ-DATA-02 requires IV Rank and IV Percentile computation as the primary entry signal for the wheel strategy. The natural implementation draws on historical implied volatility (IV) — the conventional definition of IV Rank is `(current_IV − min_IV_52w) / (max_IV_52w − min_IV_52w)`.

yfinance's `Ticker.option_chain(expiry)` API returns a point-in-time snapshot of the options chain. It provides no `history_options()` method, no historical IV time series, and no way to query the chain at a past date for most tickers. Building a 252-day daily IV series would require 252 separate `option_chain()` calls, which yfinance does not support for historical dates and which would violate REQ-NFR-02's 10-second p95 latency target even if it were possible.

The SE cross-review (SEV-REVIEW-01) identified this architectural gap in REQ v0.1.0 and raised it as a High-severity blocker. The PM's v0.2.0 revision resolved it by committing to a realised-volatility proxy derived from OHLCV data that yfinance can actually provide.

### Alternatives Considered

| Option | Disposition | Reason |
|---|---|---|
| Historical implied vol from yfinance `option_chain()` — 252 daily calls | Rejected | yfinance does not support historical date queries for options chains on most tickers; rate-limiting would violate REQ-NFR-02 (10-second p95 budget) even if it did |
| Third-party historical IV feeds (CBOE LiveVol, ORATS, etc.) | Rejected | Out of scope per Assumption A1; introduces a paid external dependency |
| VIX or index-level IV proxy (CBOE free IV indices via `pandas_datareader`) | Rejected | Index-level IV does not reflect single-stock IV; produces incorrect screening decisions for individual equities |
| 30-day rolling realised volatility from OHLCV close prices (yfinance `Ticker.history()`) | Chosen | Implementable with existing tooling, stays within the vendor routing layer, satisfies REQ-NFR-02 latency budget; realised vol is correlated with implied vol and is acceptable for MVP signal quality |

### Decision

Use 30-day rolling realised volatility computed from yfinance OHLCV close-price returns, annualised by multiplying by `√252`, as the input series for IV Rank and IV Percentile computation. The dependency of REQ-DATA-02 on REQ-DATA-01 (options chain) is removed; the actual dependency is on the existing `Ticker.history()` OHLCV feed with no new vendor registration required.

The structured output field `iv_environment: Literal["elevated", "normal", "compressed"]` encodes the result as a tri-state proxy (`iv_rank >= 50` → elevated; `25–49` → normal; `< 25` → compressed) so downstream agents consume a deterministic label rather than a raw float. This tri-state is testable without a live IV feed.

The `iv_series: Optional[list[float]]` injectable parameter is added to the raw `get_iv_metrics` function as a test seam, so unit tests bypass the yfinance OHLCV call entirely and exercise the pure statistical computation.

### Consequences

- IV Rank and IV Percentile measure realised volatility, not implied volatility. The signal is correlated with true IV but not identical: during earnings or event-driven IV spikes, realised vol may lag, causing the system to understate elevated-IV conditions.
- The `iv_environment` enum provides a structured, testable proxy usable by downstream agents (WheelAnalyst Criterion 1) without exposing the float directly.
- `iv_percentile` uses a strict less-than empirical CDF, so `iv_percentile` approaches but does not reach 100 when `current_vol == max_vol_lookback`. Tests must not assert `iv_percentile == 100` in that boundary case (documented in REQ-DATA-02).
- The zero-variance guard (flat series over the lookback window returns sentinel values `iv_rank = 50` with a note in the output string) prevents division-by-zero without raising exceptions, consistent with REQ-NFR-06.
- **User-facing accuracy note:** The CLI and reports must label this metric as 'Volatility Environment Score' or explicitly annotate it as 'based on 30-day realised volatility, not implied volatility.' Using the label 'IV Rank' without qualification creates a false accuracy claim since the metric is correlated with but not equal to implied-vol-based IV Rank. This label decision must be captured in the PLAN and CLI implementation.

### Re-evaluation Trigger

**Re-evaluation triggers:** (1) Automated: If a regression test comparing `get_iv_metrics` output against a reference IV Rank source (added in a future integration test suite) shows >20 percentile point divergence for any of the three benchmark tickers (SPY, QQQ, AAPL), file a data-source review ticket. (2) Manual: If yfinance adds a `Ticker.iv_history()` or equivalent method in a future release (monitor yfinance changelogs at each dependency upgrade). If the realised-vol proxy diverges materially from a reference IV Rank (measured as >20 percentile points difference for the same ticker on the same date), the data source decision should be revisited.

---

## ADR-WHEEL-02: WheelPhase Storage in AgentState — `Optional[str]` vs Native Enum Field

| Field | Value |
|---|---|
| **Status** | Decided |
| **Date** | 2026-05-25 |
| **Deciders** | SE-Author, PM-Author, SE-Review |

### Context

The wheel state machine requires a `wheel_phase` field in `AgentState` to route graph execution across multiple invocations. REQ-LIFE-01 directly prescribes `wheel_phase: Optional[str]` as an `AgentState` field and the `WheelPhase(str, Enum)` type as its value source. The product justification for `Optional[str]` is that it guarantees backwards-compatibility (REQ-NFR-01): any run where `wheel_phase` is not set behaves identically to the pre-wheel equity pipeline. REQ-LIFE-01 AC6 requires that an unknown `wheel_phase` value causes fallback to the equity-only path with a warning log.

The natural Python representation is a `WheelPhase` enum. However, LangGraph serialises `AgentState` to JSON via its checkpointer infrastructure, which is active at graph-compilation time regardless of whether `checkpoint_enabled` is set in the caller's config. Standard Python `Enum` instances are not JSON-serialisable by default. `WheelPhase(str, Enum)` members are themselves strings and therefore serialisable, but LangGraph's TypedDict schema validation has been observed to reject `Enum`-typed fields at `workflow.compile()` time in some LangGraph versions (SEV-REVIEW-02, first identified in SE cross-review of REQ v0.1.0).

`WheelPosition` also stores a phase value and is serialised to disk as JSON. A non-`str` enum in that model would cause `json.dumps` to raise `TypeError` at position-write time.

### Alternatives Considered

| Option | Disposition | Reason |
|---|---|---|
| `wheel_phase: Optional[WheelPhase]` — native enum in `AgentState` TypedDict | Rejected | LangGraph compilation risk: schema validation rejects non-primitive enum-typed fields in some versions; `json.dumps(state)` fails at checkpoint time |
| `wheel_phase: Optional[str]` with runtime validation inside routing logic | Chosen | Primitive `str` is JSON-serialisable by default; LangGraph checkpointer handles it without configuration; explicit fallback in `route_wheel_phase()` covers unknown values |
| `wheel_phase: Optional[WheelPhase]` with a custom LangGraph serialiser registered at graph build | Rejected | Requires patching LangGraph internals; invasive, couples the feature to a specific LangGraph version, fragile across upgrades |

### Decision

`wheel_phase: Optional[str]` is the field type in `AgentState`. The `WheelPhase(str, Enum)` class is defined and used internally as a source of string constants (e.g., `WheelPhase.SCREENING = "screening"`) but the state field is typed as plain `Optional[str]`. Validation of the stored value is the responsibility of `route_wheel_phase()`, which includes an explicit unknown-value fallback: when a `wheel_phase` string does not match any known `WheelPhase` value, the router falls through to the equity-only path and emits a warning log (REQ-LIFE-01 AC6).

Unit tests assert against the literal string values (`assert state["wheel_phase"] == "csp_open"`) without importing the enum, which simplifies test authoring.

### Consequences

- Runtime type safety is reduced: any string can be written to `wheel_phase`, including misspellings. The unknown-value fallback in `route_wheel_phase()` provides a safety net but cannot distinguish a misspelled phase from a legitimate equity-only invocation.
- Code that writes `wheel_phase` should always use the `WheelPhase` enum constants to prevent silent misspellings; this is a convention enforced by code review, not by the type system.
- The `WheelPosition` JSON file, which also stores phase values as strings, is consistent with this approach.
- **Product risk:** A `wheel_phase` string typo silently routes to the equity-only path. The warning log (required by REQ-LIFE-01 AC6) is the only user-visible signal. The CLI must surface this warning to the user (not just log it to stderr). This must be captured as a CLI requirement in the PLAN.
- **Test coverage:** REQ-LIFE-01 AC6 ('unknown `wheel_phase` → equity path + warning') is verified by a unit test that passes an unrecognised string (e.g., `'invalid_phase'`) as `wheel_phase` in `AgentState` and asserts: (a) the graph routes to the first analyst node (equity path); (b) a warning is emitted (captured via `caplog` or `capfd`).

### Re-evaluation Trigger

If a future LangGraph release adds first-class support for `str`-enum typed fields in TypedDicts with guaranteed JSON-safe checkpointing, the field type may be changed to `Optional[WheelPhase]` to restore static type safety. Monitor LangGraph release notes for `TypedDict` enum support in each version upgrade (add a checklist item to the dependency-upgrade runbook). Verify by compiling a test graph with an `Optional[WheelPhase]`-typed `AgentState` field and confirming the checkpointer round-trips it without error.

---

## ADR-WHEEL-03: LangGraph State Machine Architecture — Single Shared Graph vs Sub-graphs

| Field | Value |
|---|---|
| **Status** | Decided |
| **Date** | 2026-05-25 |
| **Deciders** | SE-Author, PM-Author, SE-Review |

### Context

The wheel feature requires phase-aware routing at the graph entry point: before any analyst node runs, the graph must inspect `wheel_phase` and branch to the correct node (first analyst, `csp_agent`, `cc_agent`, `roll_check_agent`, or `wheel_cycle_summary`). Three architectural patterns were available in LangGraph: a separate `WheelGraph` alongside the existing equity graph, LangGraph sub-graphs with their own state namespace, or a preamble conditional edge grafted onto the existing shared `StateGraph`.

The SE cross-review of REQ v0.1.0 (SEV-REVIEW-03) identified the graph branching architecture as under-specified and raised it as a High-severity issue. The PM's v0.2.0 Architecture Note resolved it by prescribing the shared graph with preamble conditional edge.

### Alternatives Considered

| Option | Disposition | Reason |
|---|---|---|
| Separate `WheelGraph` class alongside `TradingAgentsGraph` with its own `setup_graph()` | Rejected | Duplicates all analyst node registrations; requires a separate CLI entry path; breaks the existing `--analyst` flag selection; two graphs cannot share `AgentState` cleanly |
| LangGraph sub-graph with its own state namespace | Rejected | Sub-graphs require explicit field promotion between parent and child state; increases coupling surface; `AgentState` field promotion for all analyst outputs (`market_report`, `sentiment_report`, etc.) would be extensive and fragile |
| Single shared `StateGraph` with `START → wheel_router` preamble conditional edge | Chosen | Minimal structural change to `setup_graph()`; the router is a transparent pass-through when `wheel_phase is None`, preserving the equity path exactly (REQ-NFR-01); all wheel nodes share the same `AgentState`, eliminating field promotion complexity |

### Decision

Modify `setup_graph()` to replace the direct `START → first_analyst_node` plain edge with a `START → wheel_router` conditional edge. `ConditionalLogic.route_wheel_phase()` implements the routing function. When `wheel_phase is None`, the router returns the name of the first analyst node (passed to `ConditionalLogic` at construction time from `build_analyst_execution_plan()`), making it a transparent pass-through to the existing equity flow.

The five non-None `wheel_phase` values each map to a distinct target node:

| `wheel_phase` value | Target node |
|---|---|
| `"screening"` | First analyst node (standard pipeline + WheelAnalyst + CspAgent) |
| `"csp_open"` | `roll_check_agent` |
| `"cc_open"` | `cc_agent` |
| `"cycle_complete"` | `wheel_cycle_summary` |
| `None` | First analyst node (equity pass-through) |

`WheelStateError` (a `ValueError` subclass defined in `tradingagents/agents/options/exceptions.py`) is raised when the phase value implies required state that is absent — for example, `wheel_phase="cc_open"` with no open `WheelPosition` record for the ticker.

### Consequences

- The existing equity pipeline is entirely unaffected when `wheel_phase is None`: no analyst nodes, no CLI display, no config keys change (REQ-NFR-01).
- All wheel nodes share the same `AgentState` TypedDict, so inter-node communication uses the same field-access pattern as the rest of the graph. New fields (`wheel_phase`, `wheel_candidate_report`, `csp_decision`, `cc_decision`, `roll_decision`) are all `Optional[str]` to preserve LangGraph checkpoint serialisability.
- The `ConditionalLogic` constructor must receive the first analyst node name at `setup_graph()` time so that the `wheel_phase is None` pass-through can return the correct dynamic node name. This is a minor coupling increase but avoids dynamic node lookup inside the routing function.
- **Single-ticker constraint:** Because `wheel_phase` and the wheel decision fields (`csp_decision`, `cc_decision`, `roll_decision`) are single-valued fields in `AgentState`, one `TradingAgentsGraph.propagate()` call handles exactly one ticker's wheel phase at a time. Running the wheel analysis on multiple tickers requires multiple sequential `propagate()` calls. This is consistent with US-05 and US-07 (which describe per-ticker position tracking via `wheel-status`) and the existing single-ticker propagation model. It is explicitly out of scope to support concurrent multi-ticker wheel analysis in a single graph invocation (REQ out-of-scope: 'Portfolio-level margin/buying-power calculation').
- **Test coverage:** The single-ticker constraint is verified implicitly by all existing PROPERTIES tests (each test invokes one `propagate()` call per ticker). No additional test is required, but the PROPERTIES document must note that multi-ticker scenarios are tested as sequential independent calls, not concurrent ones.

### Re-evaluation Trigger

If LangGraph changes the `START` edge semantics, conditional edge return-value routing, or `StateGraph.compile()` validation in a way that rejects the preamble pattern, or if the equity pass-through integration test fails after any LangGraph version bump. If US-05 or US-07 acceptance criteria require multi-ticker batch management in a future phase, the shared-graph architecture will need to be revisited in favour of a per-ticker invocation loop or a dedicated `WheelGraph`.

---

## ADR-WHEEL-04: Structured Output Fallback Chain — Three-Layer Pattern Across 10+ LLM Providers

| Field | Value |
|---|---|
| **Status** | Decided |
| **Date** | 2026-05-25 |
| **Deciders** | SE-Author, PM-Author, SE-Review |

### Context

The four wheel decision agents (WheelAnalyst, CspAgent, CcAgent, RollCheckAgent) must return validated Pydantic schema instances (`WheelCandidateReport`, `CspDecision`, `CcDecision`, `RollDecision`) across the 10+ LLM providers supported by the codebase. LLM providers vary widely in their structured-output support: some support native JSON schema mode via `with_structured_output()`; others support only free-text generation; others support JSON mode but reject complex nested schemas or fixed-length tuple types.

REQ-NFR-04 mandates that all decision schemas use the existing `structured.py` wrapper (`bind_structured` / `invoke_structured_or_freetext`). The SE cross-review of FSPEC v0.1.0 (FSPEC-SE-02) found that the FSPEC did not specify how `structured.py`'s free-text fallback output (a raw string) is parsed back into a schema instance, creating implementation ambiguity. The SE cross-review of FSPEC v0.2.0 (FSPEC-SE2-01) found that the `bind_structured` call shown in all three agent sections omitted the required `agent_name` argument and that the `invoke_structured_or_freetext` invocation step was absent entirely.

### Alternatives Considered

| Option | Disposition | Reason |
|---|---|---|
| Provider-specific native structured output only (`with_structured_output()`) | Rejected | Fails silently on providers without native support; no fallback path; violates REQ-NFR-04 |
| JSON-mode prompt only (instruct LLM to output JSON, parse response string) | Rejected | No schema enforcement; free-form JSON requires fragile parsing; different providers use different JSON-mode activation patterns |
| `bind_structured` at construction + `invoke_structured_or_freetext` at invocation + agent-level `model_validate_json` on fallback string + safe sentinel on total failure | Chosen | Layered fallback that degrades gracefully; reuses existing `structured.py` infrastructure; agent explicitly handles the raw-string case; safe sentinel prevents graph crashes |

### Decision

A three-layer (four-step) fallback chain is applied uniformly to all four wheel decision agents:

1. **Construction:** `bind_structured(llm, Schema, agent_name)` — wraps the LLM with native structured-output support for providers that support it. The three required arguments (`llm`, `Schema`, `agent_name`) must all be supplied; omitting `agent_name` raises `TypeError` at construction time.
2. **Invocation:** `invoke_structured_or_freetext(structured_llm, plain_llm, prompt, render, agent_name)` — attempts the structured call; on failure falls back to `plain_llm.invoke(prompt).content`, returning a raw string in both cases. Agents must not assume a Pydantic instance is returned; `invoke_structured_or_freetext` always returns `str`.
3. **Agent-level parse:** The agent calls `Schema.model_validate_json(raw_str)` on the returned string. On `ValidationError`, proceeds to step 4.
4. **Safe sentinel:** On total failure (both structured and free-text paths produce unparseable output), the agent returns a pre-constructed sentinel with `tradeable=False` (for CspAgent and CcAgent) or `action="HOLD"` (for RollCheckAgent), with `rationale="Structured output failed — safe fallback applied."` The sentinel prevents the LangGraph graph from crashing and satisfies REQ-NFR-06.

The sentinel values use `tradeable=False` / `approved=False` to exempt themselves from field-range constraints that apply only on the `tradeable=True` path (e.g., `delta in (−1, 0)`, `theta <= 0`). This exemption is documented in each schema's TSPEC section.

### Consequences

- `invoke_structured_or_freetext` returns `str` in all cases (FSPEC-SE2-01 carry-forward note). Any agent code that type-checks or branches on whether the result is a Pydantic instance vs. a string is incorrect.
- The sentinel prevents graph crashes but introduces a potentially silent safe-fallback: if the LLM consistently fails schema validation, every run produces a `tradeable=False` result with no user-visible error. PROPERTIES tests must verify the sentinel path is exercised and that the returned state is detectable (non-empty `rationale` field).
- `WheelAnalyst` uses `deep_think_llm` rather than the standard LLM because the five-criterion evaluation benefits from extended reasoning. `RollCheckAgent` uses `quick_think_llm` because roll/hold/close decisions are latency-sensitive (they occur on every invocation when `wheel_phase="csp_open"`).
- **Distinguishability:** A sentinel `CspDecision(tradeable=False, rationale='Structured output failed — safe fallback applied.')` must be visually distinguishable from a genuine `tradeable=False` decision. The `rationale` field's sentinel marker string (`'Structured output failed — safe fallback applied.'`) must be checked by the CLI display layer and rendered with a distinct warning style. This sentinel marker string is a contract — it must not be changed without updating all consuming code.
- **Test coverage:** The TSPEC specifies that the three-layer fallback is verified by unit tests that mock `invoke_structured_or_freetext` to return an unparseable string, then assert the agent returns the sentinel. The sentinel `tradeable=False` / `action='HOLD'` must be verified not to cause graph crashes downstream (graph must handle both genuine `tradeable=False` and sentinel `tradeable=False` identically). A dedicated property 'Agent returns sentinel on total structured output failure' must appear in PROPERTIES.

### Re-evaluation Trigger

If `structured.py` is extended to perform JSON extraction from the free-text fallback internally (returning a Pydantic instance rather than a raw string), the agent-level `model_validate_json` step (step 3) may be removed. Any such change to `structured.py` requires updating all four wheel agents simultaneously. If the sentinel fires more than once per 100 runs in production (observable via log monitoring on the marker string), the structured output pipeline should be diagnosed.

---

## ADR-WHEEL-05: WheelPosition Persistence — Per-Cycle JSON Files vs TradingMemoryLog Extension

| Field | Value |
|---|---|
| **Status** | Decided |
| **Date** | 2026-05-25 |
| **Deciders** | SE-Author, PM-Author, SE-Review, TE-Review |

### Context

Wheel position state must persist across multiple graph invocations: the CSP open event, the assignment event, the CC open event, and the cycle-close event each occur in separate `graph.invoke()` calls, potentially days or weeks apart. The existing persistence infrastructure offers two candidate stores: the `TradingMemoryLog` markdown file (append-only, human-readable, one file per ticker), or a new structured data store introduced specifically for wheel positions.

The SE cross-review of REQ v0.1.0 (SEV-REVIEW-10) identified the position persistence scheme as under-specified and raised concurrent-access risk on Windows as a Medium-severity issue. The PM's v0.2.0 revision resolved it by prescribing per-cycle JSON files with an atomic write pattern.

### Alternatives Considered

| Option | Disposition | Reason |
|---|---|---|
| Extend `TradingMemoryLog` with structured position fields | Rejected | The memory log is append-only markdown designed for human-readable decision history, not machine-readable position state; parsing structured data from markdown is fragile; the `store_decision()` / `get_past_context()` API has no retrieval-by-field capability |
| SQLite — reuse the LangGraph checkpointer database | Rejected | The LangGraph checkpoint DB is an implementation detail of the LangGraph runtime, not a stable application storage layer; schema migrations would require LangGraph version coordination; adds a SQLite dependency for a use case that does not need relational queries |
| Single JSON file per ticker (all cycles appended) | Rejected | Concurrent writes from two simultaneous analyses of the same ticker would produce write conflicts; loading the latest open position requires parsing the entire file even when only the last entry is needed |
| Per-position JSON files with atomic write — one file per wheel cycle | Chosen | Each cycle is an independent unit of state; atomic write (temp file in same directory + `os.replace`) prevents partial writes; `load_latest_open_position` reads the latest file cheaply; consistent with the `TradingMemoryLog` atomic write pattern |

### Decision

One JSON file per wheel cycle: `{positions_dir}/{ticker}-cycle-{N}.json`, where `N` is a positive integer starting at 1. The `positions_dir` is a config key (`config["wheel"]["positions_dir"]`) defaulting to a path alongside the existing results directory. File writes use `tempfile.mkstemp(dir=dir_path)` + `os.replace()` — the temp file is created in the same directory as the target to ensure same-filesystem semantics for the atomic rename (required on Windows where cross-drive `os.replace` is not atomic).

`load_latest_open_position` sorts candidate files by integer cycle number extracted via regex, not by lexicographic string sort. Lexicographic sort silently breaks at cycle ≥ 10 (`"cycle-9"` sorts after `"cycle-10"` character-by-character), which was identified as a High-severity bug in the TE cross-review of TSPEC v0.1.0 (TE-TSPEC-04) and fixed in TSPEC v0.2.0. Positions with `status="cycle_complete"` are skipped; only the latest `status="open"` position is returned.

`TradingMemoryLog` receives a human-readable summary entry at `CYCLE_COMPLETE` — it is the reflective audit trail, not the machine-readable position store. The two stores are complementary: the JSON files are the authoritative state; the memory log is the historical record.

### Consequences

- The position directory must be cleaned up manually if a cycle is abandoned mid-flight (e.g., the user deletes the ticker from their watchlist before reaching `CYCLE_COMPLETE`). There is no garbage-collection mechanism; stale `status="open"` JSON files for a ticker will be picked up by `load_latest_open_position` on subsequent runs.
- Concurrent access from two simultaneous analyses on the same ticker is not prevented by file locking — only by the atomic write pattern, which prevents partial reads but not interleaved writes. The usage model (one analysis at a time per ticker, initiated manually via CLI) makes this acceptable for MVP.
- The `WheelPosition` schema adds two fields beyond the REQ-LIFE-02 schema definition: `csp_open_date: Optional[str]` (required to compute `cycle_duration_days` for the `cycle_annualised_return_pct` formula) and `prior_analyst_bias: Optional[str]` (required by RollCheckAgent Rule 5 — analyst-consensus-change detection). Both fields are documented as TSPEC-level schema extensions in TSPEC Section 9.1 and in the Traceability Gap Summary (Section 10.8).
- `CcAgent`, `RollCheckAgent`, and `ConditionalLogic.route_wheel_phase()` all call `load_latest_open_position`. Each of these consumers accepts an injectable `_position_loader` callable (keyword-only, leading-underscore convention) so unit tests can supply a fixture `WheelPosition` without writing real files to disk.
- **Orphan file risk:** If a wheel cycle is abandoned (graph crash after position file creation, before `CYCLE_COMPLETE`), the position file remains on disk indefinitely. The `wheel-status` CLI command (REQ-LIFE-06) will display this position as open. No automatic cleanup is provided. Users must manually delete abandoned position files. This is an acceptable MVP limitation documented in REQ Section 3 (Out of Scope: 'Portfolio-level margin / buying-power calculation').

### Re-evaluation Trigger

If the position directory grows to a scale where globbing all per-ticker JSON files becomes measurably slow (e.g., >500 cycle files, or `load_latest_open_position` exceeds 100ms on commodity hardware), or if the codebase introduces multi-ticker concurrent analysis that makes the single-file-per-cycle isolation insufficient. If users report stale/orphaned position files causing confusion in `wheel-status`, add a `tradingagents wheel-cleanup --dry-run` command in a future phase.
