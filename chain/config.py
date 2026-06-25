import os
from typing import List

from dotenv import load_dotenv
load_dotenv()

# ── NSE Polling ───────────────────────────────────────────────────────────
NSE_SYMBOLS: List[str] = [s.strip() for s in os.getenv("SYMBOLS", "NIFTY").split(",") if s.strip()]
POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))  # 2-minute target
# Jitter bounds: ±25% around the 2min target gives 90–150s spacing.
POLL_MIN_SECONDS: int = POLL_INTERVAL_SECONDS - (POLL_INTERVAL_SECONDS // 4)   # 90s floor
POLL_MAX_SECONDS: int = POLL_INTERVAL_SECONDS + (POLL_INTERVAL_SECONDS // 4)   # 150s ceiling

# Redis TTL for all market-data cache keys (40 minutes)
REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "2400"))

# Session retention window (hours) — data older than this is purged at 6 PM IST
SESSION_RETENTION_HOURS: int = int(os.getenv("SESSION_RETENTION_HOURS", "12"))

# ── Server ────────────────────────────────────────────────────────────────
API_PORT: int = int(os.getenv("API_PORT", "8000"))
APP_API_KEY: str = os.getenv("APP_API_KEY", "")  # x-api-key header for abuse prevention

# ── Cache (Redis optional) ────────────────────────────────────────────────
REDIS_URL: str = os.getenv("REDIS_URL", "")
USE_REDIS: bool = bool(REDIS_URL)
REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "100"))

# ── Proxy (optional) ──────────────────────────────────────────────────────
PROXY_URLS: List[str] = [p.strip() for p in os.getenv("PROXY_URLS", "").split(",") if p.strip()]

# ── Supabase ──────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")  # service role key — set via env, never hardcode
SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")  # Required to verify user tokens

# ── News APIs ─────────────────────────────────────────────────────────────
WORLDNEWS_API_KEY: str = os.getenv("WORLDNEWS_API_KEY", "")
GNEWS_API_KEY: str = os.getenv("GNEWS_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ── Razorpay ──────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# ── User Agents for NSE evasion ───────────────────────────────────────────
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.129 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
]

# ── Insight Engine — keyword lists (rule-based V1) ────────────────────────
BULLISH_KEYWORDS: List[str] = [
    "rally", "surge", "gain", "bullish", "up", "positive", "recovery",
    "breakout", "support", "buying", "inflow", "growth", "gdp",
]
BEARISH_KEYWORDS: List[str] = [
    "fall", "drop", "decline", "bearish", "down", "negative", "crash",
    "selloff", "resistance", "outflow", "recession", "inflation", "rbi tightening",
]
MARKET_FILTER_KEYWORDS: List[str] = [
    "nifty", "banknifty", "sensex", "nse", "bse", "rbi", "sebi",
    "market", "stock", "equity", "index", "inflation", "gdp", "rate",
    "ipo", "fii", "dii", "f&o", "options", "futures",
]