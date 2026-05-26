# Cross-Review: product-manager — DECISIONS

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/DECISIONS-wheel-options-trading.md v0.2.0
**Date:** 2026-05-25
**Iteration:** 2

---

## Summary

All six findings from the v1 PM review (PM-DECISIONS-01 through PM-DECISIONS-06) were addressed in
v0.2.0. The most significant gaps — absent user-facing accuracy labelling (PM-DECISIONS-01),
missing product-level justifications in ADR-WHEEL-02 and ADR-WHEEL-03 (PM-DECISIONS-02,
PM-DECISIONS-03), the silent sentinel risk (PM-DECISIONS-04), the missing orphan-file re-evaluation
trigger (PM-DECISIONS-05), and inconsistent REQ-ID citations (PM-DECISIONS-06) — are all resolved.
The DECISIONS document is now coherent from a product perspective.

One new Low finding is raised in this iteration: the zero-variance sentinel value (`iv_rank = 50`)
introduced in ADR-WHEEL-01 is exposed to users via the same `iv_environment` classification that
drives WheelAnalyst Criterion 1 (REQ-SCREEN-01). A user who encounters the sentinel in a genuine
flat-volatility scenario will receive an `"normal"` environment label (since `iv_rank = 50` maps to
`"normal"` per REQ-DATA-02) that is the product of a data-quality guard, not a real market signal.
No user-facing disclosure for this edge case is documented.

---

## Prior-Finding Resolution Status

| Prior ID | Description | Status in v0.2.0 |
|----------|-------------|-----------------|
| PM-DECISIONS-01 | User-facing accuracy claim for "IV Rank" label | Resolved — Consequences bullet added; label requirement ("Volatility Environment Score" or explicit annotation) captured for PLAN and CLI implementation |
| PM-DECISIONS-02 | No product justification in ADR-WHEEL-02; silent phase fall-through product risk undocumented | Resolved — REQ-LIFE-01 cited in Context; product-risk Consequences bullet added; CLI warning surface requirement added |
| PM-DECISIONS-03 | No product/scope constraint in ADR-WHEEL-03 Context; single-ticker constraint omitted | Resolved — REQ-LIFE-01 Architecture Note cited; single-ticker Consequences bullet added with US-05/US-07 scope note and out-of-scope confirmation; PM-Author added to Deciders |
| PM-DECISIONS-04 | Silent safe-fallback sentinel underdocumented; no product-observable trigger | Resolved — Distinguishability Consequences bullet added; sentinel marker string declared a contract; re-evaluation trigger (>1 in 100 sentinel fires) is production-observable |
| PM-DECISIONS-05 | No re-evaluation trigger for orphan-file risk; TE-Review absent from Deciders | Resolved — Re-evaluation trigger added with scale and concurrent-analysis conditions; `tradingagents wheel-cleanup` future command noted; TE-Review added to Deciders |
| PM-DECISIONS-06 | Inconsistent REQ-ID citations in ADR-WHEEL-02 and ADR-WHEEL-03 Context sections | Resolved — REQ-LIFE-01 citations added to both Context sections |

---

## Findings

| ID | Severity | Scope | Finding | Requirement ref |
|----|----------|-------|---------|----------------|
| F-01 | Low | Local | The zero-variance sentinel path (`iv_rank = 50`, `iv_environment = "normal"`) is not disclosed to users in the CLI or WheelCandidateReport, even though it drives a real WheelAnalyst criterion (Criterion 1). See detail below. | REQ-DATA-02, REQ-SCREEN-01, REQ-SCREEN-03 |

### F-01 Detail — Zero-variance sentinel produces an undisclosed "normal" IV environment label

ADR-WHEEL-01 correctly documents the zero-variance guard: when the OHLCV lookback window is flat
(all close prices identical), `iv_rank = 50` and `iv_environment = "normal"` are returned, and the
report string includes `"IV range is flat — rank set to neutral 50"`. This is the correct
engineering behaviour (consistent with REQ-DATA-02 AC5 and REQ-NFR-06).

