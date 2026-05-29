"""Tests for BatchTickerRecord and build_batch_summary(). PROP-TABLE-01 through PROP-TABLE-10."""
import json
import pytest
from unittest.mock import MagicMock


class TestBatchTickerRecord:
    def test_fields_accessible(self):
        from cli.batch import BatchTickerRecord
        rec = BatchTickerRecord(ticker="AAPL", final_state={"k": "v"}, decision="Buy")
        assert rec.ticker == "AAPL"
        assert rec.final_state == {"k": "v"}
        assert rec.decision == "Buy"


def _make_record(ticker, decision="Hold", wheel_report=None, trade_decision=None):
    from cli.batch import BatchTickerRecord
    state = {}
    if wheel_report is not None:
        state["wheel_candidate_report"] = wheel_report
    if trade_decision is not None:
        state["final_trade_decision"] = trade_decision
    return BatchTickerRecord(ticker=ticker, final_state=state, decision=decision)


def _render_table(table):
    """Render Rich table to a list of row-strings for assertion."""
    from io import StringIO
    from rich.console import Console
    buf = StringIO()
    console = Console(file=buf, width=200, force_terminal=False)
    console.print(table)
    return buf.getvalue()


class TestBuildBatchSummaryStandardMode:
    def test_all_success_exit_code_zero(self):
        from cli.batch import build_batch_summary, BatchTickerRecord
        results = {
            "AAPL": _make_record("AAPL", trade_decision="Buy AAPL"),
            "MSFT": _make_record("MSFT", trade_decision="Hold MSFT"),
        }
        _, exit_code = build_batch_summary(results, [], ["market"], ["AAPL", "MSFT"])
        assert exit_code == 0

    def test_one_failed_exit_code_one(self):
        from cli.batch import build_batch_summary
        results = {"AAPL": _make_record("AAPL", trade_decision="Buy")}
        _, exit_code = build_batch_summary(results, ["MSFT"], ["market"], ["AAPL", "MSFT"])
        assert exit_code == 1

    def test_all_failed_exit_code_one(self):
        from cli.batch import build_batch_summary
        _, exit_code = build_batch_summary({}, ["AAPL", "MSFT"], ["market"], ["AAPL", "MSFT"])
        assert exit_code == 1

    def test_failed_row_has_empty_decision_and_failed_status(self):
        from cli.batch import build_batch_summary
        results = {"AAPL": _make_record("AAPL", trade_decision="Buy")}
        table, _ = build_batch_summary(results, ["MSFT"], ["market"], ["AAPL", "MSFT"])
        rendered = _render_table(table)
        assert "Failed" in rendered
        assert "MSFT" in rendered

    def test_standard_first_non_empty_line_used(self):
        from cli.batch import build_batch_summary
        results = {"AAPL": _make_record("AAPL", trade_decision="\n\nBuy NVDA\nRationale")}
        table, _ = build_batch_summary(results, [], ["market"], ["AAPL"])
        rendered = _render_table(table)
        assert "Buy NVDA" in rendered

    def test_standard_decision_truncated_to_50_chars(self):
        from cli.batch import build_batch_summary
        long_line = "A" * 75
        results = {"AAPL": _make_record("AAPL", trade_decision=long_line)}
        table, _ = build_batch_summary(results, [], ["market"], ["AAPL"])
        rendered = _render_table(table)
        assert "A" * 50 in rendered
        assert "A" * 51 not in rendered

    def test_empty_decision_yields_empty_string_not_na(self):
        """PROP-NEG-06: standard mode with absent/blank final_trade_decision → "" not "N/A"."""
        from cli.batch import build_batch_summary, _standard_decision
        # Direct check of the extractor: absent and all-blank both yield ""
        assert _standard_decision({}) == ""
        assert _standard_decision({"final_trade_decision": ""}) == ""
        assert _standard_decision({"final_trade_decision": "\n\n   \n"}) == ""
        # Rendered table must not contain "N/A" for a standard-mode empty decision
        results = {"AAPL": _make_record("AAPL", trade_decision=None)}
        table, _ = build_batch_summary(results, [], ["market"], ["AAPL"])
        rendered = _render_table(table)
        assert "N/A" not in rendered

    def test_row_order_matches_ordered_tickers(self):
        from cli.batch import build_batch_summary
        results = {
            "AAPL": _make_record("AAPL", trade_decision="Buy"),
            "MSFT": _make_record("MSFT", trade_decision="Sell"),
        }
        table, _ = build_batch_summary(results, [], ["market"], ["AAPL", "MSFT"])
        rendered = _render_table(table)
        assert rendered.index("AAPL") < rendered.index("MSFT")


class TestBuildBatchSummaryWheelMode:
    def test_wheel_approved_shows_approved(self):
        from cli.batch import build_batch_summary
        from tradingagents.agents.schemas import WheelCandidateReport
        report = WheelCandidateReport(
            approved=True, iv_rank=55.0, iv_percentile=60.0,
            iv_environment="elevated", iv_assessment="ok",
            earnings_clearance_ok=True, liquidity_ok=True,
            analyst_bias="bullish",
            recommended_strike_range=[140.0, 150.0], recommended_dte_range=[28, 45],
            rationale="All pass.",
        )
        results = {"NVDA": _make_record("NVDA", wheel_report=report.model_dump_json())}
        table, _ = build_batch_summary(results, [], ["market", "wheel"], ["NVDA"])
        rendered = _render_table(table)
        assert "Approved" in rendered

    def test_wheel_rejected_shows_rejected(self):
        from cli.batch import build_batch_summary
        from tradingagents.agents.schemas import WheelCandidateReport
        report = WheelCandidateReport(
            approved=False, rejection_reason="IV too low",
            iv_rank=10.0, iv_percentile=15.0,
            iv_environment="compressed", iv_assessment="low",
            earnings_clearance_ok=True, liquidity_ok=True,
            analyst_bias="neutral",
            recommended_strike_range=[0.0, 0.0], recommended_dte_range=[28, 45],
            rationale="Failed.",
        )
        results = {"NVDA": _make_record("NVDA", wheel_report=report.model_dump_json())}
        table, _ = build_batch_summary(results, [], ["wheel"], ["NVDA"])
        rendered = _render_table(table)
        assert "Rejected" in rendered

    def test_wheel_none_report_shows_na(self):
        from cli.batch import build_batch_summary
        results = {"NVDA": _make_record("NVDA", wheel_report=None)}
        table, _ = build_batch_summary(results, [], ["wheel"], ["NVDA"])
        rendered = _render_table(table)
        assert "N/A" in rendered

    def test_wheel_malformed_json_shows_na(self):
        from cli.batch import build_batch_summary
        results = {"NVDA": _make_record("NVDA", wheel_report="not-valid-json{{")}
        table, _ = build_batch_summary(results, [], ["wheel"], ["NVDA"])
        rendered = _render_table(table)
        assert "N/A" in rendered
