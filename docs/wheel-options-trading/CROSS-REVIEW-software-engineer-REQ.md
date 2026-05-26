# Cross-Review — Software Engineer — REQ
# Document: REQ-wheel-options-trading.md

| Field | Value |
|---|---|
| Reviewer | Software Engineer (SE-Review) |
| Date | 2026-05-25 |
| Document reviewed | REQ-wheel-options-trading.md v0.1.0 |
| Recommendation | Needs revision |

---

## Summary

The REQ is well-structured and covers the four delivery phases coherently. The problem statement is accurate and the user stories map cleanly to the requirements. However, several High-severity technical gaps must be resolved before implementation can begin: the IV Rank computation method described in REQ-DATA-02 is architecturally expensive and the data source is unspecified; the `WheelPhase` enum in `AgentState` (REQ-LIFE-01) must account for LangGraph's state serialisation constraints; the proposed graph branching model is under-specified and will require significant rework of `graph/setup.py`; and the module placement prescribed by REQ-DATA-05 contradicts the existing codebase convention. Medium-severity findings cover missing dependency arrows, an untestable AC in REQ-TRADE-05, the `tuple` field types in `WheelCandidateReport` that are not JSON-serialisable, and the absence of a risk-free rate data source plan. Low-severity findings cover minor formula ambiguities and the missing `_ENV_OVERRIDES` wiring for the new wheel config keys.

---

## Findings

### [SEV-REVIEW-01] High — IV Rank/Percentile requires daily historical options IV that yfinance does not provide natively

**Requirement(s):** REQ-DATA-02

**Finding:** Assumption A3 and REQ-DATA-02 define IV Rank as `(current_IV − min_IV_52w) / (max_IV_52w − min_IV_52w)` computed from "the 30-day ATM IV of the front-month options contract, sampled daily over `lookback_days` trading days." The yfinance `Ticker.option_chain(expiry)` API returns a snapshot of the options chain at the moment the call is made; it does not provide historical IV time series. There is no `Ticker.history_options()` method or equivalent in yfinance. To build a 252-day daily IV series, the implementation would need to either (a) call `option_chain()` 252 times with historical date parameters — which yfinance does not support for most data — or (b) derive a proxy from historical OHLCV data (e.g., a 30-day realised vol or Bollinger bandwidth), which is not implied volatility. The REQ is silent on this architectural problem.

**Impact:** REQ-DATA-02 cannot be implemented as written using yfinance alone. The IV Rank and IV Percentile values will either be fabricated from an incorrect source, causing all downstream wheel suitability decisions to be meaningless, or the implementation will block waiting for a feasibility clarification.

