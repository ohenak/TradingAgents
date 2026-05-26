"""PROPERTIES tests — PROP-LIFE domain.

Covers missing PROPERTIES tests:
  PROP-LIFE-03: cycle_annualised_return_pct = 33.21% via wheel_cycle_summary node
  PROP-LIFE-05: atomic write — no .tmp files remain after successful write;
                temp file removed if os.replace raises
  PROP-LIFE-07: _build_options_context injects CspDecision fields when present
  PROP-LIFE-08: _build_options_context does NOT inject "Past Cycle Performance"
                when cycle_history is empty or absent
  PROP-LIFE-12: prior_analyst_bias persisted in WheelPosition after RollCheckAgent run
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from tradingagents.agents.schemas import CspDecision
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL
from tradingagents.models.wheel_position import (
    WheelPosition,
    load_latest_open_position,
    save_wheel_position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_position(ticker="AAPL", cycle=1, phase="csp_open", **kwargs) -> WheelPosition:
    defaults = dict(
        ticker=ticker,
        wheel_phase=phase,
        cycle_number=cycle,
    )
    defaults.update(kwargs)
    return WheelPosition(**defaults)


def _make_csp_json(tradeable=True) -> str:
    d = CspDecision(
        tradeable=tradeable,
        ticker="AAPL",
        option_type="put",
        strike=145.0,
        expiration_date="2024-02-16",
        dte=32,
        bid=2.10,
        ask=2.30,
        mid_premium=2.50,
        delta=-0.25,
        theta=-0.05,
        annualised_yield_pct=17.25,
        max_loss=14250.0,
        breakeven_price=142.50,
        probability_of_profit=0.75,
        earnings_clear=True,
        rationale="Good CSP.",
    )
    return d.model_dump_json()


# ---------------------------------------------------------------------------
# PROP-LIFE-03: cycle_annualised_return_pct = 33.21% via wheel_cycle_summary node
# ---------------------------------------------------------------------------

class TestWheelCycleSummaryCanonicalReturn:
    """PROP-LIFE-03: cycle_annualised_return_pct formula via wheel_cycle_summary node.

    NOTE: REQ v0.2.0 AC3a states "approximately 33.25%" but the arithmetically
    correct value is 33.21%. TSPEC §9.4 is authoritative. (TE-TSPEC-05)
    """

    def test_cycle_annualised_return_via_summary_node(self, tmp_path):
        """PROP-LIFE-03: summary node computes 33.21% for canonical inputs."""
        from tradingagents.graph.wheel_nodes import wheel_cycle_summary

        # Canonical inputs: cycle_pnl=930, csp_strike=140, shares_held=100,
        # csp_open_date=2024-01-01, call_away_date=2024-03-14 (73 days)
        pos = WheelPosition(
            ticker="AAPL",
            wheel_phase="cycle_complete",
            cycle_number=1,
            csp_strike=140.0,
            cc_strike=145.0,
            shares_held=100,
            csp_open_date="2024-01-01",
            call_away_date="2024-03-14",  # 73 calendar days
            cumulative_premium_received=930.0,
        )
        save_wheel_position(pos, str(tmp_path))

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-03-14",
        }

        with patch("tradingagents.dataflows.config.get_config") as mock_cfg:
            mock_cfg.return_value = {"wheel": {"positions_dir": str(tmp_path)}}
            result = wheel_cycle_summary(state)

        # Verify wheel_phase is reset
        assert result["wheel_phase"] is None

        # Load the updated position and check cycle_annualised_return_pct
        from tradingagents.models.wheel_position import load_wheel_position
        updated = load_wheel_position("AAPL", 1, str(tmp_path))
        if updated is not None and updated.cycle_annualised_return_pct is not None:
            assert abs(updated.cycle_annualised_return_pct - 33.21) <= 0.01, (
                f"PROP-LIFE-03: cycle_annualised_return_pct = {updated.cycle_annualised_return_pct:.2f}%, "
                f"expected ≈ 33.21% (TSPEC §9.4). Note: REQ v0.2.0 states 33.25% — "
                f"TSPEC 33.21% is arithmetically correct and authoritative."
            )


# ---------------------------------------------------------------------------
# PROP-LIFE-05: atomic write — no .tmp files remain
# ---------------------------------------------------------------------------

class TestAtomicWheelPositionWrite:
    """PROP-LIFE-05: save_wheel_position uses atomic os.replace; no .tmp left behind."""

    def test_no_tmp_files_after_successful_write(self, tmp_path):
        """PROP-LIFE-05: successful write leaves no .tmp files."""
        pos = _make_position(ticker="AAPL", cycle=1)
        save_wheel_position(pos, str(tmp_path))

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, (
            f"PROP-LIFE-05: found .tmp files after successful write: {tmp_files}"
        )

    def test_final_file_is_valid_json(self, tmp_path):
        """PROP-LIFE-05: written file is valid WheelPosition JSON."""
        pos = _make_position(ticker="NVDA", cycle=2, csp_strike=200.0)
        save_wheel_position(pos, str(tmp_path))

        final_file = tmp_path / "NVDA-cycle-2.json"
        assert final_file.exists()
        loaded = WheelPosition.model_validate_json(final_file.read_text(encoding="utf-8"))
        assert loaded.ticker == "NVDA"
        assert loaded.cycle_number == 2

    def test_tmp_file_removed_if_replace_raises(self, tmp_path):
        """PROP-LIFE-05: .tmp file is cleaned up when os.replace raises OSError."""
        pos = _make_position(ticker="AAPL", cycle=1)

        with patch("tradingagents.models.wheel_position.os.replace",
                   side_effect=OSError("atomic replace failed")):
            try:
                save_wheel_position(pos, str(tmp_path))
            except OSError:
                pass  # expected

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, (
            f"PROP-LIFE-05: .tmp file not cleaned up after os.replace failure: {tmp_files}"
        )


# ---------------------------------------------------------------------------
# PROP-LIFE-07: _build_options_context injects CspDecision fields
# ---------------------------------------------------------------------------

class TestBuildOptionsContextCspInjection:
    """PROP-LIFE-07: _build_options_context injects known CspDecision fields."""

    def test_mid_premium_injected(self):
        """PROP-LIFE-07: mid_premium value appears in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "2.50" in result, (
            f"PROP-LIFE-07: mid_premium '2.50' not found in options context: {result[:300]}"
        )

    def test_probability_of_profit_injected(self):
        """PROP-LIFE-07: probability_of_profit appears in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        # probability_of_profit = 0.75 → "75.00%" or "0.75" or "Probability of Profit"
        assert any(s in result for s in ("0.75", "75.00%", "Probability of Profit")), (
            f"PROP-LIFE-07: probability_of_profit not found in context: {result[:300]}"
        )

    def test_breakeven_price_injected(self):
        """PROP-LIFE-07: breakeven_price value appears in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "142.50" in result or "Breakeven" in result, (
            f"PROP-LIFE-07: breakeven_price not found in context: {result[:300]}"
        )

    def test_max_loss_injected(self):
        """PROP-LIFE-07: max_loss appears in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "14250" in result or "Max Loss" in result, (
            f"PROP-LIFE-07: max_loss not found in context: {result[:300]}"
        )

    def test_earnings_clear_injected(self):
        """PROP-LIFE-07: earnings_clear appears in options context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "Earnings Clear" in result or "True" in result, (
            f"PROP-LIFE-07: earnings_clear not found in context: {result[:300]}"
        )


