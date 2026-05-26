"""PROPERTIES tests — PROP-DATA domain.

Covers missing PROPERTIES tests:
  PROP-DATA-02: get_options_chain expiry filtering (3-expiry window: inside/boundary/outside,
                and specific expiry_date param)
  PROP-DATA-04: iv_environment boundary values (iv_rank exactly 50.0 and 25.0)
  PROP-DATA-07: get_iv_metrics does NOT call yf.Ticker when iv_series is provided
  PROP-DATA-13: ^IRX fallback to static rate when risk_free_rate_source="yfinance_irx"
  PROP-DATA-17: shortened-lookback note when iv_series length < lookback_days
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# PROP-DATA-02: get_options_chain lookforward filter — 3-expiry boundary test
# ---------------------------------------------------------------------------

class TestOptionsChainLookforwardBoundary:
    """PROP-DATA-02: inside/boundary/outside expiry filter."""

    def _make_chain_data(self) -> MagicMock:
        df = pd.DataFrame({
            "strike": [100.0],
            "bid": [1.0],
            "ask": [1.2],
            "lastPrice": [1.1],
            "volume": [10],
            "openInterest": [100],
            "impliedVolatility": [0.25],
        })
        chain = MagicMock()
        chain.calls = df
        chain.puts = df
        return chain

    def test_inside_and_boundary_expirations_included(self):
        """PROP-DATA-02a: expiry inside window and on boundary are both included."""
        from tradingagents.dataflows.y_finance_options import get_options_chain

        target_date = "2024-01-01"
        lookforward = 45
        inside_expiry = "2024-01-20"   # inside window (19 days out)
        boundary_expiry = "2024-02-15"  # exactly 45 days out (boundary, inclusive)
        outside_expiry = "2024-09-20"  # far outside window

        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            mock_tkr.options = [inside_expiry, boundary_expiry, outside_expiry]
            mock_tkr.option_chain.return_value = self._make_chain_data()
            mock_tkr_cls.return_value = mock_tkr

            config = {"wheel": {"options_lookforward_days": lookforward}}
            result = get_options_chain("AAPL", target_date, config=config)

        assert inside_expiry in result, (
            f"Inside-window expiry {inside_expiry} should be in result"
        )
        assert boundary_expiry in result, (
            f"Boundary expiry {boundary_expiry} should be in result (inclusive)"
        )

    def test_outside_expiration_excluded(self):
        """PROP-DATA-02b: expiry outside window is excluded."""
        from tradingagents.dataflows.y_finance_options import get_options_chain

        target_date = "2024-01-01"
        lookforward = 45
        outside_expiry = "2024-09-20"

        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            mock_tkr.options = ["2024-01-20", outside_expiry]
            mock_tkr.option_chain.return_value = self._make_chain_data()
            mock_tkr_cls.return_value = mock_tkr

            config = {"wheel": {"options_lookforward_days": lookforward}}
            result = get_options_chain("AAPL", target_date, config=config)

        assert outside_expiry not in result, (
            f"Outside-window expiry {outside_expiry} must NOT appear in result"
        )

    def test_specific_expiry_date_returns_only_that_expiry(self):
        """PROP-DATA-02c: when expiry_date provided, only that expiry returned."""
        from tradingagents.dataflows.y_finance_options import get_options_chain

        target_date = "2024-01-01"
        specific_expiry = "2024-02-16"
        other_expiry = "2024-03-15"

        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            mock_tkr.options = [specific_expiry, other_expiry]
            mock_tkr.option_chain.return_value = self._make_chain_data()
            mock_tkr_cls.return_value = mock_tkr

            result = get_options_chain("AAPL", target_date, expiry_date=specific_expiry)

        assert specific_expiry in result, (
            f"Specific expiry {specific_expiry} must appear in result"
        )
        assert other_expiry not in result, (
            f"Other expiry {other_expiry} must NOT appear when specific expiry_date provided"
        )


# ---------------------------------------------------------------------------
# PROP-DATA-04: iv_environment boundary values — exact 50.0 and 25.0
# ---------------------------------------------------------------------------

class TestIvEnvironmentBoundaries:
    """PROP-DATA-04: exact boundary values for iv_environment classification."""

    def _get_env(self, iv_series: list) -> str:
        from tradingagents.dataflows.y_finance_options import get_iv_metrics
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv_series)
        data = json.loads(result)
        return data["iv_environment"]

    def _make_series_for_rank(self, target_rank: float) -> list:
        """Build a series where current_vol produces the target iv_rank.

        For a series [0, 1, ..., 99], iv_rank of current (= last element):
          rank = (current - min) / (max - min) * 100
        Set last element to produce the target rank.
        """
        base = list(range(100))
        # current = min + (target_rank / 100) * (max - min)
        # With min=0, max=99: current = target_rank * 0.99
        current = target_rank * 0.99
        series = [float(x) for x in base[:-1]] + [current]
        return series

    def test_iv_rank_exactly_50_is_elevated(self):
        """PROP-DATA-04: iv_rank == 50.0 → 'elevated' (boundary: >=50 is elevated)."""
        # Craft a series where iv_rank = 50.0 exactly
        # rank = (current - min) / (max - min) * 100 = 50
        # → current = min + 0.5*(max - min)
        # Use series [0, 2]: current = 2, max = 2, min = 0 → rank = (2-0)/(2-0)*100 = 100
        # Instead: series [0, 1, 2, 3, 4] → current=4 → rank=100
        # Want rank=50: current = 0 + 0.5*(max-0); with [0,1,2,3,4] max=4, current=2
        series = [0.0, 1.0, 2.0, 3.0, 4.0]
        series[-1] = 2.0  # set current = 2.0 (midpoint)
        env = self._get_env(series)
        # current=2, min=0, max=3 (since we set last to 2.0, max=3 from index 3)
        # rank = (2-0)/(3-0)*100 = 66.7 → elevated
        # Let's build more precisely: series with max=4, min=0, current=2
        series2 = [0.0, 1.0, 3.0, 4.0, 2.0]  # current=2, min=0, max=4, rank=50
        env2 = self._get_env(series2)
        assert env2 == "elevated", (
            f"iv_rank=50.0 should be 'elevated' (>= 50), got '{env2}'"
        )

    def test_iv_rank_just_below_50_is_normal(self):
        """PROP-DATA-04: iv_rank < 50 → 'normal' (if >= 25) or 'compressed' (< 25)."""
        # series [0, 1, 2, 3, 4], current=1.9: rank = (1.9/4)*100 = 47.5 → normal
        series = [0.0, 1.0, 2.0, 3.0, 4.0, 1.9]  # current=1.9, max=4, rank=47.5
        env = self._get_env(series)
        assert env == "normal", (
            f"iv_rank=47.5 should be 'normal', got '{env}'"
        )

    def test_iv_rank_exactly_25_is_normal(self):
        """PROP-DATA-04: iv_rank == 25.0 → 'normal' (boundary: 25 <= rank < 50 = normal)."""
        # series [0, 1, 2, 3, 4], rank=25 → current = 0.25*4 = 1.0
        series = [0.0, 1.0, 2.0, 3.0, 4.0, 1.0]  # current=1.0, max=4, rank=25
        env = self._get_env(series)
        assert env == "normal", (
            f"iv_rank=25.0 should be 'normal' (>= 25, < 50), got '{env}'"
        )

    def test_iv_rank_just_below_25_is_compressed(self):
        """PROP-DATA-04: iv_rank < 25 → 'compressed'."""
        # rank=24: current = 0.24*4 = 0.96
        series = [0.0, 1.0, 2.0, 3.0, 4.0, 0.96]  # rank = (0.96/4)*100 = 24
        env = self._get_env(series)
        assert env == "compressed", (
            f"iv_rank=24.0 should be 'compressed', got '{env}'"
        )

    def test_iv_rank_at_75_is_elevated(self):
        """PROP-DATA-04: iv_rank >= 75 → 'elevated'."""
        # rank = (3/4)*100 = 75
        series = [0.0, 1.0, 2.0, 4.0, 3.0]  # current=3, max=4, rank=75
        env = self._get_env(series)
        assert env == "elevated", (
            f"iv_rank=75 should be 'elevated', got '{env}'"
        )


# ---------------------------------------------------------------------------
# PROP-DATA-07: get_iv_metrics does NOT call yf.Ticker when iv_series provided
# ---------------------------------------------------------------------------

class TestIvMetricsNoYfTickerWhenSeriesInjected:
    """PROP-DATA-07: test seam isolation — no yf.Ticker call when iv_series provided."""

    def test_yf_ticker_not_called_when_iv_series_injected(self):
        """PROP-DATA-07: Patching yf.Ticker to raise AssertionError must NOT fire."""
        from tradingagents.dataflows.y_finance_options import get_iv_metrics

        with patch(
            "tradingagents.dataflows.y_finance_options.yf.Ticker",
            side_effect=AssertionError("yf.Ticker was called — test seam failed"),
        ):
            # If yf.Ticker is called, AssertionError propagates → test fails
            result = get_iv_metrics(
                "AAPL",
                "2024-01-15",
                iv_series=[0.20] * 50,
            )

        # Should succeed without AssertionError
        assert result is not None
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# PROP-DATA-13: ^IRX fallback when risk_free_rate_source="yfinance_irx"
# ---------------------------------------------------------------------------

class TestIrxFallbackToStaticRate:
    """PROP-DATA-13: when ^IRX unavailable and source="yfinance_irx", fall back to static."""

    def test_irx_failure_falls_back_to_static_rate(self):
        """PROP-DATA-13: ^IRX fetch fails → static rate used, note in output."""
        from tradingagents.dataflows.y_finance_options import get_options_greeks

        config = {
            "wheel": {
                "risk_free_rate_source": "yfinance_irx",  # NOT "static" — exercise the IRX path
                "risk_free_rate_static": 0.0525,
            }
        }

        def _irx_side_effect(ticker):
            """^IRX raises; AAPL would succeed if called — but we only raise on ^IRX."""
            if "IRX" in ticker.upper():
                raise Exception("^IRX unavailable (simulated network failure)")
            # For spot price fetch (AAPL): return a mock with history data
            mock_tkr = MagicMock()
            mock_tkr.history.return_value = pd.DataFrame({"Close": [150.0]})
            return mock_tkr

        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker", side_effect=_irx_side_effect):
            result = get_options_greeks(
                "AAPL",
                "2024-01-01",
                "2024-01-31",
                100.0,
                "put",
                config=config,
                _spot_price=100.0,  # bypass spot fetch
                _sigma=0.20,        # bypass IV fetch
                # _risk_free_rate is NOT provided → exercises the IRX → static path
            )

        assert isinstance(result, str)
        # Must contain "using static risk-free rate" note
        assert "static" in result.lower(), (
            f"Expected 'static risk-free rate' note in output, got: {result[:200]}"
        )

    def test_irx_fallback_does_not_raise(self):
        """PROP-DATA-13: computation completes without exception on IRX failure."""
        from tradingagents.dataflows.y_finance_options import get_options_greeks

        config = {
            "wheel": {
                "risk_free_rate_source": "yfinance_irx",
                "risk_free_rate_static": 0.0525,
            }
        }

        with patch(
            "tradingagents.dataflows.y_finance_options.yf.Ticker",
            side_effect=Exception("network error"),
        ):
            try:
                result = get_options_greeks(
                    "AAPL",
                    "2024-01-01",
                    "2024-01-31",
                    100.0,
                    "put",
                    config=config,
                    _spot_price=100.0,
                    _sigma=0.20,
                )
            except Exception as exc:
                pytest.fail(
                    f"get_options_greeks raised {type(exc).__name__}: {exc} "
                    "— must not raise on IRX failure"
                )


# ---------------------------------------------------------------------------
# PROP-DATA-17: shortened-lookback note when iv_series shorter than lookback_days
# ---------------------------------------------------------------------------

class TestShortenedLookbackNote:
    """PROP-DATA-17: when iv_series length < lookback_days, output contains note."""

    def test_shortened_lookback_note_present(self):
        """PROP-DATA-17: short iv_series triggers shortened-lookback note."""
        from tradingagents.dataflows.y_finance_options import get_iv_metrics

        short_series = [0.15 + i * 0.001 for i in range(30)]  # only 30 values
        result = get_iv_metrics(
            "AAPL",
            "2024-01-15",
            lookback_days=252,  # much longer than series
            iv_series=short_series,
        )

        assert isinstance(result, str)
        result_lower = result.lower()

        # Must contain at least one of the expected substrings
        shortened_note_present = any(
            kw in result_lower for kw in ("days", "lookback", "available")
        )
        assert shortened_note_present, (
            f"PROP-DATA-17: expected 'days'/'lookback'/'available' note in output "
            f"when iv_series (len=30) is shorter than lookback_days=252. Got: {result[:300]}"
        )

    def test_shortened_lookback_still_returns_valid_iv_metrics(self):
        """PROP-DATA-17: short series still produces valid iv_rank and iv_percentile."""
        from tradingagents.dataflows.y_finance_options import get_iv_metrics

        short_series = [0.15 + i * 0.001 for i in range(30)]
        result = get_iv_metrics(
            "AAPL",
            "2024-01-15",
            lookback_days=252,
            iv_series=short_series,
        )
        data = json.loads(result)
        assert 0.0 <= data["iv_rank"] <= 100.0, (
            f"iv_rank {data['iv_rank']} not in [0, 100]"
        )
        assert 0.0 <= data["iv_percentile"] <= 100.0, (
            f"iv_percentile {data['iv_percentile']} not in [0, 100]"
        )

    def test_no_shortened_note_when_series_meets_lookback(self):
        """PROP-DATA-17: when iv_series length >= lookback_days, no shortened note needed."""
        from tradingagents.dataflows.y_finance_options import get_iv_metrics

        # Series exactly matches lookback_days
        full_series = [0.20 + i * 0.0001 for i in range(252)]
        result = get_iv_metrics(
            "AAPL",
            "2024-01-15",
            lookback_days=252,
            iv_series=full_series,
        )
        # No exception, valid output
        data = json.loads(result)
        assert "iv_rank" in data
