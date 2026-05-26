"""yfinance-backed options data functions.

Four functions:
- get_options_chain: options chain for a ticker filtered by look-ahead window
- get_iv_metrics: IV Rank / Percentile via 30-day rolling realised volatility
- get_options_greeks: Black-Scholes-Merton greeks for a specific option
- get_next_earnings_date: next earnings date with front-month options cycle comparison
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Literal, Optional

import numpy as np
import yfinance as yf
from scipy.stats import norm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# get_options_chain
# ---------------------------------------------------------------------------

def get_options_chain(
    ticker: str,
    target_date: str,
    expiry_date: Optional[str] = None,
    config: Optional[dict] = None,
) -> str:
    """Fetch the options chain for *ticker* relative to *target_date*.

    Parameters
    ----------
    ticker:       equity ticker symbol (case-insensitive)
    target_date:  reference date in YYYY-MM-DD format
    expiry_date:  optional specific expiry to return (bypasses look-ahead filter)
    config:       config dict; reads config["wheel"]["options_lookforward_days"]

    Returns
    -------
    Multi-section formatted string, one section per expiration.
    """
    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        options_lookforward_days = (config or {}).get("wheel", {}).get(
            "options_lookforward_days", 45
        )
        cutoff = target_dt + timedelta(days=options_lookforward_days)

        tkr = yf.Ticker(ticker.upper())
        available_expirations = tkr.options  # list of date strings

        if not available_expirations:
            return f"No options chain available for {ticker}"

        if expiry_date:
            # Caller requested a specific expiry — return it regardless of window
            expirations_to_fetch = [expiry_date] if expiry_date in available_expirations else []
            if not expirations_to_fetch:
                return f"No options chain available for {ticker}"
        else:
            expirations_to_fetch = [
                e for e in available_expirations
                if target_dt <= datetime.strptime(e, "%Y-%m-%d") <= cutoff
            ]

        if not expirations_to_fetch:
            return f"No options chain available for {ticker}"

        sections = []
        all_empty = True
        for expiry_str in expirations_to_fetch:
            try:
                chain = tkr.option_chain(expiry_str)
                calls_df = chain.calls
                puts_df = chain.puts
            except Exception:
                continue

            keep_cols = ["strike", "bid", "ask", "lastPrice", "volume", "openInterest", "impliedVolatility"]

            def _fmt_df(df, label):
                if df.empty:
                    return f"  {label}: (none)"
                cols = [c for c in keep_cols if c in df.columns]
                return f"  {label}:\n" + df[cols].to_string(index=False)

            if not calls_df.empty or not puts_df.empty:
                all_empty = False

            section = f"=== Expiration: {expiry_str} ===\n"
            section += _fmt_df(puts_df, "Puts") + "\n"
            section += _fmt_df(calls_df, "Calls")
            sections.append(section)

        if all_empty or not sections:
            return f"No options chain available for {ticker}"

        return "\n\n".join(sections)

    except Exception as e:
        return f"Error fetching options chain for {ticker}: {type(e).__name__}"


# ---------------------------------------------------------------------------
# get_iv_metrics
# ---------------------------------------------------------------------------

def get_iv_metrics(
    ticker: str,
    curr_date: str,
    lookback_days: int = 252,
    iv_series: Optional[list[float]] = None,
) -> str:
    """Compute IV Rank and IV Percentile via 30-day rolling realised volatility.

    Parameters
    ----------
    ticker:        equity ticker symbol
    curr_date:     reference date in YYYY-MM-DD format
    lookback_days: number of trading days for the lookback window (default 252)
    iv_series:     test seam — if provided, skip yfinance and use directly

    Returns
    -------
    JSON string with iv_rank, iv_percentile, iv_environment, plus human-readable notes.
    """
    try:
        flat_note: Optional[str] = None
        shortened_note: Optional[str] = None

        # -----------------------------------------------------------------
        # Test seam path
        # -----------------------------------------------------------------
        if iv_series is not None:
            if len(iv_series) == 0:
                return "Provided iv_series is empty"
            rolling_vol_list = iv_series
            current_vol = float(rolling_vol_list[-1])
            max_vol_lookback = float(max(rolling_vol_list))
            min_vol_lookback = float(min(rolling_vol_list))
        else:
            # -----------------------------------------------------------------
            # Production path
            # -----------------------------------------------------------------
            tkr = yf.Ticker(ticker.upper())
            hist = tkr.history(period="max")

            if hist.empty:
                return f"Insufficient OHLCV data for {ticker}"

            # Filter to rows up to curr_date, sort ascending
            curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
            hist.index = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
            hist = hist[hist.index <= curr_dt].sort_index()

            # Take last lookback_days rows
            n_available = len(hist)
            if n_available == 0:
                return f"Insufficient OHLCV data for {ticker}"

            if n_available < lookback_days:
                shortened_note = (
                    f"Lookback shortened to {n_available} trading days "
                    f"(fewer than {lookback_days} available)"
                )
                logger.info(shortened_note)

            hist = hist.tail(lookback_days)
            close = hist["Close"]

            # Compute log returns
            log_returns = np.log(close / close.shift(1)).dropna()

            # 30-day rolling realised vol annualised
            rolling_vol_series = log_returns.rolling(window=30).std() * np.sqrt(252)
            rolling_vol_series = rolling_vol_series.dropna()

            if rolling_vol_series.empty:
                return (
                    f"Insufficient data to compute rolling vol for {ticker} "
                    f"(need >= 31 close prices)"
                )

            current_vol = float(rolling_vol_series.iloc[-1])
            max_vol_lookback = float(rolling_vol_series.max())
            min_vol_lookback = float(rolling_vol_series.min())

            # Guard NaN
            if any(math.isnan(v) for v in (current_vol, max_vol_lookback, min_vol_lookback)):
                return f"IV computation returned NaN for {ticker} — check data quality"

            rolling_vol_list = rolling_vol_series.tolist()

        # -----------------------------------------------------------------
        # Zero-variance guard
        # -----------------------------------------------------------------
        if max_vol_lookback == min_vol_lookback:
            iv_rank = 50.0
            iv_percentile = 50.0
            flat_note = "IV range is flat — rank set to neutral 50"
        else:
            iv_rank = (current_vol - min_vol_lookback) / (max_vol_lookback - min_vol_lookback) * 100
            iv_rank = max(0.0, min(100.0, iv_rank))
            # Strict less-than empirical CDF: approaches but never reaches 100 when current == max
            below_count = sum(1 for v in rolling_vol_list if v < current_vol)
            iv_percentile = below_count / len(rolling_vol_list) * 100
            iv_percentile = max(0.0, min(100.0, iv_percentile))

        # Derive environment
        if iv_rank >= 50:
            iv_environment = "elevated"
        elif iv_rank >= 25:
            iv_environment = "normal"
        else:
            iv_environment = "compressed"

        result = {
            "iv_rank": round(iv_rank, 2),
            "iv_percentile": round(iv_percentile, 2),
            "iv_environment": iv_environment,
            "current_vol": round(current_vol, 6),
            "max_vol_lookback": round(max_vol_lookback, 6),
            "min_vol_lookback": round(min_vol_lookback, 6),
        }

        notes = []
        if flat_note:
            result["note"] = flat_note
            notes.append(flat_note)
        if shortened_note:
            result["lookback_note"] = shortened_note
            notes.append(shortened_note)

        report_parts = [
            f"IV Rank (Volatility Environment Score, based on 30-day realised volatility): {iv_rank:.1f}",
            f"IV Percentile: {iv_percentile:.1f}",
            f"IV Environment: {iv_environment}",
        ]
        if notes:
            report_parts.extend(notes)

        result["report"] = "\n".join(report_parts)
        return json.dumps(result)

    except Exception as e:
        logger.exception("get_iv_metrics failed for %s", ticker)
        return f"Error computing IV metrics for {ticker}: {type(e).__name__}"


# ---------------------------------------------------------------------------
# get_options_greeks  (BSM)
# ---------------------------------------------------------------------------

def get_options_greeks(
    ticker: str,
    curr_date: str,
    expiry_date: str,
    strike: float,
    option_type: Literal["put", "call"],
    config: Optional[dict] = None,
    *,
    _spot_price: Optional[float] = None,       # test seam — bypasses yfinance spot fetch
    _risk_free_rate: Optional[float] = None,   # test seam — bypasses ^IRX fetch
    _sigma: Optional[float] = None,            # test seam — bypasses IV chain fetch
) -> str:
    """Compute Black-Scholes-Merton greeks for a specific option.

    Parameters
    ----------
    ticker:           equity ticker
    curr_date:        current date YYYY-MM-DD
    expiry_date:      option expiry date YYYY-MM-DD
    strike:           option strike price (K)
    option_type:      "put" or "call"
    config:           optional config dict for risk_free_rate overrides
    _spot_price:      test seam — bypasses live spot fetch
    _risk_free_rate:  test seam — bypasses ^IRX fetch
    _sigma:           test seam — bypasses IV fetch

    Returns
    -------
    JSON string with all greeks plus interpretive text.
    """
    try:
        if option_type not in ("put", "call"):
            return f"Invalid option_type '{option_type}': must be 'put' or 'call'"

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        expiry_dt = datetime.strptime(expiry_date, "%Y-%m-%d")
        dte = (expiry_dt - curr_dt).days

        if dte < 0:
            return "Cannot compute Greeks: option has already expired"
        if dte == 0:
            return "Cannot compute Greeks for expired option"

        T = dte / 365.0

        # -----------------------------------------------------------------
        # Fetch spot price
        # -----------------------------------------------------------------
        if _spot_price is not None:
            S = float(_spot_price)
        else:
            try:
                hist = yf.Ticker(ticker.upper()).history(period="1d")
                S = float(hist["Close"].iloc[-1])
            except Exception as e:
                return f"Error fetching spot price for {ticker}: {type(e).__name__}"

        # -----------------------------------------------------------------
        # Fetch risk-free rate
        # -----------------------------------------------------------------
        rate_note = ""
        if _risk_free_rate is not None:
            r = float(_risk_free_rate)
            rate_note = "using injected risk-free rate (test seam)"
        elif config is not None and config.get("wheel", {}).get("risk_free_rate_source") == "static":
            r = float(config["wheel"]["risk_free_rate_static"])
            rate_note = "using static risk-free rate"
        else:
            try:
                irx_hist = yf.Ticker("^IRX").history(period="1d")
                r = float(irx_hist["Close"].iloc[-1]) / 100.0
            except Exception:
                static_fallback = (config or {}).get("wheel", {}).get("risk_free_rate_static", 0.0525)
                r = float(static_fallback)
                rate_note = "using static risk-free rate"

        # -----------------------------------------------------------------
        # Fetch implied volatility (sigma)
        # -----------------------------------------------------------------
        if _sigma is not None:
            sigma = float(_sigma)
        else:
            try:
                chain = yf.Ticker(ticker.upper()).option_chain(expiry_date)
                df = chain.puts if option_type == "put" else chain.calls
                if df.empty:
                    return f"Cannot compute Greeks: no {option_type} chain available for strike {strike}"
                # Find nearest strike within $0.01
                df = df.copy()
                df["_dist"] = (df["strike"] - strike).abs()
                nearest = df.loc[df["_dist"].idxmin()]
                iv_val = float(nearest["impliedVolatility"])
            except Exception as e:
                return f"Error fetching IV for {ticker} {option_type} strike {strike}: {type(e).__name__}"

            if iv_val == 0 or math.isnan(iv_val):
                return f"Cannot compute Greeks: implied volatility is zero for strike {strike}"
            sigma = iv_val

        if sigma == 0 or math.isnan(sigma):
            return f"Cannot compute Greeks: implied volatility is zero for strike {strike}"

        # -----------------------------------------------------------------
        # BSM formulas (canonical Hull 10e)
        # -----------------------------------------------------------------
        K = float(strike)
        sqrt_T = math.sqrt(T)

        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        N = norm.cdf
        Nprime = norm.pdf

        flag = 1.0 if option_type == "call" else -1.0

        delta = flag * N(flag * d1)
        gamma = Nprime(d1) / (S * sigma * sqrt_T)
        vega = S * Nprime(d1) * sqrt_T / 100.0  # per 1% change in vol

        # Theta (unified flag form, verified canonical):
        # θ_annual = (-S*N'(d1)*σ)/(2√T) - flag * r*K*e^(-rT)*N(flag*d2)
        theta_annual = (
            (-S * Nprime(d1) * sigma) / (2.0 * sqrt_T)
            - flag * r * K * math.exp(-r * T) * N(flag * d2)
        )
        theta_daily = theta_annual / 365.0

        result = {
            "delta": round(delta, 6),
            "gamma": round(gamma, 6),
            "theta": round(theta_daily, 6),
            "vega": round(vega, 6),
            "d1": round(d1, 6),
            "d2": round(d2, 6),
            "spot": round(S, 4),
            "strike": round(K, 4),
            "sigma": round(sigma, 6),
            "risk_free_rate": round(r, 6),
            "T": round(T, 6),
            "dte": dte,
            "option_type": option_type,
            "ticker": ticker.upper(),
        }
        if rate_note:
            result["rate_note"] = rate_note

        # Interpretive text
        itm_pct = abs(delta) * 100
        result["interpretation"] = (
            f"Delta {delta:.4f} — this strike is approximately {itm_pct:.0f}% likely to be "
            f"in-the-money at expiration. "
            f"Gamma {gamma:.4f} — rate of delta change per $1 move in underlying. "
            f"Theta {theta_daily:.4f} — daily time decay. "
            f"Vega {vega:.4f} — premium change per 1% vol move."
        )
        if rate_note:
            result["interpretation"] += f" ({rate_note})"

        return json.dumps(result)

    except Exception as e:
        logger.exception("get_options_greeks failed for %s %s strike %s", ticker, option_type, strike)
        return f"Error computing Greeks for {ticker} {option_type} strike {strike}: {type(e).__name__}"


# ---------------------------------------------------------------------------
# get_next_earnings_date
# ---------------------------------------------------------------------------

def get_next_earnings_date(
    ticker: str,
    curr_date: str,
) -> str:
    """Fetch the next earnings date and compare with the front-month options expiry.

    Parameters
    ----------
    ticker:    equity ticker symbol
    curr_date: reference date YYYY-MM-DD

    Returns
    -------
    Formatted string with next earnings date, days until, and within_options_cycle flag.
    """
    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d").date()
        tkr = yf.Ticker(ticker.upper())
        calendar = tkr.calendar

        # calendar may be a DataFrame or dict depending on yfinance version
        earnings_date = None
        if calendar is not None:
            if hasattr(calendar, "columns"):
                # DataFrame form — look for "Earnings Date" column or index
                if "Earnings Date" in calendar.columns:
                    dates = calendar["Earnings Date"].dropna().tolist()
                elif "Earnings Date" in calendar.index:
                    dates = calendar.loc["Earnings Date"].dropna().tolist()
                else:
                    dates = []
                # Normalise to date objects
                for d in dates:
                    candidate = d.date() if hasattr(d, "date") else d
                    if hasattr(candidate, "year") and candidate > curr_dt:
                        earnings_date = candidate
                        break
            elif isinstance(calendar, dict):
                raw = calendar.get("Earnings Date", [])
                if not isinstance(raw, list):
                    raw = [raw]
                for d in raw:
                    candidate = d.date() if hasattr(d, "date") else d
                    if hasattr(candidate, "year") and candidate > curr_dt:
                        earnings_date = candidate
                        break

        if earnings_date is None:
            return f"No upcoming earnings date available for {ticker}"

        days_until = (earnings_date - curr_dt).days

        # Compute front-month expiry (smallest expiry string > curr_date)
        available_expirations = tkr.options or []
        future_expirations = [e for e in available_expirations if e > curr_date]
        front_month_expiry = min(future_expirations) if future_expirations else None

        # String comparison works here because yfinance returns YYYY-MM-DD strings
        within_options_cycle = (
            front_month_expiry is not None
            and earnings_date <= datetime.strptime(front_month_expiry, "%Y-%m-%d").date()
        )

        earnings_date_str = earnings_date.strftime("%Y-%m-%d")
        output = (
            f"Next earnings date for {ticker}: {earnings_date_str}\n"
            f"Days until earnings: {days_until}\n"
            f"Within options cycle: {within_options_cycle}"
        )
        if front_month_expiry:
            output += f"\nFront-month expiry: {front_month_expiry}"

        return output

    except Exception:
        logger.exception("get_next_earnings_date failed for %s", ticker)
        return f"No upcoming earnings date available for {ticker}"
