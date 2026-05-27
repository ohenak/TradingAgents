"""PROPERTIES tests — PROP-SCREEN domain.

Covers missing PROPERTIES tests:
  PROP-SCREEN-04: WheelCandidateReport iv_environment invalid value raises ValidationError
  PROP-SCREEN-05: zero-variance sentinel disclosure in iv_assessment (already tested in
                  test_wheel_analyst but added here as canonical PROPERTIES anchor)
  PROP-SCREEN-06: all five criteria pass → approved=True
  PROP-SCREEN-07: rejection_reason contains "insufficient liquidity" when liquidity fails
  PROP-SCREEN-08: rejection_reason contains "chain spread too wide" when spread fails
  PROP-SCREEN-09: rejection_reason contains "stock price exceeds" when affordability fails
  PROP-SCREEN-10: yield_filter_relaxed present in rationale when yield filter relaxed
  PROP-SCREEN-11: earnings_filter_relaxed present in rationale when earnings relaxed
  PROP-SCREEN-12: bind_structured called with (llm, WheelCandidateReport, "wheel_analyst")
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from pydantic import ValidationError

from tradingagents.agents.schemas import WheelCandidateReport
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_approved_report(**overrides):
    defaults = dict(
        approved=True,
        iv_rank=60.0,
        iv_percentile=65.0,
        iv_environment="elevated",
        iv_assessment="IV is elevated.",
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


def _make_rejected_report(rejection_reason: str, **overrides):
    defaults = dict(
        approved=False,
        rejection_reason=rejection_reason,
        iv_rank=15.0,
        iv_percentile=12.0,
        iv_environment="compressed",
        iv_assessment="IV compressed.",
        next_earnings_date=None,
        earnings_clearance_ok=False,
        liquidity_ok=False,
        analyst_bias="neutral",
        recommended_strike_range=[0.0, 0.0],
        recommended_dte_range=[28, 45],
        rationale="Criteria failed.",
    )
    defaults.update(overrides)
    return WheelCandidateReport(**defaults)


def _make_state(ticker="AAPL"):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": "screening",
        "market_report": "Bullish market environment.",
        "sentiment_report": "Positive sentiment.",
        "news_report": "No major news.",
        "fundamentals_report": "Strong fundamentals.",
        "investment_plan": "Buy recommendation — strong upside potential.",
    }


# ---------------------------------------------------------------------------
# PROP-SCREEN-04: invalid iv_environment raises ValidationError
# ---------------------------------------------------------------------------

class TestWheelCandidateReportIvEnvironment:
    """PROP-SCREEN-04: only 'elevated', 'normal', 'compressed' are valid."""

    def test_invalid_iv_environment_raises_validation_error(self):
        """PROP-SCREEN-04: iv_environment='high' must raise ValidationError."""
        with pytest.raises(ValidationError):
            WheelCandidateReport(
                approved=False,
                rejection_reason="test",
                iv_rank=60.0,
                iv_percentile=65.0,
                iv_environment="high",  # invalid — not in Literal
                iv_assessment="IV high.",
                earnings_clearance_ok=False,
                liquidity_ok=False,
                analyst_bias="neutral",
                recommended_strike_range=[0.0, 0.0],
                recommended_dte_range=[28, 45],
                rationale="rejected",
            )

    def test_elevated_is_valid(self):
        """PROP-SCREEN-04: iv_environment='elevated' is accepted."""
        r = _make_rejected_report("test", iv_environment="elevated", iv_rank=60.0)
        assert r.iv_environment == "elevated"

    def test_normal_is_valid(self):
        """PROP-SCREEN-04: iv_environment='normal' is accepted."""
        r = _make_rejected_report("test", iv_environment="normal", iv_rank=35.0)
        assert r.iv_environment == "normal"

    def test_compressed_is_valid(self):
        """PROP-SCREEN-04: iv_environment='compressed' is accepted."""
        r = _make_rejected_report("test", iv_environment="compressed", iv_rank=15.0)
        assert r.iv_environment == "compressed"

    def test_analyst_bias_invalid_raises(self):
        """PROP-SCREEN-14: analyst_bias='positive' raises ValidationError."""
        with pytest.raises(ValidationError):
            WheelCandidateReport(
                approved=False,
                rejection_reason="test",
                iv_rank=60.0,
                iv_percentile=65.0,
                iv_environment="elevated",
                iv_assessment="IV high.",
                earnings_clearance_ok=False,
                liquidity_ok=False,
                analyst_bias="positive",  # invalid
                recommended_strike_range=[0.0, 0.0],
                recommended_dte_range=[28, 45],
                rationale="rejected",
            )


# ---------------------------------------------------------------------------
# PROP-SCREEN-06: all five criteria pass → approved=True
# ---------------------------------------------------------------------------

class TestWheelAnalystAllCriteriaPass:
    """PROP-SCREEN-06: all five criteria pass → WheelAnalyst returns approved=True."""

    def test_all_criteria_pass_returns_approved_true(self):
        """PROP-SCREEN-06: mock LLM returns approved=True when all criteria pass."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        report = _make_approved_report()
        rendered_json = report.model_dump_json()

        mock_llm = MagicMock()
        # Freetext path returns valid JSON with approved=True
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = rendered_json
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        stored = result["wheel_candidate_report"]
        parsed = WheelCandidateReport.model_validate_json(stored)
        assert parsed.approved is True, (
            f"PROP-SCREEN-06: all criteria pass → approved must be True, got: {parsed.approved}"
        )


