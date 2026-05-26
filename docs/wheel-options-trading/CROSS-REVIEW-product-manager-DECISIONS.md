# Cross-Review — Product Manager — DECISIONS
# Document: DECISIONS-wheel-options-trading.md v0.1.0

| Field | Value |
|---|---|
| Reviewer | Product Manager (PM-Review) |
| Date | 2026-05-25 |
| Recommendation | Needs revision |

---

## Summary

Five ADRs were reviewed against REQ-wheel-options-trading.md v0.2.0 and the ten user stories (US-01 through US-10). Overall the DECISIONS document is technically solid and clearly traces the engineering history (SE cross-reviews, TE cross-reviews, PM v0.2.0 revision). However, several ADRs lack product-level justification, product-observable re-evaluation triggers, or explicit REQ-ID citations in their Context sections. Three findings are High severity; three are Medium.

The most significant gaps are:

1. **ADR-WHEEL-01** names the metric "IV Rank" in all user-facing surfaces while computing realised volatility rank. The product consequence for user trust and accuracy claims is underdocumented.
2. **ADR-WHEEL-02** and **ADR-WHEEL-03** are presented as pure engineering decisions with no stated product constraint driving them. From a PM perspective there is no way to assess whether a different product-scope decision could have avoided these constraints.
3. **ADR-WHEEL-03** omits a product consequence that directly affects US-05: the single shared graph topology serialises wheel phases per `AgentState` invocation, meaning simultaneous multi-ticker wheel tracking in one graph run is not supported.
4. **ADR-WHEEL-04** documents the sentinel silent-failure path inadequately from a product perspective: users receive `tradeable=False` with no visible error signal under consistent LLM schema failure.
5. **ADR-WHEEL-05** has no product-level re-evaluation trigger for the stale-file orphan risk that directly threatens US-05 correctness.

---

## Findings

### [PM-DECISIONS-01] High — ADR-WHEEL-01 does not document the user-facing accuracy claim conflict created by the "IV Rank" terminology

**ADR:** ADR-WHEEL-01

**Finding:** Assumption A3 in REQ v0.2.0 explicitly states: "The terms 'IV Rank' and 'IV Percentile' are retained for user familiarity but refer to realised volatility rank/percentile." ADR-WHEEL-01 records this decision correctly in the Decision section but the Consequences section does not address what this means for product accuracy claims. The wheel strategy depends critically on elevated implied volatility as an entry signal (US-02). Users familiar with the standard definition of IV Rank (which uses historical options IV) will interpret the system's output as measuring implied volatility when it measures realised volatility. During earnings or macro events — precisely the conditions where users most depend on IV Rank — realised vol can meaningfully lag implied vol, causing the system to show "normal" environment when true IV is elevated. The Consequences section notes this lag risk in one sentence but does not state:

- Whether any user-facing disclaimer is required in the CLI display or report output.
- Whether the `WheelCandidateReport.iv_assessment` plain-English summary field (REQ-SCREEN-02) should include a disclosure that the metric is realised-vol based.
- How the product will handle a scenario where a user mis-reads the signal and sells premium into a true high-IV event that the realised-vol proxy reported as normal.

This is a product accuracy and trust issue, not an engineering issue.

**Suggested resolution:** Add a Consequences bullet stating: "User-facing CLI output (REQ-SCREEN-03, REQ-LIFE-06) and the `iv_assessment` field (REQ-SCREEN-02) must include a disclosure that IV Rank is computed from realised volatility, not historical options IV, to prevent users from treating the signal as equivalent to true IV Rank. This disclosure requirement should be carried into the FSPEC and TSPEC for WheelAnalyst and WheelCandidateReport." Tighten the re-evaluation trigger to specify a concrete, observable condition: "If yfinance or any zero-cost API provides a backward-accessible historical IV time series for individual equities (i.e., at least 252 daily IV observations per ticker retrievable in a single call within the REQ-NFR-02 10-second budget), replace the realised-vol proxy." The current trigger ("if a no-cost historical IV source becomes available") is too vague to be actionable.

