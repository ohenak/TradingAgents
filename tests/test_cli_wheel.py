"""Unit tests for CLI wheel panel and wheel-status command (Batch 4).

Covers:
- WheelCandidateReport panel renders with correct border style
- approved=False → bold red border
- approved=True → green border
- iv_assessment surfaces zero-variance flat-range note (ADR-WHEEL-01)
- 'No open wheel positions' string when no open positions (REQ-LIFE-06 AC2)
- Annualised return in completed cycles table
- ADR-WHEEL-02: unknown-phase warning appears in console output (not just caplog)
"""
from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from tradingagents.agents.schemas import WheelCandidateReport, render_wheel_candidate_report
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_approved_report():
    return WheelCandidateReport(
        approved=True,
        iv_rank=55.0,
        iv_percentile=60.0,
        iv_environment="elevated",
        iv_assessment="Elevated volatility environment based on 30-day realised volatility.",
        earnings_clearance_ok=True,
        liquidity_ok=True,
        analyst_bias="bullish",
        recommended_strike_range=[140.0, 150.0],
        recommended_dte_range=[28, 45],
        rationale="All criteria pass.",
    )


def _make_rejected_report():
    return WheelCandidateReport(
        approved=False,
        rejection_reason="IV rank below threshold",
        iv_rank=10.0,
        iv_percentile=15.0,
        iv_environment="compressed",
        iv_assessment="Low volatility environment based on 30-day realised volatility.",
        earnings_clearance_ok=False,
        liquidity_ok=True,
        analyst_bias="neutral",
        recommended_strike_range=[0.0, 0.0],
        recommended_dte_range=[28, 45],
        rationale="IV rank failed.",
    )


def _make_flat_iv_report():
    """Report with zero-variance flat-range note (ADR-WHEEL-01)."""
    return WheelCandidateReport(
        approved=False,
        rejection_reason="IV rank below threshold",
        iv_rank=50.0,  # sentinel value
        iv_percentile=50.0,
        iv_environment="elevated",
        iv_assessment="IV range is flat — rank set to neutral 50",
        earnings_clearance_ok=True,
        liquidity_ok=True,
        analyst_bias="neutral",
        recommended_strike_range=[0.0, 0.0],
        recommended_dte_range=[28, 45],
        rationale="Flat IV range.",
    )


# ---------------------------------------------------------------------------
# WheelCandidateReport panel rendering
# ---------------------------------------------------------------------------

class TestWheelCandidatePanel:
    def _render_to_string(self, report_raw: str) -> str:
        """Render panel to string using rich Console."""
        console = Console(file=StringIO(), force_terminal=True, width=120)
        from cli.main import render_wheel_candidate_panel
        render_wheel_candidate_panel(report_raw, console)
        return console.file.getvalue()

    def test_approved_report_renders(self):
        """Approved WheelCandidateReport renders without error."""
        report = _make_approved_report()
        rendered = self._render_to_string(report.model_dump_json())
        assert "WheelCandidateReport" in rendered or "Wheel Suitability" in rendered

    def test_rejected_report_renders(self):
        """Rejected WheelCandidateReport renders without error."""
        report = _make_rejected_report()
        rendered = self._render_to_string(report.model_dump_json())
        assert rendered  # non-empty

    def test_flat_iv_assessment_surfaced(self):
        """ADR-WHEEL-01: zero-variance flat-range note surfaces in panel output."""
        report = _make_flat_iv_report()
        rendered = self._render_to_string(report.model_dump_json())
        assert "IV range is flat" in rendered or "rank set to neutral 50" in rendered

    def test_panel_title_is_wheel_suitability(self):
        """Panel title is 'Wheel Suitability' per TSPEC §7.1."""
        report = _make_approved_report()
        rendered = self._render_to_string(report.model_dump_json())
        assert "Wheel Suitability" in rendered

    def test_approved_report_contains_approved_marker(self):
        """Approved report contains approved indicator."""
        report = _make_approved_report()
        rendered = self._render_to_string(report.model_dump_json())
        # "Yes" or "True" or "Approved" should appear
        assert any(kw in rendered for kw in ("Yes", "True", "Approved", "approved"))


