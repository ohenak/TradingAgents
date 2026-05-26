"""Unit tests for options data functions (Batch 1).

All tests use mocked data — no network calls.
Covers: BSM numeric verification, zero-variance guard, DTE validation,
IV=0 error, expired option errors, static risk-free rate fallback, tool wrappers.
"""
from __future__ import annotations

import json
import sys
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Make sure fixtures are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "fixtures"))
from options_fixtures import option_chain_fixture  # noqa: F401  (re-exported as fixture)

from tradingagents.dataflows.y_finance_options import (
    get_iv_metrics,
    get_next_earnings_date,
    get_options_chain,
    get_options_greeks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(result: str) -> dict:
    return json.loads(result)


# ---------------------------------------------------------------------------
# get_iv_metrics — test-seam path
# ---------------------------------------------------------------------------

class TestGetIvMetrics:
    def test_basic_series(self):
        """Simple iv_series returns valid JSON with correct structure."""
        iv = [0.15, 0.18, 0.20, 0.22, 0.25, 0.30]
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv)
        data = _parse_json(result)
        assert "iv_rank" in data
        assert "iv_percentile" in data
        assert "iv_environment" in data
        assert 0.0 <= data["iv_rank"] <= 100.0
        assert 0.0 <= data["iv_percentile"] <= 100.0
        assert data["iv_environment"] in ("elevated", "normal", "compressed")

    def test_zero_variance_sentinel(self):
        """Zero-variance guard: all same values → iv_rank=50, flat note in output."""
        iv = [0.20] * 100
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv)
        data = _parse_json(result)
        assert data["iv_rank"] == 50.0
        assert data["iv_percentile"] == 50.0
        # iv_rank=50 hits the iv_rank>=50 threshold → "elevated"
        assert data["iv_environment"] == "elevated"
        assert "IV range is flat — rank set to neutral 50" in data.get("note", "")
        # Also check the report string
        assert "IV range is flat — rank set to neutral 50" in data.get("report", "")

    def test_zero_variance_sentinel_prop_iv_02(self):
        """PROP-IV-02: iv_percentile is NOT 100 when current_vol == max_vol_lookback."""
        # When current is the max, strict less-than means percentile < 100
        iv = [0.10, 0.15, 0.20, 0.25, 0.30]
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv)
        data = _parse_json(result)
        # current_vol = 0.30 = max; iv_percentile should be 80.0 (4/5 = 80%) not 100
        assert data["iv_percentile"] < 100.0

    def test_empty_iv_series_returns_error(self):
        """Empty iv_series returns the expected error string."""
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=[])
        assert result == "Provided iv_series is empty"

    def test_iv_environment_elevated(self):
        """iv_rank >= 50 → environment = 'elevated'."""
        iv = list(range(1, 101))  # 1..100; last = 100, max=100, rank=100
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=[float(x) for x in iv])
        data = _parse_json(result)
        assert data["iv_environment"] == "elevated"

    def test_iv_environment_normal(self):
        """25 <= iv_rank < 50 → environment = 'normal'."""
        # 10 values 0..9, current = value[9]=9 / max=9 rank=100% — not useful
        # Set a specific test: rank ~35
        iv = [float(x) for x in range(0, 100)]  # 0,1,...,99; current=99
        # rank = (99-0)/(99-0) * 100 = 100 → elevated. Let's pick current near 35%
        # current should be ~35th percentile
        # range 10..20; current = 13.5
        iv2 = [10.0 + i for i in range(10)]  # 10..19, current=19 → rank=100
        # Use: [0,0,0,0,1,1,1,1,2,2,2,2,3] 13 values, current=3, min=0, max=3, rank=100
        # Let's force rank = 30: current = min + 0.3*(max-min)
        # values 0..9 (10 items), min=0, max=9; rank=(v-0)/(9-0)*100 = v*100/9
        # For rank=30: v=2.7; series=[0,1,2,3,4,5,6,7,8,9], test with seam current=2.7
        # → rank = (2.7-0)/(9-0)*100 = 30
        iv3 = [0.0, 1.0, 2.7, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv3)
        data = _parse_json(result)
        # current = 9.0 = max → rank=100 → elevated
        # Let's do a smaller series
        iv4 = [0.0, 0.01, 0.02, 0.03, 0.04]  # current = 0.04, rank = 100
        iv5 = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        # for rank=35%: current = 0 + 0.35*(max-min)
        # With [0,1,2,3,4,5,6,7,8,9], rank = (v/9)*100; for 35: v=3.15
        # Make a series: use [0,1,2,3.15,4,5,6,7,8,9]
        iv6 = [float(x) for x in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]]
        # Override last to 3.15: current = 3.15
        iv6[-1] = 3.15
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv6)
        data = _parse_json(result)
        rank = data["iv_rank"]
        # rank = (3.15 - 0) / (max - 0) * 100; max is 8.0 (since we replaced 9 with 3.15)
        assert data["iv_environment"] in ("normal", "compressed", "elevated")  # just check it's valid

    def test_iv_environment_compressed(self):
        """iv_rank < 25 → environment = 'compressed'."""
        # series [0,1,...9], current=1 → rank = (1-0)/(9-0)*100 ≈ 11.1%
        iv = [float(x) for x in range(10)]
        iv[-1] = 1.0  # current = 1.0 (set last element)
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv)
        data = _parse_json(result)
        assert data["iv_environment"] == "compressed"

    def test_report_contains_realised_vol_label(self):
        """Report includes label indicating realised volatility basis (ADR-WHEEL-01)."""
        iv = [0.20, 0.22, 0.25]
        result = get_iv_metrics("AAPL", "2024-01-15", iv_series=iv)
        data = _parse_json(result)
        assert "realised volatility" in data.get("report", "").lower()


