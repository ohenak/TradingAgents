"""Unit tests for wheel options trading schemas (Batch 2).

Covers: WheelCandidateReport model_validator, sentinel exemption, schema validation,
CspDecision, CcDecision, RollDecision, render helpers.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from tradingagents.agents.schemas import (
    CcDecision,
    CspDecision,
    RollDecision,
    WheelCandidateReport,
    WheelPhase,
    render_cc_decision,
    render_csp_decision,
    render_roll_decision,
    render_wheel_candidate_report,
)


# ---------------------------------------------------------------------------
# WheelPhase enum
# ---------------------------------------------------------------------------

class TestWheelPhase:
    def test_enum_values_are_strings(self):
        """WheelPhase enum members are str instances (JSON serialisable)."""
        for member in WheelPhase:
            assert isinstance(member.value, str)

    def test_known_phase_values(self):
        assert WheelPhase.SCREENING.value == "screening"
        assert WheelPhase.CSP_OPEN.value == "csp_open"
        assert WheelPhase.STOCK_OWNED.value == "stock_owned"
        assert WheelPhase.CC_OPEN.value == "cc_open"
        assert WheelPhase.CYCLE_COMPLETE.value == "cycle_complete"


# ---------------------------------------------------------------------------
# WheelCandidateReport model_validator
# ---------------------------------------------------------------------------

def _make_approved_report(**overrides):
    defaults = dict(
        approved=True,
        rejection_reason=None,
        iv_rank=55.0,
        iv_percentile=52.0,
        iv_environment="elevated",
        iv_assessment="IV is elevated based on 30-day realised volatility.",
        next_earnings_date="2024-03-15",
        earnings_clearance_ok=True,
        liquidity_ok=True,
        analyst_bias="bullish",
        recommended_strike_range=[140.0, 145.0],
        recommended_dte_range=[28, 45],
        rationale="All five criteria passed.",
    )
    defaults.update(overrides)
    return WheelCandidateReport(**defaults)


def _make_rejected_report(**overrides):
    defaults = dict(
        approved=False,
        rejection_reason="IV too low; spread too wide",
        iv_rank=15.0,
        iv_percentile=12.0,
        iv_environment="compressed",
        iv_assessment="IV is compressed.",
        next_earnings_date=None,
        earnings_clearance_ok=False,
        liquidity_ok=False,
        analyst_bias="bearish",
        recommended_strike_range=[0.0, 0.0],
        recommended_dte_range=[28, 45],
        rationale="Two criteria failed.",
    )
    defaults.update(overrides)
    return WheelCandidateReport(**defaults)


class TestWheelCandidateReport:
    def test_approved_valid(self):
        r = _make_approved_report()
        assert r.approved is True

    def test_rejected_valid(self):
        r = _make_rejected_report()
        assert r.approved is False

    def test_approved_without_positive_strike_range_raises(self):
        """approved=True with [0.0, 0.0] strike range must fail validation."""
        with pytest.raises(ValidationError):
            _make_approved_report(recommended_strike_range=[0.0, 0.0])

    def test_rejected_without_rejection_reason_raises(self):
        """approved=False without rejection_reason must fail validation."""
        with pytest.raises(ValidationError):
            _make_rejected_report(rejection_reason=None)

    def test_approved_with_zero_strike_single_raises(self):
        """approved=True with any zero strike value must fail."""
        with pytest.raises(ValidationError):
            _make_approved_report(recommended_strike_range=[0.0, 145.0])

    def test_iv_environment_boundaries(self):
        """iv_environment Literal values accepted correctly."""
        for env in ("elevated", "normal", "compressed"):
            r = _make_rejected_report(iv_environment=env)
            assert r.iv_environment == env

    def test_sentinel_exempt_from_strike_range_constraint(self):
        """Sentinel (approved=False, strike_range=[0.0, 0.0]) is valid."""
        r = _make_rejected_report(recommended_strike_range=[0.0, 0.0])
        assert r.recommended_strike_range == [0.0, 0.0]


# ---------------------------------------------------------------------------
# CspDecision
# ---------------------------------------------------------------------------

def _make_csp(**overrides):
    defaults = dict(
        tradeable=True,
        ticker="AAPL",
        strike=145.0,
        expiration_date="2024-02-16",
        dte=30,
        bid=1.20,
        ask=1.40,
        mid_premium=1.30,
        delta=-0.25,
        theta=-0.05,
        annualised_yield_pct=12.0,
        max_loss=14370.0,
        breakeven_price=143.70,
        probability_of_profit=0.75,
        earnings_clear=True,
        rationale="Good trade.",
    )
    defaults.update(overrides)
    return CspDecision(**defaults)


class TestCspDecision:
    def test_valid_tradeable(self):
        d = _make_csp()
        assert d.tradeable is True
        assert d.option_type == "put"

    def test_sentinel_tradeable_false_zero_fields(self):
        """Sentinel with tradeable=False and zero numeric fields is valid."""
        from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL
        d = CspDecision(
            tradeable=False,
            ticker="AAPL",
            option_type="put",
            strike=0.0, expiration_date="", dte=0, bid=0.0, ask=0.0,
            mid_premium=0.0, delta=0.0, theta=0.0, annualised_yield_pct=0.0,
            max_loss=0.0, breakeven_price=0.0, probability_of_profit=0.0,
            earnings_clear=False,
            rationale=STRUCTURED_OUTPUT_SENTINEL,
        )
        assert d.rationale == STRUCTURED_OUTPUT_SENTINEL
        assert d.tradeable is False


# ---------------------------------------------------------------------------
# CcDecision
# ---------------------------------------------------------------------------

class TestCcDecision:
    def test_valid(self):
        d = CcDecision(
            tradeable=True,
            ticker="AAPL",
            strike=155.0,
            expiration_date="2024-02-16",
            dte=30,
            bid=1.50,
            ask=1.70,
            mid_premium=1.60,
            delta=0.28,
            theta=-0.04,
            annualised_yield_on_cost_pct=14.0,
            assigned_at=140.0,
            cost_basis=138.50,
            strike_above_cost_basis=True,
            upside_to_strike_pct=3.5,
            earnings_clear=True,
            rationale="Solid CC trade.",
        )
        assert d.tradeable is True
        assert d.option_type == "call"


# ---------------------------------------------------------------------------
# RollDecision
# ---------------------------------------------------------------------------

class TestRollDecision:
    def test_hold_action(self):
        d = RollDecision(
            action="HOLD",
            ticker="AAPL",
            current_strike=145.0,
            current_expiration="2024-02-16",
            current_dte=25,
            current_value_pct_of_premium=48.0,
            trigger_reason="profit_capture",
            rationale="Profit target hit.",
        )
        assert d.action == "HOLD"

    def test_roll_action_with_new_fields(self):
        d = RollDecision(
            action="ROLL",
            ticker="AAPL",
            current_strike=145.0,
            current_expiration="2024-02-16",
            current_dte=5,
            current_value_pct_of_premium=70.0,
            trigger_reason="dte_rule",
            new_strike=140.0,
            new_expiration="2024-03-15",
            new_dte=32,
            estimated_debit_or_credit=0.50,
            rationale="DTE too low, rolling out.",
        )
        assert d.action == "ROLL"
        assert d.new_strike == 140.0


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

class TestRenderHelpers:
    def test_render_wheel_candidate_report_approved(self):
        r = _make_approved_report()
        text = render_wheel_candidate_report(r)
        assert "Approved" in text
        assert "140.00" in text  # strike range

    def test_render_wheel_candidate_report_rejected(self):
        r = _make_rejected_report()
        text = render_wheel_candidate_report(r)
        assert "Rejection Reason" in text
        assert "IV too low" in text

    def test_render_csp_decision(self):
        d = _make_csp()
        text = render_csp_decision(d)
        assert "145.0" in text
        assert "Tradeable" in text

    def test_render_cc_decision(self):
        d = CcDecision(
            tradeable=True, ticker="AAPL", strike=155.0, expiration_date="2024-02-16",
            dte=30, bid=1.50, ask=1.70, mid_premium=1.60, delta=0.28, theta=-0.04,
            annualised_yield_on_cost_pct=14.0, assigned_at=140.0, cost_basis=138.50,
            strike_above_cost_basis=True, upside_to_strike_pct=3.5, earnings_clear=True,
            rationale="Good.",
        )
        text = render_cc_decision(d)
        assert "155.0" in text
        assert "call" in text.lower()

    def test_render_roll_decision(self):
        d = RollDecision(
            action="HOLD", ticker="AAPL", current_strike=145.0,
            current_expiration="2024-02-16", current_dte=25,
            current_value_pct_of_premium=48.0, trigger_reason="profit_capture",
            rationale="Profit target hit.",
        )
        text = render_roll_decision(d)
        assert "HOLD" in text


# ---------------------------------------------------------------------------
# Sentinel constant import (ADR-WHEEL-04)
# ---------------------------------------------------------------------------

class TestSentinelConstant:
    def test_sentinel_constant_importable(self):
        """STRUCTURED_OUTPUT_SENTINEL is importable from structured.py."""
        from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL
        assert isinstance(STRUCTURED_OUTPUT_SENTINEL, str)
        assert len(STRUCTURED_OUTPUT_SENTINEL) > 0

    def test_sentinel_constant_value(self):
        """Sentinel value matches the contract string."""
        from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL
        # Do NOT hardcode the string here — import it.
        # Just verify it's a non-empty string (the exact value is tested by usage).
        assert STRUCTURED_OUTPUT_SENTINEL == "Structured output failed — safe fallback applied."
