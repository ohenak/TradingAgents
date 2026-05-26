# Cross-Review — Test Engineer — TSPEC (v2)
# Document: TSPEC-wheel-options-trading.md v0.2.0

| Field | Value |
|---|---|
| Reviewer | Test Engineer (TE-Review) |
| Date | 2026-05-25 |
| Iteration | 2 |
| Recommendation | Approved with minor changes |

---

## Resolution Status of Prior Findings

| Finding | Status | Notes |
|---|---|---|
| TE-TSPEC-01 (High) — `get_options_greeks` injectable test seams | Resolved | Section 2.1.3 adds keyword-only `_spot_price`, `_risk_free_rate`, `_sigma` seams. Correctly excluded from `@tool` wrapper. Pattern and rationale are well documented. |
| TE-TSPEC-02 (High) — BSM Theta formula canonical verification | Resolved | Section 2.1.3 now provides explicit canonical put/call forms with sign-verification note and a full numeric example (S=100, K=100, r=0.05, σ=0.20, T=30/365). Expected values and tolerances are stated for unit test assertions. |
| TE-TSPEC-03 (High) — `within_options_cycle` field missing | Resolved | Section 2.1.4 computes `within_options_cycle` using `front_month_expiry` from `yf.Ticker.options`. Output string format includes the field. Edge case (no future expiration available → `False`) is specified. |
| TE-TSPEC-04 (High) — Lexicographic sort bug in `load_latest_open_position` | Resolved | Section 9.3 replaces `sorted(Path.glob(...))` with `glob.glob` + integer-keyed `sorted(..., key=_cycle_number, reverse=True)`. Warning comment explicitly calls out the bug that was fixed. |
| TE-TSPEC-05 (Medium) — Numeric discrepancy in `cycle_annualised_return_pct` | Resolved | Section 9.4 confirms 33.21% as the authoritative value, documents the REQ discrepancy, and states PROPERTIES must assert 33.21% with tolerance ±0.01%. |
| TE-TSPEC-06 (Medium) — `CcAgent` injectable position loader | Partially resolved | Section 5.3 adds `_position_loader` keyword-only seam to `create_cc_agent`. **The same seam is NOT present in `create_roll_check_agent` (Section 5.4) or in `ConditionalLogic._load_position` (Section 6.2)**, both of which were explicitly called out in the original TE-TSPEC-06 suggested resolution. See TE-TSPEC-06-RESIDUAL below. |
| TE-TSPEC-07 (Medium) — `model_validator` on `WheelCandidateReport` | Resolved | Section 3.3 adds `@model_validator(mode="after")` enforcing: `approved=True` requires positive strike range values; `approved=False` requires non-empty `rejection_reason`. The sentinel with `[0.0, 0.0]` is exempt because `approved=False`. |
| TE-TSPEC-08 (Low) — `get_config()` global test seam documentation | Partially resolved | Function signatures include `config: Optional[dict] = None` (Option a from the suggestion). However, the note in Section 2.2 still states config is "injected at function-call time via `get_config()`" without explicitly documenting the intended unit test pattern (pass config dict directly vs. patch `get_config`). See TE-TSPEC-08-RESIDUAL below. |

---

## New or Remaining Findings

---

### [TE-TSPEC-06-RESIDUAL] [Medium] — `create_roll_check_agent` and `ConditionalLogic._load_position` still have no injectable position loader

**TSPEC sections:** Section 5.4 `RollCheckAgent`, Section 6.2 `ConditionalLogic.route_wheel_phase`

**Finding:** The original TE-TSPEC-06 suggested resolution stated: "Apply the same pattern to `create_roll_check_agent(llm, position_store_dir)` (Section 5.4) and `route_wheel_phase()` (Section 6.2 `_load_position`)." The v0.2.0 TSPEC addresses only `CcAgent`. Two remaining cases are unaddressed:

1. `create_roll_check_agent(llm: Any, position_store_dir: str)` — Section 5.4 — loads `WheelPosition` from disk via a hardcoded filesystem call inside the node function. No `_position_loader` seam is shown in the factory signature.

2. `ConditionalLogic._load_position(ticker)` — Section 6.2 — is a private helper that reads from `position_store_dir`. `route_wheel_phase()` is an instance method on `ConditionalLogic`; `_load_position` has no injection point. Unit testing `route_wheel_phase()` for the `"csp_open"` and `"cc_open"` branches (which both call `_load_position`) requires either real JSON files in a temp directory or module-level patching of whatever persistence function `_load_position` delegates to.

**Impact:** Unit tests for `RollCheckAgent` (REQ-LIFE-03 ACs 1–5) and for `route_wheel_phase` guard conditions (REQ-LIFE-01 AC5) must write real files to disk or patch a private method. This is the same testability gap TE-TSPEC-06 identified for `CcAgent` — just not yet closed for the other two consumers.

