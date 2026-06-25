"""Unified Option Chain Fetcher (NSE + BSE)

This module merges the previous NSE/BSE fetchers into a single, parametric
fetcher. Use the `exchange` parameter ("NSE" or "BSE") when calling
`fetch_option_chain_compact` to select the source.

Behavior is intentionally conservative for BSE: the BSE endpoint and
parameters may differ in the wild, so the BSE path is a best-effort wrapper
that mirrors the existing BSE file behavior while keeping the same
production-hardened features (circuit breaker, backoff, timeouts). The
fetcher now returns the full option-chain payload (no ATM±5 trimming);
`atm_strike` is still computed for downstream use.
"""
import asyncio
import logging
import time
import random
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests

from chain.config import USER_AGENTS, PROXY_URLS

logger = logging.getLogger("optionpluse.fetcher")

# Endpoints
NSE_BASE = "https://www.nseindia.com"
BSE_BASE = "https://api.bseindia.com"
BSE_OPTION_CHAIN_PATH = "/BseIndiaAPI/api/DerivOptionChain_IV/w"

_MAX_RETRIES = 1000
_CIRCUIT_FAILURE_THRESHOLD = 10
_CIRCUIT_BACKOFF_SECONDS = 600  # 10 minutes

# ATM window size (retained for atm_strike calculation; full data returned)
ATM_WINDOW = 5

# Thread pool — 10 workers covers multiple symbols + spare capacity
_pool = ThreadPoolExecutor(max_workers=10)

# ── Circuit Breaker State (per-symbol) ───────────────────────────────────────
_circuit: Dict[str, Dict] = {}


def _get_circuit(symbol: str) -> Dict:
    if symbol not in _circuit:
        _circuit[symbol] = {"failures": 0, "open_until": 0.0}
    return _circuit[symbol]


def _circuit_is_open(symbol: str) -> bool:
    c = _get_circuit(symbol)
    if c["open_until"] > time.monotonic():
        return True
    if c["open_until"] > 0:
        # Reset after backoff period
        c["failures"] = 0
        c["open_until"] = 0.0
    return False


def _record_failure(symbol: str):
    c = _get_circuit(symbol)
    c["failures"] += 1
    if c["failures"] >= _CIRCUIT_FAILURE_THRESHOLD:
        c["open_until"] = time.monotonic() + _CIRCUIT_BACKOFF_SECONDS
        logger.warning(
            "🔴 Circuit OPEN for %s after %d failures. Backing off %ds.",
            symbol, c["failures"], _CIRCUIT_BACKOFF_SECONDS,
        )


def _record_success(symbol: str):
    c = _get_circuit(symbol)
    if c["failures"] > 0:
        logger.info("🟢 Circuit CLOSED for %s after successful fetch.", symbol)
    c["failures"] = 0
    c["open_until"] = 0.0


# ── Session creation ──────────────────────────────────────────────────────────


class NSEFetchError(Exception):
    def __init__(self, symbol: str, status_code: Optional[int] = None, message: str = ""):
        self.symbol = symbol
        self.status_code = status_code
        super().__init__(f"NSEFetchError for {symbol}: {message} (status={status_code})")


def pick_proxy() -> Optional[Dict[str, str]]:
    if not PROXY_URLS:
        return None
    url = random.choice(PROXY_URLS)
    return {"http": url, "https": url}


def create_session() -> tuple:
    session = requests.Session(impersonate="chrome")
    headers = {
        "User-Agent": random.choice(USER_AGENTS) if USER_AGENTS else "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/option-chain",
    }
    session.headers.update(headers)
    proxies = pick_proxy()
    if proxies:
        session.proxies.update(proxies)

    # Warm up cookies (NSE requires a landing-page visit)
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception as e:
        logger.debug("Landing page warm-up failed (non-fatal): %s", e)
    time.sleep(0.5)
    try:
        session.get("https://www.nseindia.com/option-chain", timeout=10)
    except Exception as e:
        logger.debug("Option chain warm-up failed (non-fatal): %s", e)
    time.sleep(0.5)

    return session, session.cookies.get_dict()


def get_today_expiry(session, symbol: str = "NIFTY", exchange: str = "NSE") -> str:
    """Fetch today's expiry for NSE; fallback for BSE is conservative.

    For BSE the expiry endpoint/format may differ; this function keeps the
    previous behavior (returning NSE expiry when available) and falls back to
    today's date if the call fails.
    """
    if exchange.upper() == "NSE":
        url = f"{NSE_BASE}/api/option-chain-contract-info?symbol={symbol}"
        try:
            res = session.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                expiry_dates = data.get("expiryDates", [])
                if expiry_dates:
                    return expiry_dates[0]
        except Exception as e:
            logger.debug("Could not fetch expiry for %s: %s", symbol, e)
        return datetime.now().strftime("%d-%b-%Y")

    # BSE: no reliable public expiry endpoint in this codebase — return today
    return datetime.now().strftime("%d-%b-%Y")


