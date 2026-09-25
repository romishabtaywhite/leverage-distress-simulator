"""
Pulls Bausch Health's real 2030 Term Loan B tranche and the most recent
real SOFR value out of YOUR database, then runs the interest calculation
on real numbers - not made-up ones. Run this and read the printed
explanation alongside src/engine/interest.py to see exactly how the pieces
connect.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from engine.interest import floating_rate_interest  # noqa: E402


def get_bausch_term_loan_b(conn):
    """Pulls the one tranche we want out of debt_tranches."""
    row = conn.execute(
        """
        SELECT dt.tranche_name, dt.spread_bps, dt.original_balance, dt.rate_floor_pct
        FROM debt_tranches dt
        JOIN companies c ON dt.company_id = c.company_id
        WHERE c.ticker = 'BHC' AND dt.tranche_name = '2030 Term Loan B Facility'
        """
    ).fetchone()
    if row is None:
        raise RuntimeError(
            "Couldn't find Bausch Health's Term Loan B - did you run "
            "scripts/seed_debt_data.py yet?"
        )
    return {"tranche_name": row[0], "spread_bps": row[1], "balance": row[2], "floor_pct": row[3]}


def get_latest_sofr(conn):
    """Pulls the single most recent SOFR observation out of rate_series."""
    row = conn.execute(
        """
        SELECT obs_date, value FROM rate_series
        WHERE series_code = 'SOFR'
        ORDER BY obs_date DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        raise RuntimeError(
            "No SOFR data found - did you run src/data_ingest/fred_client.py "
            "and load it into the database yet?"
        )
    return {"obs_date": row[0], "value": row[1]}


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    tranche = get_bausch_term_loan_b(conn)
    sofr = get_latest_sofr(conn)

    print("=" * 60)
    print("REAL DATA PULLED FROM YOUR DATABASE")
    print("=" * 60)
    print(f"Tranche:          {tranche['tranche_name']}")
    print(f"Balance:          ${tranche['balance']:,.0f}")
    print(f"Spread:           {tranche['spread_bps']} basis points "
          f"({tranche['spread_bps'] / 100:.2f}%)")
    print(f"Most recent SOFR: {sofr['value']:.2f}% (as of {sofr['obs_date']})")
    print()

    result = floating_rate_interest(
        balance=tranche["balance"],
        spread_bps=tranche["spread_bps"],
        reference_rate_pct=sofr["value"],
        floor_pct=tranche["floor_pct"],
    )

    print("=" * 60)
    print("THE CALCULATION")
    print("=" * 60)
    print(f"Reference rate (SOFR):        {result['reference_rate_pct']:.2f}%")
    print(f"+ Spread:                     {result['spread_pct']:.2f}%")
    print(f"= Effective interest rate:    {result['effective_rate_pct']:.2f}%")
    print()
    print(f"Annual interest on ${tranche['balance']:,.0f}:")
    print(f"  = ${tranche['balance']:,.0f} x {result['effective_rate_pct']:.2f}%")
    print(f"  = ${result['annual_interest']:,.0f} per year")
    print()
    print(f"Quarterly interest (what shows up on one quarter's income statement):")
    print(f"  = ${result['quarterly_interest']:,.0f} per quarter")

    conn.close()