**Suggested resolution:** Apply the same `_position_loader` pattern:

```python
# create_roll_check_agent factory signature:
def create_roll_check_agent(
    llm: Any,
    position_store_dir: str,
    *,
    _position_loader: Optional[Callable[[str, str], Optional[WheelPosition]]] = None,
) -> Callable[[AgentState, RunnableConfig], dict]:
    position_loader = _position_loader or load_latest_open_position
    ...

# ConditionalLogic constructor:
def __init__(
    self,
    ...,
    _position_loader: Optional[Callable[[str, str], Optional[WheelPosition]]] = None,
):
    self._position_loader = _position_loader or load_latest_open_position
```

This is a Low-effort change that closes the final testability gap for phase-routing unit tests.

---

### [TE-TSPEC-08-RESIDUAL] [Low] — `get_config()` test mechanism undocumented; `get_next_earnings_date` has no test seam for its two yfinance calls

**TSPEC sections:** Section 2.1.4 `get_next_earnings_date`, Section 2.2 Note on `get_config()`

**Finding:** Two related testability gaps remain from TE-TSPEC-08:

1. **`get_config()` call path:** Section 2.2 Note still states the raw function uses `get_config()` when `config is None`. The intended unit test mechanism — pass a config dict directly (Option a) — is implicit from the function signatures but never stated explicitly. PROPERTIES authors must know whether to pass a test config dict or patch `get_config`.

2. **`get_next_earnings_date` test seam gap:** `get_next_earnings_date` makes two yfinance calls: `yf.Ticker.calendar` (to get earnings dates) and `yf.Ticker.options` (to get front-month expiry for `within_options_cycle`). Unlike `get_options_greeks` which received three test seams in v0.2.0, `get_next_earnings_date` has no injectable parameters. Unit tests for `within_options_cycle` computation — specifically the boundary condition where earnings falls on the same date as the front-month expiry, and the edge case where no future expiration exists — cannot be exercised without a live yfinance call or module-level patching of two separate yfinance internals.

**Impact:** Low severity overall. The `config` issue is purely a documentation gap. The `get_next_earnings_date` seam gap makes REQ-DATA-04 AC2 (the `within_options_cycle = True` boundary) harder to test cleanly, though module-level patching is workable. However, given that `get_next_earnings_date` is called by three agents (WheelAnalyst, CspAgent, CcAgent, RollCheckAgent — four total), the test surface is substantial.

**Suggested resolution:**

1. Add one sentence to Section 2.2 Note: "Unit tests should pass a `config` dict directly to the raw function rather than patching `get_config`; this is the approved test pattern."

2. Consider adding two keyword-only test seams to `get_next_earnings_date`:

```python
def get_next_earnings_date(
    ticker: str,
    curr_date: str,
    *,
    _earnings_date: Optional[str] = None,     # test seam — bypasses yf.Ticker.calendar
    _front_month_expiry: Optional[str] = None, # test seam — bypasses yf.Ticker.options
) -> str:
```

This mirrors the pattern established for `get_options_greeks` and makes all `within_options_cycle` boundary conditions unit-testable.

---

### [TE-TSPEC-09] [Low] — `CspDecision` and `CcDecision` sentinel constructors use `expiration_date=""` — no schema-level validation of date format

**TSPEC section:** Section 5.2 sentinel construction, Section 3.4 `CspDecision` schema, Section 3.5 `CcDecision` schema

**Finding:** The sentinel `CspDecision` in Section 5.2 sets `expiration_date=""` (empty string). The `CspDecision.expiration_date` field is typed `str` with description `"Expiration date in YYYY-MM-DD."` but no Pydantic validator enforces the YYYY-MM-DD format. An empty string passes type validation. The same applies to `CcDecision.expiration_date` and `RollDecision.current_expiration`. The TSPEC note in Section 3.4 states that numeric field constraints (`delta in (−1, 0)`, `theta <= 0`) apply only when `tradeable=True` — but date-format validation is not addressed.

**Impact:** A PROPERTIES test for REQ-TRADE-02 AC1 that asserts `CspDecision.expiration_date` matches the pattern `YYYY-MM-DD` would fail against the sentinel. More subtly, if parsing code downstream attempts `datetime.strptime(decision.expiration_date, "%Y-%m-%d")` on a sentinel instance with `expiration_date=""`, it will raise `ValueError`. The same safeguard note that applies to numeric constraints (Section 3.4) should explicitly extend to the `expiration_date` field.

**Suggested resolution:** Extend the sentinel note in Section 3.4 to explicitly state that `expiration_date=""` is a sentinel-only value exempt from date-format constraints, and that PROPERTIES tests for date-format validity must restrict assertions to the `tradeable=True` path. Alternatively, add a `field_validator` on `expiration_date` that accepts either an empty string or a valid YYYY-MM-DD string (where `tradeable=False` permits empty).

---

## Summary

