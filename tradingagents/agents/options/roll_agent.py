"""RollCheckAgent — Roll / Hold / Close recommendation for open wheel positions.

Evaluates five rules (all evaluated, no early exit). Priority resolution:
  Rule3 > Rule5 > Rule4 > Rule2 > Rule1

LLM tier: quick_think_llm.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable, Optional

from langchain_core.runnables import RunnableConfig

from tradingagents.agents.schemas import (
    RollDecision,
    WheelPhase,
    render_roll_decision,
)
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.options_data_tools import (
    get_next_earnings_date,
    get_options_chain,
    get_options_greeks,
)
from tradingagents.agents.utils.structured import (
    STRUCTURED_OUTPUT_SENTINEL,
    bind_structured,
    invoke_structured_or_freetext,
)
from tradingagents.dataflows.config import get_config
from tradingagents.models.wheel_position import load_latest_open_position, save_wheel_position

logger = logging.getLogger(__name__)


def _derive_analyst_bias(investment_plan: str) -> str:
    """Derive analyst bias from investment_plan text.

    Returns 'bullish', 'bearish', or 'neutral'.
    Keyword mapping:
      bullish: buy, accumulate, overweight, strong buy, long
      bearish: sell, underweight, reduce, avoid, short
      neutral: hold, neutral, market perform, equal weight (or no keywords)
    """
    plan_lower = (investment_plan or "").lower()
    bullish_kw = ("buy", "accumulate", "overweight", "strong buy", "long")
    bearish_kw = ("sell", "underweight", "reduce", "avoid", "short")

    if any(kw in plan_lower for kw in bearish_kw):
        return "bearish"
    if any(kw in plan_lower for kw in bullish_kw):
        return "bullish"
    return "neutral"


def _evaluate_rules(
    current_value_pct: float,
    current_dte: int,
    abs_delta: float,
    earnings_within_cycle: bool,
    analyst_bias_changed: bool,
    wheel_phase: str,
    take_profit_pct: float = 50.0,
    dte_to_roll: int = 21,
) -> dict:
    """Evaluate all five rules and return a dict of which rules fire.

    Rules:
        Rule1: current_value_pct <= (100 - take_profit_pct) → profit_capture → HOLD
               (50% profit target; action=HOLD per REQ-LIFE-03 AC1)
        Rule2: current_dte <= dte_to_roll → dte_rule → ROLL
        Rule3a: abs_delta > 0.85 AND wheel_phase == "csp_open"
                AND current_value_pct >= 50 → breach_rule_roll → ROLL
                (REQ-LIFE-03 AC3a: position retains value; roll to manage assignment risk)
        Rule3b: abs_delta > 0.85 AND wheel_phase == "csp_open"
                AND current_value_pct < 50 → breach_rule_close → CLOSE
                (REQ-LIFE-03 AC3b: deep loss; close to cap further losses)
        Rule4: abs_delta < 0.10 → deep_OTM exclusive boundary → HOLD
               (deep OTM, very far from strike; keep collecting theta)
        Rule5: analyst_bias changed to bearish → analyst_update → CLOSE

    Priority: Rule3 > Rule5 > Rule4 > Rule2 > Rule1
    (Rule3b takes absolute priority over Rule3a within Rule3 tier)
    """
    rules = {}
    rules["rule1"] = current_value_pct <= (100.0 - take_profit_pct)
    rules["rule2"] = current_dte <= dte_to_roll
    # Rule3 is CSP-only: split by current_value_pct to distinguish ROLL vs CLOSE
    csp_breach = abs_delta > 0.85 and wheel_phase == WheelPhase.CSP_OPEN.value
    rules["rule3_roll"] = csp_breach and current_value_pct >= 50.0
    rules["rule3_close"] = csp_breach and current_value_pct < 50.0
    # Backward-compat alias: rule3 is True if either sub-rule fires
    rules["rule3"] = csp_breach
    rules["rule4"] = abs_delta < 0.10
    rules["rule5"] = analyst_bias_changed
    return rules


def _resolve_priority(rules: dict) -> tuple[str, str]:
    """Resolve rule priority to (action, trigger_reason).

    Priority: Rule3 > Rule5 > Rule4 > Rule2 > Rule1
    Within Rule3: breach_rule_close (AC3b, deep loss) supersedes breach_rule_roll (AC3a).
    """
    if rules.get("rule3_close"):
        return ("CLOSE", "breach_rule_close")
    if rules.get("rule3_roll"):
        return ("ROLL", "breach_rule_roll")
    # Backward-compat: if rule3 fires without sub-keys (legacy callers), emit roll
    if rules.get("rule3") and not rules.get("rule3_roll") and not rules.get("rule3_close"):
        return ("ROLL", "breach_rule_roll")
    if rules.get("rule5"):
        return ("CLOSE", "analyst_update")  # REQ-LIFE-03 AC4: bias reversal → CLOSE, not ROLL
    if rules.get("rule4"):
        return ("HOLD", "profit_capture")  # deep OTM: collect theta, return HOLD
    if rules.get("rule2"):
        return ("ROLL", "dte_rule")
    if rules.get("rule1"):
        return ("HOLD", "profit_capture")
    return ("HOLD", "profit_capture")  # default: hold


def create_roll_check_agent(
    llm: Any,
    position_store_dir: Optional[str] = None,
    *,
    _position_loader: Optional[Callable] = None,
) -> Callable[[AgentState, RunnableConfig], dict]:
    """Factory returning the roll_check_agent node function.

    Args:
        llm: The LLM instance (quick_think_llm).
        position_store_dir: Override for position storage directory.
        _position_loader: Injectable seam for tests (ADR-WHEEL-05).
            Defaults to load_latest_open_position.

    Returns:
        Callable that accepts (state, config) and returns a state-update dict.
    """
    _loader = _position_loader if _position_loader is not None else load_latest_open_position
    structured_llm = bind_structured(llm, RollDecision, "roll_check_agent")

    def roll_check_agent(state: AgentState, config: RunnableConfig) -> dict:
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        cfg = get_config()
        wheel_cfg = cfg.get("wheel", {})
        wheel_phase = state.get("wheel_phase", "")

        # Resolve positions dir
        pos_dir = position_store_dir or wheel_cfg.get("positions_dir", "memory/wheel_positions")
        position = _loader(ticker, pos_dir)

        take_profit_pct = wheel_cfg.get("take_profit_pct", 50.0)
        dte_to_roll = wheel_cfg.get("dte_to_roll", 21)
        dte_low = wheel_cfg.get("recommended_dte_low", 28)
        dte_high = wheel_cfg.get("recommended_dte_high", 45)

        # Extract position fields
        current_strike = 0.0
        current_expiration = ""
        current_dte = 0
        prior_analyst_bias = None

        if position is not None:
            if wheel_phase == WheelPhase.CSP_OPEN.value:
                current_strike = position.csp_strike or 0.0
                current_expiration = position.csp_expiration or ""
            elif wheel_phase == WheelPhase.CC_OPEN.value:
                current_strike = position.cc_strike or 0.0
                current_expiration = position.cc_expiration or ""
            prior_analyst_bias = position.prior_analyst_bias

            # Compute DTE
            if current_expiration:
                try:
                    exp_dt = datetime.strptime(current_expiration, "%Y-%m-%d").date()
                    trade_dt = datetime.strptime(trade_date, "%Y-%m-%d").date() if isinstance(trade_date, str) else trade_date
                    current_dte = (exp_dt - trade_dt).days
                except (ValueError, TypeError):
                    current_dte = 0

        investment_plan = state.get("investment_plan", "")

        # Check if analyst bias changed to bearish (S1: use _derive_analyst_bias for full keyword set)
        current_bias = _derive_analyst_bias(investment_plan)
        analyst_bias_changed = (
            prior_analyst_bias is not None
            and prior_analyst_bias == "bullish"
            and current_bias == "bearish"
        )

        prompt = f"""You are the RollCheckAgent, evaluating the open {wheel_phase or "wheel"} position for {ticker}
