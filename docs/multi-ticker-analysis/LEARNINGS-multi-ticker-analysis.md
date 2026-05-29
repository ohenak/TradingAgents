# LEARNINGS — multi-ticker-analysis

| Field | Detail |
|---|---|
| Feature | multi-ticker-analysis |
| REQ | docs/multi-ticker-analysis/REQ-multi-ticker-analysis.md |
| Date Completed | 2026-05-29 |
| Total Iterations | REQ: 4, FSPEC: 4, TSPEC: 2, DECISIONS: 1, PLAN: 2, PROPERTIES: 2, IMPL: 2 |
| Upstream | REQ → FSPEC → TSPEC → DECISIONS → PLAN → PROPERTIES → IMPL |
| Harvested from | 33 CROSS-REVIEW files (REQ ×8, FSPEC ×8, TSPEC ×4, DECISIONS ×2, PLAN ×4, PROPERTIES ×4, IMPLEMENTATION ×3); 0 POSTMORTEM files — now deleted |

---

## 1. Non-Convergences

No review loop hit the 5-iteration limit; no post-mortems were produced. Two phases ran long (4 iterations each) but converged:

| Phase | Reviewer | Issue | Resolution | Iteration Count |
|---|---|---|---|---|
| REQ | se-review + te-review | Acceptance criteria repeatedly imprecise for automated testing (mock-assertability, exact format strings, exit-code specificity); a load-bearing architectural boundary (library→CLI import) surfaced late at v3 | Each round tightened ACs; the boundary was resolved by adding `asset_types` param + library-internal detection (→ DEC-MULTI-01) | 4 |
| FSPEC | se-review + te-review | Behavioral-flow correctness bugs found across rounds: interactive prompts blocking the batch loop (v1), `Live` context spanning tickers (v1), summary-table loop iterating the wrong collection (v2), list-vs-dict access mismatch (v3) | Each fixed in the flow before TSPEC; no bug escaped to implementation | 4 |

**Read:** Both long phases were driven by *precision* findings, not *disagreement*. Reviewers and authors agreed on intent every round; the churn was in making intent executable. This is healthy convergence, not thrash.

---

## 2. Cross-Feature Patterns

| Finding | Suggested Promotion Target |
|---|---|
| **Library layer (`tradingagents/`) must never import from the CLI layer (`cli/`).** Surfaced when `propagate_many()` needed asset-type detection that lived in `cli/utils.py`. Resolved via DEC-MULTI-01 (library-internal `_detect_asset_type` + `asset_types` param). Now guarded by an `ast`-based import-boundary test (PROP-NEG-01). | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — promote as a standing architectural invariant, plus reference the ast-scan test as the enforcement mechanism |
| **`message_buffer` is a module-level singleton with monkey-patched method decorators**, which makes per-run test isolation difficult. This affects any future CLI feature that drives the analysis loop. Mitigated here with `MessageBuffer.reset()` (DEC-MULTI-02). | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — note the singleton + reset-for-isolation pattern; longer term, flag the singleton itself as a refactor candidate (constructor-injected paths) |
| **Graph initialisation is expensive (~1–3 s: LLM clients, tool nodes, LangGraph compile).** Any feature that loops over work units must initialise `TradingAgentsGraph` once and reuse it, never per-iteration. | `docs/_constraints/DOMAIN-CONSTRAINTS.md` — performance invariant for loop/batch features |
| **Negative/architectural invariants need standing automated guards, not just code review.** PROP-NEG-01 (import boundary) was compliant in code but had no test until the implementation review caught it; `ast`-scan tests are the right tool (pattern already exists in `tests/test_sentinel_enforcement.py`). | Skill update candidate — see §4 |

---

## 3. Rejected Proposals (with rationale)