def _fetch_data_sync(symbol: str, is_index: bool, exchange: str = "NSE") -> Dict[str, Any]:
    """Synchronous fetch with exponential backoff and circuit breaker.

    `exchange` chooses NSE or BSE. Default is NSE to preserve prior behavior.
    """
    if _circuit_is_open(symbol):
        raise NSEFetchError(symbol=symbol, message="Circuit breaker open — skipping fetch")

    session, _ = create_session()
    expiry = get_today_expiry(session, symbol, exchange=exchange)
    type_str = "Indices" if is_index else "Equities"

    if exchange.upper() == "NSE":
        url = f"{NSE_BASE}/api/option-chain-v3?type={type_str}&symbol={symbol}&expiry={expiry}"
    else:
        # NOTE: BSE's DerivOptionChain_IV endpoint uses different query params
        # (e.g. scrip code instead of symbol, and its own expiry format). Keep
        # the previous best-effort URL pattern here; adjust params if you have
        # the authoritative BSE API spec.
        url = f"{BSE_BASE}{BSE_OPTION_CHAIN_PATH}?Scripcode={symbol}&ExpiryDate={expiry}&Type={type_str}"

    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            res = session.get(url, timeout=15)
            if res.status_code == 200:
                try:
                    data = res.json()
                    _record_success(symbol)
                    return data
                except Exception as json_exc:
                    logger.warning("Invalid JSON payload (status 200). Recreating session: %s", json_exc)
                    session, _ = create_session()
                    raise ValueError(f"Invalid JSON payload: {json_exc}")
            if res.status_code in (401, 403, 429):
                backoff = (2 ** attempt) + random.uniform(0, 1)
                logger.warning("HTTP %d for %s (attempt %d). Retrying in %.1fs.",
                               res.status_code, symbol, attempt + 1, backoff)
                time.sleep(backoff)
                continue
            # Unexpected status
            raise NSEFetchError(symbol=symbol, status_code=res.status_code,
                                message=f"Unexpected HTTP {res.status_code}")
        except NSEFetchError:
            raise
        except Exception as exc:
            last_exc = exc
            backoff = (2 ** attempt) + random.uniform(0, 1)
            logger.warning("Fetch error for %s (attempt %d/%d): %s — retrying in %.1fs",
                           symbol, attempt + 1, _MAX_RETRIES, exc, backoff)
            time.sleep(backoff)

    _record_failure(symbol)
    raise NSEFetchError(symbol=symbol, message=f"Max retries exceeded: {last_exc}")


# ── Data Extraction ───────────────────────────────────────────────────────────


def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except (ValueError, TypeError):
        try:
            return int(str(x).replace(",", ""))
        except Exception:
            return None


def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except (ValueError, TypeError):
        return None


def _extract_compact_from_raw(raw: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """
    Extract and compact option chain data, filtering to ATM±5 strikes only.
    """
    out: List[Dict[str, Any]] = []
    records = raw.get("records") or {}
    data = records.get("data") or raw.get("data") or []
    expiry_list = records.get("expiryDates") or []
    expiry: Optional[str] = expiry_list[0] if expiry_list else None

    underlying_value = records.get("underlyingValue")
    spot_price: Optional[float] = None
    try:
        spot_price = float(underlying_value) if underlying_value is not None else None
    except (ValueError, TypeError):
        pass

    atm_strike = None

    # Compute ATM strike for transparency, but do NOT filter strikes — return
    # the full option-chain payload so downstream users can access all strikes.
    if spot_price and data:
        valid_rows = [r for r in data if r.get("strikePrice") is not None]
        if valid_rows:
            all_strikes = sorted(set(r["strikePrice"] for r in valid_rows))
            atm_strike = min(all_strikes, key=lambda x: abs(x - spot_price))
            logger.debug(
                "Computed ATM strike %s from spot=%.0f across %d strikes",
                atm_strike, spot_price, len(all_strikes)
            )

    # Extract ONLY the filtered rows
    for row in data:
        strike = row.get("strikePrice")
        if strike is None:
            continue
        ce = row.get("CE") or {}
        pe = row.get("PE") or {}
        out.append({
            "strike":   strike,
            "call_oi":  _safe_int(ce.get("openInterest", 0)) or 0,
            "call_coi": _safe_int(ce.get("changeinOpenInterest", 0)) or 0,
            "put_oi":   _safe_int(pe.get("openInterest", 0)) or 0,
            "put_coi":  _safe_int(pe.get("changeinOpenInterest", 0)) or 0,
            "call_iv":  _safe_float(ce.get("impliedVolatility")),
            "put_iv":   _safe_float(pe.get("impliedVolatility")),
            "call_ltp": _safe_float(ce.get("lastPrice")),
            "put_ltp":  _safe_float(pe.get("lastPrice")),
        })

    out.sort(key=lambda x: (x["strike"] is None, x["strike"]))

    # Build used_strikes list for frontend transparency
    used_strikes = [r["strike"] for r in out]

    return {
        "symbol":       symbol,
        "expiry":       expiry,
        "spot_price":   spot_price,
        "atm_strike":   atm_strike,
        "used_strikes": used_strikes,
        "data":         out,
    }


async def fetch_option_chain_compact(symbol: str, is_index: bool = True, exchange: str = "NSE") -> Dict[str, Any]:
    """Async wrapper around the synchronous fetch.

    - `exchange`: "NSE" (default) or "BSE".
    - Hard 45-second timeout to prevent thread pool starvation.
    - Returns ATM±5 filtered compact data only.
    """
    loop = asyncio.get_event_loop()
    try:
        raw_data = await asyncio.wait_for(
            loop.run_in_executor(_pool, _fetch_data_sync, symbol, is_index, exchange),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        _record_failure(symbol)
        raise NSEFetchError(symbol=symbol, message="Fetch timed out after 45s")
    compact = _extract_compact_from_raw(raw_data, symbol)
    compact["fetched_at"] = datetime.now(timezone.utc).isoformat()
    compact["exchange"] = exchange.upper()
    return compact