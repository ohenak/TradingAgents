import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
_WHEEL_POSITIONS_DEFAULT = os.path.join(_TRADINGAGENTS_HOME, "wheel_positions")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER":         "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM":       "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM":      "quick_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL":      "backend_url",
    "TRADINGAGENTS_OUTPUT_LANGUAGE":      "output_language",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS":    "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS":      "max_risk_discuss_rounds",
    "TRADINGAGENTS_CHECKPOINT_ENABLED":   "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER":     "benchmark_ticker",
}


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value."""
    if isinstance(reference, bool):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        config[key] = _coerce(raw, config.get(key))
    return config


# ---------------------------------------------------------------------------
# Wheel options trading — nested env var overrides (ADR-WHEEL-03, TSPEC §8.2)
# ---------------------------------------------------------------------------
# Note: _apply_env_overrides handles only flat top-level keys; wheel config
# lives under config["wheel"] and needs a separate nested-override helper.
# 20 entries, one per config["wheel"] key (plus positions_dir).

_WHEEL_ENV_OVERRIDES = {
    "TRADINGAGENTS_WHEEL_MIN_IV_RANK":              ("wheel", "min_iv_rank"),
    "TRADINGAGENTS_WHEEL_EARNINGS_BUFFER_DAYS":     ("wheel", "earnings_buffer_days"),
    "TRADINGAGENTS_WHEEL_MAX_WHEEL_STOCK_PRICE":    ("wheel", "max_wheel_stock_price"),
    "TRADINGAGENTS_WHEEL_NEAR_THE_MONEY_PCT":       ("wheel", "near_the_money_pct"),
    "TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_LOW":     ("wheel", "target_csp_delta_low"),
    "TRADINGAGENTS_WHEEL_TARGET_CSP_DELTA_HIGH":    ("wheel", "target_csp_delta_high"),
    "TRADINGAGENTS_WHEEL_TARGET_CC_DELTA_LOW":      ("wheel", "target_cc_delta_low"),
    "TRADINGAGENTS_WHEEL_TARGET_CC_DELTA_HIGH":     ("wheel", "target_cc_delta_high"),
    "TRADINGAGENTS_WHEEL_MIN_ANNUALISED_YIELD_PCT": ("wheel", "min_annualised_yield_pct"),
    "TRADINGAGENTS_WHEEL_RECOMMENDED_DTE_LOW":      ("wheel", "recommended_dte_low"),
    "TRADINGAGENTS_WHEEL_RECOMMENDED_DTE_HIGH":     ("wheel", "recommended_dte_high"),
    "TRADINGAGENTS_WHEEL_OPTIONS_LOOKFORWARD_DAYS": ("wheel", "options_lookforward_days"),
    "TRADINGAGENTS_WHEEL_TAKE_PROFIT_PCT":          ("wheel", "take_profit_pct"),
    "TRADINGAGENTS_WHEEL_DTE_TO_ROLL":              ("wheel", "dte_to_roll"),
    "TRADINGAGENTS_WHEEL_IV_RANK_LOOKBACK_DAYS":    ("wheel", "iv_rank_lookback_days"),
    "TRADINGAGENTS_WHEEL_MIN_CHAIN_OI":             ("wheel", "min_chain_oi"),
    "TRADINGAGENTS_WHEEL_MAX_CHAIN_SPREAD_PCT":     ("wheel", "max_chain_spread_pct"),
    "TRADINGAGENTS_WHEEL_RISK_FREE_RATE_SOURCE":    ("wheel", "risk_free_rate_source"),
    "TRADINGAGENTS_WHEEL_RISK_FREE_RATE_STATIC":    ("wheel", "risk_free_rate_static"),
    "TRADINGAGENTS_WHEEL_POSITIONS_DIR":            ("wheel", "positions_dir"),
}


def _apply_nested_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_WHEEL_* env vars to nested config['wheel'] sub-dict."""
    for env_var, (section, key) in _WHEEL_ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        reference = config.get(section, {}).get(key)
        config[section][key] = _coerce(raw, reference)
    return config


