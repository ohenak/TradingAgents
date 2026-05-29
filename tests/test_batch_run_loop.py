"""Integration tests for batch_run_loop(). PROP-LOOP-01 through PROP-LOOP-07.

Patches cli.batch.Live as a no-op context manager in all tests.
Uses injectable dependency params to avoid circular-import issues.
"""
import pytest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch, call


def _make_graph(propagate_side_effect=None):
    g = MagicMock()
    if propagate_side_effect is not None:
        g.propagate.side_effect = propagate_side_effect
    else:
        g.propagate.return_value = ({"final_trade_decision": "Hold"}, "Hold")
    g.process_signal = MagicMock()
    return g


def _make_selections(date="2026-05-29"):
    return {
        "analysis_date": date,
        "pipeline_analyst_keys": ["market"],
        "selected_analyst_keys": ["market"],
    }


def _run(ordered_tickers, graph, tmp_path, selections=None, save_side_effect=None):
    """Helper: run batch_run_loop with all deps mocked."""
    from cli.batch import batch_run_loop
    sel = selections or _make_selections()
    config = {"results_dir": str(tmp_path), "analyst_concurrency_limit": 1}

    mock_buf = MagicMock()
    mock_console = MagicMock()
    mock_live_cls = MagicMock()
    mock_live_cls.return_value.__enter__ = MagicMock(return_value=None)
    mock_live_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_layout = MagicMock()
    mock_save = MagicMock(side_effect=save_side_effect)

    with patch("cli.batch.Live", mock_live_cls), \
         patch("cli.batch.build_analyst_execution_plan") as mock_plan, \
         patch("cli.batch.get_initial_analyst_node", return_value="Market Analyst"), \
         patch("cli.batch.AnalystWallTimeTracker"):
        mock_plan.return_value = MagicMock()
        mock_plan.return_value.specs = [MagicMock(key="market")]
        return batch_run_loop(
            ordered_tickers, config, graph, sel,
            _message_buffer=mock_buf,
            _console=mock_console,
            _save_report_to_disk=mock_save,
            _create_layout=lambda: mock_layout,
            _update_display=MagicMock(),
            _make_save_message=lambda obj, fn, lf: MagicMock(),
            _make_save_tool_call=lambda obj, fn, lf: MagicMock(),
            _make_save_report_section=lambda obj, fn, rd: MagicMock(),
        ), mock_console, mock_save


class TestBatchRunLoopPartialFail:
    def test_partial_fail_continues_loop(self, tmp_path):
        graph = _make_graph([
            ({"final_trade_decision": "Buy"}, "Buy"),
            ValueError("bad ticker"),
            ({"final_trade_decision": "Sell"}, "Sell"),
        ])
        (batch_results, failed_tickers), _, _ = _run(
            ["AAPL", "BAD", "NVDA"], graph, tmp_path
        )
        assert "BAD" in failed_tickers
        assert "AAPL" in batch_results
        assert "NVDA" in batch_results
        assert len(failed_tickers) == 1


class TestBatchRunLoopOsErrorSave:
    def test_osError_on_save_marks_failed_continues(self, tmp_path):
        graph = _make_graph()
        (batch_results, failed_tickers), _, _ = _run(
            ["T1", "T2", "T3"], graph, tmp_path,
            save_side_effect=[None, OSError("disk full"), None],
        )
        assert "T2" in failed_tickers
        assert "T1" in batch_results
        assert "T3" in batch_results


class TestBatchRunLoopAllFail:
    def test_all_fail_returns_empty_results(self, tmp_path):
        graph = _make_graph([ValueError("bad")] * 3)
        (batch_results, failed_tickers), _, _ = _run(
            ["A", "B", "C"], graph, tmp_path
        )
        assert batch_results == {}
        assert set(failed_tickers) == {"A", "B", "C"}


class TestBatchRunLoopKiPropagation:
    def test_keyboard_interrupt_propagates(self, tmp_path):
        from cli.batch import batch_run_loop
        graph = _make_graph([KeyboardInterrupt()])
        with pytest.raises(KeyboardInterrupt):
            _run(["AAPL"], graph, tmp_path)


class TestBatchRunLoopProcessSignalNonfatal:
    def test_process_signal_failure_keeps_ticker_as_success(self, tmp_path):
        graph = _make_graph()
        graph.process_signal.side_effect = Exception("signal error")
        (batch_results, failed_tickers), _, _ = _run(["AAPL"], graph, tmp_path)
        assert "AAPL" in batch_results
        assert "AAPL" not in failed_tickers


class TestBatchRunLoopProgressHeader:
    def test_progress_header_printed_before_analysis(self, tmp_path):
        graph = _make_graph()
        (_, _), mock_console, _ = _run(["AAPL", "MSFT"], graph, tmp_path)
        calls_str = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "1/2" in calls_str
        assert "AAPL" in calls_str
        assert "2/2" in calls_str
        assert "MSFT" in calls_str
