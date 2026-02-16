<<<<<<< HEAD
# Stock Dashboard (Django)

This project shows:
- Top 10 winner stocks today
- Top 10 loser stocks today
- All tracked stock status
- Auto page refresh every 2 minutes

## Ubuntu setup

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential

cd stock_dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Open: `http://127.0.0.1:8000`

## Notes

- Data source: Yahoo Finance via `yfinance`.
- "All stock status" means all symbols in the tracked universe in `market/services.py`.
- The page auto-refreshes every 120 seconds.
=======
# stock_dashboard
>>>>>>> e6dba0c3cc9dab76091219a5f03fa976c67e9609