| Proposal | Rejected By | Rationale | Reusable for future features? |
|---|---|---|---|
| Move `detect_asset_type()` from `cli/utils.py` into `tradingagents/` and import it from both layers | DEC-MULTI-01 (se-author) | Relocating a public CLI utility forces CLI import churn and couples CLI tests to a library module; the 3-line detection logic is cheap to duplicate with a consistency test guarding drift | Yes — when a CLI util is needed in the library, prefer duplication + a consistency test over relocation, unless the util is large or needed in 3+ places |
| Store original bound methods in `MessageBuffer.__init__` and restore them in `reset()` | DEC-MULTI-02 (se-author) | Would couple `__init__` to a monkey-patching pattern defined far away in `run_analysis()`; a future decorator change would silently leave stale originals. `__dict__.pop(attr, None)` is self-contained and exploits standard attribute resolution | Yes — to undo instance-level monkey-patching, delete the instance attribute (let the class method re-expose) rather than snapshotting originals |
| Trigger wheel-mode summary decision on `wheel_candidate_report` being present in state | se-review (FSPEC iteration) | Both `final_trade_decision` and `wheel_candidate_report` are populated whenever wheel runs, so state-presence is ambiguous and risks stale-state bleed; keying on `"wheel" in selected_analyst_keys` is deterministic | Yes — derive mode from the explicit selection/config, not from the incidental presence of a state key |

---

## 4. Process Learnings

- **REQ acceptance criteria churned for 4 rounds almost entirely on testability precision** — "the system normalises" vs. "`normalize_ticker_symbol()` is called and the result is `[...]`", "non-zero exit code" vs. "exit code 1", "such as `[3/5]...`" vs. an exact regex. **Signal:** for CLI/loop features, REQ authoring should default to mock-assertable phrasing (name the function called, give the exact observable string/exit code) on the first draft. A checklist item — "is every AC assertable against a mock or an exact output without further interpretation?" — would have collapsed REQ from 4 iterations to ~2.

- **The library→CLI import boundary surfaced at REQ v3, not v1.** It is an architectural fact that was knowable from the first read of the codebase. **Signal:** se-review's REQ pass should explicitly check cross-layer dependency direction for any requirement that adds a public API method calling existing helpers — catching it at v1 would have saved two REQ rounds and pre-shaped the `asset_types` API earlier.

- **A correctness bug (summary-table loop iterating `batch_results` instead of `ordered_tickers`, so failed tickers produced no rows) lived in the FSPEC through two iterations.** It was caught by se-review reading the pseudocode as if executing it. **Signal:** FSPEC pseudocode for collection-iteration flows benefits from an explicit "trace one failed item through the loop" check during review.

- **A negative property (PROP-NEG-01) was written but not implemented as a test** until the implementation review. **Signal:** the implementation/PROPERTIES-test phase should treat every `PROP-NEG-*` as a mandatory checklist line — negative properties are the easiest to silently skip because the code "already works."

- **No findings were left untagged** — all 33 cross-reviews used the Scope column consistently. No tagging-discipline learning needed this cycle.

---

## 5. Open Items for Consolidation

For `consolidate-learnings` to evaluate (harvest is not authorized to promote these):

1. **Promote the library→CLI import boundary** to `docs/_constraints/DOMAIN-CONSTRAINTS.md` as a hard architectural invariant, citing the `ast`-scan enforcement test as the mechanism. (From §2, finding 1.)
2. **Promote the graph-init-once-per-batch performance invariant** to DOMAIN-CONSTRAINTS. (From §2, finding 3.)
3. **Record the `message_buffer` singleton + `reset()`-for-isolation pattern**, and separately flag the singleton as a refactor candidate. (From §2, finding 2.)
4. **Skill-prompt update candidate (pm-author / se-review REQ checklist):** add "every AC must be mock-assertable or assert an exact observable (string / exit code / call), no interpretive verbs" — would have cut REQ iterations roughly in half. (From §4, learning 1.)
5. **Skill-prompt update candidate (se-review REQ pass):** add an explicit cross-layer dependency-direction check for requirements introducing public API methods. (From §4, learning 2.)
6. **Skill-prompt update candidate (se-implement / orchestrate-dev Phase PT):** treat each `PROP-NEG-*` as a mandatory test-coverage checklist line. (From §4, learning 4.)
