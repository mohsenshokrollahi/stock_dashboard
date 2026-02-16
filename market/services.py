from datetime import datetime, timezone

from django.core.cache import cache
import yfinance as yf

UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "UNH", "XOM",
    "LLY", "JPM", "V", "JNJ", "PG", "MA", "AVGO", "HD", "CVX", "MRK",
    "COST", "ABBV", "PEP", "KO", "ADBE", "BAC", "WMT", "MCD", "CSCO", "CRM",
    "ACN", "TMO", "NFLX", "AMD", "LIN", "DHR", "ABT", "INTC", "NKE", "VZ",
    "QCOM", "CMCSA", "TXN", "INTU", "PFE", "HON", "ORCL", "PM", "IBM", "COP",
]

CACHE_KEY = "market_snapshot"
CACHE_TIMEOUT_SECONDS = 90


def _extract_close_series(raw_data, symbol):
    if raw_data.empty:
        return None

    if hasattr(raw_data.columns, "levels") and len(raw_data.columns.levels) > 1:
        if symbol not in raw_data.columns.levels[0]:
            return None
        close_series = raw_data[(symbol, "Close")].dropna()
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
