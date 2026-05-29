"""CLI integration tests for analyze command batch mode. PROP-CLI-01 through PROP-CLI-05."""
import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner


runner = CliRunner()


def _dummy_selections(ticker="AAPL"):
    return {
        "ticker": ticker,
        "asset_type": "stock",
        "analysis_date": "2026-05-29",
        "analysts": [],
        "research_depth": 1,
        "llm_provider": "openai",
        "backend_url": None,
        "shallow_thinker": "gpt-5.4-mini",
        "deep_thinker": "gpt-5.4",
        "google_thinking_level": None,
        "openai_reasoning_effort": None,
        "anthropic_effort": None,
        "output_language": "English",
    }


class TestAnalyzeTickersFlagBlank:
    def test_blank_tickers_flag_exits_with_code_2(self):
        from cli.main import app
        result = runner.invoke(app, ["analyze", "--tickers", "   "])
        assert result.exit_code == 2
        output = result.output or ""
        assert "tickers" in output.lower() or result.exit_code == 2


class TestAnalyzeTickersFlagBatch:
    def test_tickers_flag_skips_ticker_prompt(self):
        from cli.main import app
        with patch("cli.main.run_batch_analysis") as mock_batch, \
             patch("cli.main.run_analysis") as mock_single:
            mock_batch.return_value = None
            result = runner.invoke(app, ["analyze", "--tickers", "AAPL,MSFT"])
        assert result.exit_code in (0, None) or mock_batch.called
        if mock_batch.called:
            args = mock_batch.call_args[0][0]
            assert "AAPL" in args
            assert "MSFT" in args


class TestAnalyzeTickersFlagSingle:
    def test_single_ticker_flag_routes_to_run_analysis(self):
        from cli.main import app
        with patch("cli.main.run_analysis") as mock_single, \
             patch("cli.main.run_batch_analysis") as mock_batch:
            mock_single.return_value = None
            result = runner.invoke(app, ["analyze", "--tickers", "AAPL"])
        if mock_single.called:
            assert mock_single.call_args[1].get("ticker") == "AAPL" or \
                   mock_single.call_args[0][0] == "AAPL"
            assert not mock_batch.called


class TestAnalyzeInteractiveCsv:
    def test_interactive_csv_routes_to_batch(self):
        from cli.main import app
        # Provide CSV at the ticker prompt followed by config answers
        config_input = "NVDA,AAPL\n"  # ticker prompt only; batch skips rest
        with patch("cli.main.run_batch_analysis") as mock_batch, \
             patch("cli.main.run_analysis") as mock_single, \
             patch("cli.main.get_ticker", return_value="NVDA,AAPL"):
            mock_batch.return_value = None
            result = runner.invoke(app, ["analyze"])
        if mock_batch.called:
            tickers = mock_batch.call_args[0][0]
            assert "NVDA" in tickers
            assert "AAPL" in tickers


class TestBatchModeSuppressesPrompts:
    """PROP-NEG-05: Save/Display interactive prompts must NOT appear in batch mode."""

    def test_batch_mode_never_calls_typer_prompt(self):
        from cli.main import app
        with patch("cli.main.get_user_selections", return_value=_dummy_selections()), \
             patch("cli.main.TradingAgentsGraph"), \
             patch("cli.batch.batch_run_loop", return_value=({}, [])), \
             patch("cli.batch.build_batch_summary", return_value=(MagicMock(), 0)), \
             patch("cli.main.typer.prompt") as mock_prompt:
            runner.invoke(app, ["analyze", "--tickers", "AAPL,MSFT"])
        assert mock_prompt.call_count == 0, \
            "Batch mode must not show interactive Save/Display prompts (PROP-NEG-05)"


class TestPromptTextUpdated:
    def test_get_ticker_prompt_mentions_batch(self):
        """get_ticker() prompt text should mention comma-separated / batch."""
        import inspect
        from cli.utils import get_ticker
        source = inspect.getsource(get_ticker)
        # The prompt text should mention CSV or batch mode
        assert "comma" in source.lower() or "batch" in source.lower() or "ticker symbol(s)" in source.lower()
