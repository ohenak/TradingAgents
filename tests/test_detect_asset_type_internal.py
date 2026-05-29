"""Tests for library-internal _detect_asset_type() and CRYPTO_SUFFIXES consistency.

PROP-ASSET-01 through PROP-ASSET-05, PROP-CONTRACT-01.
"""
import pytest


class TestDetectAssetTypeInternal:
    def test_btc_usd_is_crypto(self):
        from tradingagents.dataflows.utils import _detect_asset_type
        assert _detect_asset_type("BTC-USD") == "crypto"

    def test_eth_usdt_is_crypto(self):
        from tradingagents.dataflows.utils import _detect_asset_type
        assert _detect_asset_type("ETH-USDT") == "crypto"

    def test_aapl_is_stock(self):
        from tradingagents.dataflows.utils import _detect_asset_type
        assert _detect_asset_type("AAPL") == "stock"

    def test_exchange_suffix_is_stock_not_crypto(self):
        from tradingagents.dataflows.utils import _detect_asset_type
        assert _detect_asset_type("CNC.TO") == "stock"

    def test_strips_whitespace_and_uppercases(self):
        from tradingagents.dataflows.utils import _detect_asset_type
        assert _detect_asset_type("  btc-usd  ") == "crypto"


class TestCryptoSuffixesConsistency:
    """PROP-CONTRACT-01: CLI and library CRYPTO_SUFFIXES must be identical."""

    def test_crypto_suffixes_match_cli(self):
        import cli.utils as cli_utils
        import tradingagents.dataflows.utils as lib_utils
        assert cli_utils.CRYPTO_SUFFIXES == lib_utils.CRYPTO_SUFFIXES