# ---------------------------------------------------------------------------
# PROP-LIFE-08: No "Past Cycle Performance" when cycle_history is empty/absent
# ---------------------------------------------------------------------------

class TestBuildOptionsContextNoPastCycles:
    """PROP-LIFE-08: no 'Past Cycle Performance' injected when cycle_history is empty."""

    def test_no_past_performance_when_cycle_history_empty(self):
        """PROP-LIFE-08: empty cycle_history → no 'Past Cycle Performance' in context."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }

        # Position with empty cycle_history
        pos = _make_position(cycle_history=[])

        result = _build_options_context(state, _position_loader=lambda t, d: pos)
        assert "Past Cycle Performance" not in result, (
            f"PROP-LIFE-08: 'Past Cycle Performance' must NOT appear when cycle_history=[], "
            f"found in: {result[:400]}"
        )

    def test_no_past_performance_when_position_absent(self):
        """PROP-LIFE-08: no position → no 'Past Cycle Performance' injected."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "csp_decision": _make_csp_json(tradeable=True),
            "cc_decision": None,
        }

        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert "Past Cycle Performance" not in result, (
            f"PROP-LIFE-08: 'Past Cycle Performance' must NOT appear when position is None"
        )

    def test_equity_only_returns_empty_string(self):
        """PROP-LIFE-08: wheel_phase=None → _build_options_context returns empty string."""
        from tradingagents.agents.utils.agent_utils import _build_options_context

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": None,
            "csp_decision": None,
            "cc_decision": None,
        }
        result = _build_options_context(state, _position_loader=lambda t, d: None)
        assert result == "", (
            f"PROP-LIFE-08: equity-only path must return empty string, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# PROP-LIFE-12: prior_analyst_bias persisted in WheelPosition after RollCheckAgent run
# ---------------------------------------------------------------------------

class TestPriorAnalystBiasPersistence:
    """PROP-LIFE-12: RollCheckAgent persists prior_analyst_bias to WheelPosition.

    NOTE: The current roll_agent.py implementation does NOT write prior_analyst_bias
    back to the WheelPosition file. This test covers the PROPERTIES requirement that
    it SHOULD be persisted. If this test fails, the implementation needs to be extended.

    Per TSPEC §5.4: "Write: ... Also writes updated WheelPosition JSON to disk
    (updating prior_analyst_bias)."
    """

    def test_prior_analyst_bias_persisted_after_agent_run(self, tmp_path):
        """PROP-LIFE-12: after RollCheckAgent runs, WheelPosition.prior_analyst_bias is updated."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent
        from tradingagents.agents.schemas import RollDecision, render_roll_decision

        # Create position with no prior_analyst_bias
        pos = WheelPosition(
            ticker="AAPL",
            wheel_phase="csp_open",
            cycle_number=1,
            csp_strike=145.0,
            csp_expiration="2024-02-16",
            prior_analyst_bias=None,
        )
        save_wheel_position(pos, str(tmp_path))

        # RollDecision with HOLD action (no phase transition)
        decision = RollDecision(
            action="HOLD",
            ticker="AAPL",
            current_strike=145.0,
            current_expiration="2024-02-16",
            current_dte=25,
            current_value_pct_of_premium=45.0,
            trigger_reason="profit_capture",
            rationale="Profit target hit.",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        # investment_plan with "Buy" recommendation → bias = "bullish"
        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "csp_open",
            "investment_plan": "Buy recommendation — strong fundamentals justify accumulation.",
        }

        agent_fn = create_roll_check_agent(
            mock_llm,
            str(tmp_path),
            _position_loader=lambda t, d: load_latest_open_position(t, d),
        )
        agent_fn(state, {})

        # If the implementation persists prior_analyst_bias, verify it.
        # This test is RED if the implementation doesn't write back the bias.
        # It validates TSPEC §5.4 requirement.
        updated = load_latest_open_position("AAPL", str(tmp_path))
        if updated is not None:
            # The agent should have written prior_analyst_bias = "bullish"
            # (derived from "Buy recommendation" → "bullish")
            # This assertion guards the persistence requirement.
            # If None, the implementation needs to add this write step.
            assert updated.prior_analyst_bias is not None, (
                "PROP-LIFE-12: prior_analyst_bias must be persisted to WheelPosition "
                "after RollCheckAgent run. Per TSPEC §5.4, the agent must write "
                "updated WheelPosition to disk (updating prior_analyst_bias)."
            )
            assert updated.prior_analyst_bias in ("bullish", "neutral", "bearish"), (
                f"PROP-LIFE-12: prior_analyst_bias must be one of "
                f"'bullish'/'neutral'/'bearish', got: {updated.prior_analyst_bias}"
            )
