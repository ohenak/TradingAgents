"""CcAgent — Covered Call trade recommendation.

Deterministic pre-filter + LLM strike selection, produces CcDecision.
LLM tier: deep_think_llm.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, date
from typing import Any, Callable, Optional

import pandas as pd
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from tradingagents.agents.schemas import (
    CcDecision,
    WheelPhase,
    render_cc_decision,
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
from tradingagents.models.wheel_position import load_latest_open_position

logger = logging.getLogger(__name__)


def _filter_cc_candidates(
    chain_df: pd.DataFrame,
    greeks_lookup: dict,
    earnings_date: Optional[date],
    cost_basis: float,
    config: dict,
) -> list[dict]:
    """Apply Filters A, B, C, D in order. Return list of passing candidate dicts.

    Filter A: strike >= cost_basis (NEVER relaxed — call-away must be profitable)
    Filter B: target_cc_delta_low <= delta <= target_cc_delta_high (inclusive)
    Filter C: earnings_date is None OR earnings_date > expiration_date
    Filter D: annualised_yield_pct >= min_annualised_yield_pct

    Progressive relaxation: A+B+C+D → A+B+C (yield_filter_relaxed) →
                            A+B only (earnings_filter_relaxed) → A-nearest-Delta fallback
    Note: Filter A is never relaxed (strike must be >= cost_basis).
    """
    wheel_cfg = config.get("wheel", {})
    delta_low = wheel_cfg.get("target_cc_delta_low", 0.20)
    delta_high = wheel_cfg.get("target_cc_delta_high", 0.35)
    min_yield = wheel_cfg.get("min_annualised_yield_pct", 12.0)

    candidates = []
    for _, row in chain_df.iterrows():
        strike = float(row.get("strike", 0))
        delta = greeks_lookup.get(strike)
        if delta is None:
            continue

        bid = float(row.get("bid", 0))
        ask = float(row.get("ask", 0))
        dte = int(row.get("dte", 30))
        mid = (bid + ask) / 2.0

        if dte <= 0:
            continue

        # Filter A: strike must be >= cost_basis (never relaxed)
        if strike < cost_basis:
            continue

        annualised_yield = (mid / cost_basis) * (365 / dte) * 100 if cost_basis > 0 and dte > 0 else 0.0

        # Determine if earnings clear
        exp_date = None
        if "expiration_date" in row:
            try:
                exp_date = datetime.strptime(row["expiration_date"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        earnings_ok = (
            earnings_date is None
            or exp_date is None
            or earnings_date > exp_date
        )

        entry = {
            "strike": strike,
            "bid": bid,
            "ask": ask,
            "mid_premium": mid,
            "delta": delta,
            "dte": dte,
            "annualised_yield_pct": annualised_yield,
            "earnings_clear": earnings_ok,
            "expiration_date": row.get("expiration_date", ""),
        }
        candidates.append((
            entry,
            bool(delta_low <= abs(delta) <= delta_high),  # Filter B
            earnings_ok,                                    # Filter C
            annualised_yield >= min_yield,                  # Filter D
        ))

    # Full filter A+B+C+D
    full_pass = [e for e, b, c, d in candidates if b and c and d]
    if full_pass:
        return full_pass

    # Relax D (yield filter)
    bcd_pass = [e for e, b, c, d in candidates if b and c]
    if bcd_pass:
        for e in bcd_pass:
            e["notes"] = "yield_filter_relaxed"
        return bcd_pass

    # Relax C (earnings filter)
    b_pass = [e for e, b, c, d in candidates if b]
    if b_pass:
        for e in b_pass:
            e["notes"] = "earnings_filter_relaxed"
        return b_pass

    # Nearest-delta fallback (Filter A still required — only A-passing candidates used)
    if candidates:
        target_delta = (delta_low + delta_high) / 2.0
        best = min(candidates, key=lambda x: abs(abs(x[0]["delta"]) - target_delta))
        best[0]["notes"] = f"No strike matches Delta target; nearest available: {best[0]['delta']:.4f}"
        return [best[0]]

    return []


def create_cc_agent(
    llm: Any,
    config: Optional[dict] = None,
    *,
    _position_loader: Optional[Callable] = None,
) -> Callable[[AgentState, RunnableConfig], dict]:
    """Factory returning the cc_agent node function.

    Args:
        llm: The LLM instance (deep_think_llm).
        config: Optional config override (uses get_config() if None).
        _position_loader: Injectable seam for tests (ADR-WHEEL-05).
            Signature: (ticker: str, positions_dir: str) -> Optional[WheelPosition]
            Defaults to load_latest_open_position.

    Returns:
        Callable that accepts (state, config) and returns a state-update dict.
    """
    _loader = _position_loader if _position_loader is not None else load_latest_open_position
    structured_llm = bind_structured(llm, CcDecision, "cc_agent")
    # Bind options tools so the LLM can call get_options_chain, get_options_greeks, etc.
    _options_tools = [get_options_chain, get_options_greeks, get_next_earnings_date]
    llm_with_tools = llm.bind_tools(_options_tools)

    def cc_agent(state: AgentState, config: RunnableConfig) -> dict:
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        cfg = get_config()
        wheel_cfg = cfg.get("wheel", {})

        market_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        past_context = state.get("past_context", "")

        # Load the open WheelPosition to get cost basis and assignment price
        positions_dir = wheel_cfg.get("positions_dir", "memory/wheel_positions")
        position = _loader(ticker, positions_dir)

        cost_basis = 0.0
        assigned_at = 0.0
        csp_premium_received = 0.0

        if position is not None:
            assigned_at = position.csp_strike or 0.0
            csp_premium_received = position.csp_premium_received or 0.0
            cost_basis = assigned_at - csp_premium_received

        dte_low = wheel_cfg.get("recommended_dte_low", 28)
        dte_high = wheel_cfg.get("recommended_dte_high", 45)

        prompt = f"""You are the CcAgent, selecting the optimal Covered Call for {ticker}
