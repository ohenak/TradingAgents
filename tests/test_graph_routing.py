"""Unit tests for graph routing via route_wheel_phase (Batch 4).

Covers:
- PROP-ROUTE-01: unknown wheel_phase → equity path + warning
- PROP-ROUTE-02: wheel_phase=None → first_analyst_node (marked @pytest.mark.integration)
- WheelStateError on missing position for csp_open / cc_open
- wheel_phase="screening" → first_analyst_node
- wheel_phase="stock_owned" → cc_agent
- wheel_phase="cycle_complete" → wheel_cycle_summary
- TE-v2-F-03: wheel_phase="csp_open" → roll_check_agent (DEC-PLAN-02)
"""
from __future__ import annotations

import logging
import pytest

from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.wheel_nodes import WheelStateError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(wheel_phase=None, ticker="AAPL"):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": wheel_phase,
    }


def _make_logic(first_analyst="Market Analyst", position=None):
    """Create ConditionalLogic with injectable _load_position."""
    logic = ConditionalLogic(first_analyst_node=first_analyst)
    # Monkey-patch _load_position for tests
    logic._load_position = lambda ticker: position
    return logic


# ---------------------------------------------------------------------------
# PROP-ROUTE-02: wheel_phase=None → equity path (integration)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEquityPassthrough:
    def test_none_phase_routes_to_first_analyst(self):
        """PROP-ROUTE-02: wheel_phase=None → first_analyst_node (equity path)."""
        logic = _make_logic(first_analyst="Market Analyst")
        result = logic.route_wheel_phase(_make_state(wheel_phase=None))
        assert result == "Market Analyst"

    def test_none_phase_no_options_nodes(self):
        """PROP-ROUTE-02: wheel_phase=None → no wheel-specific nodes returned."""
        logic = _make_logic(first_analyst="Market Analyst")
        result = logic.route_wheel_phase(_make_state(wheel_phase=None))
        assert result not in ("csp_agent", "cc_agent", "roll_check_agent", "wheel_cycle_summary")


# ---------------------------------------------------------------------------
# wheel_phase="screening" → first_analyst_node
# ---------------------------------------------------------------------------

class TestScreeningPhase:
    def test_screening_routes_to_first_analyst(self):
        """wheel_phase='screening' → first_analyst_node."""
        logic = _make_logic(first_analyst="Market Analyst")
        result = logic.route_wheel_phase(_make_state(wheel_phase="screening"))
        assert result == "Market Analyst"


# ---------------------------------------------------------------------------
# TE-v2-F-03: wheel_phase="csp_open" → roll_check_agent (DEC-PLAN-02)
# ---------------------------------------------------------------------------

class TestCspOpenPhase:
    def test_csp_open_with_position_routes_to_roll_check(self):
        """TE-v2-F-03 / DEC-PLAN-02: wheel_phase='csp_open' → 'roll_check_agent'."""
        from tradingagents.models.wheel_position import WheelPosition
        pos = WheelPosition(ticker="AAPL", wheel_phase="csp_open", cycle_number=1)
        logic = _make_logic(position=pos)
        result = logic.route_wheel_phase(_make_state(wheel_phase="csp_open"))
        assert result == "roll_check_agent"

    def test_csp_open_without_position_raises_wheel_state_error(self):
        """WheelStateError raised when wheel_phase='csp_open' but no position."""
        logic = _make_logic(position=None)
        with pytest.raises(WheelStateError):
            logic.route_wheel_phase(_make_state(wheel_phase="csp_open"))


# ---------------------------------------------------------------------------
# wheel_phase="stock_owned" → cc_agent
# ---------------------------------------------------------------------------

class TestStockOwnedPhase:
    def test_stock_owned_routes_to_cc_agent(self):
        """wheel_phase='stock_owned' → 'cc_agent'."""
        logic = _make_logic()
        result = logic.route_wheel_phase(_make_state(wheel_phase="stock_owned"))
        assert result == "cc_agent"


# ---------------------------------------------------------------------------
# wheel_phase="cc_open" → roll_check_agent
# ---------------------------------------------------------------------------

class TestCcOpenPhase:
    def test_cc_open_with_position_routes_to_roll_check(self):
        """wheel_phase='cc_open' with position → 'roll_check_agent'."""
        from tradingagents.models.wheel_position import WheelPosition
        pos = WheelPosition(ticker="AAPL", wheel_phase="cc_open", cycle_number=1)
        logic = _make_logic(position=pos)
        result = logic.route_wheel_phase(_make_state(wheel_phase="cc_open"))
        assert result == "roll_check_agent"

    def test_cc_open_without_position_raises_wheel_state_error(self):
        """WheelStateError raised when wheel_phase='cc_open' but no position."""
        logic = _make_logic(position=None)
        with pytest.raises(WheelStateError):
            logic.route_wheel_phase(_make_state(wheel_phase="cc_open"))


# ---------------------------------------------------------------------------
# wheel_phase="cycle_complete" → wheel_cycle_summary
# ---------------------------------------------------------------------------

class TestCycleCompletePhase:
    def test_cycle_complete_routes_to_summary(self):
        """wheel_phase='cycle_complete' → 'wheel_cycle_summary'."""
        logic = _make_logic()
        result = logic.route_wheel_phase(_make_state(wheel_phase="cycle_complete"))
        assert result == "wheel_cycle_summary"


# ---------------------------------------------------------------------------
# PROP-ROUTE-01: Unknown phase → equity + warning (ADR-WHEEL-02)
# ---------------------------------------------------------------------------

class TestUnknownPhase:
    def test_unknown_phase_routes_to_equity(self):
        """PROP-ROUTE-01: unknown wheel_phase → first_analyst_node."""
        logic = _make_logic(first_analyst="Market Analyst")
        result = logic.route_wheel_phase(_make_state(wheel_phase="invalid_phase"))
        assert result == "Market Analyst"

    def test_unknown_phase_logs_warning(self, caplog):
        """PROP-ROUTE-01: unknown wheel_phase → warning logged (ADR-WHEEL-02)."""
        logic = _make_logic(first_analyst="Market Analyst")
        with caplog.at_level(logging.WARNING, logger="tradingagents.graph.conditional_logic"):
            logic.route_wheel_phase(_make_state(wheel_phase="invalid_phase"))
        # Warning should be in caplog
        assert any("invalid_phase" in record.message or "Unknown wheel_phase" in record.message
                   for record in caplog.records)


# ---------------------------------------------------------------------------
# Full screening-path test (TE-F-04)
# ---------------------------------------------------------------------------

class TestScreeningFullPath:
    def test_screening_routes_to_analyst_not_options_node(self):
        """TE-F-04: screening routes to first analyst node (not options nodes)."""
        logic = _make_logic(first_analyst="Market Analyst")
        result = logic.route_wheel_phase(_make_state(wheel_phase="screening"))
        # Must be the analyst entry point
        assert result == "Market Analyst"
        assert result != "csp_agent"
        assert result != "wheel_analyst"
        assert result != "roll_check_agent"
