"""
The payoff script: pulls a company's real EBITDA (from SEC EDGAR) and real
total interest expense (from our own engine, built over the last few
steps), and combines them into the actual interest coverage ratio - the
same metric real lenders test against a real covenant threshold.

New idea here: EBITDA isn't one single disclosed number - remember, it
stands for Earnings Before Interest, Taxes, Depreciation and Amortization.
Companies don't file a line item literally called "EBITDA". We have to
build it ourselves from pieces they DO disclose:

    EBITDA (proxy) = Operating Income  +  Depreciation & Amortization

We pull both pieces from SEC EDGAR's XBRL data, using the most recent full
fiscal year ("FY") figures disclosed.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from data_ingest.edgar_client import (  # noqa: E402
    CANDIDATE_TAGS,
    extract_concept_series,
    get_company_facts,
)
from engine.company_interest import total_quarterly_interest  # noqa: E402

TICKER = "DBD"  # Diebold has a real covenant threshold to compare against


def get_latest_annual_value(records):
    """
    From a list of disclosed data points for one concept, keeps only full
    fiscal-year figures ("FY", not a single quarter), and returns the
    most recently reported one.
    """
    annual = [r for r in records if r.get("fp") == "FY" and r.get("val") is not None]
    if not annual:
        return None
    annual.sort(key=lambda r: r["end"], reverse=True)
    return annual[0]


def get_latest_annual_metric(facts, metric_name):
    """
    Tries each candidate XBRL tag for a metric (companies don't all use the
    same tag name) until one returns real data.
    """
    for tag in CANDIDATE_TAGS[metric_name]:
        records = extract_concept_series(facts, tag)
        latest = get_latest_annual_value(records)
        if latest is not None:
            return latest["val"], tag, latest["end"]
    return None, None, None


def get_cik_for_ticker(ticker):
    for c in CANDIDATES:
        if c["ticker"] == ticker:
            return c["cik"]
    raise ValueError(f"{ticker} not found in candidate_companies.py")


def get_latest_covenant_threshold(conn, ticker, covenant_type):
    """
    Only returns a covenant if it's actually CURRENT - meaning it has no
    expiry date, or its expiry date hasn't passed yet. A covenant with a
    past expiry date (like Diebold's pre-2023 schedule, closed out at its
    Chapter 11 filing) is historical, not active, and should NOT be used
    to test today's numbers against.
    """
    row = conn.execute(
        """
        SELECT ct.threshold_value, ct.effective_date
        FROM covenant_terms ct
        JOIN companies c ON ct.company_id = c.company_id
        WHERE c.ticker = ? AND ct.covenant_type = ?
          AND (ct.expiry_date IS NULL OR ct.expiry_date > date('now'))
        ORDER BY ct.effective_date DESC
        LIMIT 1
        """,
        (ticker, covenant_type),
    ).fetchone()
    return row


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    # --- Step 1: total interest expense, from work we already did ---
    total_quarterly, details, skipped = total_quarterly_interest(conn, TICKER)
    annual_interest = total_quarterly * 4

    print(f"INTEREST EXPENSE for {TICKER}")
    print("-" * 60)
    for name, q in details:
        print(f"  {name}: ${q:,.0f} / quarter")
    if skipped:
        for name, reason in skipped:
            print(f"  (skipped: {name} - {reason})")
    print(f"  TOTAL quarterly: ${total_quarterly:,.0f}   ->  annualized: ${annual_interest:,.0f}")
    print()

    # --- Step 2: EBITDA proxy, pulled fresh from SEC EDGAR ---
    cik = get_cik_for_ticker(TICKER)
    print(f"Fetching {TICKER}'s real financials from SEC EDGAR (CIK {cik})...")
    facts = get_company_facts(cik)

    op_income, op_income_tag, op_income_date = get_latest_annual_metric(facts, "operating_income")
    d_and_a, d_and_a_tag, d_and_a_date = get_latest_annual_metric(facts, "depreciation_amortization")

    print()
    print(f"EBITDA (PROXY) for {TICKER}")
    print("-" * 60)
    if op_income is not None:
        print(f"  Operating income ({op_income_tag}, FY ending {op_income_date}): ${op_income:,.0f}")
    else:
        print("  Operating income: not found under any candidate tag - EBITDA cannot be computed")

    if d_and_a is not None:
        print(f"  + Depreciation & amortization ({d_and_a_tag}, FY ending {d_and_a_date}): ${d_and_a:,.0f}")
    else:
        print("  + Depreciation & amortization: not found under any candidate tag")

    if op_income is not None and d_and_a is not None:
        ebitda = op_income + d_and_a
        print(f"  = EBITDA proxy: ${ebitda:,.0f}")
        print()

        # --- Step 3: the actual ratio ---
        coverage_ratio = ebitda / annual_interest
        print(f"INTEREST COVERAGE RATIO for {TICKER}")
        print("-" * 60)
        print(f"  EBITDA (${ebitda:,.0f})  /  Annual interest (${annual_interest:,.0f})")
        print(f"  = {coverage_ratio:.2f}x")
        print()

        # --- Step 4: compare against the real covenant, if we have one ---
        threshold_row = get_latest_covenant_threshold(conn, TICKER, "interest_coverage")
        if threshold_row:
            threshold, effective_date = threshold_row
            print(f"Real disclosed covenant minimum (effective {effective_date}): {threshold}x")
            if coverage_ratio >= threshold:
                print(f"  -> {coverage_ratio:.2f}x >= {threshold}x: covenant PASSES "
                      f"(using today's EBITDA and today's rates)")
            else:
                print(f"  -> {coverage_ratio:.2f}x < {threshold}x: covenant would BREACH "
                      f"(using today's EBITDA and today's rates)")
        else:
            print(f"No interest coverage covenant on file for {TICKER} in our database.")
    else:
        print()
        print("Can't compute EBITDA or the coverage ratio - one of the pieces above is missing.")

    conn.close()