on {trade_date}.

{f"Past Context:{past_context}" if past_context else ""}

Analyst Context:
{market_report or "(not available)"}
{sentiment_report or "(not available)"}

Position Context:
- Assigned at (CSP strike): {assigned_at}
- CSP premium received: {csp_premium_received}
- Cost basis per share: {cost_basis:.2f} (= assigned_at - csp_premium_received)

## Your Task

1. Call get_options_chain to retrieve available call options for {ticker}
2. Call get_options_greeks for candidate strikes to assess Delta
3. Call get_next_earnings_date to check earnings clearance
4. Select the optimal call strike that:
   - Strike >= cost basis (call-away must be profitable)
   - Has Delta in [{wheel_cfg.get("target_cc_delta_low", 0.20)}, {wheel_cfg.get("target_cc_delta_high", 0.35)}]
   - Has DTE in [{dte_low}, {dte_high}] calendar days
   - Does not straddle an earnings date
   - Yields >= {wheel_cfg.get("min_annualised_yield_pct", 12.0)}% annualised on cost

5. Compute deterministic derived fields:
   - mid_premium = (bid + ask) / 2
   - annualised_yield_on_cost_pct = (mid_premium / cost_basis) * (365 / dte) * 100
   - strike_above_cost_basis = strike >= cost_basis
   - upside_to_strike_pct = (strike - current_price) / current_price * 100

6. Return CcDecision JSON with all fields filled in.

If no suitable strike is found, return CcDecision with tradeable=False and rejection_reason.
If no WheelPosition exists (cost_basis = 0), return tradeable=False with appropriate reason.
"""

        # Tool-call round: check if ToolMessage results are already in state (re-entry after ToolNode).
        from langchain_core.messages import ToolMessage as _ToolMessage
        messages = list(state.get("messages", []))
        has_tool_results = any(isinstance(m, _ToolMessage) for m in messages)

        if not has_tool_results:
            invoke_messages = [HumanMessage(content=prompt)] + messages
            try:
                ai_msg = llm_with_tools.invoke(invoke_messages)
                tool_calls = getattr(ai_msg, "tool_calls", None)
                if isinstance(tool_calls, list) and len(tool_calls) > 0:
                    return {"messages": [ai_msg]}
            except Exception as exc:
                logger.warning("cc_agent: tool-bound invocation failed (%s); proceeding to structured output", exc)

        # --- Three-layer structured output fallback (ADR-WHEEL-04) ---
        decision: Optional[CcDecision] = None
        raw: str = ""

        # Layer 1: bind_structured path
        if structured_llm is not None:
            try:
                result = structured_llm.invoke(prompt)
                if isinstance(result, CcDecision):
                    decision = result
                    raw = render_cc_decision(decision)
                elif result is not None:
                    raw = str(result)
            except Exception as exc:
                logger.warning("cc_agent: structured-output invocation failed (%s); retrying as free text", exc)

        # Layer 2: free-text path
        if not raw:
            try:
                response = llm.invoke(prompt)
                raw = response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.warning("cc_agent: free-text invocation failed (%s)", exc)

        # Layer 2b: try JSON extraction from free-text output
        if decision is None and raw:
            try:
                decision = CcDecision.model_validate_json(raw)
            except Exception:
                pass

        # Layer 3: sentinel on total failure (empty output)
        if decision is None and (not raw or raw.strip() == ""):
            decision = CcDecision(
                tradeable=False,
                ticker=ticker,
                option_type="call",
                strike=0.0, expiration_date="", dte=0, bid=0.0, ask=0.0,
                mid_premium=0.0, delta=0.0, theta=0.0,
                annualised_yield_on_cost_pct=0.0,
                assigned_at=assigned_at,
                cost_basis=cost_basis,
                strike_above_cost_basis=False,
                upside_to_strike_pct=0.0,
                earnings_clear=False,
                rationale=STRUCTURED_OUTPUT_SENTINEL,
            )
            raw = render_cc_decision(decision)

        # Phase transition: if tradeable=True, set wheel_phase = cc_open (DEC-PLAN-02)
        update: dict = {"cc_decision": raw}
        if decision is not None and decision.tradeable:
            update["wheel_phase"] = WheelPhase.CC_OPEN.value

        return update

    return cc_agent