The product gap is that `iv_environment = "normal"` feeds directly into WheelAnalyst Criterion 1
(REQ-SCREEN-01: `iv_rank >= 25` threshold check). A sentinel-generated `iv_rank = 50` will cause
Criterion 1 to pass (`50 >= 25`), approving the stock for wheel consideration despite the
underlying data being degenerate. A user who sees `WheelCandidateReport.approved = true` with
`iv_environment = "normal"` in this edge case has no way to know the IV signal is a data-quality
fallback rather than a genuine market reading.

The ADR Consequences section documents this sentinel in the context of unit testing
(`iv_percentile` boundary and the note string) but does not state that the CLI or
`WheelCandidateReport.iv_assessment` field (REQ-SCREEN-02) should surface the flat-volatility note
when the sentinel fires. This omission is a product-facing accuracy gap: the system presents a
neutral IV reading as a real signal when it is a guard value.

**Suggested resolution:** Add a Consequences bullet to ADR-WHEEL-01: "When the zero-variance
sentinel fires (`iv_rank = 50` due to flat OHLCV series), the formatted report string includes the
note `'IV range is flat — rank set to neutral 50'`. The CLI and `WheelCandidateReport.iv_assessment`
field (REQ-SCREEN-02) must surface this note verbatim when it is present in the report string, so
users are not misled by a sentinel-generated `iv_environment = 'normal'` result. This disclosure
requirement is parallel to the realised-vol label requirement captured in the same Consequences
section."

---

## Positive Observations

- **ADR-WHEEL-01 v0.2.0 accuracy label requirement** is now clearly stated as a named product
  contract: the metric must appear as 'Volatility Environment Score' or with an explicit annotation
  in CLI output. The requirement is correctly scoped to PLAN and CLI implementation. This directly
  addresses the user-trust risk raised in PM-DECISIONS-01 and closes the accuracy-claim gap.

- **ADR-WHEEL-02 v0.2.0 product-risk Consequences bullet** correctly states the user-visible
  consequence of a misspelled `wheel_phase` (equity-only report with no indication of routing
  failure) and names the affected user stories (US-05, US-06). The CLI warning surface requirement
  is actionable and traceable to REQ-SCREEN-03 and REQ-LIFE-06.

- **ADR-WHEEL-03 v0.2.0 single-ticker constraint** is now a first-class product consequence,
  correctly linking the `AgentState` architecture to the scope boundary for US-05 and US-07. The
  explicit out-of-scope statement ("Portfolio-level margin/buying-power calculation") ties the
  constraint back to the REQ scope section, making it traceable for future scope decisions.

- **ADR-WHEEL-04 v0.2.0 distinguishability requirement** adds a meaningful product contract: the
  sentinel marker string is declared immutable and must be rendered with distinct CLI styling.
  Defining the sentinel string as a contract (not an implementation detail) prevents silent
  regression in future CLI refactors.

- **ADR-WHEEL-05 v0.2.0 orphan-file re-evaluation trigger** is now product-observable: both scale
  (>500 cycle files, >100ms load time) and user-reported confusion triggers are documented. The
  `tradingagents wheel-cleanup --dry-run` future command is correctly noted as a Phase N+ item
  rather than an MVP commitment, which is consistent with the REQ out-of-scope list.

- **Decider tables** are now complete and consistent across all five ADRs. PM-Author appears in
  ADR-WHEEL-03; TE-Review appears in ADR-WHEEL-05. This was the outstanding gap in PM-DECISIONS-03
  and PM-DECISIONS-05.

---

## Recommendation

**Approved with minor changes**

F-01 is Low severity. The zero-variance sentinel disclosure gap is a minor product-accuracy
omission that can be resolved in the PLAN phase as an addendum to the existing accuracy-label
requirement in ADR-WHEEL-01 Consequences. It does not block PLAN authoring.

Recommendation: Approved
