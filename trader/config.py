"""All the knobs in one place. Override any of them with environment variables."""
import os


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- What to trade -----------------------------------------------------------
# Liquid US stocks/ETFs. Alpaca trades US markets only.
SYMBOLS = tuple(
    s.strip().upper()
    for s in os.getenv("SYMBOLS", "SPY,QQQ,AAPL,MSFT,NVDA,AMZN").split(",")
    if s.strip()
)

# --- Strategy: simple trend following ----------------------------------------
FAST_SMA = _env_int("FAST_SMA", 20)
SLOW_SMA = _env_int("SLOW_SMA", 50)
RSI_PERIOD = _env_int("RSI_PERIOD", 14)
RSI_MAX_ENTRY = _env_float("RSI_MAX_ENTRY", 75)  # don't open new positions when overbought
HISTORY_DAYS = _env_int("HISTORY_DAYS", 260)  # calendar days of bars to fetch

# --- Risk management ---------------------------------------------------------
MAX_POSITION_PCT = _env_float("MAX_POSITION_PCT", 0.10)  # max 10% of equity per position
MAX_OPEN_POSITIONS = _env_int("MAX_OPEN_POSITIONS", 5)
STOP_LOSS_PCT = _env_float("STOP_LOSS_PCT", 0.07)  # close a position down 7%
DAILY_LOSS_LIMIT_PCT = _env_float("DAILY_LOSS_LIMIT_PCT", 0.03)  # stop buying if equity is down 3% today
MIN_ORDER_USD = _env_float("MIN_ORDER_USD", 10.0)

# --- Execution ---------------------------------------------------------------
# DRY_RUN=true logs what the bot WOULD do without sending any orders.
DRY_RUN = _env_bool("DRY_RUN", False)

# --- Optional AI risk reviewer (Claude can veto a BUY, never create one) ------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_AI_FILTER = _env_bool("USE_AI_FILTER", True) and bool(ANTHROPIC_API_KEY)
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-5-5")

# --- Credentials (paper account keys) ----------------------------------------
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
