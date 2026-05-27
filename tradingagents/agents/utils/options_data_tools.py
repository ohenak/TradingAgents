"""LangChain @tool wrappers for the four options data functions.

All calls route through interface.route_to_vendor().
Test-seam parameters (iv_series, _spot_price, _risk_free_rate, _sigma) are
NOT exposed in any tool signature — they are only accessible on the raw
functions in y_finance_options.py.
"""
from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_options_chain(
    ticker: str,
    target_date: str,
    expiry_date: Optional[str] = None,
) -> str:
    """Retrieve options chain for a ticker. Returns puts and calls with
    strike, bid, ask, volume, open interest, and implied volatility.

    Parameters
    ----------
    ticker:      equity ticker symbol
    target_date: reference date in YYYY-MM-DD format
    expiry_date: optional specific expiration date to retrieve
    """
    try:
        return route_to_vendor("get_options_chain", ticker, target_date, expiry_date)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"


@tool
def get_iv_metrics(
    ticker: str,
    curr_date: str,
    lookback_days: int = 252,
) -> str:
    """Retrieve IV Rank, IV Percentile, and IV Environment for a ticker.

    Uses 30-day rolling realised volatility as a proxy for implied volatility.
    Returns iv_rank (0-100), iv_percentile (0-100), and an environment label
    (elevated / normal / compressed).

    Parameters
    ----------
    ticker:        equity ticker symbol
    curr_date:     reference date in YYYY-MM-DD format
    lookback_days: number of trading days for the lookback window (default 252)
    """
    try:
        return route_to_vendor("get_iv_metrics", ticker, curr_date, lookback_days)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"


@tool
def get_options_greeks(
    ticker: str,
    curr_date: str,
    expiry_date: str,
    strike: float,
    option_type: str,
) -> str:
    """Compute Black-Scholes-Merton greeks for a specific option contract.

    Returns delta, gamma, theta (daily), vega, d1, d2, and plain-English
    interpretations of each greek.

    Parameters
    ----------
    ticker:       equity ticker symbol
    curr_date:    current date in YYYY-MM-DD format
    expiry_date:  option expiration date in YYYY-MM-DD format
    strike:       option strike price
    option_type:  "put" or "call"
    """
    try:
        return route_to_vendor(
            "get_options_greeks", ticker, curr_date, expiry_date, strike, option_type
        )
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"


@tool
def get_next_earnings_date(
    ticker: str,
    curr_date: str,
) -> str:
    """Retrieve the next earnings date for a ticker and determine whether it
    falls within the front-month options cycle.

    Returns next earnings date, days until earnings, and whether the earnings
    date is within the front-month options expiration cycle.

    Parameters
    ----------
    ticker:    equity ticker symbol
    curr_date: reference date in YYYY-MM-DD format
    """
    try:
        return route_to_vendor("get_next_earnings_date", ticker, curr_date)
    except (ValueError, RuntimeError) as e:
        return f"Options data tool error: {e}"