---

### [PM-DECISIONS-02] High — ADR-WHEEL-02 contains no product-level justification; product consequences of reduced type safety are absent

**ADR:** ADR-WHEEL-02

**Finding:** The entire ADR is framed as a pure engineering constraint (LangGraph JSON serialisation, TypedDict schema validation). No product requirement, user story, or scope constraint is cited as the reason this decision needed to be made at all. From a PM perspective, the question is: what product constraint required the wheel phase to be stored in `AgentState` in the first place, and why did that constraint rule out alternatives? REQ-LIFE-01 is the direct source requirement (it prescribes `wheel_phase: Optional[str]` as an `AgentState` field and the `WheelPhase(str, Enum)` type), but REQ-LIFE-01 is not cited in the Context or Consequences sections. Additionally, the Deciders list omits TE-Review, which is inconsistent with the other ADRs that document all reviewers who engaged with the decision.

The Consequences section documents the engineering risk (runtime type safety is reduced) but not the product consequence: if `wheel_phase` is silently misspelled, the system silently falls through to the equity-only path (REQ-LIFE-01 AC6). A user who initiated a `"csp_open"` phase management run and received an equity-only report without any warning would have no indication that the wheel phase routing failed. This is a silent correctness failure that affects US-05 and US-06.

**Suggested resolution:** Add a Context statement tracing the decision to REQ-LIFE-01's dual constraint: (a) `AgentState` must carry `wheel_phase` for graph routing (REQ-LIFE-01 AC1–AC4), and (b) `AgentState` is JSON-serialised by LangGraph. Cite REQ-LIFE-01 explicitly. Add a Consequences bullet: "If a `wheel_phase` string is misspelled by any code path that writes to `AgentState`, the system silently falls back to equity-only analysis (REQ-LIFE-01 AC6). The user receives a standard equity report with no indication that wheel phase routing failed. This represents a correctness risk for US-05 and US-06 that is mitigated only by the code-review convention (not the type system) of always using `WheelPhase` enum constants." Add a product-observable re-evaluation trigger: "If a user-reported case of silent phase fall-through is identified in production use, consider adding an explicit warning message to the CLI output (REQ-SCREEN-03) when `wheel_phase` falls back from a non-None value to equity-only."

---

### [PM-DECISIONS-03] High — ADR-WHEEL-03 has no product/scope constraint in Context; omits a product consequence for US-05 multi-ticker tracking

**ADR:** ADR-WHEEL-03

**Finding:** The Context section describes the engineering design space (three LangGraph architectural patterns) with no mention of which product requirements or user stories constrained the choice. REQ-LIFE-01's Architecture Note prescribes the shared graph with preamble conditional edge, but this is cited only in the Decision section under the chosen option. From a PM perspective, it is unclear why the product scope required the existing `StateGraph` to be extended rather than a separate graph being acceptable. The PM-Author is listed in neither the Deciders table nor the Context, suggesting this ADR was resolved without a product-level sign-off on the scope constraint.

More critically, the Consequences section omits a product-visible limitation: because the single shared `AgentState` carries one `wheel_phase` value at a time, a single graph invocation can manage at most one wheel position per run. Simultaneous analysis of multiple tickers in wheel mode (e.g., running `wheel_phase="csp_open"` for NVDA and AAPL in the same session) is not supported by this architecture. This directly constrains the scope of US-05 ("Track open wheel positions") and US-07 ("See a running P&L... across multiple tickers") — users cannot run a multi-ticker wheel status check in one pass.

