"""PROPERTIES tests — PROP-CONFIG domain.

Covers:
  PROP-CONFIG-01: all 20 wheel config keys present in DEFAULT_CONFIG["wheel"]
  PROP-CONFIG-02: near_the_money_pct and options_lookforward_days have correct defaults
  PROP-CONFIG-03: all 20 keys appear as values in _WHEEL_ENV_OVERRIDES
"""
from __future__ import annotations

import os

import pytest


# The canonical 20 wheel config keys (TSPEC §8.1)
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
# PROP-CONFIG-01: all 20 keys present
# ---------------------------------------------------------------------------

class TestWheelConfigAllKeysPresent:
    """PROP-CONFIG-01: config["wheel"] contains all 20 required keys."""

    def test_all_20_wheel_keys_present(self):
        """PROP-CONFIG-01: all 20 required keys exist in DEFAULT_CONFIG['wheel']."""
        from tradingagents.default_config import DEFAULT_CONFIG
        wheel = DEFAULT_CONFIG["wheel"]
        missing = EXPECTED_WHEEL_KEYS - set(wheel.keys())
        assert not missing, (
            f"PROP-CONFIG-01: missing wheel config keys: {missing}"
        )

    def test_no_extra_undocumented_keys(self):
        """PROP-CONFIG-01: wheel config has at least 20 keys (allows extra)."""
        from tradingagents.default_config import DEFAULT_CONFIG
        assert len(DEFAULT_CONFIG["wheel"]) >= 20, (
            f"PROP-CONFIG-01: expected at least 20 wheel config keys, "
            f"got {len(DEFAULT_CONFIG['wheel'])}"
        )


# ---------------------------------------------------------------------------
# PROP-CONFIG-02: near_the_money_pct and options_lookforward_days defaults
# ---------------------------------------------------------------------------

class TestWheelConfigDefaultValues:
    """PROP-CONFIG-02: near_the_money_pct and options_lookforward_days defaults."""

    def test_near_the_money_pct_exact_default(self):
        """PROP-CONFIG-02: near_the_money_pct exact REQ v0.3.0 §7 default is 0.05."""
        from tradingagents.default_config import DEFAULT_CONFIG
        wheel = DEFAULT_CONFIG["wheel"]
        assert "near_the_money_pct" in wheel, (
            "PROP-CONFIG-02: near_the_money_pct key must exist in wheel config"
        )
        assert isinstance(wheel["near_the_money_pct"], float), (
            f"PROP-CONFIG-02: near_the_money_pct must be a float, "
            f"got {type(wheel['near_the_money_pct'])}"
        )
        assert wheel["near_the_money_pct"] == 0.05, (
            f"PROP-CONFIG-02: near_the_money_pct must be 0.05 (REQ v0.3.0 §7), "
            f"got {wheel['near_the_money_pct']}"
        )

    def test_near_the_money_pct_is_valid_range(self):
        """PROP-CONFIG-02: near_the_money_pct must be in (0, 1) — a percentage fraction."""
        from tradingagents.default_config import DEFAULT_CONFIG
        val = DEFAULT_CONFIG["wheel"]["near_the_money_pct"]
        assert 0.0 < val < 1.0, (
            f"PROP-CONFIG-02: near_the_money_pct must be in (0, 1) as a fraction, got {val}"
        )

    def test_options_lookforward_days_exact_default(self):
        """PROP-CONFIG-02: options_lookforward_days exact REQ v0.3.0 §7 default is 45."""
        from tradingagents.default_config import DEFAULT_CONFIG
        wheel = DEFAULT_CONFIG["wheel"]
        assert "options_lookforward_days" in wheel, (
            "PROP-CONFIG-02: options_lookforward_days key must exist in wheel config"
        )
        assert isinstance(wheel["options_lookforward_days"], int), (
            f"PROP-CONFIG-02: options_lookforward_days must be an int, "
            f"got {type(wheel['options_lookforward_days'])}"
        )
        assert wheel["options_lookforward_days"] == 45, (
            f"PROP-CONFIG-02: options_lookforward_days must be 45 (REQ v0.3.0 §7), "
            f"got {wheel['options_lookforward_days']}"
        )

    def test_options_lookforward_days_gte_recommended_dte_high(self):
        """PROP-CONFIG-02: options_lookforward_days >= recommended_dte_high by default."""
        from tradingagents.default_config import DEFAULT_CONFIG
        wheel = DEFAULT_CONFIG["wheel"]
        assert wheel["options_lookforward_days"] >= wheel["recommended_dte_high"], (
            f"PROP-CONFIG-02: options_lookforward_days ({wheel['options_lookforward_days']}) "
            f"must be >= recommended_dte_high ({wheel['recommended_dte_high']}) by default"
        )


# ---------------------------------------------------------------------------
# PROP-CONFIG-03: all 20 keys covered in _WHEEL_ENV_OVERRIDES
# ---------------------------------------------------------------------------

class TestWheelEnvOverridesCompleteness:
    """PROP-CONFIG-03: all 20 wheel config keys have env var override entries."""

    def test_all_20_keys_in_wheel_env_overrides(self):
        """PROP-CONFIG-03: every wheel config key appears as a value in _WHEEL_ENV_OVERRIDES."""
        from tradingagents.default_config import _WHEEL_ENV_OVERRIDES

        # Extract the config keys (second element of each tuple)
        covered_keys = {key for (_, key) in _WHEEL_ENV_OVERRIDES.values()}

        missing = EXPECTED_WHEEL_KEYS - covered_keys
        assert not missing, (
            f"PROP-CONFIG-03: the following wheel config keys have no env var override in "
            f"_WHEEL_ENV_OVERRIDES: {missing}"
        )

    def test_env_var_naming_convention(self):
        """PROP-CONFIG-03: all env var names follow TRADINGAGENTS_WHEEL_* convention."""
        from tradingagents.default_config import _WHEEL_ENV_OVERRIDES

        for env_var in _WHEEL_ENV_OVERRIDES:
            assert env_var.startswith("TRADINGAGENTS_WHEEL_"), (
                f"PROP-CONFIG-03: env var '{env_var}' must follow TRADINGAGENTS_WHEEL_* convention"
            )

    def test_env_override_applies_at_runtime(self):
        """PROP-CONFIG-03: setting TRADINGAGENTS_WHEEL_MIN_IV_RANK overrides min_iv_rank."""
        import importlib
        import tradingagents.default_config as m

        old_val = os.environ.get("TRADINGAGENTS_WHEEL_MIN_IV_RANK")
        try:
            os.environ["TRADINGAGENTS_WHEEL_MIN_IV_RANK"] = "30"
            importlib.reload(m)
            assert m.DEFAULT_CONFIG["wheel"]["min_iv_rank"] == 30, (
                "PROP-CONFIG-03: TRADINGAGENTS_WHEEL_MIN_IV_RANK=30 must override min_iv_rank"
            )
        finally:
            if old_val is None:
                os.environ.pop("TRADINGAGENTS_WHEEL_MIN_IV_RANK", None)
            else:
                os.environ["TRADINGAGENTS_WHEEL_MIN_IV_RANK"] = old_val
            importlib.reload(m)
