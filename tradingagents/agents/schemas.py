"""Pydantic schemas used by agents that produce structured output.

The framework's primary artifact is still prose: each agent's natural-language
reasoning is what users read in the saved markdown reports and what the
downstream agents read as context.  Structured output is layered onto the
three decision-making agents (Research Manager, Trader, Portfolio Manager)
so that:

- Their outputs follow consistent section headers across runs and providers
- Each provider's native structured-output mode is used (json_schema for
  OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic)
- Schema field descriptions become the model's output instructions, freeing
  the prompt body to focus on context and the rating-scale guidance
- A render helper turns the parsed Pydantic instance back into the same
  markdown shape the rest of the system already consumes, so display,
  memory log, and saved reports keep working unchanged
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Shared rating types
# ---------------------------------------------------------------------------


class PortfolioRating(str, Enum):
    """5-tier rating used by the Research Manager and Portfolio Manager."""

    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader.

    The Trader's job is to translate the Research Manager's investment plan
    into a concrete transaction proposal: should the desk execute a Buy, a
    Sell, or sit on Hold this round.  Position sizing and the nuanced
    Overweight / Underweight calls happen later at the Portfolio Manager.
    """

    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


# ---------------------------------------------------------------------------
# Research Manager
# ---------------------------------------------------------------------------


class ResearchPlan(BaseModel):
    """Structured investment plan produced by the Research Manager.

    Hand-off to the Trader: the recommendation pins the directional view,
    the rationale captures which side of the bull/bear debate carried the
    argument, and the strategic actions translate that into concrete
    instructions the trader can execute against.
    """

    recommendation: PortfolioRating = Field(
        description=(
            "The investment recommendation. Exactly one of Buy / Overweight / "
            "Hold / Underweight / Sell. Reserve Hold for situations where the "
            "evidence on both sides is genuinely balanced; otherwise commit to "
            "the side with the stronger arguments."
        ),
    )
    rationale: str = Field(
        description=(
            "Conversational summary of the key points from both sides of the "
            "debate, ending with which arguments led to the recommendation. "
            "Speak naturally, as if to a teammate."
        ),
    )
    strategic_actions: str = Field(
        description=(
            "Concrete steps for the trader to implement the recommendation, "
            "including position sizing guidance consistent with the rating."
        ),
    )


def render_research_plan(plan: ResearchPlan) -> str:
    """Render a ResearchPlan to markdown for storage and the trader's prompt context."""
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


# ---------------------------------------------------------------------------
# Trader
# ---------------------------------------------------------------------------


class TraderProposal(BaseModel):
    """Structured transaction proposal produced by the Trader.

    The trader reads the Research Manager's investment plan and the analyst
    reports, then turns them into a concrete transaction: what action to
    take, the reasoning that justifies it, and the practical levels for
    entry, stop-loss, and sizing.
    """

    action: TraderAction = Field(
        description="The transaction direction. Exactly one of Buy / Hold / Sell.",
    )
    reasoning: str = Field(
        description=(
            "The case for this action, anchored in the analysts' reports and "
            "the research plan. Two to four sentences."
        ),
    )
    entry_price: Optional[float] = Field(
        default=None,
        description="Optional entry price target in the instrument's quote currency.",
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description="Optional stop-loss price in the instrument's quote currency.",
    )
    position_sizing: Optional[str] = Field(
        default=None,
        description="Optional sizing guidance, e.g. '5% of portfolio'.",
    )


def render_trader_proposal(proposal: TraderProposal) -> str:
    """Render a TraderProposal to markdown.

    The trailing ``FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`` line is
    preserved for backward compatibility with the analyst stop-signal text
    and any external code that greps for it.
    """
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Portfolio Manager
# ---------------------------------------------------------------------------


class PortfolioDecision(BaseModel):
    """Structured output produced by the Portfolio Manager.

    The model fills every field as part of its primary LLM call; no separate
    extraction pass is required. Field descriptions double as the model's
    output instructions, so the prompt body only needs to convey context and
    the rating-scale guidance.
    """

    rating: PortfolioRating = Field(
        description=(
            "The final position rating. Exactly one of Buy / Overweight / Hold / "
            "Underweight / Sell, picked based on the analysts' debate."
        ),
    )
    executive_summary: str = Field(
        description=(
            "A concise action plan covering entry strategy, position sizing, "
            "key risk levels, and time horizon. Two to four sentences."
        ),
    )
    investment_thesis: str = Field(
        description=(
            "Detailed reasoning anchored in specific evidence from the analysts' "
            "debate. If prior lessons are referenced in the prompt context, "
            "incorporate them; otherwise rely solely on the current analysis."
        ),
    )
    price_target: Optional[float] = Field(
        default=None,
        description="Optional target price in the instrument's quote currency.",
    )
    time_horizon: Optional[str] = Field(
        default=None,
        description="Optional recommended holding period, e.g. '3-6 months'.",
    )


