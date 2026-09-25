"""
Pulls all the FRED series (SOFR, credit spreads, Fed Funds Rate) and saves
them into the rate_series table, so other scripts (like demo_one_tranche.py)
can read rates straight from the database instead of hitting the FRED API
every single time.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from data_ingest.fred_client import get_all_series  # noqa: E402

if __name__ == "__main__":
    print("Fetching series from FRED (this hits the real FRED API)...")
    df = get_all_series()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM rate_series")  # safe to rerun - clears and reloads fresh

    rows = [
        (row.series_code, str(row.obs_date.date()), None if pd.isna(row.value) else float(row.value))
        for row in df.itertuples()
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO rate_series (series_code, obs_date, value) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM rate_series").fetchone()[0]
    print(f"Loaded {count} rate observations into rate_series.")

    conn.close()
