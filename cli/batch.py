"""CLI-layer batch types and pure functions for multi-ticker analysis."""
from dataclasses import dataclass

from rich.table import Table


@dataclass
class BatchTickerRecord:
    """Internal CLI-layer record for a successfully completed ticker analysis.

    Distinct from BatchTickerResult (public API type in tradingagents/).
    """
    ticker: str
    final_state: dict
    decision: str


def build_batch_summary(
    batch_results: dict,
    failed_tickers: list,
    selected_analyst_keys: list,
    ordered_tickers: list,
) -> tuple:
    """Build the Rich summary Table and determine exit code.

    Precondition: every ticker in ordered_tickers is in exactly one of
    batch_results or failed_tickers (maintained by batch_run_loop).

    Returns (table, exit_code) where exit_code is 0 or 1.
    Pure function — no I/O.
    """
    wheel_mode = "wheel" in selected_analyst_keys

    table = Table(show_header=True, header_style="bold")
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Decision")
    table.add_column("Status")

    for ticker in ordered_tickers:
        if ticker in failed_tickers:
            table.add_row(ticker, "", "[red]Failed[/red]")
        else:
            rec = batch_results[ticker]
            decision_cell = _extract_decision(rec.final_state, wheel_mode)
            table.add_row(ticker, decision_cell, "[green]Success[/green]")

    exit_code = 1 if failed_tickers else 0
    return table, exit_code


def _extract_decision(final_state: dict, wheel_mode: bool) -> str:
    if wheel_mode:
        return _wheel_decision(final_state)
    return _standard_decision(final_state)


def _wheel_decision(final_state: dict) -> str:
    report_raw = final_state.get("wheel_candidate_report")
    if not report_raw:
        return "N/A"
    try:
        from tradingagents.agents.schemas import WheelCandidateReport
        report = WheelCandidateReport.model_validate_json(report_raw)
        return "Approved" if report.approved else "Rejected"
    except Exception:
        return "N/A"


def _standard_decision(final_state: dict) -> str:
    raw = final_state.get("final_trade_decision") or ""
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped[:50]
    return ""
