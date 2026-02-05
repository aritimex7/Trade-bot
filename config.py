"""
Polymarket Trading Bot - Configuration
Optimized for $10 budget with aggressive mean-reversion strategy
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API CONFIGURATION
# =============================================================================
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "")
PM_API_KEY = os.getenv("PM_API_KEY", "")
PM_API_SECRET = os.getenv("PM_API_SECRET", "")
PM_API_PASSPHRASE = os.getenv("PM_API_PASSPHRASE", "")
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS", "")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", "1"))

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# API Endpoints
GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

# =============================================================================
# TRADING PARAMETERS - Optimized for $10 budget, max trades
# =============================================================================

# Budget & Position Sizing
INITIAL_BALANCE = 10.0  # Starting balance in USDC
MAX_TRADE_SIZE = 0.50   # Max per trade (5% of budget)
MIN_TRADE_SIZE = 0.30   # Min per trade
MAX_POSITIONS = 3       # Max concurrent positions

# Signal Thresholds (Aggressive for more trades)
Z_SCORE_BUY_THRESHOLD = -1.2   # Buy when oversold (was -1.5)
Z_SCORE_SELL_THRESHOLD = 1.2   # Sell when overbought
MAX_SPREAD_PCT = 5.0           # Max spread % allowed (was 3%)
MIN_NET_EV = 0.01              # Minimum edge required (was 0.02)

# Risk Management
STOP_LOSS_PCT = 0.15           # 15% stop loss
TAKE_PROFIT_PCT = 0.25         # 25% take profit
TRAILING_STOP_PCT = 0.10       # 10% trailing from high
MAX_DAILY_LOSS_PCT = 0.02      # 2% max daily loss
COOLDOWN_HOURS = 24            # Hours to pause after max loss

# Market Filters
MIN_VOLUME_24H = 10000         # Minimum $10k volume (was $15k)
MIN_LIQUIDITY = 5000           # Minimum $5k liquidity

# Technical Analysis
SMA_PERIOD = 20                # Period for Simple Moving Average
VOLATILITY_PERIOD = 20         # Period for volatility calculation
PRICE_HISTORY_HOURS = 1        # Hours of price history to fetch

# Execution
POLL_INTERVAL_SECONDS = 10     # Main loop interval
ORDER_TYPE = "GTC"             # Good Till Cancelled
FEE_RATE = 0.002               # 0.2% trading fee estimate
SLIPPAGE_ESTIMATE = 0.005      # 0.5% slippage estimate

# Logging
TRADE_HISTORY_FILE = "history.csv"
LOG_LEVEL = "INFO"

# =============================================================================
# CATEGORY BUCKETS (Max 1 position per category to reduce correlation)
# =============================================================================
CATEGORY_BUCKETS = {
    "politics": ["election", "president", "congress", "senate", "vote", "trump", "biden"],
    "crypto": ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "coin"],
    "sports": ["nfl", "nba", "soccer", "football", "championship", "super bowl"],
    "entertainment": ["oscar", "grammy", "movie", "song", "album", "celebrity"],
    "economics": ["fed", "interest rate", "inflation", "gdp", "recession", "stock"],
    "tech": ["ai", "openai", "google", "apple", "microsoft", "meta", "tesla"],
    "world": ["war", "ukraine", "russia", "china", "europe", "asia"],
}


def validate_config():
    """Validate that all required config values are set."""
    errors = []
    
    if not PRIVATE_KEY:
        errors.append("PRIVATE_KEY is required")
    if not PM_API_KEY:
        errors.append("PM_API_KEY is required")
    if not PM_API_SECRET:
        errors.append("PM_API_SECRET is required")
    if not PM_API_PASSPHRASE:
        errors.append("PM_API_PASSPHRASE is required")
    
    if errors:
        print("❌ Configuration errors:")
        for e in errors:
            print(f"   - {e}")
        return False
    
    print("✅ Configuration validated successfully")
    return True


if __name__ == "__main__":
    validate_config()
    print(f"\n📊 Trading Parameters:")
    print(f"   Budget: ${INITIAL_BALANCE}")
    print(f"   Max Trade: ${MAX_TRADE_SIZE}")
    print(f"   Z-Score Threshold: {Z_SCORE_BUY_THRESHOLD}")
    print(f"   Max Spread: {MAX_SPREAD_PCT}%")
    print(f"   Poll Interval: {POLL_INTERVAL_SECONDS}s")
