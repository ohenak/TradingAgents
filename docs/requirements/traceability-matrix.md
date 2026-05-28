# Requirements Traceability Matrix

_Last updated: 2026-05-27 (added Feature: Multi-Ticker Sequential Analysis v0.1.0)_

## Feature: Wheel Options Trading

| User Story | Requirement ID | Requirement Title | FSPEC | Phase | Priority |
|---|---|---|---|---|---|
| US-01 | REQ-SCREEN-01 | WheelAnalyst agent | — | 2 | P0 |
| US-01 | REQ-SCREEN-02 | WheelCandidateReport schema | — | 2 | P0 |
| US-01, US-09 | REQ-SCREEN-03 | CLI integration for wheel screening | — | 2 | P1 |
| US-02 | REQ-DATA-02 | IV Rank and IV Percentile tools | — | 1 | P0 |
| US-02 | REQ-SCREEN-01 | WheelAnalyst agent | — | 2 | P0 |
| US-03 | REQ-DATA-01 | Options chain retrieval tool | — | 1 | P0 |
| US-03 | REQ-DATA-03 | Options Greeks calculation | — | 1 | P0 |
| US-03 | REQ-TRADE-01 | CspAgent | — | 3 | P0 |
| US-03 | REQ-TRADE-02 | CspDecision schema | — | 3 | P0 |
| US-03, US-04 | REQ-TRADE-05 | Risk debate options adaptation | — | 3 | P1 |
| US-04 | REQ-TRADE-03 | CcAgent | — | 3 | P0 |
| US-04 | REQ-TRADE-04 | CcDecision schema | — | 3 | P0 |
| US-05 | REQ-LIFE-01 | Wheel phase state machine | — | 4 | P0 |
| US-05, US-07 | REQ-LIFE-02 | Position tracker | — | 4 | P0 |
| US-06 | REQ-LIFE-03 | RollCheckAgent | — | 4 | P0 |
| US-06 | REQ-LIFE-04 | RollDecision schema | — | 4 | P0 |
| US-07 | REQ-LIFE-05 | Memory log integration | — | 4 | P1 |
| US-07, US-09 | REQ-LIFE-06 | CLI wheel-status command | — | 4 | P1 |
| US-08 | REQ-DATA-04 | Earnings date lookup tool | — | 1 | P0 |
| US-10 | REQ-DATA-05 | Options tools registration | — | 1 | P0 |
| US-10 | REQ-NFR-03 | Configurability via env vars | — | All | — |

## Feature: Multi-Ticker Sequential Analysis

| User Story | Requirement ID | Requirement Title | FSPEC | Phase | Priority |
|---|---|---|---|---|---|
| US-01 | REQ-BATCH-01 | Multi-ticker input at the CLI | — | 1 | P0 |
| US-02 | REQ-BATCH-02 | Shared configuration across all tickers | — | 1 | P0 |
| US-01, US-02 | REQ-BATCH-03 | Sequential execution | — | 1 | P0 |
| US-04 | REQ-BATCH-04 | Error isolation | — | 1 | P1 |
| US-05 | REQ-BATCH-05 | Per-ticker auto-save | — | 1 | P1 |
| US-03 | REQ-BATCH-06 | Post-run summary table | — | 1 | P1 |
| US-06 | REQ-API-01 | `propagate_many` convenience method | — | 1 | P2 |
| US-01 | REQ-NFR-01 | No regressions on single-ticker flow | — | 1 | P0 |
| US-01, US-04 | REQ-NFR-02 | Progress indication between tickers | — | 1 | P1 |

## Dependency Chain

```
REQ-DATA-01 (options chain)
  ├── REQ-DATA-02 (IV metrics)
  ├── REQ-DATA-03 (Greeks)
  └── REQ-DATA-05 (tool registration)
        ├── REQ-SCREEN-01 (WheelAnalyst)
        │     └── REQ-SCREEN-02 (WheelCandidateReport)
        │           ├── REQ-SCREEN-03 (CLI)
        │           └── REQ-TRADE-01 (CspAgent)
        │                 └── REQ-TRADE-02 (CspDecision)
        └── REQ-TRADE-03 (CcAgent)
              └── REQ-TRADE-04 (CcDecision)

REQ-DATA-04 (earnings)
  ├── REQ-SCREEN-01
  ├── REQ-TRADE-01
  └── REQ-LIFE-03 (RollCheckAgent)

REQ-TRADE-02 + REQ-TRADE-04
  └── REQ-LIFE-01 (phase state machine)
        ├── REQ-LIFE-02 (position tracker)
        │     ├── REQ-LIFE-05 (memory log)
        │     └── REQ-LIFE-06 (CLI wheel-status)
        └── REQ-LIFE-03 (RollCheckAgent)
              └── REQ-LIFE-04 (RollDecision)
```
