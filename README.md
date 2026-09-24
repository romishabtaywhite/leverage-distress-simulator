# Leveraged Finance Distress Simulator

**Research question:** Given a real leveraged capital structure with floating-rate
(SOFR-indexed) debt, how did the 2020-2026 rate cycle affect interest coverage,
covenant headroom, and sponsor equity returns - and which capital-structure
features best predict which credits are most vulnerable to distress under
rate stress?

Full project roadmap: see project notes / roadmap doc.

## Phase 1 setup

1. Clone this repo and `cd` into it.
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate      # on Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and fill in:
   - `FRED_API_KEY` - free, register at https://fred.stlouisfed.org/docs/api/api_key.html
   - `SEC_EDGAR_USER_AGENT` - your name + email (SEC requires this, no key needed)
5. Initialize the database:
   ```
   python scripts/init_db.py
   ```
6. Smoke-test the data clients:
   ```
   python src/data_ingest/edgar_client.py
   python src/data_ingest/fred_client.py
   ```
   Both should run without errors and print some output confirming data was pulled.

## Project structure

```
leverage-distress-simulator/
├── README.md
├── requirements.txt
├── .env.example
├── db/
│   ├── schema.sql
│   └── leverage_sim.db        (created locally, gitignored)
├── data/
│   ├── raw/                    (gitignored)
│   └── cache/                  (gitignored - EDGAR API response cache)
├── src/
│   └── data_ingest/
│       ├── edgar_client.py
│       ├── fred_client.py
│       └── candidate_companies.py
└── scripts/
    └── init_db.py
```
