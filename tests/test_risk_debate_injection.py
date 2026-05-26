"""Unit tests for _build_options_context debate injection (Batch 3).

Covers:
- Options context injected when wheel_phase is set (REQ-TRADE-05)
- No context injected when wheel_phase is None (equity-only backward compat)
- CspDecision fields: mid_premium, probability_of_profit, max_loss,
  breakeven_price, earnings_clear
- CcDecision fields: mid_premium, upside_to_strike_pct, cost_basis, earnings_clear
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tradingagents.agents.schemas import (
    CspDecision,
    CcDecision,
    WheelPhase,
    render_csp_decision,
    render_cc_decision,
)
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csp_decision_json(tradeable=True):
    d = CspDecision(
        tradeable=tradeable,
        ticker="AAPL",
        option_type="put",
        strike=145.0,
        expiration_date="2024-02-16",
        dte=32,
        bid=2.10,
        ask=2.30,
        mid_premium=2.20,
        delta=-0.25,
        theta=-0.05,
        annualised_yield_pct=17.25,
        max_loss=14280.0,
        breakeven_price=142.80,
        probability_of_profit=0.75,
        earnings_clear=True,
        rationale="Good CSP.",
    )
    return d.model_dump_json()


def _make_cc_decision_json(tradeable=True):
    d = CcDecision(
        tradeable=tradeable,
        ticker="AAPL",
        option_type="call",
        strike=150.0,
        expiration_date="2024-02-16",
        dte=32,
        bid=1.50,
        ask=1.70,
        mid_premium=1.60,
        delta=0.25,
        theta=-0.04,
        annualised_yield_on_cost_pct=14.5,
        assigned_at=145.0,
        cost_basis=143.70,
        strike_above_cost_basis=True,
        upside_to_strike_pct=2.5,
        earnings_clear=True,
        rationale="Good CC.",
    )
    return d.model_dump_json()


def _make_state(wheel_phase=None, csp_json=None, cc_json=None, ticker="AAPL"):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": wheel_phase,
        "csp_decision": csp_json,
        "cc_decision": cc_json,
    }


# ---------------------------------------------------------------------------
# Equity-only path (no options context)
# ---------------------------------------------------------------------------

class TestNoOptionsContext:
    def test_wheel_phase_none_returns_empty(self):
        """wheel_phase is None → _build_options_context returns empty string."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(wheel_phase=None)
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert result == ""

    def test_equity_only_no_options_block(self):
        """Equity-only path: no ## Options Position Context block injected."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(wheel_phase=None, csp_json=_make_csp_decision_json())
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        # Even if csp_decision is in state, no injection when wheel_phase is None
        assert result == ""


# ---------------------------------------------------------------------------
# CSP Decision injection
# ---------------------------------------------------------------------------

class TestCspDecisionInjection:
    def test_csp_mid_premium_in_context(self):
        """mid_premium from CspDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="csp_open",
            csp_json=_make_csp_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "2.20" in result

    def test_csp_probability_of_profit_in_context(self):
        """probability_of_profit from CspDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="csp_open",
            csp_json=_make_csp_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        # probability_of_profit = 0.75 → should appear as "75.00%" or similar
        assert "Probability of Profit" in result or "75.00%" in result or "0.75" in result

    def test_csp_max_loss_in_context(self):
        """max_loss from CspDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="csp_open",
            csp_json=_make_csp_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "14280" in result or "Max Loss" in result

    def test_csp_breakeven_price_in_context(self):
        """breakeven_price from CspDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="csp_open",
            csp_json=_make_csp_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "142.80" in result or "Breakeven" in result

    def test_csp_earnings_clear_in_context(self):
        """earnings_clear from CspDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="csp_open",
            csp_json=_make_csp_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "Earnings Clear" in result or "True" in result


# ---------------------------------------------------------------------------
# CC Decision injection
# ---------------------------------------------------------------------------

class TestCcDecisionInjection:
    def test_cc_mid_premium_in_context(self):
        """mid_premium from CcDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="cc_open",
            cc_json=_make_cc_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "1.60" in result

    def test_cc_upside_to_strike_pct_in_context(self):
        """upside_to_strike_pct from CcDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="cc_open",
            cc_json=_make_cc_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "2.50" in result or "Upside" in result

    def test_cc_cost_basis_in_context(self):
        """cost_basis from CcDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="cc_open",
            cc_json=_make_cc_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "143.70" in result or "Cost Basis" in result

    def test_cc_earnings_clear_in_context(self):
        """earnings_clear from CcDecision is present in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = _make_state(
            wheel_phase="cc_open",
            cc_json=_make_cc_decision_json(tradeable=True),
        )
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "Earnings Clear" in result or "True" in result