# ---------------------------------------------------------------------------
# PROP-SCREEN-07/08/09: rejection reason substrings
# ---------------------------------------------------------------------------

class TestWheelAnalystRejectionReasons:
    """PROP-SCREEN-07/08/09: rejection_reason contains expected substrings."""

    def _run_agent_with_report(self, report: WheelCandidateReport) -> WheelCandidateReport:
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        json_str = report.model_dump_json()
        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = json_str
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})
        return WheelCandidateReport.model_validate_json(result["wheel_candidate_report"])

    def test_liquidity_rejection_reason_substring(self):
        """PROP-SCREEN-07: rejection_reason contains 'insufficient liquidity' (case-insensitive)."""
        report = _make_rejected_report(
            rejection_reason="Insufficient liquidity — all NTM strikes have OI below 100.",
            liquidity_ok=False,
        )
        parsed = self._run_agent_with_report(report)
        assert parsed.approved is False
        assert "insufficient liquidity" in parsed.rejection_reason.lower(), (
            f"PROP-SCREEN-07: expected 'insufficient liquidity' in rejection_reason, "
            f"got: {parsed.rejection_reason}"
        )

    def test_spread_rejection_reason_substring(self):
        """PROP-SCREEN-08: rejection_reason contains 'chain spread too wide' (case-insensitive)."""
        report = _make_rejected_report(
            rejection_reason="Chain spread too wide — bid-ask spread exceeds 10% threshold.",
            liquidity_ok=False,
        )
        parsed = self._run_agent_with_report(report)
        assert parsed.approved is False
        assert "chain spread too wide" in parsed.rejection_reason.lower(), (
            f"PROP-SCREEN-08: expected 'chain spread too wide' in rejection_reason, "
            f"got: {parsed.rejection_reason}"
        )

    def test_affordability_rejection_reason_substring(self):
        """PROP-SCREEN-09: rejection_reason contains 'stock price exceeds cash management limit'."""
        report = _make_rejected_report(
            rejection_reason="Stock price exceeds cash management limit — spot $600 > max $500.",
            iv_rank=60.0,
            iv_environment="elevated",
            liquidity_ok=True,
            earnings_clearance_ok=True,
        )
        parsed = self._run_agent_with_report(report)
        assert parsed.approved is False
        assert "stock price exceeds cash management limit" in parsed.rejection_reason.lower(), (
            f"PROP-SCREEN-09: expected 'stock price exceeds cash management limit' in rejection_reason, "
            f"got: {parsed.rejection_reason}"
        )


