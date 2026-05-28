# REQ — Portfolio Management

| Field | Value |
|---|---|
| **Status** | Draft |
| **Author** | PM-Author (Claude Code) |
| **Version** | 0.1.0 |
| **Created** | 2026-05-27 |
| **Upstream** | Conversation context (user request) → **REQ** |
| **Downstream** | FSPEC, TSPEC, PROPERTIES |
| **Cross-Reviews** | — |
| **LEARNINGS** | `docs/portfolio-management/LEARNINGS-portfolio-management.md` |

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2026-05-27 | Initial draft |

---

## 1. Problem Statement

TradingAgents delivers per-ticker trading recommendations but has no concept of a portfolio. A user who holds ten stocks and three open wheel positions across multiple tickers must mentally track their total capital deployment, per-position allocation, and available buying power. There is no way to ask "what should I do with everything I currently own?" — the user must individually launch an analysis per ticker and manually reconcile results.

Three compounding problems:

1. **No holdings ledger.** There is nowhere to record what you own (shares, contracts, cost basis) so the system can reason about your actual exposure.
2. **No buying-power awareness.** The system cannot tell you how much capital is free to deploy, or warn you that a new CSP would over-extend a position.
3. **No portfolio-level scan.** Running a fresh analysis per ticker is manual, slow, and does not route holdings through the correct agent automatically — wheel positions through the roll agent, stock positions through the analyst pipeline.

---

## 2. User Stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | Trader | Record my current stock and options holdings with cost basis | I have a single source of truth for what I own |
| US-02 | Trader | Track my available buying power at all times | I know how much capital I can deploy before adding a new position |
| US-03 | Trader | Set a target allocation % per position | I can manage concentration risk and know when a position has drifted |
| US-04 | Trader | See each position's current allocation % relative to its target | I can rebalance before I am overexposed to a single name |
| US-05 | Trader | Run a single command that analyses every holding I own | I get a suggested action per position without launching separate analyses manually |
| US-06 | Wheel options trader | Have the portfolio scan automatically route open wheel positions through the wheel lifecycle agents | I receive Roll / Hold / Close recommendations that reflect my actual cost basis and wheel phase |
| US-07 | Trader | See a consolidated action table after a portfolio scan completes | I can triage all positions in one view and prioritise what needs attention today |
| US-08 | Trader | Have portfolio state persist across sessions | I do not need to re-enter my holdings every time I open the terminal |
| US-09 | Developer | Manage the portfolio programmatically via the Python API | I can embed portfolio tracking in scripts and notebooks |

---

## 3. Scope

### In Scope
- Portfolio holdings ledger: stock positions (ticker, shares, average cost basis, purchase date) and options positions (ticker, type PUT/CALL, strike, expiry, contracts, average premium paid/received)
- Automatic import of existing open `WheelPosition` records into the portfolio as options positions (Phase 1)
- CLI commands: `portfolio add`, `portfolio remove`, `portfolio update`, `portfolio show`
- Buying-power tracking: total account capital (user-declared), market value of stock positions (fetched via yfinance on demand), available cash, capital reserved for open CSPs (strike × 100 × contracts)
- Per-position allocation tracking: current % of portfolio by market value, refreshed on `portfolio show` and `portfolio scan`
- Target allocation per position (optional, user-set %) with drift alerts at a configurable threshold
- `portfolio scan` command: sequentially runs TradingAgents analysis against all holdings using the existing batch infrastructure, routing each position through the appropriate agent pipeline
- Post-scan summary table: one row per position, showing ticker, position type, suggested action, and a rationale excerpt
- JSON persistence to `~/.tradingagents/portfolio/` (overridable via `TRADINGAGENTS_PORTFOLIO_DIR`)
- Python API: `Portfolio` class with `add_position`, `remove_position`, `get_positions`, `buying_power` methods; `TradingAgentsGraph.scan_portfolio(portfolio, date)` convenience method

### Out of Scope
- Broker API integration, live order execution, or real-time price feeds
- Margin account mechanics (margin calls, RegT, portfolio margin)
- Options positions not in the wheel lifecycle receiving wheel-specific agent routing — these receive standard pipeline recommendations only
- Automatic rebalancing or order generation
- Cross-position correlation analysis or portfolio-level risk metrics (beta, VaR)
- Tax lot tracking or wash-sale detection
- Multi-account or multi-currency support
- Sector grouping or benchmark comparison (deferred to a later phase)

