"""
Extends the deep tranche-level research (previously only DBD, BHC, CYH,
PRTYQ) to two more currently-public companies: Charter Communications and
American Airlines.

BOTH of these companies have capital structures far more complex than the
original 4 - dozens of fixed-rate note series across multiple issuing
entities, with only a modest slice of real floating-rate bank debt on
top. Cataloging every individual note would be a huge undertaking with
little payoff. Instead: model the REAL disclosed floating tranche exactly
(balance, spread, floor - all real, verified figures), then DERIVE an
implied blended rate for the remaining "fixed" balance that exactly
reproduces the company's REAL total interest expense today (already
pulled and verified via static_features.py during the ML dataset build).

This is a genuine decomposition, not a guess: the floating piece is 100%
real disclosed terms; the "fixed" piece's rate is solved for algebraically
so that floating_interest + fixed_interest = the company's actual real
total interest expense at today's actual real SOFR. It is explicitly NOT
any single real bond's coupon - it's a blended average, and is labeled
as such everywhere it's used.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.edgar_client import get_cik_for_ticker  # noqa: E402
from engine.company_interest import get_latest_rate  # noqa: E402

# Real, disclosed floating-rate tranches, verified via each company's
# actual FY2025 10-K / recent 8-K credit agreement amendments.
NEW_COMPANIES = {
    "CHTR": {
        "name": "Charter Communications, Inc.",
        "is_distressed": 0,
        "notes": "Real floating tranche is a weighted blend of its CCO Holdings credit "
                 "facility term loans (A-6, A-7, B-3, B-4, B-5) plus drawn revolver, "
                 "~$12.04B at a balance-weighted spread of ~165bps over SOFR, 0% floor, "
                 "per its FY2025 10-K. This is ~13% of Charter's total $94.8B debt - the "
                 "rest is fixed-rate notes across many series, deliberately not "
                 "individually catalogued (see script docstring).",
        "floating_balance": 12_042_000_000,
        "floating_spread_bps": 165,
        "floating_floor_pct": 0.0,
    },
    "AAL": {
        "name": "American Airlines Group Inc.",
        "is_distressed": 0,
        "notes": "Real floating tranche is the $1.85B 2026 Term Loans (SOFR + 3.00%, 0% "
                 "floor), the most recent and largest single credit facility per its "
                 "May 2026 8-K amendment. The bulk of AAL's remaining debt is aircraft-"
                 "secured EETC financing, mostly fixed-rate - not individually "
                 "catalogued (see script docstring).",
        "floating_balance": 1_850_000_000,
        "floating_spread_bps": 300,
        "floating_floor_pct": 0.0,
    },
}


def get_or_create_company_id(conn, ticker, name, cik, is_distressed, notes):
    row = conn.execute("SELECT company_id FROM companies WHERE ticker = ?", (ticker,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO companies (name, ticker, cik, is_distressed, notes) VALUES (?, ?, ?, ?, ?)",
        (name, ticker, cik, is_distressed, notes),
    )
    return cur.lastrowid


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    current_sofr = get_latest_rate(conn, "SOFR")

    for ticker, info in NEW_COMPANIES.items():
        # Pull the company's REAL total debt, interest expense, EBITDA -
        # already computed and verified during the ML dataset build.
        row = conn.execute(
            "SELECT total_debt, interest_expense, adjusted_ebitda FROM ml_dataset WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if row is None:
            print(f"{ticker}: not found in ml_dataset - run build_ml_dataset.py first. Skipping.")
            continue
        total_debt, total_interest_expense, adjusted_ebitda = row

        floating_balance = info["floating_balance"]
        spread_pct = info["floating_spread_bps"] / 100
        floating_rate_today = max(current_sofr, info["floating_floor_pct"]) + spread_pct
        floating_interest_today = floating_balance * (floating_rate_today / 100)

        fixed_balance = total_debt - floating_balance
        fixed_interest = total_interest_expense - floating_interest_today
        implied_fixed_rate_pct = (fixed_interest / fixed_balance) * 100

        print(f"{ticker}:")
        print(f"  Real total debt: ${total_debt:,.0f}, real total interest expense: ${total_interest_expense:,.0f}")
        print(f"  Floating tranche: ${floating_balance:,.0f} @ SOFR+{info['floating_spread_bps']}bps "
              f"= {floating_rate_today:.2f}% today -> ${floating_interest_today:,.0f}/yr")
        print(f"  Implied fixed remainder: ${fixed_balance:,.0f} @ {implied_fixed_rate_pct:.2f}% "
              f"(derived, not a single real coupon) -> ${fixed_interest:,.0f}/yr")

        if implied_fixed_rate_pct < 0 or implied_fixed_rate_pct > 15:
            print(f"  WARNING: implied fixed rate {implied_fixed_rate_pct:.2f}% is implausible - "
                  f"skipping this company rather than seed a nonsensical figure.")
            print()
            continue

        cik = get_cik_for_ticker(ticker)
        company_id = get_or_create_company_id(conn, ticker, info["name"], cik,
                                              info["is_distressed"], info["notes"])

        conn.execute("DELETE FROM debt_tranches WHERE company_id = ?", (company_id,))
        conn.execute(
            """INSERT INTO debt_tranches
               (company_id, tranche_name, tranche_type, rate_type, reference_rate,
                spread_bps, rate_floor_pct, fixed_rate_pct, original_balance,
                seniority_rank, source_accession)
               VALUES (?, ?, 'term_loan', 'floating', 'SOFR', ?, ?, NULL, ?, 1, ?)""",
            (company_id, f"{ticker} real disclosed floating tranche", info["floating_spread_bps"],
             info["floating_floor_pct"], floating_balance, "Verified via FY2025/2026 10-K and 8-K filings"),
        )
        conn.execute(
            """INSERT INTO debt_tranches
               (company_id, tranche_name, tranche_type, rate_type, reference_rate,
                spread_bps, rate_floor_pct, fixed_rate_pct, original_balance,
                seniority_rank, source_accession)
               VALUES (?, ?, 'senior_notes', 'fixed', NULL, NULL, NULL, ?, ?, 2, ?)""",
            (company_id, f"{ticker} implied blended fixed remainder (DERIVED, not a real single coupon)",
             implied_fixed_rate_pct, fixed_balance,
             "Derived to reproduce real total interest expense - see script docstring"),
        )
        conn.commit()
        print(f"  Seeded 2 tranches for company_id={company_id}")
        print()

    conn.close()
