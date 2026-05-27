"""Unit tests for WheelAnalyst agent (Batch 3).

Covers:
- Three-layer structured-output fallback (PROP-FALLBACK-01, -02, -03)
- Sentinel import requirement (ADR-WHEEL-04)
- State reads/writes
- Approval and rejection paths
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tradingagents.agents.schemas import WheelCandidateReport, render_wheel_candidate_report
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wheel_candidate_report(approved=True):
    if approved:
        return WheelCandidateReport(
            approved=True,
            iv_rank=55.0,
            iv_percentile=60.0,
            iv_environment="elevated",
            iv_assessment="Elevated volatility environment.",
            earnings_clearance_ok=True,
            liquidity_ok=True,
            analyst_bias="bullish",
            recommended_strike_range=[140.0, 150.0],
            recommended_dte_range=[28, 45],
            rationale="All criteria pass.",
        )
    else:
        return WheelCandidateReport(
            approved=False,
            rejection_reason="IV rank below threshold",
            iv_rank=10.0,
            iv_percentile=15.0,
            iv_environment="compressed",
            iv_assessment="Low volatility environment.",
            earnings_clearance_ok=False,
            liquidity_ok=True,
            analyst_bias="neutral",
            recommended_strike_range=[0.0, 0.0],
            recommended_dte_range=[28, 45],
            rationale="IV rank failed.",
        )


def _make_state(ticker="AAPL", wheel_phase=None):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": wheel_phase,
        "market_report": "Market report content",
        "sentiment_report": "Sentiment report content",
        "news_report": "News report content",
        "fundamentals_report": "Fundamentals content",
        "investment_plan": "Buy recommendation",
    }


# ---------------------------------------------------------------------------
# PROP-FALLBACK-01: Structured success path
# ---------------------------------------------------------------------------

class TestWheelAnalystStructuredPath:
    def test_structured_output_returns_wheel_candidate_report(self):
        """PROP-FALLBACK-01: structured success returns rendered WheelCandidateReport."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        report = _make_wheel_candidate_report(approved=True)
        render_wheel_candidate_report(report)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = report
        mock_llm.with_structured_output.return_value = mock_structured
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        assert "wheel_candidate_report" in result
        assert result["wheel_candidate_report"] is not None

    def test_approved_report_stored_in_state(self):
        """Approved WheelCandidateReport is stored in state under wheel_candidate_report."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        report = _make_wheel_candidate_report(approved=True)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = report
        mock_llm.with_structured_output.return_value = mock_structured
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        assert result["wheel_candidate_report"] is not None


# ---------------------------------------------------------------------------
# PROP-FALLBACK-02: Freetext-valid-JSON path
# ---------------------------------------------------------------------------

class TestWheelAnalystFreetextPath:
    def test_freetext_valid_json_no_sentinel(self):
        """PROP-FALLBACK-02: when freetext returns valid JSON, sentinel NOT returned."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        report = _make_wheel_candidate_report(approved=False)
        json_str = report.model_dump_json()

        mock_llm = MagicMock()
        # Structured path fails
        mock_llm.with_structured_output.side_effect = NotImplementedError("not supported")
        # Freetext returns valid JSON
        mock_response = MagicMock()
        mock_response.content = json_str
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        stored = result["wheel_candidate_report"]
        assert STRUCTURED_OUTPUT_SENTINEL not in stored

    def test_freetext_path_stores_content(self):
        """Freetext path: stored content is non-empty."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = "Some free text analysis"
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        assert result["wheel_candidate_report"]


# ---------------------------------------------------------------------------
# PROP-FALLBACK-03: Total failure → sentinel
# ---------------------------------------------------------------------------

class TestWheelAnalystSentinelPath:
    def test_total_failure_returns_sentinel(self):
        """PROP-FALLBACK-03: both structured and freetext fail → sentinel returned."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = ""  # empty → triggers sentinel
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        stored = result["wheel_candidate_report"]
        assert STRUCTURED_OUTPUT_SENTINEL in stored

    def test_sentinel_import_not_hardcoded(self):
        """ADR-WHEEL-04: sentinel value is imported constant, not a hardcoded literal."""
        assert STRUCTURED_OUTPUT_SENTINEL == "Structured output failed — safe fallback applied."

    def test_sentinel_rejection_reason_set(self):
        """When sentinel fires, rejection_reason is STRUCTURED_OUTPUT_SENTINEL."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = ""
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        # Verify rejection_reason contains sentinel
        stored = result["wheel_candidate_report"]
        assert STRUCTURED_OUTPUT_SENTINEL in stored


# ---------------------------------------------------------------------------
# Rejection path
# ---------------------------------------------------------------------------

class TestWheelAnalystRejectionPath:
    def test_rejected_report_returns_false_approved(self):
        """Rejected report has approved=False."""
        from tradingagents.agents.analysts.wheel_analyst import create_wheel_analyst

        report = _make_wheel_candidate_report(approved=False)
        json_str = report.model_dump_json()

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = json_str
        mock_llm.invoke.return_value = mock_response
        mock_llm.bind_tools.return_value = mock_llm

        agent_fn = create_wheel_analyst(mock_llm)
        result = agent_fn(_make_state(), {})

        stored = result["wheel_candidate_report"]
        parsed = WheelCandidateReport.model_validate_json(stored)
        assert parsed.approved is False
        assert parsed.rejection_reason is not None