### Assumptions
- Position quantities are entered manually; there is no broker sync.
- Market value is fetched on-demand via yfinance using the closing price for the analysis date; intraday prices are not used.
- A single portfolio per user is supported. Multi-portfolio support is out of scope.
- Wheel positions already tracked by `WheelPosition` are the authoritative source for wheel cost basis; the portfolio ledger imports them and does not duplicate the state machine.
- Total account capital is a user-declared figure (e.g. `$50,000`); the system does not compute it from broker data.

---

## 4. Requirements

### Domain: Portfolio Holdings Ledger (REQ-PORT)

---

#### REQ-PORT-01 — Holdings data model

**Description:** The system maintains a portfolio ledger containing two position types:
- **Stock position:** ticker, shares (integer), average cost basis per share, purchase date (YYYY-MM-DD).
- **Options position:** ticker, option type (PUT or CALL), strike price, expiry date (YYYY-MM-DD), number of contracts (integer), average premium per contract (positive = received, negative = paid), source (`wheel` or `manual`).

Each position has a system-assigned unique ID. The ledger is persisted as JSON to `~/.tradingagents/portfolio/portfolio.json`.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01, US-08

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a stock position is added via `portfolio add --type stock --ticker AAPL --shares 100 --cost 175.50 --date 2026-01-10` | the command runs | the position is saved to `portfolio.json` with all fields and a unique ID |
| AC2 | Trader | an options position is added via `portfolio add --type option --ticker NVDA --option-type PUT --strike 200 --expiry 2026-07-18 --contracts 1 --premium 4.30` | the command runs | the position is saved with `source: manual` and all fields |
| AC3 | Trader | `portfolio.json` exists with two positions | the application restarts | both positions are loaded correctly with no data loss |
| AC4 | Trader | an invalid field is provided (e.g. negative shares, expiry in the past) | the command runs | a validation error is displayed and no record is written |

**Dependencies:** None

---

#### REQ-PORT-02 — CLI portfolio commands

**Description:** The CLI exposes four sub-commands under `portfolio`:
- `portfolio add` — add a stock or options position (see REQ-PORT-01 for flags)
- `portfolio remove --id <ID>` — remove a position by its ID
- `portfolio update --id <ID> [field overrides]` — update mutable fields (shares, cost basis, contracts, premium) of an existing position
- `portfolio show` — display all positions in a Rich table with current market value and allocation % (prices fetched via yfinance)

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01, US-04, US-08

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | two positions exist | `portfolio show` is run | a table is printed with columns: ID, Ticker, Type, Details, Cost Basis, Market Value, Allocation %, Target %, Drift |
| AC2 | Trader | a position with ID `abc123` exists | `portfolio remove --id abc123` is run | the position is deleted from `portfolio.json` and confirmed in the terminal |
| AC3 | Trader | a stock position exists | `portfolio update --id abc123 --shares 150` is run | the shares field is updated; all other fields are unchanged |
| AC4 | Trader | `portfolio show` is run and yfinance is unavailable for one ticker | the command completes | market value for that ticker shows `N/A`; other positions display correctly |

**Dependencies:** REQ-PORT-01

---

#### REQ-PORT-03 — Auto-import of open wheel positions

**Description:** On `portfolio show` and `portfolio scan`, the system reads all open `WheelPosition` records from `~/.tradingagents/cache/wheel_positions/` and merges them into the portfolio view as options positions with `source: wheel`. Wheel positions are read-only in the portfolio ledger — they are managed exclusively by the wheel lifecycle agents.

**Priority:** P1
**Phase:** 1
**Source user stories:** US-01, US-06

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | two open `WheelPosition` records exist (one `csp_open`, one `cc_open`) | `portfolio show` is run | both appear in the holdings table with `source: wheel` and are marked read-only |
| AC2 | Trader | a wheel position is shown in `portfolio show` | `portfolio remove` is attempted on its ID | an error is returned: "Wheel positions are managed by the wheel lifecycle — use wheel-status to manage them" |
| AC3 | Trader | no `WheelPosition` files exist | `portfolio show` is run | no wheel rows appear; the command completes without error |