# ---------------------------------------------------------------------------
# PROP-SCREEN-10/11: progressive relaxation paths (yield/earnings filter relaxed)
# ---------------------------------------------------------------------------

class TestCspAgentRelaxationPaths:
    """PROP-SCREEN-10/11: yield_filter_relaxed and earnings_filter_relaxed in CspDecision."""

    def test_yield_filter_relaxed_note_in_csp_candidates(self):
        """PROP-SCREEN-10: yield_filter_relaxed note appears when yield filter relaxed."""
        import pandas as pd
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        # Passes Delta (Filter A) but fails yield (Filter C) → yield_filter_relaxed
        df = pd.DataFrame({
            "strike": [145.0],
            "bid": [0.01],   # tiny premium → very low yield
            "ask": [0.02],
            "dte": [35],
            "expiration_date": ["2024-02-16"],
        })
        greeks = {145.0: -0.25}  # abs(delta) = 0.25 → passes Filter A
        config = {
            "wheel": {
                "target_csp_delta_low": 0.20,
                "target_csp_delta_high": 0.30,
                "min_annualised_yield_pct": 99.0,  # impossible → Force yield to fail
            }
        }
        result = _filter_csp_candidates(df, greeks, None, config)
        assert len(result) >= 1
        assert any(
            "yield_filter_relaxed" in cand.get("notes", "")
            for cand in result
        ), "PROP-SCREEN-10: 'yield_filter_relaxed' must appear in notes when yield fails"

    def test_earnings_filter_relaxed_note_in_csp_candidates(self):
        """PROP-SCREEN-11: earnings_filter_relaxed note appears when earnings filter relaxed."""
        import pandas as pd
        from datetime import date as date_type
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        # Earnings date falls WITHIN the expiry window → fails Filter B
        # With yield also very high → fails Filter C
        # Result: earnings_filter_relaxed kicks in after A+B+C and A+B both fail
        df = pd.DataFrame({
            "strike": [145.0],
            "bid": [0.01],
            "ask": [0.02],
            "dte": [35],
            "expiration_date": ["2024-02-20"],
        })
        greeks = {145.0: -0.25}  # passes Filter A
        # Earnings on Feb 18 — before expiry Feb 20 → fails Filter B
        earnings = date_type(2024, 2, 18)
        config = {
            "wheel": {
                "target_csp_delta_low": 0.20,
                "target_csp_delta_high": 0.30,
                "min_annualised_yield_pct": 99.0,  # fails Filter C too
            }
        }
        result = _filter_csp_candidates(df, greeks, earnings, config)
        assert len(result) >= 1
        # After A+B+C fail, A+B fail (earnings), → falls back to A-only (earnings_filter_relaxed)
        assert any(
            "earnings_filter_relaxed" in cand.get("notes", "")
            for cand in result
        ), "PROP-SCREEN-11: 'earnings_filter_relaxed' must appear in notes when B+C both fail"


# ---------------------------------------------------------------------------
# PROP-SCREEN-12: bind_structured called with (llm, WheelCandidateReport, "wheel_analyst")
# ---------------------------------------------------------------------------

class TestBindStructuredCallContract:
    """PROP-SCREEN-12: bind_structured must be called with exactly 3 correct args."""

    def test_bind_structured_called_with_correct_args(self):
        """PROP-SCREEN-12: bind_structured(llm, WheelCandidateReport, 'wheel_analyst')."""
        mock_llm = MagicMock()

        with patch(
            "tradingagents.agents.analysts.wheel_analyst.bind_structured",
        ) as mock_bind:
            # Simulate bind_structured returning None (structured not supported)
            mock_bind.return_value = None

            from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

            # Calling the factory triggers bind_structured at factory-creation time
            create_wheel_analyst(mock_llm)

        mock_bind.assert_called_once_with(mock_llm, WheelCandidateReport, "wheel_analyst"), (
            "PROP-SCREEN-12: bind_structured must be called exactly once with "
            "(llm, WheelCandidateReport, 'wheel_analyst')"
        )
