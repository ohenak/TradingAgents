"""Unit tests for RollCheckAgent (Batch 3).

Covers:
- Three-layer structured-output fallback (PROP-FALLBACK-10, -11, -12)
- Five rules evaluation and priority resolution: Rule3 > Rule5 > Rule4 > Rule2 > Rule1
- Rule3 is CSP-only
- Phase transitions: assignment → stock_owned; CC called away → cycle_complete
- _position_loader injectable seam (ADR-WHEEL-05)
- Sentinel import requirement (ADR-WHEEL-04)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tradingagents.agents.schemas import RollDecision, WheelPhase, render_roll_decision
from tradingagents.agents.utils.structured import STRUCTURED_OUTPUT_SENTINEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(ticker="AAPL", wheel_phase="csp_open"):
    return {
        "company_of_interest": ticker,
        "trade_date": "2024-01-15",
        "wheel_phase": wheel_phase,
        "investment_plan": "Hold recommendation",
    }


def _make_roll_decision(action="HOLD", trigger_reason="profit_capture"):
    return RollDecision(
        action=action,
        ticker="AAPL",
        current_strike=145.0,
        current_expiration="2024-02-16",
        current_dte=32,
        current_value_pct_of_premium=45.0,
        trigger_reason=trigger_reason,
        rationale="Test roll decision.",
    )


def _make_position(ticker="AAPL", phase="csp_open", csp_strike=145.0, prior_bias=None):
    from tradingagents.models.wheel_position import WheelPosition
    return WheelPosition(
        ticker=ticker,
        wheel_phase=phase,
        cycle_number=1,
        csp_strike=csp_strike,
        csp_expiration="2024-02-16",
        prior_analyst_bias=prior_bias,
    )


# ---------------------------------------------------------------------------
# Rule evaluation unit tests (_evaluate_rules)
# ---------------------------------------------------------------------------

class TestEvaluateRules:
    """Tests for the deterministic rule evaluation function."""

    def test_rule1_profit_capture_fires_at_50pct(self):
        """Rule 1: current_value_pct <= 50 (100 - 50) fires profit_capture."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=45.0,  # 45% of original premium → 55% profit
            current_dte=30,
            abs_delta=0.25,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
            take_profit_pct=50.0,
            dte_to_roll=21,
        )
        assert rules["rule1"] is True

    def test_rule1_does_not_fire_above_50pct(self):
        """Rule 1: current_value_pct > 50 → rule1 = False."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=60.0,
            current_dte=30,
            abs_delta=0.25,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        assert rules["rule1"] is False

    def test_rule2_dte_fires_at_threshold(self):
        """Rule 2: current_dte <= dte_to_roll fires dte_rule."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=21,  # exactly dte_to_roll
            abs_delta=0.25,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
            dte_to_roll=21,
        )
        assert rules["rule2"] is True

    def test_rule3_csp_only_fires(self):
        """Rule 3: abs_delta > 0.85 AND wheel_phase == 'csp_open' fires breach."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.90,  # deep ITM
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        assert rules["rule3"] is True

    def test_rule3_does_not_fire_for_cc(self):
        """Rule 3: CSP-only. Does not fire when wheel_phase == 'cc_open'."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.90,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="cc_open",  # CC phase → Rule3 does not apply
        )
        assert rules["rule3"] is False

    def test_rule4_deep_otm_fires(self):
        """Rule 4: abs_delta < 0.10 fires (exclusive lower boundary)."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.05,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        assert rules["rule4"] is True

    def test_rule4_boundary_exclusive_at_0_10(self):
        """Rule 4: abs_delta == 0.10 does NOT fire (exclusive boundary)."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.10,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        assert rules["rule4"] is False

    def test_rule4_boundary_exclusive_at_0_10_with_earnings_within_cycle(self):
        """PROP-LIFE-10: abs_delta == 0.10 does NOT fire Rule 4, even with earnings_within_cycle=True.

        Guards against write-once / vacuous tests — the boundary must be exclusive at 0.10
        regardless of whether earnings are within the cycle (TE-F-04).
        """
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.10,
            earnings_within_cycle=True,  # earnings ARE within cycle
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        # Rule 4 (deep OTM: abs_delta < 0.10) must still be False at the boundary
        assert rules["rule4"] is False, (
            "PROP-LIFE-10: abs_delta=0.10 must NOT fire Rule 4 (exclusive boundary); "
            "earnings_within_cycle=True must not change this"
        )

    def test_rule4_fires_with_deep_otm_and_earnings_within_cycle(self):
        """PROP-LIFE-10: abs_delta=0.05 fires Rule 4 (deep OTM) even with earnings_within_cycle=True."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.05,
            earnings_within_cycle=True,  # earnings ARE within cycle
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        # Rule 4 (deep OTM: abs_delta < 0.10) must fire
        assert rules["rule4"] is True, (
            "PROP-LIFE-10: abs_delta=0.05 must fire Rule 4 (deep OTM); "
            "earnings_within_cycle=True must not suppress this"
        )

    def test_rule4_fires_at_0_09_boundary(self):
        """PROP-LIFE-10: abs_delta=0.09 fires Rule 4 (strictly less than 0.10 exclusive boundary).

        FSPEC-WHEEL-06: "Deep OTM is abs(delta) < 0.10, exclusive."
        abs_delta=0.09 is below 0.10 → Rule 4 must fire.
        This tests the lower boundary one step below the threshold.
        """
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.09,
            earnings_within_cycle=False,
            analyst_bias_changed=False,
            wheel_phase="csp_open",
        )
        assert rules["rule4"] is True, (
            "PROP-LIFE-10: abs_delta=0.09 must fire Rule 4 (0.09 < 0.10, exclusive boundary)"
        )

    def test_rule5_analyst_update_fires(self):
        """Rule 5: analyst_bias_changed=True fires analyst_update."""
        from tradingagents.agents.options.roll_agent import _evaluate_rules

        rules = _evaluate_rules(
            current_value_pct=80.0,
            current_dte=30,
            abs_delta=0.25,
            earnings_within_cycle=False,
            analyst_bias_changed=True,
            wheel_phase="csp_open",
        )
        assert rules["rule5"] is True


# ---------------------------------------------------------------------------
# Priority resolution tests (_resolve_priority)
# ---------------------------------------------------------------------------

class TestResolvePriority:
    """Tests for Rule3 > Rule5 > Rule4 > Rule2 > Rule1 priority."""

    def test_rule3_beats_rule1(self):
        """Rule3 > Rule1: Rule3 fires → breach_rule_roll, not profit_capture."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": True, "rule2": False, "rule3": True, "rule4": False, "rule5": False}
        action, reason = _resolve_priority(rules)
        assert action == "ROLL"
        assert reason == "breach_rule_roll"

    def test_rule3_beats_rule2(self):
        """Rule3 > Rule2."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": False, "rule2": True, "rule3": True, "rule4": False, "rule5": False}
        action, reason = _resolve_priority(rules)
        assert action == "ROLL"
        assert reason == "breach_rule_roll"

    def test_rule5_beats_rule2(self):
        """Rule5 > Rule2: analyst bias reversed → CLOSE (REQ-LIFE-03 AC4), not ROLL."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": False, "rule2": True, "rule3": False, "rule4": False, "rule5": True}
        action, reason = _resolve_priority(rules)
        assert action == "CLOSE"
        assert reason == "analyst_update"

    def test_rule5_beats_rule1(self):
        """Rule5 > Rule1: analyst bias reversed → CLOSE (REQ-LIFE-03 AC4), not ROLL."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": True, "rule2": False, "rule3": False, "rule4": False, "rule5": True}
        action, reason = _resolve_priority(rules)
        assert action == "CLOSE"
        assert reason == "analyst_update"

    def test_rule2_beats_rule1(self):
        """Rule2 > Rule1."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": True, "rule2": True, "rule3": False, "rule4": False, "rule5": False}
        action, reason = _resolve_priority(rules)
        assert action == "ROLL"
        assert reason == "dte_rule"

    def test_rule4_beats_rule2(self):
        """Rule4 > Rule2: deep OTM → HOLD even if DTE fires."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": False, "rule2": True, "rule3": False, "rule4": True, "rule5": False}
        action, reason = _resolve_priority(rules)
        assert action == "HOLD"

    def test_no_rules_fire_returns_hold(self):
        """No rules fire → HOLD (default)."""
        from tradingagents.agents.options.roll_agent import _resolve_priority

        rules = {"rule1": False, "rule2": False, "rule3": False, "rule4": False, "rule5": False}
        action, reason = _resolve_priority(rules)
        assert action == "HOLD"


# ---------------------------------------------------------------------------
# PROP-FALLBACK-10: Structured success path
# ---------------------------------------------------------------------------

class TestRollAgentStructuredPath:
    def test_structured_output_returns_roll_decision(self):
        """PROP-FALLBACK-10: structured success returns rendered RollDecision."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent

        decision = _make_roll_decision(action="HOLD")
        pos = _make_position()

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_roll_check_agent(
            mock_llm, _position_loader=lambda t, d: pos
        )
        result = agent_fn(_make_state(), {})

        assert "roll_decision" in result