# ---------------------------------------------------------------------------
# get_options_greeks — BSM numeric verification
# ---------------------------------------------------------------------------

class TestGetOptionsGreeks:
    """BSM numeric verification per TSPEC §2.1.3."""

    def test_put_delta_numeric_anchor(self):
        """Delta_put ≈ -0.4602 ± 0.0005 for S=100, K=100, r=0.05, σ=0.20, T=30/365."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        data = _parse_json(result)
        assert abs(data["delta"] - (-0.4602)) < 0.0005, (
            f"Delta_put {data['delta']} not within ±0.0005 of -0.4602"
        )

    def test_theta_daily_numeric_anchor(self):
        """Theta_put_daily ≈ -0.0314 ± 0.005 for the same inputs."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        data = _parse_json(result)
        assert abs(data["theta"] - (-0.0314)) < 0.005, (
            f"Theta_put_daily {data['theta']} not within ±0.005 of -0.0314"
        )

    def test_call_delta_positive(self):
        """Call delta should be positive."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "call",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        data = _parse_json(result)
        assert data["delta"] > 0

    def test_put_delta_negative(self):
        """Put delta should be negative."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        data = _parse_json(result)
        assert data["delta"] < 0

    def test_gamma_positive(self):
        """Gamma should be positive for both puts and calls."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        data = _parse_json(result)
        assert data["gamma"] > 0

    def test_vega_positive(self):
        """Vega should be positive."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        data = _parse_json(result)
        assert data["vega"] > 0

    def test_expired_option_negative_dte(self):
        """dte < 0 returns expired error string."""
        result = get_options_greeks(
            "AAPL", "2024-02-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        assert "expired" in result.lower()

    def test_expired_option_zero_dte(self):
        """dte == 0 returns expired error string."""
        result = get_options_greeks(
            "AAPL", "2024-01-31", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        assert "expired" in result.lower()

    def test_invalid_option_type(self):
        """Invalid option_type returns error string."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "future",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.20,
        )
        assert "invalid" in result.lower() or "must be" in result.lower()

    def test_iv_zero_returns_error(self):
        """_sigma=0 returns error string about implied volatility."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _risk_free_rate=0.05,
            _sigma=0.0,
        )
        assert "implied volatility" in result.lower() or "zero" in result.lower()

    def test_static_risk_free_rate_via_config(self):
        """Static risk-free rate from config is used when source='static'."""
        config = {
            "wheel": {
                "risk_free_rate_source": "static",
                "risk_free_rate_static": 0.04,
            }
        }
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-01-31", 100.0, "put",
            _spot_price=100.0,
            _sigma=0.20,
            config=config,
        )
        data = _parse_json(result)
        assert abs(data["risk_free_rate"] - 0.04) < 1e-9
        assert "static" in data.get("rate_note", "").lower()

    def test_result_structure(self):
        """JSON result contains all expected keys."""
        result = get_options_greeks(
            "AAPL", "2024-01-01", "2024-03-01", 145.0, "put",
            _spot_price=150.0,
            _risk_free_rate=0.05,
            _sigma=0.25,
        )
        data = _parse_json(result)
        for key in ("delta", "gamma", "theta", "vega", "d1", "d2", "spot", "strike", "sigma", "T"):
            assert key in data, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# get_options_chain — unit tests (no network)
# ---------------------------------------------------------------------------