**Dependencies:** REQ-PORT-01, existing `WheelPosition` model (REQ-LIFE-02)

---

### Domain: Buying Power Tracking (REQ-BP)

---

#### REQ-BP-01 — Account capital declaration

**Description:** The user declares their total account capital (cash + total portfolio value) via `portfolio set-capital <amount>`. This figure is stored in `portfolio.json` and used as the denominator for all allocation and buying-power calculations. Capital can be updated at any time.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-02

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | no capital has been set | `portfolio show` is run | a yellow notice is displayed: "Total capital not set — run `portfolio set-capital <amount>` to enable buying power and allocation tracking" |
| AC2 | Trader | `portfolio set-capital 50000` is run | the command completes | `$50,000.00` is persisted and shown in `portfolio show` |
| AC3 | Trader | capital is already set | `portfolio set-capital 55000` is run | the value is updated in place with a confirmation message |

**Dependencies:** REQ-PORT-01

---

#### REQ-BP-02 — Buying power calculation and display

**Description:** Available buying power is computed as:

```
Buying Power = Total Capital
             − (stock positions: shares × current price)
             − (open CSP positions: strike × 100 × contracts)
             − (manual long options: premium paid × 100 × contracts)
```

CC positions and received-premium CSPs do not consume buying power (they are already backed by stock or cash secured at CSP open). Buying power is displayed in `portfolio show` and updated on every `portfolio scan`.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-02

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | capital = $50,000; one stock position AAPL 100 shares at current price $200 | `portfolio show` is run | deployed = $20,000; available buying power = $30,000 |
| AC2 | Trader | capital = $50,000; one open CSP NVDA strike $200, 1 contract | `portfolio show` is run | reserved for CSP = $20,000; available buying power = $30,000 |
| AC3 | Trader | total capital is not set | `portfolio show` is run | buying power row shows `N/A` (not an error) |
| AC4 | Trader | a price fetch fails for one position | `portfolio show` is run | that position's market value is excluded from the deployed total with a `N/A` note; buying power shows a conservative estimate assuming the missing position consumes its full cost basis |

**Dependencies:** REQ-BP-01, REQ-PORT-01

---

### Domain: Allocation Management (REQ-ALLOC)

---

#### REQ-ALLOC-01 — Current allocation tracking

**Description:** For each position, the system computes current allocation % = (market value of position / total capital) × 100. Values are displayed in `portfolio show` and refreshed on every `portfolio scan`. Options positions use intrinsic value (max(S − K, 0) for calls; max(K − S, 0) for puts) × 100 × contracts as their market value proxy.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-04

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | capital = $50,000; AAPL 100 shares at $200 ($20,000 market value) | `portfolio show` is run | AAPL allocation shows `40.00%` |
| AC2 | Trader | an options position is out-of-the-money | `portfolio show` is run | allocation for that position shows `0.00%` or the intrinsic value percentage, not cost basis % |

**Dependencies:** REQ-BP-01, REQ-PORT-01

---

#### REQ-ALLOC-02 — Target allocation per position

**Description:** The user can set a target allocation % for any position via `portfolio set-target --id <ID> --target <pct>`. Target allocations are stored in `portfolio.json`. The sum of all targets need not equal 100% (the remaining % is implicitly cash/buying power).

**Priority:** P1
**Phase:** 1
**Source user stories:** US-03

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a position exists | `portfolio set-target --id abc123 --target 10` is run | target allocation of `10.00%` is saved and shown in the Target % column of `portfolio show` |
| AC2 | Trader | no target is set for a position | `portfolio show` is run | the Target % cell shows `—` and the Drift cell shows `—` |

**Dependencies:** REQ-ALLOC-01

---

#### REQ-ALLOC-03 — Drift alerts

**Description:** When current allocation deviates from the target allocation by more than a configurable threshold (default: 5 percentage points, overridable via `TRADINGAGENTS_ALLOC_DRIFT_THRESHOLD`), the position row in `portfolio show` is highlighted and a drift indicator is shown (e.g. `+7.2pp ▲` or `−3.1pp ▼`).

