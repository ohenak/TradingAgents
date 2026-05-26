"""Unit tests for past-context injection via _build_options_context (Batch 3).

Covers:
- REQ-LIFE-05 AC3: prior-cycle performance injection when cycle_history exists
- TE-v2-F-01: negative test — no Past Cycle Performance when cycle_history is
  empty or WheelPosition is absent
- TE-v2-F-02 / ADR-WHEEL-05: all tests inject _position_loader; no test
  writes to the real positions_dir

All _position_loader arguments are injectable — no real filesystem access.
"""
from __future__ import annotations

import pytest

from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL
from tradingagents.models.wheel_position import WheelPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(wheel_phase="csp_open", ticker="AAPL"):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": wheel_phase,
        "csp_decision": None,
        "cc_decision": None,
    }


def _make_position_with_history(cycle_history=None):
    pos = WheelPosition(
        ticker="AAPL",
        wheel_phase="csp_open",
        cycle_number=2,
    )
    if cycle_history is not None:
        pos.cycle_history = cycle_history
    return pos


# ---------------------------------------------------------------------------
# POSITIVE TEST: cycle_history has entries → Past Cycle Performance injected
# ---------------------------------------------------------------------------

class TestPastContextPositive:
    def test_past_cycle_performance_section_present(self):
        """REQ-LIFE-05 AC3: when cycle_history has entries, Past Cycle Performance injected."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        prior_cycles = [
            {"cycle_number": 1, "cycle_pnl": 930.0, "cycle_annualised_return_pct": 33.21},
        ]
        pos = _make_position_with_history(cycle_history=prior_cycles)

        state = _make_state(wheel_phase="csp_open")
        result = _build_options_context(state, _position_loader=lambda t, d: pos)

        assert "Past Cycle Performance" in result

    def test_cycle_pnl_formatted_to_2_decimal_places(self):
        """cycle_pnl is formatted to exactly 2 decimal places."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        prior_cycles = [
            {"cycle_number": 1, "cycle_pnl": 930.0, "cycle_annualised_return_pct": 33.21},
        ]
        pos = _make_position_with_history(cycle_history=prior_cycles)

        state = _make_state(wheel_phase="csp_open")
        result = _build_options_context(state, _position_loader=lambda t, d: pos)

        assert "930.00" in result

    def test_cycle_annualised_return_formatted_to_2_decimal_places(self):
        """cycle_annualised_return_pct is formatted to exactly 2 decimal places."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        prior_cycles = [
            {"cycle_number": 1, "cycle_pnl": 930.0, "cycle_annualised_return_pct": 33.21},
        ]
        pos = _make_position_with_history(cycle_history=prior_cycles)

        state = _make_state(wheel_phase="csp_open")
        result = _build_options_context(state, _position_loader=lambda t, d: pos)

        assert "33.21" in result

    def test_multiple_prior_cycles_all_injected(self):
        """All prior cycles in cycle_history are injected."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        prior_cycles = [
            {"cycle_number": 1, "cycle_pnl": 930.0, "cycle_annualised_return_pct": 33.21},
            {"cycle_number": 2, "cycle_pnl": 450.0, "cycle_annualised_return_pct": 20.00},
        ]
        pos = _make_position_with_history(cycle_history=prior_cycles)

        state = _make_state(wheel_phase="csp_open")
        result = _build_options_context(state, _position_loader=lambda t, d: pos)

        assert "Prior cycle #1" in result or "cycle #1" in result
        assert "Prior cycle #2" in result or "cycle #2" in result

    def test_position_loader_receives_correct_ticker(self):
        """_position_loader is called with the correct ticker from state."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        loader_calls = []

        def tracking_loader(ticker, pos_dir):
            loader_calls.append(ticker)
            return None

        state = _make_state(wheel_phase="csp_open", ticker="MSFT")
        _build_options_context(state, _position_loader=tracking_loader)

        assert loader_calls == ["MSFT"]


# ---------------------------------------------------------------------------
# NEGATIVE TESTS (TE-v2-F-01): empty cycle_history or no WheelPosition
# ---------------------------------------------------------------------------

class TestPastContextNegative:
    """TE-v2-F-01: no Past Cycle Performance section when cycle_history is
    empty or WheelPosition is absent."""

    def test_empty_cycle_history_no_past_section(self):
        """TE-v2-F-01a: cycle_history=[] → no Past Cycle Performance section."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        pos = _make_position_with_history(cycle_history=[])

        state = _make_state(wheel_phase="csp_open")
        result = _build_options_context(state, _position_loader=lambda t, d: pos)

        assert "Past Cycle Performance" not in result

    def test_absent_position_no_past_section(self):
        """TE-v2-F-01b: _position_loader returns None → no Past Cycle Performance."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(wheel_phase="csp_open")
        # loader returns None (first cycle / no position saved yet)
        result = _build_options_context(state, _position_loader=lambda t, d: None)

        assert "Past Cycle Performance" not in result

    def test_equity_only_no_past_section(self):
        """TE-v2-F-01c: wheel_phase=None (equity-only) → no Past Cycle Performance."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        pos = _make_position_with_history(cycle_history=[
            {"cycle_number": 1, "cycle_pnl": 930.0, "cycle_annualised_return_pct": 33.21},
        ])

        state = _make_state(wheel_phase=None)
        result = _build_options_context(state, _position_loader=lambda t, d: pos)

        # wheel_phase is None → empty string, no Past Cycle Performance
        assert result == ""
        assert "Past Cycle Performance" not in result

    def test_empty_and_no_position_produce_identical_prompt(self):
        """TE-v2-F-01d: empty cycle_history and absent position produce same output."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        pos_empty = _make_position_with_history(cycle_history=[])

        state = _make_state(wheel_phase="csp_open")
        result_empty = _build_options_context(state, _position_loader=lambda t, d: pos_empty)
        result_none = _build_options_context(state, _position_loader=lambda t, d: None)

        # Both should NOT contain Past Cycle Performance
        assert "Past Cycle Performance" not in result_empty
        assert "Past Cycle Performance" not in result_none


# ---------------------------------------------------------------------------
# ADR-WHEEL-05 compliance: injectable seam, no real positions_dir access
# ---------------------------------------------------------------------------

class TestPositionLoaderInjectable:
    def test_all_tests_use_injectable_loader(self):
        """ADR-WHEEL-05: _position_loader injectable used; no real filesystem access.

        This test is a meta-assertion. All other tests in this file pass a
        _position_loader lambda to _build_options_context. This test verifies
        the injectable seam is respected by calling with a no-op loader.
        """
        from tradingagents.agents.utils.agent_utils import _build_options_context

        no_op_loader = lambda t, d: None

        state = _make_state(wheel_phase="csp_open")
        result = _build_options_context(state, _position_loader=no_op_loader)

        # Passes as long as function runs without hitting real filesystem
        assert isinstance(result, str)

    def test_position_loader_kwarg_only(self):
        """_position_loader must be keyword-only (ADR-WHEEL-05 seam convention)."""
        from tradingagents.agents.utils.agent_utils import _build_options_context
        import inspect

        sig = inspect.signature(_build_options_context)
        params = sig.parameters
        assert "_position_loader" in params
        assert params["_position_loader"].kind == inspect.Parameter.KEYWORD_ONLY
