"""
Same interest calculation as before, but now summed across ALL of a real
company's debt tranches at once - some floating, some fixed - to get one
number: total interest expense for the whole company, right now.

Honest handling of gaps: a few tranches in our researched data are missing
a confirmed spread or balance (we flagged these explicitly when the data
was entered). Rather than guessing a number to fill the gap, this script
skips those tranches and tells you exactly why - so the total you get is
always traceable back to real, confirmed inputs only.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from engine.interest import fixed_rate_interest, floating_rate_interest  # noqa: E402

TICKER = "BHC"  # change this to DBD, CYH, or PRTYQ to try other companies


def get_company_tranches(conn, ticker):
    rows = conn.execute(
        """
        SELECT dt.tranche_name, dt.rate_type, dt.reference_rate, dt.spread_bps,
               dt.rate_floor_pct, dt.fixed_rate_pct, dt.original_balance
        FROM debt_tranches dt
        JOIN companies c ON dt.company_id = c.company_id
        WHERE c.ticker = ?
        """,
        (ticker,),
    ).fetchall()
    columns = ["tranche_name", "rate_type", "reference_rate", "spread_bps",
               "rate_floor_pct", "fixed_rate_pct", "original_balance"]
    return [dict(zip(columns, row)) for row in rows]


def get_latest_rate(conn, series_code):
    row = conn.execute(
        "SELECT value FROM rate_series WHERE series_code = ? ORDER BY obs_date DESC LIMIT 1",
        (series_code,),
    ).fetchone()
    return row[0] if row else None


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    tranches = get_company_tranches(conn, TICKER)

    print(f"Tranches found for {TICKER}: {len(tranches)}")
    print("=" * 70)

    total_quarterly_interest = 0.0
    skipped = []

    for t in tranches:
        name = t["tranche_name"]

        if t["rate_type"] == "fixed":
            if t["fixed_rate_pct"] is None or t["original_balance"] is None:
                skipped.append((name, "fixed rate or balance not confirmed in our research"))
                continue
            r = fixed_rate_interest(t["original_balance"], t["fixed_rate_pct"])
            print(f"{name}")
            print(f"  Fixed rate: {t['fixed_rate_pct']:.3f}%  |  Balance: ${t['original_balance']:,.0f}")
            print(f"  -> Quarterly interest: ${r['quarterly_interest']:,.0f}")

        elif t["rate_type"] == "floating":
            if t["spread_bps"] is None or t["original_balance"] is None:
                skipped.append((name, "spread or balance not confirmed in our research"))
                continue
            if t["reference_rate"] != "SOFR":
                skipped.append((name, f"reference rate is {t['reference_rate']}, "
                                       f"and we've only loaded SOFR history so far"))
                continue

            latest_rate = get_latest_rate(conn, "SOFR")
            r = floating_rate_interest(
                balance=t["original_balance"],
                spread_bps=t["spread_bps"],
                reference_rate_pct=latest_rate,
                floor_pct=t["rate_floor_pct"],
            )
            print(f"{name}")
            print(f"  SOFR: {latest_rate:.2f}%  +  Spread: {r['spread_pct']:.2f}%  "
                  f"=  Effective rate: {r['effective_rate_pct']:.2f}%  |  "
                  f"Balance: ${t['original_balance']:,.0f}")
            print(f"  -> Quarterly interest: ${r['quarterly_interest']:,.0f}")

        else:
            skipped.append((name, f"unrecognized rate_type '{t['rate_type']}'"))
            continue

        total_quarterly_interest += r["quarterly_interest"]
        print()

    if skipped:
        print("-" * 70)
        print("Skipped (not included in the total below):")
        for name, reason in skipped:
            print(f"  - {name}: {reason}")
        print()

    print("=" * 70)
    print(f"TOTAL quarterly interest expense for {TICKER} "
          f"(from confirmed tranches only): ${total_quarterly_interest:,.0f}")
    print(f"Implied annual run-rate: ${total_quarterly_interest * 4:,.0f}")

    conn.close()