**Priority:** P1
**Phase:** 1
**Source user stories:** US-03, US-04

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | AAPL target = 10%, current = 17.5% (drift = +7.5pp); threshold = 5pp | `portfolio show` is run | AAPL row is highlighted in yellow with `+7.5pp ▲` in the Drift column |
| AC2 | Trader | MSFT target = 15%, current = 13.8% (drift = −1.2pp); threshold = 5pp | `portfolio show` is run | MSFT row is not highlighted; Drift shows `−1.2pp` in normal style |
| AC3 | Trader | `TRADINGAGENTS_ALLOC_DRIFT_THRESHOLD=3` is set | `portfolio show` is run | positions drifting > 3pp are highlighted |

**Dependencies:** REQ-ALLOC-02

---

### Domain: Portfolio Scan (REQ-SCAN)

---

#### REQ-SCAN-01 — `portfolio scan` CLI command

**Description:** `portfolio scan [--date YYYY-MM-DD]` analyses every holding in the portfolio sequentially and produces a suggested action for each. If `--date` is omitted, today's date is used. The user is prompted once for LLM provider, model, analyst selection, and research depth; these settings apply to all positions.

**Priority:** P0
**Phase:** 2
**Source user stories:** US-05, US-07

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | three positions exist | `portfolio scan` is run | the user is prompted once for LLM settings, then all three positions are analysed sequentially |
| AC2 | Trader | `portfolio scan --date 2026-05-20` is run | the scan completes | all analyses use `2026-05-20` as the trade date |
| AC3 | Trader | no positions exist | `portfolio scan` is run | the command prints "No holdings in portfolio. Add positions with `portfolio add`." and exits cleanly |

**Dependencies:** REQ-PORT-01, REQ-BATCH-03 (sequential execution from multi-ticker REQ)

---

#### REQ-SCAN-02 — Stock position routing

**Description:** Each stock position is routed through the standard TradingAgents analyst pipeline (same as `tradingagents analyze`). The final decision (Buy More / Hold / Sell) is extracted from the Portfolio Manager's output and stored in the scan result for that position.

**Priority:** P0
**Phase:** 2
**Source user stories:** US-05, US-07

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | AAPL stock position in portfolio | `portfolio scan` is run | AAPL is analysed through the standard pipeline; the result shows `Buy More`, `Hold`, or `Sell` |
| AC2 | Trader | AAPL analysis raises an exception | the scan continues | AAPL is marked `Error` in the summary table; the next position begins |

**Dependencies:** REQ-SCAN-01

---

#### REQ-SCAN-03 — Wheel position routing

**Description:** Each position with `source: wheel` is routed through the appropriate wheel lifecycle agent based on its `wheel_phase`:
- `csp_open` → RollCheckAgent (produces Roll / Hold / Close)
- `stock_owned` → CcAgent (produces a CC recommendation)
- `cc_open` → RollCheckAgent (produces Roll / Hold / Close)

The WheelPosition's cost basis and phase state are injected into the agent context automatically. The result (action + rationale) is stored in the scan result.

**Priority:** P0
**Phase:** 2
**Source user stories:** US-06, US-07

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a `WheelPosition` in `csp_open` phase for NVDA | `portfolio scan` is run | NVDA's wheel position is routed to RollCheckAgent; the result shows `Roll`, `Hold`, or `Close` with a trigger reason |
| AC2 | Trader | a `WheelPosition` in `stock_owned` phase for AAPL | `portfolio scan` is run | AAPL's wheel position is routed to CcAgent; the result shows a specific CC strike/expiry recommendation |
| AC3 | Trader | a wheel position and a stock position both exist for the same ticker | `portfolio scan` is run | both are analysed separately and both appear as distinct rows in the summary table |

**Dependencies:** REQ-SCAN-01, REQ-LIFE-03, REQ-TRADE-03 (existing wheel lifecycle agents)

---

#### REQ-SCAN-04 — Manual options position routing

**Description:** Options positions with `source: manual` (not in the wheel lifecycle) are routed through the standard analyst pipeline with options context (current delta, DTE, P&L vs. premium received/paid) injected into the Trader agent prompt. The Trader produces a Hold / Close recommendation. Wheel-specific agents (CspAgent, CcAgent, RollCheckAgent) are not invoked for manual options.

