from __future__ import annotations

from typing import Callable, Optional

from langchain_core.messages import HumanMessage, RemoveMessage

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Applied to every agent whose output reaches the saved report —
    analysts, researchers, debaters, research manager, trader, and
    portfolio manager — so a non-English run produces a fully localized
    report rather than a mix of languages.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str, asset_type: str = "stock") -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    instrument_label = "asset" if asset_type == "crypto" else "instrument"
    extra_hint = (
        " Treat it as a crypto asset rather than a company, and do not assume company fundamentals are available."
        if asset_type == "crypto"
        else ""
    )
    return (
        f"The {instrument_label} to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`, `-USD`)."
        + extra_hint
    )

def _build_options_context(
    state,
    *,
    _position_loader: Optional[Callable] = None,
) -> str:
    """Build options context string for injection into debate agent prompts.

    When wheel_phase is None (equity-only path), returns empty string so the
    debate prompt is completely unchanged (REQ-NFR-01 backward compatibility).

    When wheel_phase is set, injects a structured block with:
    - CspDecision fields: mid_premium, probability_of_profit, max_loss,
      breakeven_price, earnings_clear
    - CcDecision fields: mid_premium, upside_to_strike_pct, cost_basis,
      earnings_clear

    Also injects prior-cycle performance when WheelPosition.cycle_history
    contains at least one completed cycle (REQ-LIFE-05 AC3).

    Args:
        state: AgentState dict.
        _position_loader: Injectable seam for tests (ADR-WHEEL-05).
            Defaults to load_latest_open_position.

    Returns:
        Empty string when wheel_phase is None; formatted options context otherwise.
    """
    wheel_phase = state.get("wheel_phase")
    if not wheel_phase:
        return ""

    # Late imports to avoid circular dependencies
    from tradingagents.agents.schemas import CspDecision, CcDecision
    from tradingagents.dataflows.config import get_config

    cfg = get_config()
    wheel_cfg = cfg.get("wheel", {})
    ticker = state.get("company_of_interest", "")

    sections = ["\n## Options Position Context\n"]

    # CSP Decision context
    csp_raw = state.get("csp_decision")
    if csp_raw:
        try:
            csp = CspDecision.model_validate_json(csp_raw)
            if csp.tradeable:
                sections.append(
                    f"**Open CSP Position:**\n"
                    f"- Strike: {csp.strike}\n"
                    f"- Expiration: {csp.expiration_date} (DTE: {csp.dte})\n"
                    f"- Mid Premium: {csp.mid_premium:.2f}\n"
                    f"- Probability of Profit: {csp.probability_of_profit:.2%}\n"
                    f"- Max Loss: {csp.max_loss:.2f}\n"
                    f"- Breakeven Price: {csp.breakeven_price:.2f}\n"
                    f"- Earnings Clear: {csp.earnings_clear}\n"
                )
        except Exception:
            pass

    # CC Decision context
    cc_raw = state.get("cc_decision")
    if cc_raw:
        try:
            cc = CcDecision.model_validate_json(cc_raw)
            if cc.tradeable:
                sections.append(
                    f"**Open Covered Call Position:**\n"
                    f"- Strike: {cc.strike}\n"
                    f"- Expiration: {cc.expiration_date} (DTE: {cc.dte})\n"
                    f"- Mid Premium: {cc.mid_premium:.2f}\n"
                    f"- Cost Basis: {cc.cost_basis:.2f}\n"
                    f"- Upside to Strike: {cc.upside_to_strike_pct:.2f}%\n"
                    f"- Earnings Clear: {cc.earnings_clear}\n"
                )
        except Exception:
            pass

    # Past-cycle performance injection (REQ-LIFE-05 AC3)
    if _position_loader is not None or True:
        loader = _position_loader
        if loader is None:
            try:
                from tradingagents.models.wheel_position import load_latest_open_position
                loader = load_latest_open_position
            except Exception:
                loader = None

        if loader is not None:
            try:
                positions_dir = wheel_cfg.get("positions_dir", "memory/wheel_positions")
                position = loader(ticker, positions_dir)
                if position is not None and position.cycle_history:
                    past_lines = ["**Past Cycle Performance:**"]
                    for entry in position.cycle_history:
                        n = entry.get("cycle_number", "?")
                        pnl = entry.get("cycle_pnl", 0.0)
                        ann_ret = entry.get("cycle_annualised_return_pct", 0.0)
                        past_lines.append(
                            f"- Prior cycle #{n}: P&L={pnl:.2f}, "
                            f"Annualised return={ann_ret:.2f}%"
                        )
                    sections.append("\n".join(past_lines) + "\n")
            except Exception:
                pass

    if len(sections) <= 1:
        # Only the header was added — no meaningful content
        return ""

    return "\n".join(sections)


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
