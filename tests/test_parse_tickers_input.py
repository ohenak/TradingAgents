"""Tests for parse_tickers_input() pure function. PROP-INPUT-01 through PROP-INPUT-06."""
import pytest


class TestParseTickers:
    def test_empty_string_returns_empty(self):
        from cli.utils import parse_tickers_input
        assert parse_tickers_input("") == []

    def test_blank_string_returns_empty(self):
        from cli.utils import parse_tickers_input
        assert parse_tickers_input("  ") == []

    def test_single_ticker_normalized(self):
        from cli.utils import parse_tickers_input
        assert parse_tickers_input("AAPL") == ["AAPL"]

    def test_normalizes_strips_deduplicates_first_occurrence(self):
        from cli.utils import parse_tickers_input
        assert parse_tickers_input(" nvda , AAPL , nvda ") == ["NVDA", "AAPL"]

    def test_preserves_exchange_and_crypto_suffixes(self):
        from cli.utils import parse_tickers_input
        assert parse_tickers_input("CNC.TO,BTC-USD") == ["CNC.TO", "BTC-USD"]
