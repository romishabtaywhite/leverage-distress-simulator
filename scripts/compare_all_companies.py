"""
Runs the full chain - total debt, EBITDA, interest expense, leverage ratio,
interest coverage ratio - for all 4 companies at once, and prints a
side-by-side comparison table.

Note on Party City: it's fully liquidated (see candidate_companies.py), so
SEC EDGAR only has its LAST disclosed EBITDA from before its 2023 Chapter 11
filing - there's no "today" for a company that no longer operates. That's
intentional here, not a bug: we're using Party City as a historical case,
not a live one.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from engine.company_interest import get_total_debt_balance, total_quarterly_interest  # noqa: E402
from engine.ebitda import get_ebitda_proxy  # noqa: E402


def get_cik_for_ticker(ticker):
    for c in CANDIDATES:
        if c["ticker"] == ticker:
            return c["cik"]
    raise ValueError(f"{ticker} not found in candidate_companies.py")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    results = []

    for c in CANDIDATES:
        ticker = c["ticker"]
        if ticker == "AAPL":
            continue  # not a leverage case study - skip in this comparison

        print(f"Processing {ticker} ({c['name']})...")

        total_debt, debt_skipped = get_total_debt_balance(conn, ticker)
        total_quarterly, interest_details, interest_skipped = total_quarterly_interest(conn, ticker)
        annual_interest = total_quarterly * 4

        cik = get_cik_for_ticker(ticker)
        ebitda, adjusted_ebitda, ebitda_details = get_ebitda_proxy(cik)

        row = {
            "ticker": ticker,
            "total_debt": total_debt,
            "annual_interest": annual_interest,
            "ebitda": ebitda,
            "adjusted_ebitda": adjusted_ebitda,
            "impairment_addback": ebitda_details.get("impairment_addback", 0.0) or 0.0,
            "ebitda_as_of": ebitda_details.get("operating_income_date"),
            "is_distressed": c["is_distressed"],
        }

        # Use ADJUSTED EBITDA for the ratios - one-time non-cash impairment
        # charges shouldn't drive a "can this company service its debt?"
        # metric, the same way a real lender's covenant test wouldn't count them.
        if adjusted_ebitda is not None and adjusted_ebitda > 0 and annual_interest > 0:
            row["leverage_ratio"] = total_debt / adjusted_ebitda
            row["coverage_ratio"] = adjusted_ebitda / annual_interest
        else:
            row["leverage_ratio"] = None
            row["coverage_ratio"] = None

        results.append(row)

    print()
    header = (f"{'Ticker':<8}{'Total Debt':>15}{'Ann. Interest':>16}{'Adj. EBITDA':>15}"
              f"{'(as of)':>12}{'Leverage':>11}{'Coverage':>11}{'Distressed?':>13}")
    print(header)
    print("-" * len(header))

    for r in results:
        leverage_str = f"{r['leverage_ratio']:.2f}x" if r["leverage_ratio"] is not None else "undefined"
        coverage_str = f"{r['coverage_ratio']:.2f}x" if r["coverage_ratio"] is not None else "undefined"
        distressed_str = "Yes" if r["is_distressed"] else "No"
        ebitda_str = f"{r['adjusted_ebitda']:,.0f}" if r["adjusted_ebitda"] is not None else "not found"
        as_of_str = r["ebitda_as_of"] if r["ebitda_as_of"] is not None else "n/a"

        print(f"{r['ticker']:<8}{r['total_debt']:>15,.0f}{r['annual_interest']:>16,.0f}"
              f"{ebitda_str:>15}{as_of_str:>12}{leverage_str:>11}"
              f"{coverage_str:>11}{distressed_str:>13}")

    print()
    print("Impairment add-backs applied (raw EBITDA -> Adjusted EBITDA):")
    any_addback = False
    for r in results:
        if r["impairment_addback"]:
            any_addback = True
            print(f"  {r['ticker']}: raw EBITDA ${r['ebitda']:,.0f}  +  impairment add-back "
                  f"${r['impairment_addback']:,.0f}  =  adjusted EBITDA ${r['adjusted_ebitda']:,.0f}")
    if not any_addback:
        print("  (none of these companies had a disclosed impairment charge in their most recent fiscal year)")

    conn.close()