DEFAULT_CONFIG = _apply_nested_env_overrides(_apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "analyst_concurrency_limit": 1,
    # News / data fetching parameters
    # Increase for longer lookback strategies or to broaden macro coverage;
    # decrease to reduce token usage in agent prompts.
    "news_article_limit": 20,             # max articles per ticker (ticker-news)
    "global_news_article_limit": 10,      # max articles for global/macro news
    "global_news_lookback_days": 7,       # macro news lookback window
    # Search queries used by get_global_news for macro headlines. Extend or
    # replace to broaden geographic / sector coverage.
    "global_news_queries": [
        "Federal Reserve interest rates inflation",
        "S&P 500 earnings GDP economic outlook",
        "geopolitical risk trade war sanctions",
        "ECB Bank of England BOJ central bank policy",
        "oil commodities supply chain energy",
    ],
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
        "options_data": "yfinance",          # Options: yfinance (alpha_vantage stub only)
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # Benchmark for alpha calculation in the reflection layer.
    # ``benchmark_ticker`` (when set) overrides the suffix map for all
    # tickers; leave it None to use ``benchmark_map`` for auto-detection
    # based on the ticker's exchange suffix. SPY remains the US default
    # so the reflection label keeps reading "Alpha vs SPY" for US tickers
    # while non-US tickers get their regional index automatically.
    "benchmark_ticker": None,
    "benchmark_map": {
        ".NS":  "^NSEI",    # NSE India (Nifty 50)
        ".BO":  "^BSESN",   # BSE India (Sensex)
        ".T":   "^N225",    # Tokyo (Nikkei 225)
        ".HK":  "^HSI",     # Hong Kong (Hang Seng)
        ".L":   "^FTSE",    # London (FTSE 100)
        ".TO":  "^GSPTSE",  # Toronto (TSX Composite)
        ".AX":  "^AXJO",    # Australia (ASX 200)
        "":     "SPY",      # default for US-listed tickers (no suffix)
    },
    # -----------------------------------------------------------------------
    # Wheel options trading configuration (TSPEC §8.1)
    # All 18 keys have inline comments per REQ-NFR-07.
    # Note: recommended_dte_low = 28 is authoritative (DEC-PLAN-01);
    # REQ-TRADE-03 text "21–45 DTE" was corrected to "28–45" in REQ v0.3.0.
    # All defaults below match REQ v0.3.0 §7 config table (authoritative).
    # -----------------------------------------------------------------------
    "wheel": {
        # Screening thresholds
        "min_iv_rank": 25,                    # int: minimum IV Rank to approve a wheel candidate
        "earnings_buffer_days": 14,           # int: min days between target expiry and next earnings
        "max_wheel_stock_price": 500.0,       # float: maximum stock price for cash manageability
        "near_the_money_pct": 0.05,           # float: ±% of spot price defining near-the-money strikes (Criterion 2)
                                              # REQ v0.3.0 §7 default: 0.05

        # CSP parameters
        "target_csp_delta_low": 0.20,         # float: lower bound of target put delta (inclusive)
        "target_csp_delta_high": 0.30,        # float: upper bound of target put delta (inclusive)

        # CC parameters
        "target_cc_delta_low": 0.20,          # float: lower bound of target call delta (inclusive)
        "target_cc_delta_high": 0.35,         # float: upper bound of target call delta (inclusive)

        # Yield and timing
        "min_annualised_yield_pct": 12.0,     # float: minimum annualised premium yield to accept a trade
        "recommended_dte_low": 28,            # int: minimum DTE (calendar days) for new positions
        "recommended_dte_high": 45,           # int: maximum DTE (calendar days) for new positions
        "options_lookforward_days": 45,       # int: chain look-ahead window (calendar days); must be >= recommended_dte_high
                                              # REQ v0.3.0 §7 default: 45

        # Roll management
        "take_profit_pct": 50.0,              # float: roll/close when contract value is at or below this % of premium received
        "dte_to_roll": 21,                    # int: roll when DTE falls to or below this value (calendar days)

        # IV computation
        "iv_rank_lookback_days": 252,         # int: trading days for IV Rank/Percentile computation

        # Liquidity filters
        "min_chain_oi": 100,                  # int: minimum open interest for a strike to be liquid
        "max_chain_spread_pct": 10.0,         # float: max bid/ask spread as % of mid for liquidity filter

        # Risk-free rate
        "risk_free_rate_source": "yfinance_irx",  # str: "yfinance_irx" or "static"
        "risk_free_rate_static": 0.0525,      # float: static risk-free rate (decimal, not percent)

        # Position persistence
        "positions_dir": _WHEEL_POSITIONS_DEFAULT,  # str: directory for per-position JSON files
    },
}))