on {trade_date}.

Position:
- Ticker: {ticker}
- Phase: {wheel_phase}
- Current Strike: {current_strike}
- Current Expiration: {current_expiration}
- Current DTE: {current_dte}
- Prior Analyst Bias: {prior_analyst_bias or "(not available)"}

Investment Plan (current):
{investment_plan or "(not available)"}

## Your Task

Evaluate ALL FIVE rules (no early exit):

Rule 1 (Profit Capture): If current contract value <= {100.0 - take_profit_pct:.0f}% of original premium
   → trigger: profit_capture, action: HOLD

Rule 2 (DTE Rule): If current DTE <= {dte_to_roll} days
   → trigger: dte_rule, action: ROLL to [{dte_low}, {dte_high}] DTE expiry

Rule 3 (Breach — CSP only): If abs(delta) > 0.85 AND wheel_phase == "csp_open"
   Sub-case 3a (breach_rule_roll): current option value >= 50% of premium received
   → trigger: breach_rule_roll, action: ROLL (position retains value; manage assignment risk — REQ-LIFE-03 AC3a)
   Sub-case 3b (breach_rule_close): current option value < 50% of premium received
   → trigger: breach_rule_close, action: CLOSE (deep loss; cap further losses — REQ-LIFE-03 AC3b)

Rule 4 (Deep OTM): If abs(delta) < 0.10
   → trigger: profit_capture, action: HOLD (collect theta, very far OTM)

Rule 5 (Analyst Update): If analyst bias changed from non-bearish to bearish
   → trigger: analyst_update, action: CLOSE (exit position — REQ-LIFE-03 AC4)

Priority when multiple rules fire: Rule3 > Rule5 > Rule4 > Rule2 > Rule1

1. Call get_options_greeks to obtain current delta for the open position
2. Obtain current market value of the contract
3. Evaluate all five rules
4. Apply priority resolution
5. For ROLL action: use get_options_chain to identify the best roll target
6. Return RollDecision JSON

