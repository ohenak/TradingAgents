"""WheelPosition Pydantic model and atomic JSON persistence helpers.

File path convention: {positions_dir}/{ticker}-cycle-{N}.json

Atomic write pattern: tempfile.mkstemp + os.replace (same directory → same
filesystem, so os.replace is atomic on both POSIX and Windows).

Integer-sort rule: load_latest_open_position sorts by integer cycle number,
NOT lexicographically. String sort breaks at cycle >= 10:
    "cycle-9" sorts AFTER "cycle-10" character-by-character.
(TE-TSPEC-04; ADR-WHEEL-05 PROP-POSN-01)
"""
from __future__ import annotations

import glob
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WheelPosition(BaseModel):
    """Persistent record of a single wheel strategy cycle for one ticker."""

    ticker: str = Field(description="Equity ticker symbol.")
    wheel_phase: str = Field(description="WheelPhase string value.")
    cycle_number: int = Field(description="Monotonically increasing per ticker.")

    # CSP fields
    csp_open_date: Optional[str] = Field(
        default=None,
        description=(
            "YYYY-MM-DD when CSP was opened. Required for cycle_duration_days computation "
            "in wheel_cycle_summary (cycle_duration_days = call_away_date - csp_open_date). "
            "NOTE: not in REQ-LIFE-02 schema table — TSPEC extension, functionally required "
            "for REQ-LIFE-02 AC3a formula (PM-TSPEC-03)."
        ),
    )
    csp_strike: Optional[float] = Field(default=None)
    csp_expiration: Optional[str] = Field(default=None, description="YYYY-MM-DD.")
    csp_premium_received: Optional[float] = Field(default=None)

    # Assignment fields
    assignment_date: Optional[str] = Field(default=None, description="YYYY-MM-DD if assigned.")
    shares_held: Optional[int] = Field(default=None, description="Always 100 per contract.")
    cost_basis_per_share: Optional[float] = Field(
        default=None,
        description="csp_strike - csp_premium_received.",
    )

    # CC fields
    cc_strike: Optional[float] = Field(default=None)
    cc_expiration: Optional[str] = Field(default=None, description="YYYY-MM-DD.")
    cc_premium_received: Optional[float] = Field(default=None)

    # Completion fields
    call_away_date: Optional[str] = Field(default=None, description="YYYY-MM-DD if called away.")
    cumulative_premium_received: float = Field(default=0.0)
    cycle_pnl: Optional[float] = Field(default=None, description="Realised at cycle end.")
    cycle_annualised_return_pct: Optional[float] = Field(default=None)

    # Roll/analyst tracking
    prior_analyst_bias: Optional[str] = Field(
        default=None,
        description=(
            "Analyst bias from the previous RollCheckAgent run: 'bullish', 'neutral', or 'bearish'. "
            "NOTE: not in REQ-LIFE-02 schema table — TSPEC extension, required for RollCheckAgent "
            "Rule 5 (FSPEC-WHEEL-06). PROPERTIES tests must cover this field (PM-TSPEC-03)."
        ),
    )

    # Prior cycle performance history (for past-context injection, REQ-LIFE-05 AC3)
    cycle_history: list[dict] = Field(
        default_factory=list,
        description=(
            "List of completed cycle summary dicts. Each entry has keys: "
            "cycle_number, cycle_pnl, cycle_annualised_return_pct, cycle_duration_days. "
            "Populated by wheel_cycle_summary when a cycle completes."
        ),
    )

    notes: str = Field(default="")


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def save_wheel_position(position: WheelPosition, positions_dir: str) -> None:
    """Write WheelPosition to disk using atomic temp-file + os.replace pattern.

    The temp file is created in the same directory as the target file so that
    os.replace is guaranteed to be atomic (same filesystem).
    """
    dir_path = Path(positions_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / f"{position.ticker}-cycle-{position.cycle_number}.json"
    json_str = position.model_dump_json(indent=2)

    # Write to temp file in the same directory (same filesystem → atomic rename)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(json_str)
        os.replace(tmp_path, file_path)
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_wheel_position(
    ticker: str, cycle_number: int, positions_dir: str
) -> Optional[WheelPosition]:
    """Load a WheelPosition JSON file by ticker and cycle number.

    Returns None if the file does not exist.
    """
    file_path = Path(positions_dir) / f"{ticker}-cycle-{cycle_number}.json"
    if not file_path.exists():
        return None
    return WheelPosition.model_validate_json(file_path.read_text(encoding="utf-8"))


def load_latest_open_position(
    ticker: str, positions_dir: str
) -> Optional[WheelPosition]:
    """Load the most recent non-complete WheelPosition for the given ticker.

    Uses INTEGER-sorted cycle file loading to correctly handle cycle numbers >= 10.
    String sort MUST NOT be used — 'cycle-10' sorts before 'cycle-9' lexicographically.
    (TE-TSPEC-04; ADR-WHEEL-05 regression test PROP-POSN-01)
    """
    pattern = os.path.join(positions_dir, f"{ticker}-cycle-*.json")
    files = glob.glob(pattern)
    if not files:
        return None

    def _cycle_number(path: str) -> int:
        """Extract integer cycle number from filename for correct numeric ordering."""
        try:
            return int(os.path.basename(path).split("-cycle-")[1].replace(".json", ""))
        except (ValueError, IndexError):
            return -1

    # Sort by integer cycle number descending — NOT lexicographically
    files_sorted = sorted(files, key=_cycle_number, reverse=True)

    for path in files_sorted:
        pos = WheelPosition.model_validate_json(
            Path(path).read_text(encoding="utf-8")
        )
        if pos.wheel_phase != "cycle_complete":
            return pos
    return None
