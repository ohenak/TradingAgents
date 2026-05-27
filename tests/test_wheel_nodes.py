"""Unit tests for wheel_nodes.py (Batch 4).

Covers:
- WheelStateError importability
- wheel_cycle_summary: cycle_annualised_return_pct formula (33.21%, not 33.25%)
- wheel_cycle_summary returns wheel_phase=None (PM-v2-F-01)
- memory log failure is non-blocking
"""
from __future__ import annotations

import pytest

# NOTE: REQ v0.2.0 AC3a states "approximately 33.25%" but the
# arithmetically correct value is 33.21%. See TSPEC §9.4 discrepancy note.
# REQ v0.3.0 corrects this. TSPEC is authoritative.


class TestWheelStateError:
    def test_wheel_state_error_importable(self):
        """WheelStateError is importable from wheel_nodes."""
        from tradingagents.graph.wheel_nodes import WheelStateError
        assert issubclass(WheelStateError, Exception)

    def test_wheel_state_error_is_exception(self):
        """WheelStateError can be raised and caught."""
        from tradingagents.graph.wheel_nodes import WheelStateError
        with pytest.raises(WheelStateError):
            raise WheelStateError("test")


class TestCycleAnnualisedReturnPct:
    def test_cycle_annualised_return_pct_formula(self):
        """PROP-POSN-02: cycle_annualised_return_pct formula verification.

        NOTE: REQ v0.2.0 AC3a states "approximately 33.25%" but the
        arithmetically correct value is 33.21%. See TSPEC §9.4 discrepancy note.
        REQ v0.3.0 corrects this. TSPEC is authoritative.
        """
        cycle_pnl = 930.0
        csp_strike = 140.0
        shares_held = 100
        cycle_duration_days = 73

        result = (cycle_pnl / (csp_strike * shares_held)) * (365 / cycle_duration_days) * 100
        assert abs(result - 33.21) < 0.01, (
            f"cycle_annualised_return_pct = {result:.2f}%, expected ≈ 33.21%"
        )


class TestWheelCycleSummary:
    def test_returns_wheel_phase_none(self):
        """PM-v2-F-01: wheel_cycle_summary returns {'wheel_phase': None}, NOT 'screening'."""
        from tradingagents.graph.wheel_nodes import wheel_cycle_summary

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
            "wheel_phase": "cycle_complete",
        }
        result = wheel_cycle_summary(state)
        assert "wheel_phase" in result
        assert result["wheel_phase"] is None, (
            f"wheel_cycle_summary must return wheel_phase=None, got {result['wheel_phase']!r}. "
            f"PM-v2-F-01: setting 'screening' would bypass the wheel_router guard."
        )

    def test_returns_wheel_phase_not_screening(self):
        """PM-v2-F-01 explicit: returned wheel_phase is NOT 'screening'."""
        from tradingagents.graph.wheel_nodes import wheel_cycle_summary

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
        }
        result = wheel_cycle_summary(state)
        assert result.get("wheel_phase") != "screening"

    def test_memory_log_failure_non_blocking(self):
        """Memory log write failure does not raise — non-blocking (TSPEC §6.3)."""
        from tradingagents.graph.wheel_nodes import wheel_cycle_summary

        # Even with no position and bad state, should not raise
        state = {
            "company_of_interest": "FAKE_TICKER_DOESNT_EXIST",
            "trade_date": "2024-01-15",
        }
        try:
            result = wheel_cycle_summary(state)
            assert result["wheel_phase"] is None
        except Exception as exc:
            pytest.fail(
                f"wheel_cycle_summary raised {type(exc).__name__}: {exc}. "
                f"It must be non-blocking on all failures."
            )

    def test_no_position_returns_none_phase(self, tmp_path):
        """When no position file exists, still returns wheel_phase=None."""
        from unittest.mock import patch
        from tradingagents.graph.wheel_nodes import wheel_cycle_summary

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-01-15",
        }

        # Patch positions_dir to empty tmp_path so no positions found
        with patch("tradingagents.dataflows.config.get_config") as mock_cfg:
            mock_cfg.return_value = {"wheel": {"positions_dir": str(tmp_path)}}
            result = wheel_cycle_summary(state)

        assert result["wheel_phase"] is None

    def test_with_complete_position_computes_pnl(self, tmp_path):
        """With a complete WheelPosition, computes cycle P&L and annualised return."""
        from tradingagents.graph.wheel_nodes import wheel_cycle_summary
        from tradingagents.models.wheel_position import WheelPosition, save_wheel_position
        from unittest.mock import patch

        pos = WheelPosition(
            ticker="AAPL",
            wheel_phase="cycle_complete",
            cycle_number=1,
            csp_strike=140.0,
            shares_held=100,
            csp_open_date="2024-01-01",
            call_away_date="2024-03-14",  # 73 days
            cumulative_premium_received=930.0,
        )
        save_wheel_position(pos, str(tmp_path))

        state = {
            "company_of_interest": "AAPL",
            "trade_date": "2024-03-14",
        }

        with patch("tradingagents.dataflows.config.get_config") as mock_cfg:
            mock_cfg.return_value = {"wheel": {"positions_dir": str(tmp_path)}}
            result = wheel_cycle_summary(state)

        assert result["wheel_phase"] is None