def render_pm_decision(decision: PortfolioDecision) -> str:
    """Render a PortfolioDecision back to the markdown shape the rest of the system expects.

    Memory log, CLI display, and saved report files all read this markdown,
    so the rendered output preserves the exact section headers (``**Rating**``,
    ``**Executive Summary**``, ``**Investment Thesis**``) that downstream
    parsers and the report writers already handle.
    """
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Wheel Options Trading schemas  (Phases 2–4)
# ---------------------------------------------------------------------------


class WheelPhase(str, Enum):
    """Wheel strategy lifecycle phases. str, Enum ensures JSON-serialisability."""

    SCREENING = "screening"
    CSP_OPEN = "csp_open"
    STOCK_OWNED = "stock_owned"
    CC_OPEN = "cc_open"
    CYCLE_COMPLETE = "cycle_complete"


# TriggerReason is a Literal type alias, not an Enum, so it serialises
# as a plain string in all contexts.
TriggerReason = Literal[
    "profit_capture",
    "dte_rule",
    "breach_rule_roll",
    "breach_rule_close",
    "earnings_rule",
    "analyst_update",
]


class WheelCandidateReport(BaseModel):
    """Wheel suitability screening report produced by WheelAnalyst."""

    approved: bool = Field(
        description="True if all five criteria passed and the stock is suitable for the wheel."
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Semicolon-delimited failure reasons when approved=False. Null when approved=True.",
    )
    iv_rank: float = Field(
        description="Realised-vol-based IV Rank in [0, 100]."
    )
    iv_percentile: float = Field(
        description="Fraction of lookback days with lower vol than today, expressed as [0, 100]."
    )
    iv_environment: Literal["elevated", "normal", "compressed"] = Field(
        description="Derived from iv_rank: elevated>=50, normal 25-50, compressed<25."
    )
    iv_assessment: str = Field(
        description="Plain-English summary of the current IV environment."
    )
    next_earnings_date: Optional[str] = Field(
        default=None,
        description="Next earnings date in YYYY-MM-DD format, or None if unavailable.",
    )
    earnings_clearance_ok: bool = Field(
        description="True if next earnings is sufficiently beyond the target expiration."
    )
    liquidity_ok: bool = Field(
        description="True if at least one near-the-money strike meets OI and spread criteria."
    )
    analyst_bias: Literal["bullish", "neutral", "bearish"] = Field(
        description="Derived from the existing investment_plan recommendation field."
    )
    recommended_strike_range: list[float] = Field(
        min_length=2,
        max_length=2,
        description="[low_strike, high_strike] anchored to target Delta bounds. Sentinel [0.0, 0.0] when approved=False.",
    )
    recommended_dte_range: list[int] = Field(
        min_length=2,
        max_length=2,
        description="[dte_low, dte_high] in calendar days from config.",
    )
    rationale: str = Field(
        description="Always-populated rationale string; non-empty even when approved=False."
    )

    @model_validator(mode="after")
    def validate_approved_fields(self) -> "WheelCandidateReport":
        """Enforce schema contract: approved=True requires positive strike range;
        approved=False requires a rejection_reason. (TE-TSPEC-07)"""
        if self.approved:
            if not self.recommended_strike_range or len(self.recommended_strike_range) != 2:
                raise ValueError("approved=True requires recommended_strike_range with 2 elements")
            if any(v <= 0 for v in self.recommended_strike_range):
                raise ValueError("approved=True requires positive strike range values")
        else:
            if not self.rejection_reason:
                raise ValueError("approved=False requires a non-empty rejection_reason")
        return self


