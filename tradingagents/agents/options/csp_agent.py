"""CspAgent — Cash-Secured Put trade recommendation.

Deterministic pre-filter + LLM strike selection, produces CspDecision.
LLM tier: deep_think_llm.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, date
from typing import Any, Callable, Optional

import pandas as pd
from langchain_core.runnables import RunnableConfig

from tradingagents.agents.schemas import (
    CspDecision,
    WheelCandidateReport,
    WheelPhase,
    render_csp_decision,
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

logger = logging.getLogger(__name__)


def _filter_csp_candidates(
    chain_df: pd.DataFrame,
    greeks_lookup: dict,
    earnings_date: Optional[date],
    config: dict,
) -> list[dict]:
    """Apply Filters A, B, C in order. Return list of passing candidate dicts.

    Filter A: target_csp_delta_low <= abs(delta) <= target_csp_delta_high (inclusive)
    Filter B: earnings_date is None OR earnings_date > expiration_date
    Filter C: annualised_yield_pct >= min_annualised_yield_pct

    Progressive relaxation: A+B+C → A+B (yield_filter_relaxed) →
                            A only (earnings_filter_relaxed) → nearest-Delta fallback
    """
    wheel_cfg = config.get("wheel", {})
    delta_low = wheel_cfg.get("target_csp_delta_low", 0.20)
    delta_high = wheel_cfg.get("target_csp_delta_high", 0.30)
    min_yield = wheel_cfg.get("min_annualised_yield_pct", 12.0)

    candidates = []
    for _, row in chain_df.iterrows():
        strike = float(row.get("strike", 0))
        delta = greeks_lookup.get(strike)
        if delta is None:
            continue

        bid = float(row.get("bid", 0))
        ask = float(row.get("ask", 0))
        expiration_str = row.get("expiration", None) or row.get("contractSymbol", "")
        dte = int(row.get("dte", 30))
        mid = (bid + ask) / 2.0

        if dte <= 0:
            continue

        annualised_yield = (mid / strike) * (365 / dte) * 100 if strike > 0 and dte > 0 else 0.0

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
        candidates.append((entry, bool(delta_low <= abs(delta) <= delta_high), earnings_ok, annualised_yield >= min_yield))

    # Full filter A+B+C
    full_pass = [e for e, a, b, c in candidates if a and b and c]
    if full_pass:
        return full_pass

    # Relax C (yield filter)
    ab_pass = [e for e, a, b, c in candidates if a and b]
    if ab_pass:
        for e in ab_pass:
            e["notes"] = "yield_filter_relaxed"
        return ab_pass

    # Relax B (earnings filter)
    a_pass = [e for e, a, b, c in candidates if a]
    if a_pass:
        for e in a_pass:
            e["notes"] = "earnings_filter_relaxed"
        return a_pass

    # Nearest-delta fallback
    if candidates:
        # Sort by closeness to midpoint of target delta range
        target_delta = (delta_low + delta_high) / 2.0
        best = min(candidates, key=lambda x: abs(abs(x[0]["delta"]) - target_delta))
        best[0]["notes"] = f"No strike matches Delta target; nearest available: {best[0]['delta']:.4f}"
        return [best[0]]

    return []


def create_csp_agent(llm: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    """Factory returning the csp_agent node function.

    Args:
        llm: The LLM instance (deep_think_llm).

    Returns:
        Callable that accepts (state, config) and returns a state-update dict.
    """
    structured_llm = bind_structured(llm, CspDecision, "csp_agent")

    def csp_agent(state: AgentState, config: RunnableConfig) -> dict:
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        cfg = get_config()
        wheel_cfg = cfg.get("wheel", {})

        market_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        past_context = state.get("past_context", "")

        # Read WheelCandidateReport if available
        wheel_candidate_json = state.get("wheel_candidate_report")
        strike_range = [0.0, 0.0]
        dte_low = wheel_cfg.get("recommended_dte_low", 28)
        dte_high = wheel_cfg.get("recommended_dte_high", 45)

        if wheel_candidate_json:
            try:
                wcr = WheelCandidateReport.model_validate_json(wheel_candidate_json)
                strike_range = wcr.recommended_strike_range
                dte_low, dte_high = wcr.recommended_dte_range[0], wcr.recommended_dte_range[1]
            except Exception:
                pass

        prompt = f"""You are the CspAgent, selecting the optimal Cash-Secured Put for {ticker}
on {trade_date}.

{f"Past Context:{past_context}" if past_context else ""}

Analyst Context:
{market_report or "(not available)"}
{sentiment_report or "(not available)"}

Wheel Analyst Recommendation:
- Recommended strike range: {strike_range}
- Recommended DTE range: [{dte_low}, {dte_high}] calendar days

## Your Task

1. Call get_options_chain to retrieve available put options for {ticker}
2. Call get_options_greeks for candidate strikes to assess Delta
3. Call get_next_earnings_date to check earnings clearance
4. Select the optimal put strike that:
   - Has Delta in [{wheel_cfg.get("target_csp_delta_low", 0.20)}, {wheel_cfg.get("target_csp_delta_high", 0.30)}]
   - Has DTE in [{dte_low}, {dte_high}] calendar days
   - Does not straddle an earnings date
   - Yields >= {wheel_cfg.get("min_annualised_yield_pct", 12.0)}% annualised

5. Compute deterministic derived fields:
   - mid_premium = (bid + ask) / 2
   - annualised_yield_pct = (mid_premium / strike) * (365 / dte) * 100
   - max_loss = (strike * 100) - (mid_premium * 100)
   - breakeven_price = strike - mid_premium
   - probability_of_profit = 1 - abs(delta)

6. Return CspDecision JSON with all fields filled in.

If no suitable strike is found, return CspDecision with tradeable=False and rejection_reason.
"""

        # --- Three-layer structured output fallback (ADR-WHEEL-04) ---
        decision: Optional[CspDecision] = None
        raw: str = ""

        # Layer 1: bind_structured path
        if structured_llm is not None:
            try:
                result = structured_llm.invoke(prompt)
                if isinstance(result, CspDecision):
                    decision = result
                    raw = render_csp_decision(decision)
                elif result is not None:
                    raw = str(result)
            except Exception as exc:
                logger.warning("csp_agent: structured-output invocation failed (%s); retrying as free text", exc)

        # Layer 2: free-text path
        if not raw:
            try:
                response = llm.invoke(prompt)
                raw = response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.warning("csp_agent: free-text invocation failed (%s)", exc)

        # Layer 2b: try JSON extraction from free-text output
        if decision is None and raw:
            try:
                decision = CspDecision.model_validate_json(raw)
            except Exception:
                pass

        # Layer 3: sentinel on total failure (empty output)
        if decision is None and (not raw or raw.strip() == ""):
            decision = CspDecision(
                tradeable=False,
                ticker=ticker,
                option_type="put",
                strike=0.0, expiration_date="", dte=0, bid=0.0, ask=0.0,
                mid_premium=0.0, delta=0.0, theta=0.0, annualised_yield_pct=0.0,
                max_loss=0.0, breakeven_price=0.0, probability_of_profit=0.0,
                earnings_clear=False,
                rationale=STRUCTURED_OUTPUT_SENTINEL,
            )
            raw = render_csp_decision(decision)

        # Phase transition: if tradeable=True, set wheel_phase = csp_open (DEC-PLAN-02)
        update: dict = {"csp_decision": raw}
        if decision is not None and decision.tradeable:
            update["wheel_phase"] = WheelPhase.CSP_OPEN.value

        return update

    return csp_agent
