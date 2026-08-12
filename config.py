"""Configuration: env vars, thresholds, symbols, lot sizes."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- 美股觀察清單 ---
WATCHLIST = ["QQQ", "SPY", "NVDA", "GOOG", "TSLA", "SMH"]

# --- Telegram 配置 ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
# --- Telegram ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Market parameters ---
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "6.5"))

# Symbols tracked
SYMBOLS: list[str] = ["BANKNIFTY"]

# Upstox instrument keys for index spot prices
INDEX_INSTRUMENT_KEYS: dict[str, str] = {
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
}

# Lot sizes (used for display / normalization)
LOT_SIZES: dict[str, int] = {
    "BANKNIFTY": 15,
}

# Strike step for each index
STRIKE_STEPS: dict[str, int] = {
    "BANKNIFTY": 100,
}

# --- GEX thresholds ---
# Percentage proximity thresholds
GAMMA_FLIP_PROXIMITY_PCT: float = 0.3   # Signal when spot within 0.3% of flip
GAMMA_SQUEEZE_PROXIMITY_PCT: float = 0.5
PIN_RISK_PROXIMITY_PCT: float = 0.2
WALL_BREACH_PROXIMITY_PCT: float = 0.1  # Must be past the wall by this %

# GEX magnitude shift threshold
GEX_MAGNITUDE_SHIFT_PCT: float = 40.0   # 40% change triggers signal

# Volume spike multiplier for squeeze detection
VOLUME_SPIKE_MULTIPLIER: float = 2.0

# Near-ATM strikes for delta flow (N above + N below spot)
NEAR_ATM_STRIKES: int = 5

# --- Momentum scoring weights ---
MOMENTUM_WEIGHTS: dict[str, float] = {
    "gex_regime": 0.35,
    "delta_flow": 0.30,
    "gex_roc": 0.20,
    "pcr_gex": 0.15,
}

# Momentum interpretation thresholds
MOMENTUM_STRONG_BULLISH: int = 75
MOMENTUM_MODERATE_BULLISH: int = 60
MOMENTUM_MODERATE_BEARISH: int = 40
MOMENTUM_STRONG_BEARISH: int = 25

# --- Signal suppression ---
SIGNAL_SUPPRESS_MINUTES: int = 15
# These signal types are never suppressed
NEVER_SUPPRESS_SIGNALS: set[str] = {"GAMMA_FLIP", "WALL_BREACH"}

# --- Scheduler ---
MARKET_OPEN_HOUR: int = 9
MARKET_OPEN_MINUTE: int = 15
MARKET_CLOSE_HOUR: int = 15
MARKET_CLOSE_MINUTE: int = 30
FETCH_INTERVAL_MINUTES: int = 3
SUMMARY_INTERVAL_MINUTES: int = 30

# NSE holidays for 2026 (update annually)
NSE_HOLIDAYS: list[str] = [
    "2026-01-26",  # Republic Day
    "2026-03-10",  # Maha Shivaratri
    "2026-03-17",  # Holi
    "2026-03-31",  # Id-Ul-Fitr
    "2026-04-02",  # Ram Navami
    "2026-04-03",  # Mahavir Jayanti
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-04-18",  # Good Friday
    "2026-05-01",  # Maharashtra Day
    "2026-05-25",  # Buddha Purnima
    "2026-06-07",  # Eid-Ul-Adha (Bakri Id)
    "2026-07-07",  # Muharram
    "2026-08-15",  # Independence Day
    "2026-08-16",  # Janmashtami
    "2026-09-05",  # Milad-un-Nabi
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-09",  # Diwali (Laxmi Pujan)
    "2026-11-10",  # Diwali (Balipratipada)
    "2026-11-30",  # Guru Nanak Jayanti
    "2026-12-25",  # Christmas
]

# --- Storage ---
DB_PATH: str = os.path.join(os.path.dirname(__file__), "gex_data.db")
PURGE_DAYS: int = 30

# --- Logging ---
LOG_DIR: str = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE: str = os.path.join(LOG_DIR, "gex.log")
LOG_MAX_BYTES: int = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT: int = 3
