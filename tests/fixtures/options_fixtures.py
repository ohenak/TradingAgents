"""Canonical test fixtures for options data tests.

All options data unit tests must use these fixtures.
"""
import pytest
import pandas as pd


@pytest.fixture
def option_chain_fixture():
    def _make(ticker: str, expiry: str) -> pd.DataFrame:
        return pd.DataFrame({
            "strike":           [135.0, 140.0, 145.0, 150.0, 155.0],
            "bid":              [  5.20,  3.40,  2.10,  1.20,  0.60],
            "ask":              [  5.40,  3.60,  2.30,  1.40,  0.80],
            "lastPrice":        [  5.30,  3.50,  2.20,  1.30,  0.70],
            "volume":           [   120,   250,   310,   180,    90],
            "openInterest":     [   450,   800,  1200,   600,   200],
            "impliedVolatility":[  0.35,  0.32,  0.30,  0.28,  0.26],
        })
    return _make
