"""CLI-layer batch types and pure functions for multi-ticker analysis."""
import logging
from dataclasses import dataclass
from pathlib import Path

from rich.live import Live
from rich.table import Table

from tradingagents.dataflows.utils import _detect_asset_type
from tradingagents.graph.analyst_execution import (
    build_analyst_execution_plan,
    get_initial_analyst_node,
    AnalystWallTimeTracker,
)

logger = logging.getLogger(__name__)


@dataclass
class BatchTickerRecord:
    """Internal CLI-layer record for a successfully completed ticker analysis.

    Distinct from BatchTickerResult (public API type in tradingagents/).
    """
    ticker: str
    final_state: dict
    decision: str


def batch_run_loop(
    ordered_tickers: list,
    config: dict,
    graph,
    selections: dict,
    checkpoint: bool = False,
    # Injectable dependencies (default to cli.main implementations)
    _message_buffer=None,
    _console=None,
    _save_report_to_disk=None,
    _create_layout=None,
    _update_display=None,
    _make_save_message=None,
    _make_save_tool_call=None,
    _make_save_report_section=None,
) -> tuple:
    """Run analysis for each ticker sequentially. Returns (batch_results, failed_tickers).

    batch_results: dict[str, BatchTickerRecord] — only successful tickers.
    failed_tickers: list[str] — tickers that failed at any step.
    """
    import cli.main as _main_mod
    message_buffer = _message_buffer if _message_buffer is not None else _main_mod.message_buffer
    console = _console if _console is not None else _main_mod.console
    save_report_to_disk = _save_report_to_disk if _save_report_to_disk is not None else _main_mod.save_report_to_disk
    create_layout = _create_layout if _create_layout is not None else _main_mod.create_layout
    update_display = _update_display if _update_display is not None else _main_mod.update_display
    make_save_message_decorator = _make_save_message if _make_save_message is not None else _main_mod.make_save_message_decorator
    make_save_tool_call_decorator = _make_save_tool_call if _make_save_tool_call is not None else _main_mod.make_save_tool_call_decorator
    make_save_report_section_decorator = _make_save_report_section if _make_save_report_section is not None else _main_mod.make_save_report_section_decorator

    date = selections["analysis_date"]
    pipeline_analyst_keys = selections.get("pipeline_analyst_keys", ["market"])
    N = len(ordered_tickers)
    batch_results: dict = {}
    failed_tickers: list = []

    analyst_plan = build_analyst_execution_plan(
        pipeline_analyst_keys,
        concurrency_limit=config.get("analyst_concurrency_limit", 1),
    )

    for i, ticker in enumerate(ordered_tickers):
        console.print(f"[{i + 1}/{N}] Analyzing {ticker} on {date}")
        asset_type = _detect_asset_type(ticker)

        results_dir = Path(config["results_dir"]) / ticker / date
        results_dir.mkdir(parents=True, exist_ok=True)
        report_dir = results_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        log_file = results_dir / "message_tool.log"
        log_file.touch(exist_ok=True)

        message_buffer.reset()
        message_buffer.add_message = make_save_message_decorator(
            message_buffer, "add_message", log_file
        )
        message_buffer.add_tool_call = make_save_tool_call_decorator(
            message_buffer, "add_tool_call", log_file
        )
        message_buffer.update_report_section = make_save_report_section_decorator(
            message_buffer, "update_report_section", report_dir
        )
        message_buffer.init_for_analysis(pipeline_analyst_keys)

        layout = create_layout()

        try:
            with Live(layout, refresh_per_second=4):
                update_display(layout)
                final_state, decision = graph.propagate(ticker, date, asset_type=asset_type)

            # Step 3a: persist to memory log (non-fatal)
            try:
                graph.process_signal(decision)
            except Exception as sig_err:
                logger.warning("process_signal failed for %s: %s", ticker, sig_err)

            console.print(f"✓ {ticker} complete")

            # Step 4: auto-save report
            try:
                save_report_to_disk(final_state, ticker, results_dir)
                batch_results[ticker] = BatchTickerRecord(
                    ticker=ticker, final_state=final_state, decision=decision
                )
            except OSError:
                console.print(f"[FAILED] {ticker}: OSError")
                failed_tickers.append(ticker)

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            console.print(f"[FAILED] {ticker}: {type(exc).__name__}")
            failed_tickers.append(ticker)

    return batch_results, failed_tickers


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
