"""
Computes the leverage ratio (Total Debt / EBITDA) for a real company and
tests it against the real covenant threshold on file - completing the
second half of the covenant pair we started with interest coverage.

IMPORTANT DIRECTION DIFFERENCE from interest coverage:
  - Interest coverage covenant = a MINIMUM. Breach = falling BELOW it.
  - Leverage ratio covenant    = a MAXIMUM. Breach = rising ABOVE it.
Easy to mix up, so the code below spells out which direction it's
checking rather than leaving it implicit.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from engine.company_interest import get_total_debt_balance  # noqa: E402
from engine.ebitda import get_ebitda_proxy  # noqa: E402

TICKER = "DBD"  # change to try other companies


def get_cik_for_ticker(ticker):
    for c in CANDIDATES:
        if c["ticker"] == ticker:
            return c["cik"]
    raise ValueError(f"{ticker} not found in candidate_companies.py")


def get_current_leverage_covenant(conn, ticker):
    """Only a covenant with no expiry, or an expiry still in the future, counts as current."""
    row = conn.execute(
        """
        SELECT ct.threshold_value, ct.effective_date
        FROM covenant_terms ct
        JOIN companies c ON ct.company_id = c.company_id
        WHERE c.ticker = ? AND ct.covenant_type = 'leverage_ratio'
          AND (ct.expiry_date IS NULL OR ct.expiry_date > date('now'))
        ORDER BY ct.effective_date DESC
        LIMIT 1
        """,
        (ticker,),
    ).fetchone()
    return row


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    # --- Total debt: sum of every confirmed tranche balance ---
    total_debt, skipped_debt = get_total_debt_balance(conn, TICKER)
    print(f"TOTAL DEBT for {TICKER}")
    print("-" * 60)
    print(f"  Sum of confirmed tranche balances: ${total_debt:,.0f}")
    for name, reason in skipped_debt:
        print(f"  (excluded: {name} - {reason})")
    print()

    # --- EBITDA: same real EDGAR pull as before ---
    cik = get_cik_for_ticker(TICKER)
    print(f"Fetching {TICKER}'s real financials from SEC EDGAR (CIK {cik})...")
    ebitda, details = get_ebitda_proxy(cik)

    if ebitda is None:
        print("Couldn't compute EBITDA - one of the required disclosures is missing.")
        conn.close()
        raise SystemExit(0)

    print(f"  Operating income ({details['operating_income_tag']}, "
          f"FY ending {details['operating_income_date']}): ${details['operating_income']:,.0f}")
    print(f"  + D&A ({details['depreciation_amortization_tag']}, "
          f"FY ending {details['depreciation_amortization_date']}): "
          f"${details['depreciation_amortization']:,.0f}")
    print(f"  = EBITDA proxy: ${ebitda:,.0f}")
    print()

    # --- The actual ratio ---
    leverage_ratio = total_debt / ebitda
    print(f"LEVERAGE RATIO for {TICKER}")
    print("-" * 60)
    print(f"  Total debt (${total_debt:,.0f})  /  EBITDA (${ebitda:,.0f})")
    print(f"  = {leverage_ratio:.2f}x")
    print(f"  (in plain terms: it would take {leverage_ratio:.2f} years of EBITDA at this level")
    print(f"   to pay off all of {TICKER}'s confirmed debt)")
    print()

    # --- Compare against the real covenant, if current ---
    threshold_row = get_current_leverage_covenant(conn, TICKER)
    if threshold_row:
        threshold, effective_date = threshold_row
        print(f"Real disclosed covenant MAXIMUM (effective {effective_date}): {threshold}x")
        if leverage_ratio <= threshold:
            print(f"  -> {leverage_ratio:.2f}x <= {threshold}x: covenant PASSES "
                  f"(leverage ratio covenants breach when you go OVER the max)")
        else:
            print(f"  -> {leverage_ratio:.2f}x > {threshold}x: covenant would BREACH")
    else:
        print(f"No CURRENT leverage ratio covenant on file for {TICKER}.")

    conn.close()
