from django.shortcuts import render

from .services import get_market_snapshot


def dashboard(request):
    context = get_market_snapshot()
    return render(request, "market/dashboard.html", context)