For ROLL: populate new_strike, new_expiration, new_dte, estimated_debit_or_credit.
"""

        # --- Three-layer structured output fallback (ADR-WHEEL-04) ---
        decision: Optional[RollDecision] = None
        raw: str = ""

        # Layer 1: bind_structured path
        if structured_llm is not None:
            try:
                result = structured_llm.invoke(prompt)
                if isinstance(result, RollDecision):
                    decision = result
                    raw = render_roll_decision(decision)
                elif result is not None:
                    raw = str(result)
            except Exception as exc:
                logger.warning("roll_check_agent: structured-output invocation failed (%s); retrying as free text", exc)

        # Layer 2: free-text path
        if not raw:
            try:
                response = llm.invoke(prompt)
                raw = response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.warning("roll_check_agent: free-text invocation failed (%s)", exc)

        # Layer 2b: try JSON extraction from free-text output
        if decision is None and raw:
            try:
                decision = RollDecision.model_validate_json(raw)
            except Exception:
                pass

        # Layer 3: sentinel on total failure (empty output)
        if decision is None and (not raw or raw.strip() == ""):
            decision = RollDecision(
                action="HOLD",
                ticker=ticker,
                current_strike=current_strike,
                current_expiration=current_expiration,
                current_dte=current_dte,
                current_value_pct_of_premium=100.0,
                trigger_reason="profit_capture",
                rationale=STRUCTURED_OUTPUT_SENTINEL,
            )
            raw = render_roll_decision(decision)

        # C2: Apply deterministic rule override — deterministic rules take precedence over LLM.
        # Only override when at least one rule actually fires (any rule is True).
        # When no rule fires, the LLM's decision stands (default HOLD from _resolve_priority
        # is not a "firing" — it's just the safe default).
        if decision is not None:
            # Compute position-level inputs for rule evaluation
            current_value_pct = getattr(decision, "current_value_pct_of_premium", 100.0) or 100.0
            current_dte_val = getattr(decision, "current_dte", current_dte) or current_dte
            # delta is not available without tool calls; use safe default 0.25 (normal range).
            # Rules 3 (>0.85) and 4 (<0.10) won't fire at 0.25, which is the correct fallback.
            abs_delta_val = abs(getattr(decision, "current_delta", 0.25) or 0.25)

            det_rules = _evaluate_rules(
                current_value_pct=current_value_pct,
                current_dte=current_dte_val,
                abs_delta=abs_delta_val,
                earnings_within_cycle=False,
                analyst_bias_changed=analyst_bias_changed,
                wheel_phase=wheel_phase,
                take_profit_pct=take_profit_pct,
                dte_to_roll=dte_to_roll,
            )
            # Only override if at least one deterministic rule actually fired
            any_rule_fired = any(det_rules.get(k) for k in ("rule1", "rule2", "rule3", "rule3_roll", "rule3_close", "rule4", "rule5"))
            if any_rule_fired:
                det_action, det_trigger = _resolve_priority(det_rules)
                # Never downgrade a CLOSE to ROLL: if the LLM says CLOSE and the deterministic
                # system says ROLL (e.g. due to Rule 2 at DTE=0 / expiry), keep CLOSE.
                # CLOSE is always valid and deterministic ROLL at expiry would be operationally wrong.
                should_override = (
                    det_action != decision.action or det_trigger != decision.trigger_reason
                ) and not (decision.action == "CLOSE" and det_action == "ROLL")
                if should_override:
                    logger.debug(
                        "roll_check_agent: deterministic override LLM action=%s/trigger=%s → %s/%s",
                        decision.action, decision.trigger_reason, det_action, det_trigger,
                    )
                    decision = decision.model_copy(update={
                        "action": det_action,
                        "trigger_reason": det_trigger,
                    })
                    raw = render_roll_decision(decision)

        # Persist prior_analyst_bias to WheelPosition (TSPEC §5.4)
        if position is not None:
            new_bias = _derive_analyst_bias(investment_plan)
            position.prior_analyst_bias = new_bias
            try:
                save_wheel_position(position, pos_dir)
            except Exception as exc:
                logger.warning("roll_check_agent: failed to persist prior_analyst_bias (%s)", exc)

        # Phase transitions based on RollDecision (DEC-PLAN-02)
        update: dict = {"roll_decision": raw}

        if decision is not None and decision.action == "CLOSE":
            if wheel_phase == WheelPhase.CSP_OPEN.value:
                # B1: distinguish trigger_reason to route correctly
                if decision.trigger_reason in ("breach_rule_close", "analyst_update"):
                    # Buying back the put to exit — no stock received
                    update["wheel_phase"] = WheelPhase.CYCLE_COMPLETE.value
                else:
                    # Manual assignment path (e.g. put exercised, stock received)
                    update["wheel_phase"] = WheelPhase.STOCK_OWNED.value
            elif wheel_phase == WheelPhase.CC_OPEN.value:
                # CC called away
                update["wheel_phase"] = WheelPhase.CYCLE_COMPLETE.value

        return update

    return roll_check_agent