The TSPEC v0.2.0 successfully resolves five of the original eight findings fully (TE-TSPEC-01, 02, 03, 04, 05, 07) and makes meaningful progress on two others (TE-TSPEC-06, 08). The formula correctness, test seam design for `get_options_greeks`, the `within_options_cycle` computation, the integer sort fix, and the `model_validator` addition are all well-executed and testable.

Three residual gaps remain, all of them Low-to-Medium severity:

- **TE-TSPEC-06-RESIDUAL (Medium):** `create_roll_check_agent` and `ConditionalLogic._load_position` still lack injectable position loaders, making unit tests for REQ-LIFE-03 ACs and REQ-LIFE-01 AC5 dependent on filesystem I/O or private-method patching.
- **TE-TSPEC-08-RESIDUAL (Low):** The `get_config()` test pattern is undocumented; `get_next_earnings_date` lacks test seams for its two yfinance calls, making `within_options_cycle` boundary tests harder.
- **TE-TSPEC-09 (Low):** Sentinel instances use `expiration_date=""`, which is not exempted from date-format assertions in the schema note — a PROPERTIES authoring trap.

None of these findings block implementation start. The two Medium findings (TE-TSPEC-06-RESIDUAL) should be resolved before PLAN authoring finalises the `create_roll_check_agent` and `ConditionalLogic` signatures. The two Low findings can be resolved in PROPERTIES or addressed during implementation.

**Recommendation:** Approved with minor changes. The TSPEC is implementable as written. The three residual findings should be addressed in a TSPEC v0.2.1 patch before implementation begins.

---

## Approved Items

The following items are well-specified from a testability perspective and require no further changes:

1. **`get_options_greeks` test seams (`_spot_price`, `_risk_free_rate`, `_sigma`)** — Keyword-only, leading-underscore, excluded from `@tool` wrapper. The BSM numeric example makes the expected test assertion explicit. Tolerance widening (±0.005 on Theta_daily) is justified by interest-rate term sensitivity and is correctly documented.

2. **BSM Theta unified flag formula and sign verification** — Section 2.1.3 shows the derivation for both put and call paths explicitly. The canonical forms are confirmed against Hull 10e. The numeric walkthrough is detailed enough to reproduce independently.

3. **`get_next_earnings_date` `within_options_cycle` computation** — Uses `front_month_expiry` from `yf.Ticker.options` as the anchor, not a caller-supplied expiration. The edge case (no future expiration → `False`) is explicitly specified. The output string format includes the field, satisfying REQ-DATA-04 AC1.

4. **`load_latest_open_position` integer sort** — Section 9.3 uses `glob.glob` + `int(path.split("-cycle-")[1].replace(".json",""))` keyed sort. The inline warning comment documents the lexicographic bug being avoided. This is the correct fix for TE-TSPEC-04.

5. **`WheelCandidateReport.model_validator`** — The validator correctly enforces the two-sided contract: `approved=True` requires positive strike range; `approved=False` requires non-empty `rejection_reason`. The sentinel `[0.0, 0.0]` is exempt because it pairs with `approved=False`. The `any(v <= 0 for v in ...)` check correctly catches `[0.0, 0.0]` on the `approved=True` path.

6. **`CcAgent._position_loader` seam** — Section 5.3 factory signature uses keyword-only `_position_loader` with default of `load_latest_open_position`. Pattern mirrors the `CspAgent` `WheelCandidateReport` injection from state (in-memory) and the `get_iv_metrics` `iv_series` seam. Correctly documented.

7. **`cycle_annualised_return_pct` formula and authoritative value** — Section 9.4 documents the arithmetic (33.21%), the REQ discrepancy (33.25%), and the PROPERTIES assertion guidance (assert 33.21% ± 0.01%). The traceability gap (REQ v0.3.0 patch pending) is noted.

8. **`RollCheckAgent` rule priority code pattern** — The explicit `if/elif` chain with named boolean variables is preserved and is highly unit-testable. Each rule is independently exercisable. Priority order (Rule 3 > Rule 5 > Rule 4 > Rule 2 > Rule 1) is unambiguous.

9. **Sentinel design with `tradeable=False` / `approved=False` exemption from numeric constraints** — Section 3.4 note correctly states that `delta in (−1, 0)` and `theta <= 0` apply only to `tradeable=True` paths. PROPERTIES tests are directed to restrict numeric range assertions accordingly. This prevents false-failing sentinel tests.

10. **`config["wheel"]` 18-key dict and `_WHEEL_ENV_OVERRIDES`** — All 18 keys have inline comments (REQ-NFR-07). All have env var entries in `_WHEEL_ENV_OVERRIDES` with the `TRADINGAGENTS_WHEEL_*` naming convention (REQ-NFR-03). The constraint that `_apply_env_overrides` only handles flat top-level keys is correctly diagnosed and the `_apply_nested_env_overrides` helper resolves it cleanly.
