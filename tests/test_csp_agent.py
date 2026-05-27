"""Unit tests for CspAgent (Batch 3).

Covers:
- Three-layer structured-output fallback (PROP-FALLBACK-04, -05, -06)
- _filter_csp_candidates: Delta bounds (inclusive), earnings, yield relaxation
- Phase transition: tradeable=True → wheel_phase = "csp_open" (DEC-PLAN-02)
- Sentinel import requirement (ADR-WHEEL-04)
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from tradingagents.agents.schemas import CspDecision, WheelPhase, render_csp_decision
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(ticker="AAPL", wheel_phase="screening"):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": wheel_phase,
        "market_report": "Market report",
        "sentiment_report": "Sentiment report",
        "past_context": "",
        "wheel_candidate_report": None,
    }


def _make_chain_df(strikes=None, dte=35):
    if strikes is None:
        strikes = [135.0, 140.0, 145.0, 150.0, 155.0]
    n = len(strikes)
    return pd.DataFrame({
        "strike": strikes,
        "bid": [2.10] * n,
        "ask": [2.30] * n,
        "dte": [dte] * n,
        "expiration_date": ["2024-02-16"] * n,
    })


def _make_csp_decision(tradeable=True, ticker="AAPL"):
    return CspDecision(
        tradeable=tradeable,
        ticker=ticker,
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
        rationale="Good CSP opportunity.",
    )


# ---------------------------------------------------------------------------
# _filter_csp_candidates unit tests
# ---------------------------------------------------------------------------

class TestFilterCspCandidates:
    """Tests for the deterministic filter function."""

    def _make_greeks(self, strikes_deltas: dict) -> dict:
        return {float(k): v for k, v in strikes_deltas.items()}

    def test_delta_lower_bound_inclusive(self):
        """Delta == target_csp_delta_low (0.20) is included (inclusive boundary)."""
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        df = _make_chain_df([145.0])
        # abs(delta) = 0.20 exactly → should pass Filter A
        greeks = self._make_greeks({145.0: -0.20})
        config = {"wheel": {
            "target_csp_delta_low": 0.20,
            "target_csp_delta_high": 0.30,
            "min_annualised_yield_pct": 5.0,  # low so yield passes
        }}
        result = _filter_csp_candidates(df, greeks, None, config)
        assert len(result) == 1
        assert result[0]["strike"] == 145.0

    def test_delta_upper_bound_inclusive(self):
        """Delta == target_csp_delta_high (0.30) is included (inclusive boundary)."""
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        df = _make_chain_df([145.0])
        greeks = self._make_greeks({145.0: -0.30})
        config = {"wheel": {
            "target_csp_delta_low": 0.20,
            "target_csp_delta_high": 0.30,
            "min_annualised_yield_pct": 5.0,
        }}
        result = _filter_csp_candidates(df, greeks, None, config)
        assert len(result) == 1

    def test_delta_outside_range_excluded(self):
        """Delta outside [0.20, 0.30] fails Filter A → nearest-delta fallback."""
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        df = _make_chain_df([145.0])
        greeks = self._make_greeks({145.0: -0.10})  # too far OTM
        config = {"wheel": {
            "target_csp_delta_low": 0.20,
            "target_csp_delta_high": 0.30,
            "min_annualised_yield_pct": 5.0,
        }}
        result = _filter_csp_candidates(df, greeks, None, config)
        # Falls back to nearest-delta
        assert len(result) == 1
        assert "notes" in result[0]
        assert "nearest available" in result[0]["notes"]

    def test_earnings_filter_removes_straddling_expiry(self):
        """Strike with earnings within expiry window fails Filter B."""
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        df = _make_chain_df([145.0])
        # Make expiration_date in chain_df after earnings
        df["expiration_date"] = "2024-02-20"
        greeks = self._make_greeks({145.0: -0.25})
        earnings = date(2024, 2, 18)  # between today and expiration
        config = {"wheel": {
            "target_csp_delta_low": 0.20,
            "target_csp_delta_high": 0.30,
            "min_annualised_yield_pct": 5.0,
        }}
        result = _filter_csp_candidates(df, greeks, earnings, config)
        # earnings_date (Feb 18) is NOT > exp_date (Feb 20) → earnings_ok=False
        # Falls back to earnings_filter_relaxed
        assert any("earnings_filter_relaxed" in e.get("notes", "") for e in result)

    def test_yield_filter_relaxation(self):
        """When yield fails but Delta and earnings pass, yield_filter_relaxed note added."""
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        # Low bid/ask → low premium → low yield
        df = pd.DataFrame({
            "strike": [145.0],
            "bid": [0.01],
            "ask": [0.02],
            "dte": [35],
            "expiration_date": ["2024-02-16"],
        })
        greeks = self._make_greeks({145.0: -0.25})
        config = {"wheel": {
            "target_csp_delta_low": 0.20,
            "target_csp_delta_high": 0.30,
            "min_annualised_yield_pct": 99.0,  # impossibly high
        }}
        result = _filter_csp_candidates(df, greeks, None, config)
        assert len(result) == 1
        assert "yield_filter_relaxed" in result[0].get("notes", "")

    def test_empty_dataframe_returns_empty(self):
        """Empty chain returns empty list."""
        from tradingagents.agents.options.csp_agent import _filter_csp_candidates

        df = pd.DataFrame(columns=["strike", "bid", "ask", "dte"])
        result = _filter_csp_candidates(df, {}, None, {"wheel": {}})
        assert result == []


# ---------------------------------------------------------------------------
# PROP-FALLBACK-04: Structured success path
# ---------------------------------------------------------------------------

class TestCspAgentStructuredPath:
    def test_structured_output_returns_csp_decision(self):
        """PROP-FALLBACK-04: structured success returns rendered CspDecision."""
        from tradingagents.agents.options.csp_agent import create_csp_agent

        decision = _make_csp_decision(tradeable=True)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_csp_agent(mock_llm)
        result = agent_fn(_make_state(), {})

        assert "csp_decision" in result


# ---------------------------------------------------------------------------
# PROP-FALLBACK-05: Freetext-valid-JSON path
# ---------------------------------------------------------------------------

class TestCspAgentFreetextPath:
    def test_freetext_valid_json_no_sentinel(self):
        """PROP-FALLBACK-05: freetext with valid JSON → no sentinel."""
        from tradingagents.agents.options.csp_agent import create_csp_agent

        decision = _make_csp_decision(tradeable=False)
        decision_with_reason = CspDecision(
            **{**decision.model_dump(), "rejection_reason": "No suitable strike"}
        )
        json_str = decision_with_reason.model_dump_json()

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = json_str
        mock_llm.invoke.return_value = mock_response

        agent_fn = create_csp_agent(mock_llm)
        result = agent_fn(_make_state(), {})

        assert STRUCTURED_OUTPUT_SENTINEL not in result["csp_decision"]


# ---------------------------------------------------------------------------
# PROP-FALLBACK-06: Total failure → sentinel
# ---------------------------------------------------------------------------

class TestCspAgentSentinelPath:
    def test_total_failure_returns_sentinel(self):
        """PROP-FALLBACK-06: both paths fail → sentinel returned."""
        from tradingagents.agents.options.csp_agent import create_csp_agent

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = ""
        mock_llm.invoke.return_value = mock_response

        agent_fn = create_csp_agent(mock_llm)
        result = agent_fn(_make_state(), {})

        assert STRUCTURED_OUTPUT_SENTINEL in result["csp_decision"]

    def test_sentinel_import_not_hardcoded(self):
        """ADR-WHEEL-04: sentinel is imported from structured.py."""
        assert STRUCTURED_OUTPUT_SENTINEL == "Structured output failed — safe fallback applied."


# ---------------------------------------------------------------------------
# Phase transition (DEC-PLAN-02)
# ---------------------------------------------------------------------------

class TestCspAgentPhaseTransition:
    def test_tradeable_true_sets_csp_open_phase(self):
        """DEC-PLAN-02: tradeable=True → wheel_phase = 'csp_open' in returned state."""
        from tradingagents.agents.options.csp_agent import create_csp_agent

        decision = _make_csp_decision(tradeable=True)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_csp_agent(mock_llm)
        result = agent_fn(_make_state(), {})

        assert result.get("wheel_phase") == WheelPhase.CSP_OPEN.value

    def test_tradeable_false_no_phase_transition(self):
        """tradeable=False → no wheel_phase change."""
        from tradingagents.agents.options.csp_agent import create_csp_agent

        decision = _make_csp_decision(tradeable=False)
        decision_dict = decision.model_dump()
        decision_dict["rejection_reason"] = "No suitable strike"
        non_tradeable = CspDecision(**decision_dict)

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = non_tradeable
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_csp_agent(mock_llm)
        result = agent_fn(_make_state(), {})

        assert "wheel_phase" not in result or result.get("wheel_phase") != WheelPhase.CSP_OPEN.value
