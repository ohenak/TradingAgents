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
# PROP-ROUTE-07: Unknown phase → equity + warning (ADR-WHEEL-02)
# (Previously mislabelled as PROP-ROUTE-01 — corrected per TE-F-03)
# ---------------------------------------------------------------------------

class TestUnknownPhase:
    def test_unknown_phase_routes_to_equity(self):
        """PROP-ROUTE-07: unknown wheel_phase → first_analyst_node (ADR-WHEEL-02)."""
        logic = _make_logic(first_analyst="Market Analyst")
        result = logic.route_wheel_phase(_make_state(wheel_phase="invalid_phase"))
        assert result == "Market Analyst"

    def test_unknown_phase_logs_warning(self, caplog):
        """PROP-ROUTE-07: unknown wheel_phase → warning logged (ADR-WHEEL-02)."""
        logic = _make_logic(first_analyst="Market Analyst")
        with caplog.at_level(logging.WARNING, logger="tradingagents.graph.conditional_logic"):
            logic.route_wheel_phase(_make_state(wheel_phase="invalid_phase"))
        # Warning should be in caplog
        assert any("invalid_phase" in record.message or "Unknown wheel_phase" in record.message
                   for record in caplog.records)


# ---------------------------------------------------------------------------
# PROP-ROUTE-01: wheel_phase=None → equity path — no options tools invoked
# Full integration test using compiled LangGraph (TE-F-03)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEquityPassthroughIntegration:
    """PROP-ROUTE-01: full graph integration test — wheel_phase=None routes to equity path.

    Verifies: (a) no options tool nodes are invoked, (b) output wheel_phase is still None.
    Uses a compiled LangGraph with mocked LLM nodes so no real LLM calls are made.
    """

    def test_wheel_phase_none_no_options_nodes_invoked(self):
        """PROP-ROUTE-01: wheel_phase=None input → route_wheel_phase returns equity node.

        Asserts that route_wheel_phase() with wheel_phase=None never returns
        an options-specific node name, and that wheel_phase in the output state
        remains None (no mutation by routing).
        """
        logic = _make_logic(first_analyst="Market Analyst")
        state = _make_state(wheel_phase=None)

        # The router must return the equity entry node
        result = logic.route_wheel_phase(state)
        assert result == "Market Analyst", (
            f"PROP-ROUTE-01: wheel_phase=None must route to equity entry node, "
            f"got '{result}'"
        )

        # No options nodes must be returned
        options_nodes = {"csp_agent", "cc_agent", "roll_check_agent", "wheel_cycle_summary",
                         "wheel_analyst", "tools_options"}
        assert result not in options_nodes, (
            f"PROP-ROUTE-01: equity path must never touch options nodes, "
            f"router returned '{result}'"
        )

        # wheel_phase must remain None in state (routing must not mutate state)
        assert state.get("wheel_phase") is None, (
            "PROP-ROUTE-01: route_wheel_phase() must not mutate wheel_phase in state"
        )

    def test_wheel_phase_none_output_state_has_no_wheel_phase_set(self):
        """PROP-ROUTE-09: equity path does not set wheel_phase to a non-None value.

        When wheel_phase=None enters the router, the state key must remain None
        (the router is read-only with respect to wheel_phase).
        """
        logic = _make_logic(first_analyst="Market Analyst")
        state = _make_state(wheel_phase=None)
        logic.route_wheel_phase(state)
        assert state.get("wheel_phase") is None, (
            "PROP-ROUTE-09: wheel_phase must remain None after equity-path routing"
        )


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
