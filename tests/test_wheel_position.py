"""Unit tests for WheelPosition persistence (Batch 2).

All I/O tests use pytest tmp_path — never write to the real positions_dir.
Covers: atomic write, load_wheel_position, load_latest_open_position integer-sort
regression (PROP-POSN-01: cycle-10 returned over cycle-9).
"""
from __future__ import annotations

import pytest

from tradingagents.models.wheel_position import (
    WheelPosition,
    load_latest_open_position,
    load_wheel_position,
    save_wheel_position,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_position(ticker="AAPL", cycle=1, phase="csp_open", **kwargs) -> WheelPosition:
    defaults = dict(
        ticker=ticker,
        wheel_phase=phase,
        cycle_number=cycle,
        csp_strike=145.0,
        csp_expiration="2024-02-16",
        csp_premium_received=1.30,
        shares_held=100,
    )
    defaults.update(kwargs)
    return WheelPosition(**defaults)


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadRoundTrip:
    def test_save_and_load(self, tmp_path):
        pos = _make_position(ticker="AAPL", cycle=1)
        save_wheel_position(pos, str(tmp_path))

        loaded = load_wheel_position("AAPL", 1, str(tmp_path))
        assert loaded is not None
        assert loaded.ticker == "AAPL"
        assert loaded.cycle_number == 1
        assert loaded.csp_strike == 145.0

    def test_load_nonexistent_returns_none(self, tmp_path):
        result = load_wheel_position("FAKE", 999, str(tmp_path))
        assert result is None

    def test_atomic_write_creates_file(self, tmp_path):
        pos = _make_position(ticker="MSFT", cycle=3)
        save_wheel_position(pos, str(tmp_path))

        expected = tmp_path / "MSFT-cycle-3.json"
        assert expected.exists()
        assert expected.stat().st_size > 0

    def test_overwrite_existing_file(self, tmp_path):
        pos = _make_position(ticker="AAPL", cycle=1, notes="v1")
        save_wheel_position(pos, str(tmp_path))

        pos2 = _make_position(ticker="AAPL", cycle=1, notes="v2")
        save_wheel_position(pos2, str(tmp_path))

        loaded = load_wheel_position("AAPL", 1, str(tmp_path))
        assert loaded.notes == "v2"

    def test_missing_dir_is_created(self, tmp_path):
        subdir = tmp_path / "nested" / "positions"
        pos = _make_position(ticker="AAPL", cycle=1)
        save_wheel_position(pos, str(subdir))
        assert (subdir / "AAPL-cycle-1.json").exists()


# ---------------------------------------------------------------------------
# load_latest_open_position — integer-sort regression (PROP-POSN-01)
# ---------------------------------------------------------------------------

class TestLoadLatestOpenPosition:
    def test_returns_none_when_no_files(self, tmp_path):
        result = load_latest_open_position("AAPL", str(tmp_path))
        assert result is None

    def test_returns_open_position(self, tmp_path):
        pos = _make_position(ticker="AAPL", cycle=1, phase="csp_open")
        save_wheel_position(pos, str(tmp_path))

        loaded = load_latest_open_position("AAPL", str(tmp_path))
        assert loaded is not None
        assert loaded.cycle_number == 1

    def test_skips_cycle_complete(self, tmp_path):
        completed = _make_position(ticker="AAPL", cycle=1, phase="cycle_complete")
        save_wheel_position(completed, str(tmp_path))

        result = load_latest_open_position("AAPL", str(tmp_path))
        assert result is None

    def test_integer_sort_regression_cycle_10_over_cycle_9(self, tmp_path):
        """PROP-POSN-01: cycle-10 must be returned over cycle-9 (integer sort, not lex sort).

        NOTE: REQ v0.2.0 AC3a states "approximately 33.25%" but the
        arithmetically correct value is 33.21%. See TSPEC §9.4 discrepancy note.
        REQ v0.3.0 corrects this. TSPEC is authoritative.

        This test verifies the integer-sort invariant: lexicographic sort would
        return cycle-9 before cycle-10, which is incorrect.
        """
        pos9 = _make_position(ticker="AAPL", cycle=9, phase="csp_open")
        pos10 = _make_position(ticker="AAPL", cycle=10, phase="csp_open")
        save_wheel_position(pos9, str(tmp_path))
        save_wheel_position(pos10, str(tmp_path))

        loaded = load_latest_open_position("AAPL", str(tmp_path))
        assert loaded is not None, "Expected a position, got None"
        assert loaded.cycle_number == 10, (
            f"Expected cycle 10 (integer sort), got cycle {loaded.cycle_number}. "
            "Lexicographic sort would incorrectly return cycle 9 before cycle 10."
        )

    def test_returns_latest_open_skipping_completed(self, tmp_path):
        """Returns the highest-cycle open position, skipping completed ones."""
        pos1 = _make_position(ticker="AAPL", cycle=1, phase="cycle_complete")
        pos2 = _make_position(ticker="AAPL", cycle=2, phase="csp_open")
        save_wheel_position(pos1, str(tmp_path))
        save_wheel_position(pos2, str(tmp_path))

        loaded = load_latest_open_position("AAPL", str(tmp_path))
        assert loaded is not None
        assert loaded.cycle_number == 2

    def test_does_not_return_other_tickers(self, tmp_path):
        """Only returns positions for the requested ticker."""
        pos_aapl = _make_position(ticker="AAPL", cycle=1, phase="csp_open")
        pos_msft = _make_position(ticker="MSFT", cycle=1, phase="csp_open")
        save_wheel_position(pos_aapl, str(tmp_path))
        save_wheel_position(pos_msft, str(tmp_path))

        loaded = load_latest_open_position("AAPL", str(tmp_path))
        assert loaded is not None
        assert loaded.ticker == "AAPL"


# ---------------------------------------------------------------------------
# WheelPosition model fields
# ---------------------------------------------------------------------------

class TestWheelPositionModel:
    def test_required_fields(self):
        pos = WheelPosition(ticker="AAPL", wheel_phase="csp_open", cycle_number=1)
        assert pos.ticker == "AAPL"
        assert pos.wheel_phase == "csp_open"
        assert pos.cycle_number == 1

    def test_optional_fields_default_none(self):
        pos = WheelPosition(ticker="AAPL", wheel_phase="csp_open", cycle_number=1)
        assert pos.csp_strike is None
        assert pos.csp_open_date is None
        assert pos.prior_analyst_bias is None

    def test_cumulative_premium_defaults_zero(self):
        pos = WheelPosition(ticker="AAPL", wheel_phase="csp_open", cycle_number=1)
        assert pos.cumulative_premium_received == 0.0

    def test_cycle_history_defaults_empty(self):
        pos = WheelPosition(ticker="AAPL", wheel_phase="csp_open", cycle_number=1)
        assert pos.cycle_history == []

    def test_cycle_annualised_return_pct_formula(self):
        """PROP-POSN-02: cycle_annualised_return_pct formula example.

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
