import csv
from datetime import datetime, timezone
import io
import json
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from django.core.cache import cache
from django.db.models import Avg
from django.utils import timezone as dj_timezone

from .models import DailyLeaderSnapshot

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
    return _build_rows_stooq()


def _status_label(status_key):
    if status_key == DailyLeaderSnapshot.GROUP_WINNER:
        return "Winner"
    if status_key == DailyLeaderSnapshot.GROUP_LOSER:
        return "Loser"
    return "No previous record"


def _attach_previous_status(top_gainers, top_losers):
    symbols = [row["symbol"] for row in (top_gainers + top_losers)]
    if not symbols:
        return

    today = dj_timezone.localdate()
    status_map = {}
    for symbol in symbols:
        previous = (
            DailyLeaderSnapshot.objects.filter(symbol=symbol, snapshot_date__lt=today)
            .order_by("-snapshot_date", "-captured_at")
            .first()
        )
        status_map[symbol] = previous.group if previous else None

    for row in top_gainers + top_losers:
        status_key = status_map.get(row["symbol"])
        row["previous_status"] = status_key or "new"
        row["previous_status_label"] = _status_label(status_key)


def _save_daily_snapshots(top_gainers, top_losers):
    snapshot_date = dj_timezone.localdate()

    for row in top_gainers:
        DailyLeaderSnapshot.objects.update_or_create(
            snapshot_date=snapshot_date,
            symbol=row["symbol"],
            group=DailyLeaderSnapshot.GROUP_WINNER,
            defaults={
                "company_name": row["company_name"],
                "close_price": row["price"],
                "change_pct": row["change_pct"],
            },
        )

    for row in top_losers:
        DailyLeaderSnapshot.objects.update_or_create(
            snapshot_date=snapshot_date,
            symbol=row["symbol"],
            group=DailyLeaderSnapshot.GROUP_LOSER,
            defaults={
                "company_name": row["company_name"],
                "close_price": row["price"],
                "change_pct": row["change_pct"],
            },
        )


def _build_history_chart_data():
    all_dates = list(
        DailyLeaderSnapshot.objects.order_by("snapshot_date")
        .values_list("snapshot_date", flat=True)
        .distinct()
    )
    dates = all_dates[-10:]

    labels = [str(day) for day in dates]
    winners_avg = []
    losers_avg = []

    for day in dates:
        winner_avg = (
            DailyLeaderSnapshot.objects.filter(
                snapshot_date=day,
                group=DailyLeaderSnapshot.GROUP_WINNER,
            ).aggregate(avg=Avg("change_pct"))["avg"]
        )
        loser_avg = (
            DailyLeaderSnapshot.objects.filter(
                snapshot_date=day,
                group=DailyLeaderSnapshot.GROUP_LOSER,
            ).aggregate(avg=Avg("change_pct"))["avg"]
        )

        winners_avg.append(round(float(winner_avg), 2) if winner_avg is not None else None)
        losers_avg.append(round(float(loser_avg), 2) if loser_avg is not None else None)

    return {
        "labels": labels,
        "winner_avg_change": winners_avg,
        "loser_avg_change": losers_avg,
    }


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
        "history_chart_json": json.dumps(
            {"labels": [], "winner_avg_change": [], "loser_avg_change": []}
        ),
        "error": "",
    }

    try:
        rows = _build_rows()
        rows.sort(key=lambda x: x["change_pct"], reverse=True)
        top_gainers = rows[:10]
        top_losers = sorted(rows, key=lambda x: x["change_pct"])[:10]

        _attach_previous_status(top_gainers, top_losers)
        _save_daily_snapshots(top_gainers, top_losers)

        context["stocks"] = rows
        context["top_gainers"] = top_gainers
        context["top_losers"] = top_losers
        context["history_chart_json"] = json.dumps(_build_history_chart_data())

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