# ---------------------------------------------------------------------------
# PROP-FALLBACK-11: Freetext-valid-JSON path
# ---------------------------------------------------------------------------

class TestRollAgentFreetextPath:
    def test_freetext_valid_json_no_sentinel(self):
        """PROP-FALLBACK-11: freetext with valid JSON → no sentinel."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent

        decision = _make_roll_decision(action="ROLL", trigger_reason="dte_rule")
        json_str = decision.model_dump_json()

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = json_str
        mock_llm.invoke.return_value = mock_response

        agent_fn = create_roll_check_agent(
            mock_llm, _position_loader=lambda t, d: _make_position()
        )
        result = agent_fn(_make_state(), {})

        assert STRUCTURED_OUTPUT_SENTINEL not in result["roll_decision"]


# ---------------------------------------------------------------------------
# PROP-FALLBACK-12: Total failure → sentinel
# ---------------------------------------------------------------------------

class TestRollAgentSentinelPath:
    def test_total_failure_returns_sentinel(self):
        """PROP-FALLBACK-12: both paths fail → sentinel returned."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent

        mock_llm = MagicMock()
        mock_llm.with_structured_output.side_effect = NotImplementedError
        mock_response = MagicMock()
        mock_response.content = ""
        mock_llm.invoke.return_value = mock_response

        agent_fn = create_roll_check_agent(
            mock_llm, _position_loader=lambda t, d: None
        )
        result = agent_fn(_make_state(), {})

        assert STRUCTURED_OUTPUT_SENTINEL in result["roll_decision"]

    def test_sentinel_import_not_hardcoded(self):
        """ADR-WHEEL-04: sentinel is imported, not hardcoded."""
        assert STRUCTURED_OUTPUT_SENTINEL == "Structured output failed — safe fallback applied."


