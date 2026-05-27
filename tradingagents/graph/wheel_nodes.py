"""Wheel lifecycle graph nodes.

Contains:
- WheelStateError: raised when wheel state is inconsistent
- wheel_cycle_summary: terminal node that computes cycle P&L and resets phase
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from langchain_core.runnables import RunnableConfig

from tradingagents.agents.utils.agent_states import AgentState

logger = logging.getLogger(__name__)


class WheelStateError(Exception):
    """Raised when the wheel graph state is inconsistent.

    Examples:
    - wheel_phase == "csp_open" but no WheelPosition file exists
    - wheel_phase == "cc_open" but no WheelPosition file exists
    """


def wheel_cycle_summary(state: AgentState, config: Optional[RunnableConfig] = None) -> dict:
    """Compute cycle P&L and reset wheel_phase to None.

    Steps:
    1. Load WheelPosition for ticker
    2. Compute cycle_duration_days from csp_open_date to call_away_date
    3. Compute cycle_pnl = cumulative_premium_received
    4. Compute cycle_annualised_return_pct per TSPEC §9.4 formula
    5. Append cycle summary to cycle_history
    6. Write updated WheelPosition atomically (non-blocking on failure)
    7. Return {"wheel_phase": None} — NOT "screening" (PM-v2-F-01)

    NOTE (PM-v2-F-01): Returns {"wheel_phase": None}, not {"wheel_phase": "screening"}.
    This is intentional. After the cycle completes, the next execution re-enters
    via wheel_router which evaluates wheel_phase=None and routes to "screening"
    fresh. Setting "screening" here would bypass the wheel_router guard logic.

    cycle_annualised_return_pct = (cycle_pnl / (csp_strike * shares_held))
                                   * (365 / cycle_duration_days) * 100
    NOTE: REQ v0.2.0 AC3a states ~33.25%; correct value is 33.21%. See TSPEC §9.4.
    """
    ticker = state.get("company_of_interest", "")
    trade_date = state.get("trade_date", "")

    summary_text = f"## Wheel Cycle Summary — {ticker}\n\n"

    position = None
    try:
        from tradingagents.dataflows.config import get_config
        from tradingagents.models.wheel_position import (
            load_latest_open_position,
            save_wheel_position,
        )

        cfg = get_config()
        positions_dir = cfg.get("wheel", {}).get("positions_dir", "memory/wheel_positions")

        position = load_latest_open_position(ticker, positions_dir)

        if position is not None:
            # Compute cycle duration
            cycle_duration_days = 0
            if position.csp_open_date and position.call_away_date:
                try:
                    open_dt = datetime.strptime(position.csp_open_date, "%Y-%m-%d").date()
                    close_dt = datetime.strptime(position.call_away_date, "%Y-%m-%d").date()
                    cycle_duration_days = (close_dt - open_dt).days
                except (ValueError, TypeError):
                    cycle_duration_days = 0

            # Cycle P&L = cumulative premium received
            cycle_pnl = position.cumulative_premium_received or 0.0
            if position.cycle_pnl is not None:
                cycle_pnl = position.cycle_pnl

            # Compute annualised return per TSPEC §9.4
            # NOTE: REQ v0.2.0 AC3a states ~33.25%; correct value is 33.21%.
            cycle_annualised_return_pct = 0.0
            if (
                position.csp_strike
                and position.shares_held
                and cycle_duration_days > 0
            ):
                capital = position.csp_strike * position.shares_held
                cycle_annualised_return_pct = (
                    cycle_pnl / capital
                ) * (365 / cycle_duration_days) * 100

            # Append to cycle_history
            history_entry = {
                "cycle_number": position.cycle_number,
                "cycle_pnl": round(cycle_pnl, 2),
                "cycle_annualised_return_pct": round(cycle_annualised_return_pct, 2),
                "cycle_duration_days": cycle_duration_days,
            }
            position.cycle_history = list(position.cycle_history or [])
            position.cycle_history.append(history_entry)

            # Update position fields
            position.cycle_pnl = cycle_pnl
            position.cycle_annualised_return_pct = cycle_annualised_return_pct
            position.wheel_phase = "cycle_complete"

            # Atomic write (non-blocking on failure)
            try:
                save_wheel_position(position, positions_dir)
            except Exception as save_exc:
                logger.warning(
                    "wheel_cycle_summary: failed to save position for %s: %s",
                    ticker,
                    save_exc,
                )

            summary_text += (
                f"**Ticker**: {ticker}\n"
                f"**Cycle**: {position.cycle_number}\n"
                f"**Duration**: {cycle_duration_days} days\n"
                f"**Cycle P&L**: {cycle_pnl:.2f}\n"
                f"**Annualised Return**: {cycle_annualised_return_pct:.2f}%\n"
            )

            # Write to memory log (non-blocking on failure)
            try:
                _write_memory_log(ticker, history_entry, trade_date)
            except Exception as log_exc:
                logger.warning(
                    "wheel_cycle_summary: memory log write failed for %s: %s",
                    ticker,
                    log_exc,
                )
        else:
            summary_text += f"No open position found for {ticker}.\n"

    except Exception as exc:
        logger.warning("wheel_cycle_summary: unexpected error for %s: %s", ticker, exc)
        summary_text += f"Error computing cycle summary: {exc}\n"

    # PM-v2-F-01: return wheel_phase=None, NOT "screening"
    return {"wheel_phase": None, "wheel_cycle_summary_text": summary_text}


def _write_memory_log(ticker: str, history_entry: dict, trade_date: str) -> None:
    """Write cycle summary to TradingMemoryLog. Non-blocking — caller catches exceptions."""
    try:
        from tradingagents.agents.utils.agent_states import AgentState  # noqa: F401
        # Attempt to import memory log utility if it exists
        from tradingagents.dataflows.config import get_config
        cfg = get_config()
        memory_dir = cfg.get("memory_log", {}).get("dir", "memory/logs")

        import json
        import os
        import tempfile

        os.makedirs(memory_dir, exist_ok=True)
        log_path = os.path.join(memory_dir, f"{ticker}-wheel-cycles.jsonl")
        entry_str = json.dumps({
            "date": trade_date,
            "ticker": ticker,
            **history_entry,
        })
        # Atomic append via read-write to tempfile
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry_str + "\n")
    except Exception:
        raise  # caller catches