**Suggested resolution:** Add a Context statement: "REQ-LIFE-01 Architecture Note requires the wheel phase routing to be implemented within the existing `StateGraph` topology to preserve compatibility with REQ-NFR-01 (existing equity pipeline unchanged). This requirement ruled out a separate `WheelGraph` at the product-scope level, not solely at the engineering level." Add a Consequences bullet: "The single `AgentState` per graph invocation means only one ticker's wheel phase can be active per run. Users who wish to manage multiple simultaneous wheel positions must invoke the graph separately per ticker. This is a known product limitation that constrains the scope of US-05 and US-07 for MVP. Multi-ticker batch wheel management is explicitly deferred (REQ scope: 'one wheel cycle = one ticker per invocation')." Add PM-Author to the Deciders table. Add a product-level re-evaluation trigger: "If US-05 or US-07 acceptance criteria require multi-ticker batch management in a future phase, the shared-graph architecture will need to be revisited in favour of a per-ticker invocation loop or a dedicated WheelGraph."

---

### [PM-DECISIONS-04] Medium — ADR-WHEEL-04 understates the product impact of the silent safe-fallback sentinel path

**ADR:** ADR-WHEEL-04

**Finding:** The Consequences section notes: "if the LLM consistently fails schema validation, every run produces a `tradeable=False` result with no user-visible error." This is accurate, but the product impact is understated. From a user perspective (US-03, US-04, US-06), a `tradeable=False` result that originates from a structured-output failure is indistinguishable from a genuine `tradeable=False` assessment from the LLM: both have a `rationale` field, and the sentinel's rationale is `"Structured output failed — safe fallback applied."` A user who does not inspect the raw rationale string will interpret the result as a genuine "do not trade" recommendation. There is no documented requirement that the CLI display (REQ-SCREEN-03, REQ-LIFE-06) surface the sentinel rationale prominently, and no re-evaluation trigger is product-observable. The trigger is entirely internal to `structured.py`: "if `structured.py` is extended to return a Pydantic instance rather than a raw string." No user-facing or operational signal triggers re-evaluation.

Additionally, REQ-NFR-04 is the cited product requirement, but the ADR does not note whether the PROPERTIES tests required by REQ-NFR-05 will include a test that the CLI prominently flags sentinel results to users.

**Suggested resolution:** Add a Consequences bullet: "When the sentinel is returned, the `rationale` field value `'Structured output failed — safe fallback applied.'` must be surfaced distinctly in the CLI report (e.g., a warning banner in the Rich panel) so users can distinguish a genuine 'do not trade' assessment from a system failure. This requirement should be carried into the FSPEC for the CLI display layer (REQ-SCREEN-03) and the `tradingagents wheel-status` command (REQ-LIFE-06)." Add a product-observable re-evaluation trigger: "If users report unexplained `tradeable=False` outputs that cannot be traced to a genuine assessment, audit the sentinel path. If the sentinel is firing on more than 5% of runs for a given LLM provider, escalate to a structured-output integration fix for that provider." Cite REQ-NFR-05 as the source for the PROPERTIES test requirement.

---

### [PM-DECISIONS-05] Medium — ADR-WHEEL-05 has no product-level re-evaluation trigger for the stale-file orphan risk that directly threatens US-05

**ADR:** ADR-WHEEL-05

**Finding:** The Consequences section correctly documents that stale `status="open"` JSON files will be picked up by `load_latest_open_position` on subsequent runs if a cycle is abandoned mid-flight. This is a correctness risk for US-05 ("Track open wheel positions and their cost basis") — a user who abandons a NVDA wheel cycle (e.g., closes the position manually at their broker without running the `CYCLE_COMPLETE` path) will see the old position re-surfaced on the next run. There is no re-evaluation trigger that captures this product risk. The re-evaluation trigger for this ADR is absent entirely (unlike ADRs 01, 02, and 04 which have explicit triggers). The Deciders list also omits TE-Review, which reviewed the TSPEC and identified the lexicographic sort bug (TE-TSPEC-04) that this ADR references — TE-Review should be a named Decider given that contribution.

