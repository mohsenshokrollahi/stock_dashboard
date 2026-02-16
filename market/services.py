from datetime import datetime, timezone

from django.core.cache import cache
import yfinance as yf

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
CACHE_TIMEOUT_SECONDS = 90


def _extract_close_series(raw_data, symbol):
    if raw_data.empty:
        return None

    if hasattr(raw_data.columns, "levels") and len(raw_data.columns.levels) > 1:
        close_series = None

        # yfinance may return MultiIndex as (symbol, field) OR (field, symbol).
        if symbol in raw_data.columns.levels[0] and "Close" in raw_data.columns.levels[1]:
            close_series = raw_data[(symbol, "Close")].dropna()
        elif "Close" in raw_data.columns.levels[0] and symbol in raw_data.columns.levels[1]:
            close_series = raw_data[("Close", symbol)].dropna()
        else:
            return None
    else:
        if "Close" not in raw_data.columns:
            return None
        close_series = raw_data["Close"].dropna()

    if close_series.empty:
        return None
    return close_series


def _build_rows():
    tickers = " ".join(UNIVERSE)
    raw_data = yf.download(
        tickers=tickers,
        period="5d",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=True,
        group_by="ticker",
    )

    rows = []
    for symbol in UNIVERSE:
        close_series = _extract_close_series(raw_data, symbol)
        # Fallback for symbols missing from the bulk response.
        if close_series is None or len(close_series) < 2:
            symbol_data = yf.download(
                tickers=symbol,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            close_series = _extract_close_series(symbol_data, symbol)

        if close_series is None or len(close_series) < 2:
            continue

        prev_close = float(close_series.iloc[-2])
        last_price = float(close_series.iloc[-1])
        if prev_close == 0:
            continue

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

    return rows


def get_market_snapshot():
    cached = cache.get(CACHE_KEY)
    if cached:
        return cached

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
    except Exception as exc:
        context["error"] = str(exc)

    cache.set(CACHE_KEY, context, CACHE_TIMEOUT_SECONDS)
    return context
