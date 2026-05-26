"""WheelAnalyst — five-criterion suitability screening for the wheel strategy.

Produces a WheelCandidateReport with approval/rejection and a recommended
strike range when approved.

LLM tier: deep_think_llm (five-criterion evaluation requires extended reasoning).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig

from tradingagents.agents.schemas import (
    WheelCandidateReport,
    render_wheel_candidate_report,
)
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.options_data_tools import (
    get_iv_metrics,
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


def create_wheel_analyst(llm: Any) -> Callable[[AgentState, RunnableConfig], dict]:
    """Factory returning the wheel_analyst node function.

    Args:
        llm: The LLM instance (deep_think_llm).

    Returns:
        Callable that accepts (state, config) and returns a state-update dict.
    """
    structured_llm = bind_structured(llm, WheelCandidateReport, "wheel_analyst")

    def wheel_analyst(state: AgentState, config: RunnableConfig) -> dict:
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        cfg = get_config()
        wheel_cfg = cfg.get("wheel", {})

        # Context from upstream analyst team
        market_report = state.get("market_report", "")
        sentiment_report = state.get("sentiment_report", "")
        news_report = state.get("news_report", "")
        fundamentals_report = state.get("fundamentals_report", "")
        investment_plan = state.get("investment_plan", "")
        past_context = state.get("past_context", "")

        # Wheel config thresholds for prompt
        min_iv_rank = wheel_cfg.get("min_iv_rank", 25)
        earnings_buffer_days = wheel_cfg.get("earnings_buffer_days", 14)
        max_wheel_stock_price = wheel_cfg.get("max_wheel_stock_price", 500.0)
        min_chain_oi = wheel_cfg.get("min_chain_oi", 100)
        max_chain_spread_pct = wheel_cfg.get("max_chain_spread_pct", 10.0)
        near_the_money_pct = wheel_cfg.get("near_the_money_pct", 0.05)
        dte_low = wheel_cfg.get("recommended_dte_low", 28)
        dte_high = wheel_cfg.get("recommended_dte_high", 45)
        target_csp_delta_low = wheel_cfg.get("target_csp_delta_low", 0.20)
        target_csp_delta_high = wheel_cfg.get("target_csp_delta_high", 0.30)

        # Build options tool list for prompt
        tools = [get_iv_metrics, get_options_chain, get_options_greeks, get_next_earnings_date]

        # Bind tools to the LLM (use the LLM directly here, not the structured version,
        # since tool calling happens in the invocation below)
        llm_with_tools = llm.bind_tools(tools)

        prompt = f"""You are the WheelAnalyst, responsible for evaluating whether {ticker} is
suitable for the wheel options strategy as of {trade_date}.

{f"Past Context:{past_context}" if past_context else ""}

Analyst Reports:
=== Market Report ===
{market_report or "(not available)"}

=== Sentiment Report ===
{sentiment_report or "(not available)"}

=== News Report ===
{news_report or "(not available)"}

=== Fundamentals Report ===
{fundamentals_report or "(not available)"}

=== Investment Plan ===
{investment_plan or "(not available)"}

## Your Task

Evaluate {ticker} against these five criteria IN ORDER (no early exit — evaluate all five):

1. **IV Environment**: iv_rank >= {min_iv_rank} (elevated enough for premium selling)
   - Use get_iv_metrics tool to obtain IV Rank
   - IMPORTANT: If the report contains "IV range is flat — rank set to neutral 50", include
     this note verbatim in the iv_assessment field (ADR-WHEEL-01 disclosure requirement)

2. **Chain Liquidity**: At least one near-the-money strike (within ±{near_the_money_pct*100:.0f}% of spot)
   has OI >= {min_chain_oi} AND bid/ask spread <= {max_chain_spread_pct}% of mid
   - Use get_options_chain tool to fetch the chain

3. **Earnings Clearance**: Next earnings date is at least {earnings_buffer_days} days beyond
   the target expiration ({dte_low}-{dte_high} DTE from today)
   - Use get_next_earnings_date tool

4. **Price Affordability**: Spot price <= ${max_wheel_stock_price}
   (for cash-secured put capital manageability)

5. **Analyst Consensus**: Recommendation from investment_plan is not Sell/Underweight
   - Parse the investment_plan for recommendation; default to Pass if unparseable

## Output Requirements

After calling the data tools, produce a WheelCandidateReport JSON with:
- approved: True if ALL five criteria pass
- rejection_reason: Semicolon-separated list of failed criteria when approved=False
- iv_rank, iv_percentile, iv_environment: from get_iv_metrics output
- iv_assessment: Plain-English summary; MUST surface zero-variance flat-range note if present
  Label this as "Volatility Environment Score (based on 30-day realised volatility)"
- next_earnings_date, earnings_clearance_ok: from get_next_earnings_date output
- liquidity_ok: whether Criterion 2 passed
- analyst_bias: "bullish" (Buy/Overweight), "neutral" (Hold), "bearish" (Sell/Underweight)
- recommended_strike_range: [low_strike, high_strike] anchored to Delta {target_csp_delta_low}–{target_csp_delta_high}
  when approved=True; [0.0, 0.0] when approved=False
- recommended_dte_range: [{dte_low}, {dte_high}]
- rationale: Detailed justification (non-empty even when approved=False)

CRITICAL: All rejections must accumulate — report all failing criteria, not just the first.
"""

        # --- Three-layer structured output fallback (ADR-WHEEL-04) ---
        report = None
        raw: str = ""

        # Layer 1: bind_structured path
        if structured_llm is not None:
            try:
                result = structured_llm.invoke(prompt)
                if isinstance(result, WheelCandidateReport):
                    report = result
                    raw = render_wheel_candidate_report(report)
                elif result is not None:
                    raw = str(result)
            except Exception as exc:
                logger.warning("wheel_analyst: structured-output invocation failed (%s); retrying as free text", exc)

        # Layer 2: free-text path
        if not raw:
            try:
                response = llm.invoke(prompt)
                raw = response.content if hasattr(response, "content") else str(response)
            except Exception as exc:
                logger.warning("wheel_analyst: free-text invocation failed (%s)", exc)

        # Layer 2b: try JSON extraction from free-text output
        if report is None and raw:
            try:
                report = WheelCandidateReport.model_validate_json(raw)
            except Exception:
                pass  # raw may be rendered markdown — valid for state storage

        # Layer 3: sentinel on total failure
        if report is None and (not raw or raw.strip() == ""):
            report = WheelCandidateReport(
                approved=False,
                rejection_reason=STRUCTURED_OUTPUT_SENTINEL,
                iv_rank=0.0,
                iv_percentile=0.0,
                iv_environment="compressed",
                iv_assessment="",
                earnings_clearance_ok=False,
                liquidity_ok=False,
                analyst_bias="neutral",
                recommended_strike_range=[0.0, 0.0],
                recommended_dte_range=[28, 45],
                rationale=STRUCTURED_OUTPUT_SENTINEL,
            )
            raw = render_wheel_candidate_report(report)

        return {"wheel_candidate_report": raw}

    return wheel_analyst
