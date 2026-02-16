import csv
from datetime import datetime, timezone
import io
import json
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.core.cache import cache

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "V", "JNJ",
    "PG", "MA", "HD", "CVX", "MRK",
    "KO", "BAC", "WMT", "NFLX", "AMD",
]

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "NVDA": "NVIDIA Corp.",
    "META": "Meta Platforms Inc.",
    "TSLA": "Tesla Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble Co.",
    "MA": "Mastercard Inc.",
    "HD": "Home Depot Inc.",
    "CVX": "Chevron Corp.",
    "MRK": "Merck & Co.",
    "KO": "Coca-Cola Co.",
    "BAC": "Bank of America Corp.",
    "WMT": "Walmart Inc.",
    "NFLX": "Netflix Inc.",
    "AMD": "Advanced Micro Devices Inc.",
}

CACHE_KEY = "market_snapshot"
CACHE_TIMEOUT_SECONDS = 600
STALE_CACHE_KEY = "market_snapshot_stale"


def _build_rows_yahoo_quote():
    symbols = ",".join(UNIVERSE)
    url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols={}".format(
        quote(symbols)
    )
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 Safari/537.36"
            )
        },
    )
    with urlopen(req, timeout=6) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))

    results = payload.get("quoteResponse", {}).get("result", [])
    rows = []
    for item in results:
        symbol = item.get("symbol")
        if symbol not in UNIVERSE:
            continue

        price = item.get("regularMarketPrice")
        prev_close = item.get("regularMarketPreviousClose")
        change_pct = item.get("regularMarketChangePercent")
        if price is None or prev_close in (None, 0) or change_pct is None:
            continue

        rows.append(
            {
                "symbol": symbol,
                "company_name": COMPANY_NAMES.get(symbol, item.get("shortName", symbol)),
                "price": round(float(price), 2),
                "previous_close": round(float(prev_close), 2),
                "change_pct": round(float(change_pct), 2),
            }
        )
    return rows


def _fetch_last_two_closes_stooq(symbol):
    url = "https://stooq.com/q/d/l/?s={}&i=d".format(symbol.lower() + ".us")
    with urlopen(url, timeout=4) as resp:
        text = resp.read().decode("utf-8", errors="ignore")

    parsed_rows = list(csv.DictReader(io.StringIO(text)))
    parsed_rows = [
        row for row in parsed_rows if row.get("Close") and row["Close"] != "N/D"
    ]
    if len(parsed_rows) < 2:
        return None

    parsed_rows.sort(key=lambda row: row["Date"])
    prev_close = float(parsed_rows[-2]["Close"])
    last_price = float(parsed_rows[-1]["Close"])
    if prev_close == 0:
        return None
    return prev_close, last_price


def _build_rows_stooq():
    rows = []
    for symbol in UNIVERSE:
        try:
            values = _fetch_last_two_closes_stooq(symbol)
            if not values:
                continue
            prev_close, last_price = values
            change_pct = ((last_price - prev_close) / prev_close) * 100
            rows.append(
                {
                    "symbol": symbol,
                    "company_name": COMPANY_NAMES.get(symbol, symbol),
                    "price": round(last_price, 2),
                    "previous_close": round(prev_close, 2),
                    "change_pct": round(change_pct, 2),
                }
            )
        except (HTTPError, URLError, ssl.SSLError, socket.timeout, TimeoutError, ValueError):
            continue
    return rows


def _build_rows():
    try:
        rows = _build_rows_yahoo_quote()
        if rows:
            return rows
    except HTTPError as exc:
        if exc.code != 429:
            raise
    except (URLError, ssl.SSLError, socket.timeout, TimeoutError, ValueError):
        pass

    return _build_rows_stooq()


def get_market_snapshot():
    cached = cache.get(CACHE_KEY)
    if cached:
        return cached

    stale = cache.get(STALE_CACHE_KEY)
    context = {
        "generated_at": datetime.now(timezone.utc),
        "stocks": [],
        "top_gainers": [],
        "top_losers": [],
        "error": "",
    }

    try:
        rows = _build_rows()
        rows.sort(key=lambda x: x["change_pct"], reverse=True)
        context["stocks"] = rows
        context["top_gainers"] = rows[:10]
        context["top_losers"] = sorted(rows, key=lambda x: x["change_pct"])[:10]
        cache.set(CACHE_KEY, context, CACHE_TIMEOUT_SECONDS)
        cache.set(STALE_CACHE_KEY, context, 86400)
        return context
    except Exception as exc:
        if stale:
            stale["error"] = (
                "Live update is temporarily limited. Showing last cached data."
            )
            return stale
        context["error"] = str(exc)
        return context