**Priority:** P1
**Phase:** 2
**Source user stories:** US-05, US-07

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | a manual PUT option on SPY exists | `portfolio scan` is run | the standard pipeline runs for SPY with options context injected; result shows `Hold` or `Close` |
| AC2 | Trader | a manual CALL option is deeply in-the-money with 5 DTE | `portfolio scan` is run | DTE and moneyness are included in the Trader's context; the recommendation reflects the urgency |

**Dependencies:** REQ-SCAN-01, REQ-SCAN-02

---

#### REQ-SCAN-05 — Post-scan summary table

**Description:** After all positions have been scanned, a summary table is printed with one row per position:

| Column | Content |
|---|---|
| Ticker | Stock symbol |
| Type | `Stock`, `CSP`, `CC`, `Manual PUT/CALL` |
| Phase | Wheel phase if applicable, else `—` |
| Action | Suggested action (e.g. `Hold`, `Roll`, `Sell`, `Close`) |
| Key Signal | One-line rationale excerpt (≤ 80 chars) |
| Status | `OK` or `Error` |

The table is also saved to the results directory alongside the per-position report files.

**Priority:** P0
**Phase:** 2
**Source user stories:** US-07

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | five positions scanned (three succeed, two error) | scan completes | a 5-row table is printed; error rows show `Error` in the Status column with no Action |
| AC2 | Trader | scan completes | results directory is checked | a `portfolio-scan-{date}.md` summary file exists containing the same table |
| AC3 | Trader | all positions are wheel positions in `csp_open` | scan completes | the Action column shows `Roll`, `Hold`, or `Close` for each; the Type column shows `CSP` |

**Dependencies:** REQ-SCAN-02, REQ-SCAN-03, REQ-SCAN-04

---

### Domain: Python API (REQ-PORT-API)

---

#### REQ-PORT-API-01 — `Portfolio` Python class

**Description:** A `Portfolio` class is exposed at `tradingagents.portfolio.Portfolio` with methods:
- `add_position(position: StockPosition | OptionsPosition) -> str` — adds a position, returns its ID
- `remove_position(id: str) -> None`
- `update_position(id: str, **kwargs) -> None`
- `get_positions() -> list[StockPosition | OptionsPosition]`
- `buying_power(as_of_date: str) -> BuyingPowerSummary` — fetches current prices and computes the breakdown
- `set_capital(amount: float) -> None`

The class reads and writes `portfolio.json` atomically.

**Priority:** P2
**Phase:** 2
**Source user stories:** US-09

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Developer | `p = Portfolio(); p.add_position(StockPosition(ticker="AAPL", shares=100, cost_basis=175.5, purchase_date="2026-01-10"))` | the call completes | position is persisted and `p.get_positions()` returns it |
| AC2 | Developer | `p.buying_power("2026-05-27")` is called | it returns | a `BuyingPowerSummary` with `total`, `deployed`, `reserved_options`, and `available` fields |

**Dependencies:** REQ-PORT-01, REQ-BP-02

---

#### REQ-PORT-API-02 — `scan_portfolio` convenience method

**Description:** `TradingAgentsGraph.scan_portfolio(portfolio, date)` iterates over all positions in the `Portfolio` object, applies the correct routing per position type, and returns a list of `PortfolioScanResult` records — one per position — containing the position ID, ticker, suggested action, rationale, and any error.

**Priority:** P2
**Phase:** 2
**Source user stories:** US-09

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Developer | a `Portfolio` with two stock and one wheel position is passed | `graph.scan_portfolio(portfolio, "2026-05-27")` completes | three `PortfolioScanResult` records are returned in portfolio order |
| AC2 | Developer | one position raises an exception during scan | `scan_portfolio` continues | the failing position's result has `action=None`, `error=<exception message>` |

**Dependencies:** REQ-PORT-API-01, REQ-SCAN-02, REQ-SCAN-03

---

### Domain: Non-Functional Requirements (REQ-PORT-NFR)

---

#### REQ-PORT-NFR-01 — Persistent JSON storage with atomic writes