class CspDecision(BaseModel):
    """Cash-secured put trade recommendation produced by CspAgent."""

    tradeable: bool = Field(description="True if a viable CSP trade was found.")
    rejection_reason: Optional[str] = Field(default=None)
    ticker: str = Field(description="Equity ticker.")
    option_type: Literal["put"] = Field(default="put")
    strike: float = Field(description="Selected put strike price.")
    expiration_date: str = Field(description="Expiration date in YYYY-MM-DD.")
    dte: int = Field(description="Calendar days to expiration from trade_date.")
    bid: float = Field(description="Put bid price.")
    ask: float = Field(description="Put ask price.")
    mid_premium: float = Field(description="(bid + ask) / 2.")
    delta: float = Field(description="Put delta as a negative value, e.g. -0.25.")
    theta: float = Field(description="Daily theta decay (<=0).")
    annualised_yield_pct: float = Field(
        description="(mid_premium / strike) * (365 / dte) * 100."
    )
    max_loss: float = Field(description="(strike * 100) - (mid_premium * 100) per contract.")
    breakeven_price: float = Field(description="strike - mid_premium.")
    probability_of_profit: float = Field(description="1 - abs(delta).")
    earnings_clear: bool = Field(
        description="True if selected expiration does not straddle an earnings date."
    )
    rationale: str = Field(description="Always-populated rationale string.")


class CcDecision(BaseModel):
    """Covered call trade recommendation produced by CcAgent."""

    tradeable: bool = Field(description="True if a viable CC trade was found.")
    rejection_reason: Optional[str] = Field(default=None)
    ticker: str = Field(description="Equity ticker.")
    option_type: Literal["call"] = Field(default="call")
    strike: float = Field(description="Selected call strike price.")
    expiration_date: str = Field(description="Expiration date in YYYY-MM-DD.")
    dte: int = Field(description="Calendar days to expiration from trade_date.")
    bid: float
    ask: float
    mid_premium: float = Field(description="(bid + ask) / 2.")
    delta: float = Field(description="Call delta as a positive value, e.g. 0.25.")
    theta: float = Field(description="Daily theta (<=0).")
    annualised_yield_on_cost_pct: float = Field(
        description="(mid_premium / cost_basis) * (365 / dte) * 100."
    )
    assigned_at: float = Field(description="The CSP strike from the prior WheelPosition.")
    cost_basis: float = Field(description="assigned_at - csp_premium_received.")
    strike_above_cost_basis: bool = Field(description="Computed: strike >= cost_basis.")
    upside_to_strike_pct: float = Field(
        description="(strike - current_price) / current_price * 100."
    )
    earnings_clear: bool
    rationale: str = Field(description="Always-populated rationale string.")


class RollDecision(BaseModel):
    """Roll/hold/close recommendation produced by RollCheckAgent."""

    action: Literal["HOLD", "ROLL", "CLOSE"] = Field(
        description="Recommended action for the open position."
    )
    ticker: str
    current_strike: float
    current_expiration: str = Field(description="YYYY-MM-DD.")
    current_dte: int = Field(description="Calendar days remaining.")
    current_value_pct_of_premium: float = Field(
        description="(current_contract_value / original_premium_received) * 100, in [0, 100]."
    )
    trigger_reason: TriggerReason = Field(
        description="Which rule fired. One of six Literal values."
    )
    new_strike: Optional[float] = Field(default=None, description="Populated for ROLL action.")
    new_expiration: Optional[str] = Field(default=None, description="YYYY-MM-DD. Populated for ROLL.")
    new_dte: Optional[int] = Field(default=None)
    estimated_debit_or_credit: Optional[float] = Field(
        default=None,
        description="new_mid_premium - current_contract_value. Positive=credit. Populated for ROLL.",
    )
    rationale: str = Field(description="Always-populated rationale string.")


# ---------------------------------------------------------------------------
# Wheel render helpers
# ---------------------------------------------------------------------------

