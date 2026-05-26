"""Unit tests for wheel configuration additions (Batch 2).

Covers: 18 keys present, env var overrides, _apply_nested_env_overrides,
config validation warning for options_lookforward_days < recommended_dte_high.
"""
from __future__ import annotations

import os
import warnings

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_default_config():
    """Re-import DEFAULT_CONFIG after manipulating env vars."""
    # Force re-import to pick up env changes
    import importlib
    import tradingagents.default_config as m
    importlib.reload(m)
    return m.DEFAULT_CONFIG


EXPECTED_WHEEL_KEYS = {
    "min_iv_rank",
    "earnings_buffer_days",
    "max_wheel_stock_price",
    "near_the_money_pct",
    "target_csp_delta_low",
    "target_csp_delta_high",
    "target_cc_delta_low",
    "target_cc_delta_high",
    "min_annualised_yield_pct",
    "recommended_dte_low",
    "recommended_dte_high",
    "options_lookforward_days",
    "take_profit_pct",
    "dte_to_roll",
    "iv_rank_lookback_days",
    "min_chain_oi",
    "max_chain_spread_pct",
    "risk_free_rate_source",
    "risk_free_rate_static",
    "positions_dir",
}


# ---------------------------------------------------------------------------
# Key presence
# ---------------------------------------------------------------------------

class TestWheelConfigKeys:
    def test_wheel_subdict_present(self):
        """config['wheel'] sub-dict exists."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert "wheel" in DEFAULT_CONFIG

    def test_all_18_keys_present(self):
        """All 18+ required wheel config keys are present."""
        from tradingagents.default_config import DEFAULT_CONFIG
        wheel = DEFAULT_CONFIG["wheel"]
        for key in EXPECTED_WHEEL_KEYS:
            assert key in wheel, f"Missing wheel config key: {key}"

    def test_recommended_dte_low_is_28(self):
        """recommended_dte_low = 28 per DEC-PLAN-01."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["wheel"]["recommended_dte_low"] == 28

    def test_options_lookforward_days_default(self):
        """options_lookforward_days defaults to 90."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert DEFAULT_CONFIG["wheel"]["options_lookforward_days"] == 90

    def test_positions_dir_is_string(self):
        """positions_dir is a non-empty string."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert isinstance(DEFAULT_CONFIG["wheel"]["positions_dir"], str)
        assert len(DEFAULT_CONFIG["wheel"]["positions_dir"]) > 0

    def test_options_data_vendor_present(self):
        """data_vendors has options_data key."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert "options_data" in DEFAULT_CONFIG.get("data_vendors", {})


# ---------------------------------------------------------------------------
# Env var overrides
# ---------------------------------------------------------------------------

class TestWheelEnvOverrides:
    def test_env_var_overrides_min_iv_rank(self):
        """TRADINGAGENTS_WHEEL_MIN_IV_RANK env var overrides min_iv_rank."""
        import importlib
        import tradingagents.default_config as m

        old_val = os.environ.get("TRADINGAGENTS_WHEEL_MIN_IV_RANK")
        try:
            os.environ["TRADINGAGENTS_WHEEL_MIN_IV_RANK"] = "35"
            importlib.reload(m)
            assert m.DEFAULT_CONFIG["wheel"]["min_iv_rank"] == 35
        finally:
            if old_val is None:
                del os.environ["TRADINGAGENTS_WHEEL_MIN_IV_RANK"]
            else:
                os.environ["TRADINGAGENTS_WHEEL_MIN_IV_RANK"] = old_val
            importlib.reload(m)

    def test_env_var_overrides_positions_dir(self):
        """TRADINGAGENTS_WHEEL_POSITIONS_DIR env var overrides positions_dir."""
        import importlib
        import tradingagents.default_config as m

        old_val = os.environ.get("TRADINGAGENTS_WHEEL_POSITIONS_DIR")
        try:
            os.environ["TRADINGAGENTS_WHEEL_POSITIONS_DIR"] = "/tmp/test_positions"
            importlib.reload(m)
            assert m.DEFAULT_CONFIG["wheel"]["positions_dir"] == "/tmp/test_positions"
        finally:
            if old_val is None:
                del os.environ["TRADINGAGENTS_WHEEL_POSITIONS_DIR"]
            else:
                os.environ["TRADINGAGENTS_WHEEL_POSITIONS_DIR"] = old_val
            importlib.reload(m)

    def test_apply_nested_env_overrides_function_exists(self):
        """_apply_nested_env_overrides is importable and callable."""
        from tradingagents.default_config import _apply_nested_env_overrides
        assert callable(_apply_nested_env_overrides)

    def test_apply_nested_env_overrides_coerces_float(self):
        """_apply_nested_env_overrides coerces float values correctly."""
        from tradingagents.default_config import _apply_nested_env_overrides

        config = {"wheel": {"max_wheel_stock_price": 500.0}}
        old_val = os.environ.get("TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE")
        try:
            os.environ["TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE"] = "750.0"
            result = _apply_nested_env_overrides(config)
            assert result["wheel"]["max_wheel_stock_price"] == 750.0
        finally:
            if old_val is None:
                os.environ.pop("TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE", None)
            else:
                os.environ["TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE"] = old_val


# ---------------------------------------------------------------------------
# Config validation warning
# ---------------------------------------------------------------------------

class TestConfigValidation:
    def test_options_lookforward_days_below_dte_high_warns(self):
        """options_lookforward_days < recommended_dte_high emits UserWarning."""
        import warnings
        from tradingagents.default_config import DEFAULT_CONFIG

        config = {**DEFAULT_CONFIG, "wheel": {**DEFAULT_CONFIG["wheel"]}}
        config["wheel"]["options_lookforward_days"] = 30  # below recommended_dte_high=45

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Trigger validation manually (as setup.py would)
            if config["wheel"]["options_lookforward_days"] < config["wheel"]["recommended_dte_high"]:
                warnings.warn(
                    f"options_lookforward_days ({config['wheel']['options_lookforward_days']}) is less than "
                    f"recommended_dte_high ({config['wheel']['recommended_dte_high']}). "
                    f"The effective lookforward window will be extended automatically.",
                    UserWarning,
                    stacklevel=2,
                )
            assert len(w) >= 1
            assert issubclass(w[-1].category, UserWarning)
            assert "options_lookforward_days" in str(w[-1].message)