**Suggested resolution:** Choose one of the following and document it in the REQ: (1) Redefine IV Rank using a proxy that yfinance can actually provide — e.g., compute a 30-day historical realised volatility percentile using `Ticker.history()` close prices; this is implementable with existing tooling at the cost of using realised rather than implied volatility. (2) Integrate a third-party historical-IV data source (e.g., CBOE's free IV indices for the underlying index, or the `pandas_datareader` FRED feed for VIX as a proxy). (3) Defer IV Rank to Phase 2 pending a data vendor decision. Update Assumption A1 accordingly.

---

### [SEV-REVIEW-02] High — WheelPhase enum in AgentState violates LangGraph serialisation requirements

**Requirement(s):** REQ-LIFE-01

**Finding:** REQ-LIFE-01 requires adding `wheel_phase: Optional[WheelPhase]` to `AgentState`. LangGraph uses JSON serialisation (via its checkpointer, whether or not `checkpoint_enabled` is True in the config, because the checkpoint infrastructure is part of the graph compilation pipeline). Python `Enum` instances are not JSON-serialisable by default; they must be either declared as `str` enums (`class WheelPhase(str, Enum)`) or handled by a custom serialiser. The existing state fields are all primitive types (`str`, `int`, annotated TypedDicts). Additionally, `WheelPosition` (REQ-LIFE-02) is proposed to be stored as JSON on disk — if `WheelPosition.wheel_phase` is a `WheelPhase` enum, standard `json.dumps` will raise `TypeError`.

**Impact:** Adding a non-serialisable enum field to `AgentState` will cause LangGraph graph compilation or checkpoint errors at runtime, even with `checkpoint_enabled=False`, because LangGraph validates state schema on compilation. The `WheelPosition` JSON persistence will also fail silently or raise on write.

**Suggested resolution:** Declare `WheelPhase` as `class WheelPhase(str, Enum)` with string values (e.g., `SCREENING = "screening"`). Use `Optional[str]` in `AgentState` rather than `Optional[WheelPhase]` and validate the value on read, or confirm `str` enum members are tolerated by the LangGraph version in use. Document this constraint in the TSPEC.

---

### [SEV-REVIEW-03] High — Graph branching architecture for wheel phases is under-specified and conflicts with existing setup.py structure

**Requirement(s):** REQ-LIFE-01, REQ-SCREEN-01

**Finding:** REQ-LIFE-01 describes conditional routing edges based on `wheel_phase`. The current `graph/setup.py` builds a single linear-with-loops graph and does not support top-level branching at the START node. Adding wheel-phase routing requires either (a) a second `StateGraph` specific to the wheel pipeline, or (b) a new top-level `START → router` conditional edge that branches before any analysts run. This means `setup_graph()` must be heavily restructured or a new factory function introduced. The REQ uses phrases like "runs analyst pipeline + WheelAnalyst → CspAgent" without specifying whether this is the same `StateGraph` with additional conditional edges grafted onto the existing topology, or a separate sub-graph. LangGraph sub-graphs exist but have their own state namespace constraints. REQ-SCREEN-01 AC5 ("when `wheel` is not in `selected_analysts`, graph runs as before") is incompatible with global `wheel_phase` routing unless the two paths share an identical graph but have dead-code paths guarded at runtime.

**Impact:** Without a clear architectural decision (shared graph with extra conditional edges vs. separate wheel graph vs. LangGraph sub-graph pattern), engineers will make conflicting design choices. The existing `ConditionalLogic` class would need multiple new methods; tool nodes for options data tools are not mentioned in the graph setup flow at all.

**Suggested resolution:** Add an Architecture Note to Phase 4 requirements specifying the integration pattern. The lowest-risk approach consistent with the codebase is to add `wheel_phase` routing to `setup_graph()` as a new preamble conditional edge (START → `wheel_router` → existing first analyst node or `csp_open_router`), and register a new `ConditionalLogic.route_wheel_phase()` method. The TSPEC should capture this. The REQ should at minimum state the chosen pattern so the TSPEC author is not left guessing.

---

### [SEV-REVIEW-04] High — REQ-DATA-05 module placement contradicts the existing codebase convention

**Requirement(s):** REQ-DATA-05

**Finding:** REQ-DATA-05 specifies that options tools be wrapped in `tradingagents/agents/utils/options_data_tools.py`. However, examining the codebase: the existing `@tool`-decorated LangChain tools live in `tradingagents/agents/utils/core_stock_tools.py`, which wraps functions from `tradingagents/dataflows/interface.py` via `route_to_vendor()`. The new raw data functions are correctly targeted at `tradingagents/dataflows/y_finance.py`. The `@tool` wrapper layer should follow the same convention and route through `interface.py` — it must not import from `y_finance.py` directly, because that would bypass the vendor-routing and fallback chain implemented in `interface.py`. Placing options tools in `agents/utils/` rather than directly routing through `interface.py` is acceptable only if the wrapper calls `route_to_vendor("get_options_chain", ...)`, which requires the new methods to be registered in `VENDOR_METHODS` in `interface.py`. The REQ says "registered in `tradingagents/dataflows/interface.py` under the `options` category" but the proposed new `TOOLS_CATEGORIES` key name `"options"` conflicts with the existing `data_vendors` config dict which uses `"core_stock_apis"`, `"technical_indicators"`, `"fundamental_data"`, `"news_data"` — none of which maps to a generic `"options"` category. The `interface.py` category lookup (`get_category_for_method`) will raise `ValueError` for any uncategorised tool.

**Impact:** Options tools will either bypass the vendor-routing layer (losing fallback behaviour) or fail at runtime with a `ValueError` from `get_category_for_method`. REQ-DATA-01's AC3 (routing to an Alpha Vantage adapter) cannot be satisfied without correct interface registration.

**Suggested resolution:** (1) Add `"options_data"` as a named category to `TOOLS_CATEGORIES` in `interface.py`, mirroring the existing pattern. (2) Register all four new methods in `VENDOR_METHODS` with `yfinance` implementations and `alpha_vantage` stub entries. (3) Clarify in the REQ that the `@tool` wrappers in `options_data_tools.py` must call `route_to_vendor()` — not import `y_finance.py` functions directly.

---

### [SEV-REVIEW-05] Medium — `tuple[float, float]` and `tuple[int, int]` fields in WheelCandidateReport are not JSON-serialisable by Pydantic v2 in strict mode

**Requirement(s):** REQ-SCREEN-02

**Finding:** The `WheelCandidateReport` schema includes `recommended_strike_range: tuple[float, float]` and `recommended_dte_range: tuple[int, int]`. In Pydantic v2, `tuple` is serialised to a JSON array, which is acceptable; however, `with_structured_output()` in LangChain generates JSON schemas from Pydantic models. Most LLM providers' JSON schema mode does not support fixed-length tuple types — they are emitted as `array` with `prefixItems`, which is a JSON Schema draft 2020-12 feature that OpenAI's `json_schema` mode and Anthropic's tool-use schema do not reliably handle. When `structured.py`'s `bind_structured()` attempts `llm.with_structured_output(WheelCandidateReport)`, the LLM may fail schema validation or ignore the tuple constraint. Additionally, `AgentState` is a TypedDict — if `WheelCandidateReport` is stored as a field in `AgentState`, the tuple type will fail LangGraph's JSON serialisation at checkpoint time.

**Impact:** LLM providers will likely emit a plain `array` for these fields, potentially with wrong element counts. Schema validation will silently pass while the data is incorrect. Tests for AC1 may pass with mocked data but fail in live runs.

**Suggested resolution:** Replace `tuple[float, float]` with a small Pydantic sub-model or use `list[float]` with a `Field(min_length=2, max_length=2)` constraint that survives JSON schema generation. Example: `recommended_strike_range: list[float] = Field(min_length=2, max_length=2, description="[low_strike, high_strike]")`.

---

### [SEV-REVIEW-06] Medium — REQ-DATA-02 dependency on REQ-DATA-01 is overstated; actual dependency introduces hidden complexity

**Requirement(s):** REQ-DATA-02

**Finding:** REQ-DATA-02 lists `REQ-DATA-01` as its dependency. This implies IV Rank is computed from options chain data fetched by `get_options_chain`. However, as documented in SEV-REVIEW-01, building a 252-day IV history requires repeated historical chain snapshots, not a single call to `get_options_chain`. If the correct implementation uses a different data source (realised vol from OHLCV, or a third-party IV feed), then the dependency on REQ-DATA-01 is either incorrect or incomplete. If IV Rank is derived directly from the current chain's ATM IV plus historical OHLCV, then the actual dependency is on the existing `get_YFin_data_online` (OHLCV), not REQ-DATA-01. This dependency error will mislead the TSPEC author and could cause Phase 1 to be sequenced incorrectly.

**Impact:** The TSPEC may design the IV Rank function to make 252 calls to `get_options_chain` in a loop, which at yfinance's throttle limits (roughly 2,000 requests/hour, shared across all calls in the process) would take several minutes per ticker and trigger rate-limiting — violating REQ-NFR-02's 10-second budget.

**Suggested resolution:** Revise the dependency and description of REQ-DATA-02 once the IV source decision (SEV-REVIEW-01) is made. If using OHLCV-derived realised vol, mark the dependency as `None` or reference the existing OHLCV function. If using the current options chain only, remove the 252-day lookback as unimplementable and redefine IV Rank from the single current chain snapshot.

---

### [SEV-REVIEW-07] Medium — REQ-TRADE-05 acceptance criteria are untestable as written

**Requirement(s):** REQ-TRADE-05

**Finding:** REQ-TRADE-05 AC1 states: "Aggressive debater arguments reference the premium yield and probability of profit." This criterion tests the content of an LLM's free-text response — it is non-deterministic and cannot be reliably verified by a unit test or integration test. The criterion is qualitative prose inspection masquerading as a testable AC. Similarly, AC2 ("Conservative debater flags binary event risk") has no concrete, observable assertion that a test can make. The existing agents (`create_aggressive_debator`, etc.) take string prompts and return unstructured prose; there is no structured output from the risk debate agents.

**Impact:** REQ-NFR-05 requires "at least one unit test" for every new agent. If the ACs for REQ-TRADE-05 are untestable, either (a) the test engineer writes a test that always passes by checking for any non-empty string response, creating false assurance, or (b) this requirement will be flagged as untestable during PROPERTIES creation and delay the phase.

**Suggested resolution:** Reframe AC1 and AC2 as prompt-injection or context-propagation tests: verify that when the system is in wheel mode, the prompt assembled for the risk debate agents contains the serialised `CspDecision` fields (premium yield, probability of profit). This is testable deterministically by inspecting the constructed prompt string before LLM invocation. Add an AC that verifies the prompt template includes a `{options_context}` variable that is populated when `wheel_phase` is not None.

---

### [SEV-REVIEW-08] Medium — Risk-free rate source is under-specified for BSM Greeks calculation

**Requirement(s):** REQ-DATA-03

**Finding:** REQ-DATA-03 specifies "risk-free rate from the 3-month T-bill (static fallback: 5.25%)". The "primary" source for the T-bill rate is not named. If the intent is to fetch it live, yfinance exposes it via `yf.Ticker("^IRX")` (13-week T-bill yield) but the value returned is in percent (e.g., 5.25 for 5.25%) and must be divided by 100 for use in BSM. If the intent is a config-driven static value, the `default_config.py` has no `risk_free_rate` key. The 5.25% rate named in the REQ is a 2024 rate; as of the document date (2026-05-25) the rate will be materially different, causing systematically mis-priced Greeks.

**Impact:** If the live feed is used and parses the yfinance value incorrectly (using 5.25 instead of 0.0525), all Greeks will be wrong. If the static fallback is used without surfacing it in config, a stale rate silently mis-prices all recommendations, which is a correctness risk for a system that traders use to make real trading decisions.

**Suggested resolution:** Add a `risk_free_rate_source: "yfinance_irx" | "static"` config key under `config["wheel"]` and a `risk_free_rate_static: 0.0525` fallback. Document the parsing convention (decimal, not percentage). Add an AC to REQ-DATA-03: "When `^IRX` is unavailable, function falls back to `config['wheel']['risk_free_rate_static']` and logs a warning."

---

### [SEV-REVIEW-09] Medium — Missing dependency: REQ-SCREEN-01 depends on REQ-DATA-03 (Greeks used in liquidity check)

**Requirement(s):** REQ-SCREEN-01

**Finding:** REQ-SCREEN-01 criterion 2 checks chain liquidity using near-the-money strikes with OI ≥ 100 and bid/ask spread ≤ 10% of mid. Criterion 5 references the existing analyst consensus. Neither of these requires REQ-DATA-03 (Greeks). However, REQ-SCREEN-01 also feeds into REQ-TRADE-01 (CspAgent), which selects a strike "targeting a put Delta between `target_delta_low` and `target_delta_high`". The `WheelCandidateReport` produced by `WheelAnalyst` includes a `recommended_strike_range` that, to be actionable for CspAgent's Delta-based selection, must itself be grounded in Greek values. If the WheelAnalyst does not call `get_options_greeks` to anchor the recommended range, CspAgent will receive a dollar-value range with no Delta information, breaking REQ-TRADE-01 AC4. The dependency chain REQ-SCREEN-01 → REQ-DATA-03 is missing.

**Impact:** Phase 2 implementation may omit Greeks from `WheelAnalyst`'s tool set. The `recommended_strike_range` will be computed from raw chain prices rather than Delta, making it potentially inconsistent with REQ-TRADE-01's Delta-based selection and producing trades outside the configured Delta envelope.

**Suggested resolution:** Add `REQ-DATA-03` to `REQ-SCREEN-01`'s dependencies table. Clarify in the description whether `WheelAnalyst` itself calls `get_options_greeks` to compute an approximate Delta-anchored strike range, or delegates that computation entirely to `CspAgent`.

---

### [SEV-REVIEW-10] Medium — `WheelPosition` persistence scheme conflicts with TradingMemoryLog design and introduces concurrent-access risk

**Requirement(s):** REQ-LIFE-02, REQ-LIFE-05

**Finding:** REQ-LIFE-02 says `WheelPosition` is "persisted (as JSON) alongside the memory log" and "keyed by `{ticker}-cycle-{N}`". REQ-LIFE-05 also writes to `TradingMemoryLog` at `CYCLE_COMPLETE`. The existing `TradingMemoryLog` uses a single markdown file with an atomic temp-file write pattern. REQ-LIFE-02 appears to describe a separate JSON file per position. If `wheel-status` (REQ-LIFE-06) reads multiple position files while a running LangGraph graph is writing them, there is no locking mechanism. On Windows (the target platform), file-system locking is mandatory and a concurrent write to the same file from two graph invocations will raise `PermissionError`. The REQ does not address concurrency or the directory structure for position files.

**Impact:** Two simultaneous wheel analyses on different tickers could corrupt each other's position files. On the Windows target platform this is more likely to produce visible errors than on Unix. The design also creates an inconsistency: wheel cycle history is split across two storage backends (JSON files for positions, markdown memory log for reflections).

**Suggested resolution:** Define the position store's directory path as a config key (e.g., `config["wheel"]["positions_dir"]`). Specify that writes use the same atomic temp-file + rename pattern as `TradingMemoryLog`. Clarify whether cycle history in the memory log duplicates or references the JSON position file.

---

### [SEV-REVIEW-11] Low — `online_tools` config key referenced in REQ-DATA-01 AC3 does not exist in the codebase

**Requirement(s):** REQ-DATA-01

**Finding:** REQ-DATA-01 AC3 states: "when `online_tools` config key `options_chain` is set to `alpha_vantage`, tool routes to Alpha Vantage adapter." The actual config dict (`default_config.py`) uses `data_vendors` and `tool_vendors` as the routing keys — there is no `online_tools` key. This is a terminology error that will confuse the engineer implementing the routing, who will look for `online_tools` in `interface.py` and not find it.

**Impact:** Low — the intention is clear, but the wrong key name will cause implementation friction and potentially a mis-implemented routing path.

**Suggested resolution:** Replace `online_tools` with `config["wheel"]["options_data_vendor"]` or `config["data_vendors"]["options_data"]` consistently throughout the REQ, matching the existing `data_vendors` structure.

---

### [SEV-REVIEW-12] Low — New wheel config keys are not wired into `_ENV_OVERRIDES` in `default_config.py`

**Requirement(s):** REQ-NFR-03, Section 7 (Configuration Keys)

**Finding:** REQ-NFR-03 requires all wheel thresholds to be overridable via `TRADINGAGENTS_WHEEL_*` env vars. The existing `_apply_env_overrides()` mechanism in `default_config.py` requires explicit entries in the `_ENV_OVERRIDES` dict for each key. The REQ lists 14 new config keys but does not enumerate the corresponding `TRADINGAGENTS_WHEEL_*` env var names or specify that the implementation must add them to `_ENV_OVERRIDES`. Without this, the env-var override will not work even if the keys are present in `DEFAULT_CONFIG`.

**Impact:** Low — NFR-03 will fail silently: the env vars will be set but ignored. Caught at test time.

**Suggested resolution:** Add a table in Section 7 mapping each config key to its `TRADINGAGENTS_WHEEL_*` env var name. The TSPEC author must then add all entries to `_ENV_OVERRIDES`.

---

### [SEV-REVIEW-13] Low — REQ-TRADE-02 `annualised_yield_pct` formula uses calendar days, not trading days — document the convention

**Requirement(s):** REQ-TRADE-02

**Finding:** The `annualised_yield_pct` formula is `(mid_premium / strike) × (365/dte) × 100`. The `dte` field is described as "days to expiration from trade_date" — it is ambiguous whether this is calendar days or trading days. Options markets use calendar days for DTE, and using 365 (calendar) is conventional. However, the `annualised_yield_pct` on a 30-DTE trade computed with 252/30 (trading days) versus 365/30 (calendar days) differs by ~45%, which would make the `min_annualised_yield_pct = 12%` threshold meaningless without the convention documented. Similarly, `cycle_annualised_return_pct` in `WheelPosition` (REQ-LIFE-02) has the same ambiguity.

**Impact:** Low but creates a consistency gap: if one agent uses 365 and another uses 252, comparisons across the system will be incorrect.

**Suggested resolution:** Explicitly state "DTE is always calendar days; annualisation uses 365" in REQ-TRADE-02 description and REQ-LIFE-02 description.

---

### [SEV-REVIEW-14] Low — REQ-DATA-04 `within_options_cycle` flag logic described in AC2 appears inverted

**Requirement(s):** REQ-DATA-04

**Finding:** REQ-DATA-04 AC2 states: "Earnings is 10 days away and the next expiration is 30 days away → `within_options_cycle` is `True`." The description says `within_options_cycle` is `True` if "any front-month expiration falls on or after the earnings date." If earnings is in 10 days and the expiration is in 30 days, the expiration is *after* the earnings date, so `True` is correct. However, the description's phrasing "falls on or after the earnings date" actually captures a different condition than intended. The intent for the wheel strategy is to flag whether earnings falls *within* the option's remaining life (i.e., earnings date < expiration date). The current description is ambiguous enough that an engineer could implement the complement condition. The correct logical test is: `within_options_cycle = earnings_date <= expiration_date` (where both are future dates). The AC2 example is consistent with this formula but the prose description is misleadingly phrased.

**Impact:** Low — AC2 is unambiguous as an example; the prose is confusing but not blocking.

**Suggested resolution:** Rewrite the description as: "`within_options_cycle` is `True` if the next earnings date falls on or before the front-month expiration date — meaning earnings will occur before the option expires."

---

## Approved Items

- **Problem Statement (Section 1):** Accurately reflects the actual gaps in the codebase. The six identified gaps are all real and verified against `y_finance.py`, `agent_states.py`, and `schemas.py`.
- **REQ-DATA-01 (Options Chain Retrieval):** The core `yf.Ticker.option_chain(expiry)` API is real and available in yfinance. The tool signature, return format, and error-handling approach (returning a string rather than raising) are all consistent with the existing codebase pattern (`get_fundamentals`, etc.).
- **REQ-DATA-03 (Greeks Calculation):** BSM Greeks computation from yfinance-supplied IV, underlying price, and a static or fetched risk-free rate is fully implementable in Python using `scipy.stats.norm`. The acceptance criteria (Delta range for ATM put, 0-DTE guard) are concrete and testable.
- **REQ-DATA-04 (Earnings Date Lookup):** `yf.Ticker.calendar` is a real yfinance attribute. The function signature and ACs are implementable and well-specified.
- **REQ-SCREEN-02, REQ-TRADE-02, REQ-TRADE-04, REQ-LIFE-04 (Pydantic schemas):** All field names and types (excluding the `tuple` issue in REQ-SCREEN-02) are well-chosen, consistent with the existing schema style in `schemas.py`, and produce clear `render_*` functions. `Optional[str]` for `rejection_reason` with a conditional-non-null AC is correctly specified.
- **REQ-NFR-01 (Backwards compatibility):** The `wheel_phase is None → equity path unchanged` guard is the correct design choice. The spec correctly identifies that existing equity flows must not be disturbed.
- **REQ-NFR-04 (Structured output via `structured.py`):** Correctly references the existing `structured.py` wrapper pattern. New decision schemas (CSP, CC, Roll) are appropriately routed through this layer.
- **REQ-NFR-06 (Error handling):** The requirement that data fetch failures return graceful error strings to the agent (not exceptions) is consistent with the existing error handling in `y_finance.py` and is correctly specified.
- **REQ-LIFE-05 (Memory log integration):** The proposed integration with `TradingMemoryLog` (append entry at `CYCLE_COMPLETE`, inject as `past_context` on subsequent runs) is well-aligned with the existing `store_decision()` / `get_past_context()` API and requires no breaking changes to the memory module.
- **Section 7 (Configuration keys):** The set of thresholds is complete for the described strategy. Default values are reasonable industry conventions for the wheel strategy (0.20–0.30 Delta, 28–45 DTE, 12% annualised yield, 21 DTE roll trigger).