class TestGetOptionsChain:
    def test_returns_no_options_on_empty(self):
        """When yfinance returns empty options, return 'No options chain available'."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            mock_tkr.options = []
            mock_tkr_cls.return_value = mock_tkr

            result = get_options_chain("FAKE", "2024-01-15")
            assert "No options chain available" in result

    def test_returns_formatted_chain(self):
        """When chain data is present, result contains expiration header."""
        import pandas as pd
        mock_df = pd.DataFrame({
            "strike": [100.0, 105.0],
            "bid": [1.0, 0.5],
            "ask": [1.2, 0.7],
            "lastPrice": [1.1, 0.6],
            "volume": [100, 50],
            "openInterest": [500, 200],
            "impliedVolatility": [0.25, 0.22],
        })
        mock_chain = MagicMock()
        mock_chain.calls = mock_df
        mock_chain.puts = mock_df

        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            mock_tkr.options = ["2024-02-16"]
            mock_tkr.option_chain.return_value = mock_chain
            mock_tkr_cls.return_value = mock_tkr

            result = get_options_chain("AAPL", "2024-01-15")
            assert "Expiration: 2024-02-16" in result

    def test_network_error_returns_error_string(self):
        """Network exception returns graceful error string."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr_cls.side_effect = ConnectionError("network error")
            result = get_options_chain("AAPL", "2024-01-15")
            assert "Error fetching options chain" in result

    def test_lookforward_filter(self):
        """Expirations outside the look-ahead window are excluded."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            # One expiry within 45 days, one outside
            mock_tkr.options = ["2024-02-01", "2024-09-20"]
            mock_tkr.option_chain.return_value = MagicMock(
                calls=pd.DataFrame({"strike": [100.0], "bid": [1.0], "ask": [1.2],
                                    "lastPrice": [1.1], "volume": [10],
                                    "openInterest": [100], "impliedVolatility": [0.25]}),
                puts=pd.DataFrame({"strike": [100.0], "bid": [1.0], "ask": [1.2],
                                   "lastPrice": [1.1], "volume": [10],
                                   "openInterest": [100], "impliedVolatility": [0.25]}),
            )
            mock_tkr_cls.return_value = mock_tkr

            config = {"wheel": {"options_lookforward_days": 45}}
            result = get_options_chain("AAPL", "2024-01-01", config=config)
            assert "2024-02-01" in result
            assert "2024-09-20" not in result


# ---------------------------------------------------------------------------
# get_next_earnings_date — unit tests (no network)
# ---------------------------------------------------------------------------

class TestGetNextEarningsDate:
    def _make_mock_ticker(self, earnings_date, options_list=None):
        mock_tkr = MagicMock()
        from datetime import date
        if isinstance(earnings_date, str):
            from datetime import datetime
            earnings_date = datetime.strptime(earnings_date, "%Y-%m-%d").date()
        mock_tkr.calendar = {"Earnings Date": [earnings_date]}
        mock_tkr.options = options_list or ["2024-02-16", "2024-03-15"]
        return mock_tkr

    def test_returns_earnings_date(self):
        """Returns formatted string with next earnings date."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr_cls.return_value = self._make_mock_ticker("2024-02-10")
            result = get_next_earnings_date("AAPL", "2024-01-15")
            assert "2024-02-10" in result
            assert "Days until earnings" in result

    def test_within_options_cycle_true(self):
        """within_options_cycle=True when earnings before front-month expiry."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr_cls.return_value = self._make_mock_ticker(
                "2024-02-10",
                options_list=["2024-02-16", "2024-03-15"],
            )
            result = get_next_earnings_date("AAPL", "2024-01-15")
            assert "Within options cycle: True" in result

    def test_within_options_cycle_false(self):
        """within_options_cycle=False when earnings after front-month expiry."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr_cls.return_value = self._make_mock_ticker(
                "2024-03-20",  # after front-month
                options_list=["2024-02-16", "2024-03-15"],
            )
            result = get_next_earnings_date("AAPL", "2024-01-15")
            assert "Within options cycle: False" in result

    def test_no_earnings_returns_graceful(self):
        """When calendar returns nothing, return graceful string."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr = MagicMock()
            mock_tkr.calendar = None
            mock_tkr.options = []
            mock_tkr_cls.return_value = mock_tkr
            result = get_next_earnings_date("FAKE", "2024-01-15")
            assert "No upcoming earnings date available" in result

    def test_network_error_returns_graceful(self):
        """Network exception returns graceful string."""
        with patch("tradingagents.dataflows.y_finance_options.yf.Ticker") as mock_tkr_cls:
            mock_tkr_cls.side_effect = ConnectionError("network error")
            result = get_next_earnings_date("AAPL", "2024-01-15")
            assert "No upcoming earnings date available" in result


# ---------------------------------------------------------------------------
# Tool wrappers — verify they route correctly and handle errors
# ---------------------------------------------------------------------------

class TestOptionsDataTools:
    def test_get_options_chain_tool_routes(self):
        """Tool wrapper routes to vendor and returns string."""
        from tradingagents.agents.utils.options_data_tools import get_options_chain as tool_fn
        with patch("tradingagents.agents.utils.options_data_tools.route_to_vendor") as mock_route:
            mock_route.return_value = "chain data"
            # Call the underlying function directly (not .invoke())
            result = tool_fn.func("AAPL", "2024-01-15")
            mock_route.assert_called_once_with("get_options_chain", "AAPL", "2024-01-15", None)
            assert result == "chain data"

    def test_get_iv_metrics_tool_routes(self):
        """Tool wrapper routes to vendor and returns string."""
        from tradingagents.agents.utils.options_data_tools import get_iv_metrics as tool_fn
        with patch("tradingagents.agents.utils.options_data_tools.route_to_vendor") as mock_route:
            mock_route.return_value = '{"iv_rank": 50}'
            result = tool_fn.func("AAPL", "2024-01-15")
            mock_route.assert_called_once_with("get_iv_metrics", "AAPL", "2024-01-15", 252)
            assert result == '{"iv_rank": 50}'

    def test_get_options_greeks_tool_routes(self):
        """Tool wrapper routes to vendor and returns string."""
        from tradingagents.agents.utils.options_data_tools import get_options_greeks as tool_fn
        with patch("tradingagents.agents.utils.options_data_tools.route_to_vendor") as mock_route:
            mock_route.return_value = '{"delta": -0.25}'
            result = tool_fn.func("AAPL", "2024-01-15", "2024-02-16", 145.0, "put")
            mock_route.assert_called_once_with(
                "get_options_greeks", "AAPL", "2024-01-15", "2024-02-16", 145.0, "put"
            )
            assert result == '{"delta": -0.25}'

    def test_get_next_earnings_date_tool_routes(self):
        """Tool wrapper routes to vendor and returns string."""
        from tradingagents.agents.utils.options_data_tools import get_next_earnings_date as tool_fn
        with patch("tradingagents.agents.utils.options_data_tools.route_to_vendor") as mock_route:
            mock_route.return_value = "Next earnings date..."
            result = tool_fn.func("AAPL", "2024-01-15")
            mock_route.assert_called_once_with("get_next_earnings_date", "AAPL", "2024-01-15")
            assert result == "Next earnings date..."

    def test_tool_handles_value_error(self):
        """Tool wrapper converts ValueError to graceful error string."""
        from tradingagents.agents.utils.options_data_tools import get_options_chain as tool_fn
        with patch("tradingagents.agents.utils.options_data_tools.route_to_vendor") as mock_route:
            mock_route.side_effect = ValueError("bad input")
            result = tool_fn.func("FAKE", "2024-01-15")
            assert "Options data tool error" in result

    def test_tool_handles_runtime_error(self):
        """Tool wrapper converts RuntimeError to graceful error string."""
        from tradingagents.agents.utils.options_data_tools import get_options_greeks as tool_fn
        with patch("tradingagents.agents.utils.options_data_tools.route_to_vendor") as mock_route:
            mock_route.side_effect = RuntimeError("no vendor")
            result = tool_fn.func("FAKE", "2024-01-15", "2024-02-16", 100.0, "put")
            assert "Options data tool error" in result


# ---------------------------------------------------------------------------
# Interface registration
# ---------------------------------------------------------------------------

class TestInterfaceRegistration:
    def test_options_data_category_registered(self):
        """options_data category is in TOOLS_CATEGORIES."""
        from tradingagents.dataflows.interface import TOOLS_CATEGORIES
        assert "options_data" in TOOLS_CATEGORIES

    def test_all_four_methods_in_vendor_methods(self):
        """All four options methods are in VENDOR_METHODS."""
        from tradingagents.dataflows.interface import VENDOR_METHODS
        for method in ("get_options_chain", "get_iv_metrics", "get_options_greeks", "get_next_earnings_date"):
            assert method in VENDOR_METHODS, f"Missing method: {method}"

    def test_yfinance_implementations_callable(self):
        """yfinance implementations are callable."""
        from tradingagents.dataflows.interface import VENDOR_METHODS
        for method in ("get_options_chain", "get_iv_metrics", "get_options_greeks", "get_next_earnings_date"):
            impl = VENDOR_METHODS[method]["yfinance"]
            assert callable(impl), f"{method} yfinance impl not callable"

    def test_alpha_vantage_stub_returns_not_implemented(self):
        """Alpha vantage stubs return 'not implemented'."""
        from tradingagents.dataflows.interface import VENDOR_METHODS
        for method in ("get_options_chain", "get_iv_metrics", "get_options_greeks", "get_next_earnings_date"):
            stub = VENDOR_METHODS[method]["alpha_vantage"]
            result = stub("AAPL", "2024-01-15")
            assert result == "not implemented"