**Description:** All portfolio state is stored in `~/.tradingagents/portfolio/portfolio.json`. Writes use an atomic write-then-rename pattern (write to a temp file, then `os.replace`) to prevent corruption on crash. The path is overridable via `TRADINGAGENTS_PORTFOLIO_DIR`.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-08

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | `TRADINGAGENTS_PORTFOLIO_DIR=/tmp/myport` is set | `portfolio add` is run | `portfolio.json` is written to `/tmp/myport/` |
| AC2 | System | a process crash occurs mid-write | the application restarts | `portfolio.json` is either the previous valid state or the new state; it is never a partial/corrupt file |

**Dependencies:** REQ-PORT-01

---

#### REQ-PORT-NFR-02 — No regressions on existing CLI commands

**Description:** The `portfolio` sub-commands are additive. No existing command (`analyze`, `wheel-status`, or any other) changes behaviour, prompts, or output as a result of this feature.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | portfolio feature is installed | `tradingagents analyze` is run with a single ticker | behaviour, prompts, output, and save paths are identical to pre-feature |
| AC2 | Trader | portfolio feature is installed | `tradingagents wheel-status` is run | output is identical to pre-feature |

**Dependencies:** REQ-PORT-01

---

#### REQ-PORT-NFR-03 — No broker API or real-time feed

**Description:** All position quantities are entered manually. Current prices are fetched via yfinance on demand (closing price for the given date). The system makes no connections to broker APIs, FIX feeds, or Level 2 data sources.

**Priority:** P0
**Phase:** 1
**Source user stories:** US-01, US-09

**Acceptance criteria:**

| # | Who | Given | When | Then |
|---|---|---|---|---|
| AC1 | Trader | yfinance is unavailable | `portfolio show` is run | market values show `N/A`; no crash occurs; no broker connection is attempted |

**Dependencies:** REQ-PORT-01

---

## 5. Dependency Map

```
REQ-PORT-01 (holdings data model)
  ├── REQ-PORT-02 (CLI commands)
  ├── REQ-PORT-03 (wheel position import) ← REQ-LIFE-02 (WheelPosition)
  ├── REQ-BP-01 (capital declaration)
  │     └── REQ-BP-02 (buying power calculation)
  ├── REQ-ALLOC-01 (allocation tracking)
  │     └── REQ-ALLOC-02 (target allocation)
  │           └── REQ-ALLOC-03 (drift alerts)
  └── REQ-PORT-NFR-01 (atomic persistence)

REQ-SCAN-01 (portfolio scan command) ← REQ-BATCH-03 (sequential execution)
  ├── REQ-SCAN-02 (stock routing)
  ├── REQ-SCAN-03 (wheel routing) ← REQ-LIFE-03, REQ-TRADE-03
  ├── REQ-SCAN-04 (manual options routing)
  └── REQ-SCAN-05 (post-scan summary table)

REQ-PORT-API-01 (Portfolio class)
  └── REQ-PORT-API-02 (scan_portfolio method)
        ← REQ-SCAN-02, REQ-SCAN-03
```

**Cross-feature dependencies:**
- `REQ-PORT-03` depends on `REQ-LIFE-02` (WheelPosition — existing, implemented)
- `REQ-SCAN-03` depends on `REQ-LIFE-03` (RollCheckAgent — existing) and `REQ-TRADE-03` (CcAgent — existing)
- `REQ-SCAN-01` reuses `REQ-BATCH-03` sequential execution infrastructure (multi-ticker REQ, not yet implemented)

---

## 6. Open Questions

| # | Question | Impact | Owner |
|---|---|---|---|
| OQ-01 | Should `portfolio scan` re-run the full analyst team for stock positions, or only the Trader/risk agents using the most recent cached analyst reports? | Cost and latency vs. freshness | User |
| OQ-02 | For options positions in `stock_owned` phase (waiting to sell CC), should the CC recommendation be produced automatically on every scan, or only when the user explicitly requests it? | UX flow and agent cost | User |
| OQ-03 | Should drift alerts also appear inline during `portfolio scan`, or only in `portfolio show`? | Scope of REQ-ALLOC-03 | User |
| OQ-04 | Should the post-scan summary file be appended to a rolling log, or overwrite on each scan? | Historical tracking | User |
| OQ-05 | Is Phase 2 (portfolio scan) blocked on multi-ticker REQ-BATCH being implemented first, or should it be built standalone? | Delivery sequencing | User |