def render_wheel_candidate_report(r: WheelCandidateReport) -> str:
    """Render WheelCandidateReport to markdown string."""
    parts = [
        f"**Approved**: {'Yes' if r.approved else 'No'}",
    ]
    if r.rejection_reason:
        parts.append(f"**Rejection Reason**: {r.rejection_reason}")
    parts.extend([
        f"**IV Rank (Volatility Environment Score, based on 30-day realised volatility)**: {r.iv_rank:.1f}",
        f"**IV Percentile**: {r.iv_percentile:.1f}",
        f"**IV Environment**: {r.iv_environment}",
        f"**IV Assessment**: {r.iv_assessment}",
        f"**Next Earnings Date**: {r.next_earnings_date or 'N/A'}",
        f"**Earnings Clearance**: {'OK' if r.earnings_clearance_ok else 'FAIL'}",
        f"**Liquidity OK**: {r.liquidity_ok}",
        f"**Analyst Bias**: {r.analyst_bias}",
        f"**Recommended Strike Range**: [{r.recommended_strike_range[0]:.2f}, {r.recommended_strike_range[1]:.2f}]",
        f"**Recommended DTE Range**: [{r.recommended_dte_range[0]}, {r.recommended_dte_range[1]}] calendar days",
        f"**Rationale**: {r.rationale}",
    ])
    return "\n".join(parts)


def render_csp_decision(d: CspDecision) -> str:
    """Render CspDecision to markdown string."""
    parts = [
        f"**Tradeable**: {d.tradeable}",
        f"**Ticker**: {d.ticker}",
        f"**Option Type**: {d.option_type}",
        f"**Strike**: {d.strike}",
        f"**Expiration**: {d.expiration_date}",
        f"**DTE**: {d.dte}",
        f"**Bid**: {d.bid}",
        f"**Ask**: {d.ask}",
        f"**Mid Premium**: {d.mid_premium:.2f}",
        f"**Delta**: {d.delta:.4f}",
        f"**Theta (daily)**: {d.theta:.4f}",
        f"**Annualised Yield**: {d.annualised_yield_pct:.2f}%",
        f"**Max Loss**: {d.max_loss:.2f}",
        f"**Breakeven**: {d.breakeven_price:.2f}",
        f"**Probability of Profit**: {d.probability_of_profit:.2%}",
        f"**Earnings Clear**: {d.earnings_clear}",
        f"**Rationale**: {d.rationale}",
    ]
    if d.rejection_reason:
        parts.insert(1, f"**Rejection Reason**: {d.rejection_reason}")
    return "\n".join(parts)


def render_cc_decision(d: CcDecision) -> str:
    """Render CcDecision to markdown string."""
    parts = [
        f"**Tradeable**: {d.tradeable}",
        f"**Ticker**: {d.ticker}",
        f"**Option Type**: {d.option_type}",
        f"**Strike**: {d.strike}",
        f"**Expiration**: {d.expiration_date}",
        f"**DTE**: {d.dte}",
        f"**Bid**: {d.bid}",
        f"**Ask**: {d.ask}",
        f"**Mid Premium**: {d.mid_premium:.2f}",
        f"**Delta**: {d.delta:.4f}",
        f"**Theta (daily)**: {d.theta:.4f}",
        f"**Annualised Yield on Cost**: {d.annualised_yield_on_cost_pct:.2f}%",
        f"**Assigned At**: {d.assigned_at}",
        f"**Cost Basis**: {d.cost_basis:.2f}",
        f"**Strike Above Cost Basis**: {d.strike_above_cost_basis}",
        f"**Upside to Strike**: {d.upside_to_strike_pct:.2f}%",
        f"**Earnings Clear**: {d.earnings_clear}",
        f"**Rationale**: {d.rationale}",
    ]
    if d.rejection_reason:
        parts.insert(1, f"**Rejection Reason**: {d.rejection_reason}")
    return "\n".join(parts)


def render_roll_decision(d: RollDecision) -> str:
    """Render RollDecision to markdown string."""
    parts = [
        f"**Action**: {d.action}",
        f"**Ticker**: {d.ticker}",
        f"**Current Strike**: {d.current_strike}",
        f"**Current Expiration**: {d.current_expiration}",
        f"**Current DTE**: {d.current_dte}",
        f"**Current Value (% of Premium)**: {d.current_value_pct_of_premium:.1f}%",
        f"**Trigger Reason**: {d.trigger_reason}",
    ]
    if d.new_strike is not None:
        parts.append(f"**New Strike**: {d.new_strike}")
    if d.new_expiration is not None:
        parts.append(f"**New Expiration**: {d.new_expiration}")
    if d.new_dte is not None:
        parts.append(f"**New DTE**: {d.new_dte}")
    if d.estimated_debit_or_credit is not None:
        parts.append(f"**Estimated Debit/Credit**: {d.estimated_debit_or_credit:.2f}")
    parts.append(f"**Rationale**: {d.rationale}")
    return "\n".join(parts)
