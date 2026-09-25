"""
Reusable version of the tranche-summing logic from demo_company_total_interest.py.
Pulled into the engine module so other scripts can call it directly instead
of copy-pasting the same loop.
"""

import sqlite3

from engine.interest import fixed_rate_interest, floating_rate_interest


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


def total_quarterly_interest(conn: sqlite3.Connection, ticker: str):
    """
    Sums quarterly interest across every confirmed tranche for a company,
    using today's latest known rates. Returns (total, details, skipped) so
    callers can inspect exactly what was included and what wasn't.
    """
    tranches = get_company_tranches(conn, ticker)
    total = 0.0
    details = []
    skipped = []

    for t in tranches:
        name = t["tranche_name"]

        if t["rate_type"] == "fixed":
            if t["fixed_rate_pct"] is None or t["original_balance"] is None:
                skipped.append((name, "fixed rate or balance not confirmed in our research"))
                continue
            r = fixed_rate_interest(t["original_balance"], t["fixed_rate_pct"])

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
        else:
            skipped.append((name, f"unrecognized rate_type '{t['rate_type']}'"))
            continue

        details.append((name, r["quarterly_interest"]))
        total += r["quarterly_interest"]

    return total, details, skipped
