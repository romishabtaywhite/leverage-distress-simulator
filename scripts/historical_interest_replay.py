"""
Applies the exact same interest calculation as demo_one_tranche.py, but
repeated once per quarter across SOFR's real history - showing how the
cost of this one loan has actually moved over time as rates changed.

New idea introduced here: RESAMPLING. Our rate_series table has a SOFR
value for nearly every single day since 2018 - far more detail than we
need. We only want one value per quarter (the value on the last day of
each quarter), so we use pandas to collapse daily data down to quarterly
data. This is an extremely common step in any project involving
time-series data, not something specific to finance.

SIMPLIFICATION we're deliberately making here: this treats the loan
balance as constant at $3 billion for the entire history, which isn't
literally true (this exact loan didn't exist before 2025, and real loans
amortize down over time). The point right now is purely to build
intuition for how much the RATE side of the equation alone can move the
interest bill - Phase 2's later steps will add the balance-over-time
piece properly.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from engine.interest import floating_rate_interest  # noqa: E402

BALANCE = 3_000_000_000
SPREAD_BPS = 625
FLOOR_PCT = 0.0


def get_quarterly_sofr(conn):
    """Reads all daily SOFR observations, then keeps only the last
    observation in each calendar quarter."""
    df = pd.read_sql(
        "SELECT obs_date, value FROM rate_series WHERE series_code = 'SOFR' ORDER BY obs_date",
        conn,
        parse_dates=["obs_date"],
    )
    df = df.set_index("obs_date")
    quarterly = df.resample("QE").last().dropna()  # "QE" = quarter-end
    return quarterly


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    quarterly_sofr = get_quarterly_sofr(conn)
    conn.close()

    print(f"{'Quarter':<12}{'SOFR':>8}{'Effective Rate':>16}{'Quarterly Interest':>22}")
    print("-" * 58)

    results = []
    for date, row in quarterly_sofr.iterrows():
        r = floating_rate_interest(
            balance=BALANCE,
            spread_bps=SPREAD_BPS,
            reference_rate_pct=row["value"],
            floor_pct=FLOOR_PCT,
        )
        results.append((date, r))
        quarter_label = f"{date.year} Q{date.quarter}"
        print(
            f"{quarter_label:<12}{r['reference_rate_pct']:>7.2f}%"
            f"{r['effective_rate_pct']:>15.2f}%"
            f"{r['quarterly_interest']:>20,.0f}"
        )

    lowest = min(results, key=lambda x: x[1]["quarterly_interest"])
    highest = max(results, key=lambda x: x[1]["quarterly_interest"])

    print()
    print(f"Cheapest quarter:  {lowest[0].year} Q{lowest[0].quarter} "
          f"-> ${lowest[1]['quarterly_interest']:,.0f}")
    print(f"Priciest quarter:  {highest[0].year} Q{highest[0].quarter} "
          f"-> ${highest[1]['quarterly_interest']:,.0f}")
    print(f"Difference:        ${highest[1]['quarterly_interest'] - lowest[1]['quarterly_interest']:,.0f} "
          f"more per quarter, on the exact same $3B balance, purely from the rate moving.")
