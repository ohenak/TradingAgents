# Cross-Review: product-manager — DECISIONS

**Reviewer:** product-manager
**Document reviewed:** docs/wheel-options-trading/DECISIONS-wheel-options-trading.md v0.3.0
**Date:** 2026-05-25
**Iteration:** 3

---

## Summary

All prior PM findings have been addressed. The single finding from the v2 review (F-01, Low — zero-variance sentinel disclosure gap in ADR-WHEEL-01) is fully resolved in v0.3.0. The new zero-variance sentinel disclosure Consequences bullet correctly names the affected fields (REQ-SCREEN-02, REQ-SCREEN-03), explains the Criterion 1 pass-through risk, and carries the disclosure requirement forward to the PLAN and FSPEC for WheelAnalyst and WheelCandidateReport. This closes the product accuracy gap identified in the v2 review.

The remaining v0.3.0 additions — the equity-passthrough integration test invariant (ADR-WHEEL-03), tmp_path isolation and integer-sort regression test (ADR-WHEEL-05), sentinel constant enforcement and three-level fallback test coverage with level-2 freetext-JSON scenario (ADR-WHEEL-04) — are TE-driven changes reviewed from a product lens below. None introduce scope creep, silently drop product requirements, or make product decisions without PM traceability.

---

## Prior-Finding Resolution Status

| Prior ID | Description | Status in v0.3.0 |
|----------|-------------|-----------------|
| PM-DECISIONS-01 (v1) | User-facing accuracy claim for "IV Rank" label | Carried resolved from v0.2.0 — no regression |
| PM-DECISIONS-02 (v1) | No product justification in ADR-WHEEL-02; silent phase fall-through risk | Carried resolved from v0.2.0 — no regression |
| PM-DECISIONS-03 (v1) | No product/scope constraint in ADR-WHEEL-03; single-ticker constraint omitted | Carried resolved from v0.2.0 — no regression |
| PM-DECISIONS-04 (v1) | Silent safe-fallback sentinel underdocumented | Carried resolved from v0.2.0 — reinforced in v0.3.0 by sentinel constant enforcement and test-coverage additions |
| PM-DECISIONS-05 (v1) | No re-evaluation trigger for orphan-file risk | Carried resolved from v0.2.0 — no regression |
| PM-DECISIONS-06 (v1) | Inconsistent REQ-ID citations in ADR-WHEEL-02 and ADR-WHEEL-03 | Carried resolved from v0.2.0 — no regression |
| F-01 (v2) | Zero-variance sentinel produces undisclosed "normal" IV environment label (ADR-WHEEL-01) | Resolved — Consequences bullet added; disclosure requirement named to REQ-SCREEN-02, REQ-SCREEN-03, REQ-DATA-02, REQ-SCREEN-01; Criterion 1 pass-through risk documented; PLAN and FSPEC carry-forward stated |

---

## Findings

No new findings.

---

## New v0.3.0 Additions — Product Lens Assessment

### ADR-WHEEL-01 — Zero-variance sentinel disclosure (Consequences bullet)

The new bullet addresses F-01 from the v2 review in full. The disclosure requirement is:

- Scoped to the correct user-facing surfaces (REQ-SCREEN-02 `iv_assessment` field, REQ-SCREEN-03 CLI output).
- Explicitly carries the requirement to the PLAN and FSPEC, making it traceable for the implementation phase.
- Correctly identifies the product risk: `iv_rank = 50` passes WheelAnalyst Criterion 1 (`>= 25`), so a sentinel-generated approval based on degenerate data would not self-evidently fail downstream — making the disclosure non-optional.
- The parallel framing ("parallel to the realised-vol label requirement") provides correct cross-reference to the v0.2.0 accuracy-label requirement that PM-DECISIONS-01 resolved.

No product gaps remain in ADR-WHEEL-01.

### ADR-WHEEL-03 — Equity-passthrough integration test invariant (Consequences bullet)

The new bullet prescribes a dedicated integration test asserting that `wheel_phase is None` passes through to `fundamental_analyst` unchanged, with no options-layer tools invoked and output fields functionally equivalent to a pre-feature equity-only run. From a product perspective this is the primary regression guard for REQ-NFR-01 (existing equity pipeline unchanged), and naming it explicitly as a PROPERTIES document requirement is the correct product-contract mechanism. No scope creep; no product decisions absent from REQ/FSPEC.

### ADR-WHEEL-04 — Sentinel constant enforcement (Consequences bullet)

The STRUCTURED_OUTPUT_SENTINEL module-level constant requirement directly strengthens the distinguishability contract established in the v0.2.0 Consequences bullet (PM-DECISIONS-04). Requiring all four wheel agents and the CLI display layer to import the constant rather than hardcoding the string is a product-beneficial enforcement: it ensures the sentinel marker string cannot silently drift from the CLI rendering contract without surfacing as a test failure. No product decisions made; this is an implementation discipline requirement that protects an existing product contract.

### ADR-WHEEL-04 — Three-level fallback test coverage with level-2 freetext-JSON scenario (Consequences bullet)

The level-2 freetext-valid-JSON scenario guards against the silent `tradeable=False` risk: without it, a valid freetext JSON response could be misclassified as a total fallback, producing a spurious `tradeable=False` outcome that a user would interpret as a genuine "do not trade" recommendation. This test requirement directly protects US-03, US-04, and US-06 acceptance criteria. Carrying this as a PROPERTIES requirement is consistent with REQ-NFR-05. No scope creep.

### ADR-WHEEL-05 — tmp_path isolation and integer-sort regression test (Consequences bullets)

The tmp_path isolation requirement prevents test pollution of the real `positions_dir`, which protects the correctness of `wheel-status` (REQ-LIFE-06) during development. The integer-sort regression test for cycle ≥ 10 guards against re-introduction of the lexicographic sort bug (TE-TSPEC-04), which is a correctness risk for US-05. Both requirements are product-visible in their consequences and correctly named as PROPERTIES document requirements. No scope creep.

---

## Positive Observations

- The zero-variance sentinel disclosure bullet in ADR-WHEEL-01 v0.3.0 is precisely scoped: it names the sentinel note verbatim (`'IV range is flat — rank set to neutral 50'`), names the exact output fields, cites the correct REQ IDs, and explains why the disclosure is non-optional (Criterion 1 pass-through). This is a model product-consequence statement.
- The STRUCTURED_OUTPUT_SENTINEL constant requirement in ADR-WHEEL-04 upgrades an informal contract (sentinel marker string declared in prose) to an enforceable implementation contract (module-level constant, imported by consumers). This prevents silent CLI rendering regression without requiring additional product specification.
- The equity-passthrough integration test invariant in ADR-WHEEL-03 correctly identifies the PROPERTIES document as the right home for this requirement, keeping the DECISIONS document focused on the decision record and delegating test specification to the appropriate artifact.
- All five ADRs continue to carry their v0.2.0 product justifications, REQ-ID citations, and re-evaluation triggers without regression. The v0.3.0 additions are purely additive.

---

## Recommendation

**Approved**

All prior PM findings (six from v1, one from v2) are resolved. No new findings are raised. The v0.3.0 additions are product-consistent and strengthen existing product contracts without introducing scope creep or untraced product decisions. The DECISIONS document is approved from a product perspective.

Recommendation: Approved
