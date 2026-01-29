# Market Analyzer

Local dashboard that scores popular stocks and commodities over the last ~21 trading days and explains the signal reasons.

## Setup

1) Create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Add API keys (optional but recommended):

```bash
cp .env.example .env
```

Fill in `ALPHA_VANTAGE_KEY` (stocks) and `FRED_API_KEY` (commodities) in `.env`.

3) Run the server:

```bash
python run.py
```

Open http://127.0.0.1:5000

## Customize

- Edit the universe in `app/config.py` (tickers or FRED series IDs).
- Adjust scoring rules in `app/analysis.py`.