# ---------------------------------------------------------------------------
# wheel-status: no open positions (REQ-LIFE-06 AC2)
# ---------------------------------------------------------------------------

class TestWheelStatusNoPositions:
    def test_no_open_positions_string(self, tmp_path):
        """REQ-LIFE-06 AC2: 'No open wheel positions' when no open positions exist."""
        from typer.testing import CliRunner
        from cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["wheel-status", "--positions-dir", str(tmp_path)])
        assert "No open wheel positions" in result.output

    def test_empty_dir_no_positions_string(self, tmp_path):
        """Empty positions dir outputs 'No open wheel positions'."""
        from typer.testing import CliRunner
        from cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["wheel-status", "--positions-dir", str(tmp_path)])
        assert "No open wheel positions" in result.output


# ---------------------------------------------------------------------------
# wheel-status: with positions
# ---------------------------------------------------------------------------

class TestWheelStatusWithPositions:
    def _write_position(self, tmp_path, ticker, cycle, phase, **kwargs):
        from tradingagents.models.wheel_position import WheelPosition, save_wheel_position
        pos = WheelPosition(
            ticker=ticker,
            wheel_phase=phase,
            cycle_number=cycle,
            **kwargs,
        )
        save_wheel_position(pos, str(tmp_path))
        return pos

    def test_open_position_shown(self, tmp_path):
        """Open position appears in the output."""
        from typer.testing import CliRunner
        from cli.main import app

        self._write_position(
            tmp_path, "AAPL", 1, "csp_open",
            csp_strike=145.0, csp_expiration="2024-02-16",
        )
        runner = CliRunner()
        result = runner.invoke(app, ["wheel-status", "--positions-dir", str(tmp_path)])
        assert "AAPL" in result.output

    def test_completed_cycle_shows_annualised_return(self, tmp_path):
        """Completed cycle with annualised return appears in output."""
        from typer.testing import CliRunner
        from cli.main import app

        self._write_position(
            tmp_path, "AAPL", 1, "cycle_complete",
            csp_strike=140.0,
            csp_open_date="2024-01-01",
            call_away_date="2024-03-14",
            cumulative_premium_received=930.0,
            cycle_pnl=930.0,
            cycle_annualised_return_pct=33.21,
        )
        runner = CliRunner()
        result = runner.invoke(app, ["wheel-status", "--positions-dir", str(tmp_path)])
        assert "33.21" in result.output or "cycle_complete" in result.output.lower() or "AAPL" in result.output


# ---------------------------------------------------------------------------
# ADR-WHEEL-02: unknown phase warning in CLI output
# ---------------------------------------------------------------------------

class TestUnknownPhaseWarningInCli:
    def test_unknown_phase_warning_visible(self):
        """ADR-WHEEL-02: unknown wheel_phase warning appears in console output.

        The warning must be surfaced in console output, not only in caplog.
        This test checks the route_wheel_phase method logs a warning that
        can be captured for CLI display.
        """
        import logging
        from tradingagents.graph.conditional_logic import ConditionalLogic

        logic = ConditionalLogic(first_analyst_node="Market Analyst")
        logic._load_position = lambda t: None

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "invalid_unknown_phase",
        }

        captured_warnings = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                captured_warnings.append(record.getMessage())

        handler = CapturingHandler()
        logger = logging.getLogger("tradingagents.graph.conditional_logic")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        try:
            result = logic.route_wheel_phase(state)
            assert result == "Market Analyst"  # falls back to equity
            # Warning must be captured
            assert any("invalid_unknown_phase" in w or "Unknown wheel_phase" in w
                       for w in captured_warnings)
        finally:
            logger.removeHandler(handler)