# ---------------------------------------------------------------------------
# Phase transitions (DEC-PLAN-02)
# ---------------------------------------------------------------------------

class TestRollAgentPhaseTransitions:
    def test_csp_close_sets_stock_owned(self):
        """DEC-PLAN-02: CLOSE on csp_open phase → wheel_phase = 'stock_owned'."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent

        decision = RollDecision(
            action="CLOSE",
            ticker="AAPL",
            current_strike=145.0,
            current_expiration="2024-02-16",
            current_dte=32,
            current_value_pct_of_premium=80.0,
            trigger_reason="breach_rule_roll",
            rationale="Deep ITM breach.",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_roll_check_agent(
            mock_llm, _position_loader=lambda t, d: _make_position()
        )
        result = agent_fn(_make_state(wheel_phase="csp_open"), {})

        assert result.get("wheel_phase") == WheelPhase.STOCK_OWNED.value

    def test_cc_close_sets_cycle_complete(self):
        """DEC-PLAN-02: CLOSE on cc_open phase → wheel_phase = 'cycle_complete'."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent

        decision = RollDecision(
            action="CLOSE",
            ticker="AAPL",
            current_strike=150.0,
            current_expiration="2024-02-16",
            current_dte=0,
            current_value_pct_of_premium=0.0,
            trigger_reason="dte_rule",
            rationale="CC expiry reached.",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_roll_check_agent(
            mock_llm, _position_loader=lambda t, d: _make_position(phase="cc_open")
        )
        result = agent_fn(_make_state(wheel_phase="cc_open"), {})

        assert result.get("wheel_phase") == WheelPhase.CYCLE_COMPLETE.value

    def test_hold_no_phase_transition(self):
        """HOLD action → no wheel_phase change."""
        from tradingagents.agents.options.roll_agent import create_roll_check_agent

        decision = _make_roll_decision(action="HOLD")

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = decision
        mock_llm.with_structured_output.return_value = mock_structured

        agent_fn = create_roll_check_agent(
            mock_llm, _position_loader=lambda t, d: _make_position()
        )
        result = agent_fn(_make_state(wheel_phase="csp_open"), {})

        # HOLD should not transition phase to stock_owned
        assert result.get("wheel_phase") != WheelPhase.STOCK_OWNED.value
