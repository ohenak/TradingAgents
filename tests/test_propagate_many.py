"""Tests for BatchTickerResult dataclass and TradingAgentsGraph.propagate_many().

PROP-API-01 through PROP-API-07.
"""
import pytest
from unittest.mock import MagicMock, patch, call


class TestBatchTickerResult:
    def test_success_fields_accessible(self):
        from tradingagents.graph.batch import BatchTickerResult
        r = BatchTickerResult(ticker="AAPL", state={"k": "v"}, decision="Buy", error=None)
        assert r.ticker == "AAPL"
        assert r.state == {"k": "v"}
        assert r.decision == "Buy"
        assert r.error is None

    def test_failure_fields_accessible(self):
        from tradingagents.graph.batch import BatchTickerResult
        err = ValueError("bad ticker")
        r = BatchTickerResult(ticker="BAD", state=None, decision=None, error=err)
        assert r.ticker == "BAD"
        assert r.state is None
        assert r.decision is None
        assert r.error is err


class TestPropagateManyEmpty:
    def test_empty_tickers_returns_empty_list(self, mock_graph):
        results = mock_graph.propagate_many([], "2026-05-29")
        assert results == []
        mock_graph.propagate.assert_not_called()


class TestPropagateManySuccess:
    def test_all_succeed_returns_results_in_input_order(self, mock_graph):
        from tradingagents.graph.batch import BatchTickerResult
        mock_graph.propagate.side_effect = [
            ({"market": "up"}, "Buy"),
            ({"market": "down"}, "Sell"),
        ]
        results = mock_graph.propagate_many(["AAPL", "MSFT"], "2026-05-29")
        assert len(results) == 2
        assert results[0].ticker == "AAPL"
        assert results[0].decision == "Buy"
        assert results[0].error is None
        assert results[1].ticker == "MSFT"
        assert results[1].decision == "Sell"
        assert results[1].error is None


class TestPropagateManyPartialFailure:
    def test_one_fail_error_encoded_others_succeed(self, mock_graph):
        err = ValueError("bad ticker")
        mock_graph.propagate.side_effect = [
            ({"k": "v"}, "Buy"),
            err,
            ({"k": "v2"}, "Hold"),
        ]
        results = mock_graph.propagate_many(["AAPL", "BAD", "NVDA"], "2026-05-29")
        assert results[0].error is None
        assert results[1].error is err
        assert results[1].state is None
        assert results[1].decision is None
        assert results[2].error is None
        assert results[2].decision == "Hold"


class TestPropagateManyAssetTypes:
    def test_asset_types_length_mismatch_raises_value_error(self, mock_graph):
        with pytest.raises(ValueError, match="asset_types length"):
            mock_graph.propagate_many(["AAPL", "MSFT"], "2026-05-29", asset_types=["stock"])

    def test_asset_types_none_calls_internal_detection(self, mock_graph):
        mock_graph.propagate.return_value = ({}, "Hold")
        with patch("tradingagents.graph.trading_graph._detect_asset_type", return_value="stock") as mock_detect:
            mock_graph.propagate_many(["AAPL"], "2026-05-29", asset_types=None)
            mock_detect.assert_called_once_with("AAPL")

    def test_explicit_asset_type_bypasses_detection(self, mock_graph):
        mock_graph.propagate.return_value = ({}, "Buy")
        with patch("tradingagents.graph.trading_graph._detect_asset_type") as mock_detect:
            mock_graph.propagate_many(["AAPL"], "2026-05-29", asset_types=["crypto"])
            mock_detect.assert_not_called()
            mock_graph.propagate.assert_called_once_with("AAPL", "2026-05-29", asset_type="crypto")

    def test_mixed_explicit_types_passed_per_ticker(self, mock_graph):
        mock_graph.propagate.return_value = ({}, "Hold")
        mock_graph.propagate_many(["AAPL", "BTC-USD"], "2026-05-29", asset_types=["stock", "crypto"])
        assert mock_graph.propagate.call_args_list == [
            call("AAPL", "2026-05-29", asset_type="stock"),
            call("BTC-USD", "2026-05-29", asset_type="crypto"),
        ]

    def test_keyboard_interrupt_propagates(self, mock_graph):
        mock_graph.propagate.side_effect = KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            mock_graph.propagate_many(["AAPL"], "2026-05-29")


@pytest.fixture
def mock_graph(mock_llm_client):
    """TradingAgentsGraph instance with propagate() mocked."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.propagate = MagicMock()
    return graph