**Suggested resolution:** Add a re-evaluation trigger: "If user-reported cases of stale position files re-surfacing after manual position closure become frequent (indicating the MVP usage pattern assumption — 'one analysis at a time per ticker, initiated manually' — is not holding), implement a position GC mechanism: a `tradingagents wheel-close {ticker} {cycle}` CLI command that transitions the cycle file to `status='abandoned'` and removes it from the active position index." Add TE-Review to the Deciders table. Optionally, note that a product-level acceptance criterion for US-05 should require the CLI `wheel-status` command (REQ-LIFE-06) to display a staleness warning if a position file has not been updated in more than a configurable number of days.

---

### [PM-DECISIONS-06] Low — REQ-ID citations are inconsistent across ADRs: ADR-WHEEL-02 and ADR-WHEEL-03 cite no REQ IDs in their Context sections

**ADR:** ADR-WHEEL-02, ADR-WHEEL-03

**Finding:** ADR-WHEEL-01 cites REQ-DATA-02, REQ-NFR-02, and Assumption A1/A3. ADR-WHEEL-04 cites REQ-NFR-04. ADR-WHEEL-05 cites REQ-LIFE-02. However, ADR-WHEEL-02's Context section cites no REQ ID (REQ-LIFE-01 prescribes the `wheel_phase: Optional[str]` field directly). ADR-WHEEL-03's Context section cites no REQ ID (REQ-LIFE-01 Architecture Note prescribes the shared-graph integration constraint). This inconsistency makes it difficult to perform requirements traceability: a reader following REQ-LIFE-01 to the DECISIONS document cannot locate the relevant ADRs without reading the full text of each.

**Suggested resolution:** Add explicit REQ-ID references to the Context section of ADR-WHEEL-02 ("This decision is required by REQ-LIFE-01, which mandates `wheel_phase: Optional[str]` in `AgentState`...") and ADR-WHEEL-03 ("This decision is required by REQ-LIFE-01 Architecture Note, which prescribes the shared graph with preamble conditional edge..."). Consider adding a Traceability Index at the end of the DECISIONS document mapping each REQ ID to the ADR(s) it constrains, mirroring the Traceability Gap Summary pattern used in the TSPEC.

---

## Approved Items

The following aspects of the DECISIONS document are approved without change:

- **ADR-WHEEL-01 Decision and Alternatives table:** The four-option alternatives table is genuine, not a strawman. The rejection reasons for third-party IV feeds (Assumption A1), 252-call yfinance approach (REQ-NFR-02 budget), and index-level VIX proxy (single-stock accuracy) are each grounded in product constraints. The chosen option is correctly traced to implementability within the existing vendor routing layer.
- **ADR-WHEEL-01 zero-variance guard:** Documenting the `iv_rank = 50` sentinel for flat vol series and the `iv_percentile` boundary behaviour (strict less-than CDF) as consequences is thorough and testable.
- **ADR-WHEEL-02 Decision:** The `WheelPhase(str, Enum)` pattern as a source of string constants while storing `Optional[str]` in `AgentState` is a clean resolution to the LangGraph serialisation constraint. The unit-test implication (assert on literal strings, not enum imports) is correctly documented.
- **ADR-WHEEL-03 routing table:** The five-row `wheel_phase` → target-node mapping table is clear, complete, and consistent with REQ-LIFE-01 AC1–AC5. The `WheelStateError` guard for `cc_open` with no open position is correctly documented.
- **ADR-WHEEL-04 four-step fallback chain:** The three-layer (four-step) pattern is unambiguous. The note that `invoke_structured_or_freetext` always returns `str` and that agents must not assume a Pydantic instance is a critical implementation clarification. The `WheelAnalyst`/`RollCheckAgent` LLM tier selection (`deep_think_llm` vs `quick_think_llm`) is a useful product-relevant consequence.
- **ADR-WHEEL-05 atomic write pattern and lexicographic sort fix:** The `tempfile.mkstemp + os.replace` pattern with same-directory temp file for Windows atomic semantics is correctly motivated. The TE-identified lexicographic sort bug (TE-TSPEC-04) and its regex-based integer sort fix are correctly documented as High-severity consequences. The two-store complementarity (JSON = authoritative state; memory log = reflective audit trail) is a clear product-level architectural statement.
