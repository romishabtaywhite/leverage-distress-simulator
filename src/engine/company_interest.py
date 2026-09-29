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


def get_total_debt_balance(conn: sqlite3.Connection, ticker: str):
    """
    Sums the outstanding principal balance across every tranche with a
    confirmed balance, regardless of whether it's floating or fixed rate -
    for a leverage ratio, ALL debt counts, not just the floating-rate piece.
    Returns (total, skipped) so gaps are visible, same pattern as the
    interest function above.
    """
    tranches = get_company_tranches(conn, ticker)
    total = 0.0
    skipped = []

    for t in tranches:
        if t["original_balance"] is None:
            skipped.append((t["tranche_name"], "balance not confirmed in our research"))
            continue
        total += t["original_balance"]

    return total, skipped


def total_quarterly_interest(conn: sqlite3.Connection, ticker: str, sofr_override: float = None):
    """
    Sums quarterly interest across every confirmed tranche for a company.

    By default uses today's REAL latest known SOFR rate. Pass sofr_override
    to instead use a hypothetical rate - this is what makes scenario
    testing possible: "what would this company's interest bill be if SOFR
    were X%?" rather than always answering only for today's actual rate.
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
            rate_to_use = sofr_override if sofr_override is not None else get_latest_rate(conn, "SOFR")
            r = floating_rate_interest(
                balance=t["original_balance"],
                spread_bps=t["spread_bps"],
                reference_rate_pct=rate_to_use,
                floor_pct=t["rate_floor_pct"],
            )
        else:
            skipped.append((name, f"unrecognized rate_type '{t['rate_type']}'"))
            continue

        details.append((name, r["quarterly_interest"]))
        total += r["quarterly_interest"]

    return total, details, skipped
