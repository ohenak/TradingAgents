"""Tests for library-internal _detect_asset_type() and CRYPTO_SUFFIXES consistency.

PROP-ASSET-01 through PROP-ASSET-05, PROP-CONTRACT-01, PROP-NEG-01.
"""
import ast
from pathlib import Path

import pytest

import tradingagents


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


def _imports_cli(source: str) -> bool:
    """Return True if source has any `import cli...` or `from cli... import` statement."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "cli" or mod.startswith("cli."):
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "cli" or alias.name.startswith("cli."):
                    return True
    return False


class TestLibraryImportBoundary:
    """PROP-NEG-01 / DEC-MULTI-01: tradingagents/ must never import from cli/."""

    def test_no_library_module_imports_cli(self):
        pkg_root = Path(tradingagents.__file__).parent
        violations = []
        for py_file in pkg_root.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            if _imports_cli(source):
                violations.append(str(py_file.relative_to(pkg_root.parent)))
        assert not violations, (
            "Library layer must not import from cli/ (DEC-MULTI-01). "
            f"Offending files: {violations}"
        )
