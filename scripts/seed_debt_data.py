"""
Seeds the database with the 4 candidate companies, plus a fully worked
example of real debt tranche + covenant data for Diebold Nixdorf.

IMPORTANT: The Diebold Nixdorf figures below are transcribed from real SEC
10-Q/10-K debt footnotes (FY2021-2023 filings, CIK 0000028823) found during
research, but table extraction from filings is imperfect - some column
headers were ambiguous in the source. Before relying on these for anything
beyond a working prototype, pull the actual filing text yourself at
https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000028823
and confirm exact figures, dates, and which covenant threshold applies to
which specific quarter.

Bausch Health, Community Health Systems, and Party City are seeded as
companies only - their debt_tranches and covenant_terms rows are left for
you to research and add the same way, using this script as the template.
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))


def get_or_create_company(conn, ticker, name, cik, is_distressed, distress_date, notes):
    cur = conn.execute("SELECT company_id FROM companies WHERE cik = ?", (cik,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        """INSERT INTO companies (name, ticker, cik, is_distressed, distress_date, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, ticker, cik, is_distressed, distress_date, notes),
    )
    return cur.lastrowid


def seed_companies(conn):
    from data_ingest.candidate_companies import CANDIDATES

    ids = {}
    for c in CANDIDATES:
        company_id = get_or_create_company(
            conn, c["ticker"], c["name"], c["cik"], c["is_distressed"], c["distress_date"], c["notes"]
        )
        ids[c["ticker"]] = company_id
        print(f"Company: {c['name']} ({c['ticker']}) -> company_id={company_id}")
    return ids


def seed_diebold_debt_tranches(conn, company_id):
    """
    Real disclosed tranches, transcribed from Diebold Nixdorf's FY2021 10-Q
    and FY2023 10-Q debt footnotes. Balances are in USD millions in the
    source filings - converted to raw dollars here for schema consistency.
    """
    conn.execute("DELETE FROM debt_tranches WHERE company_id = ?", (company_id,))

    tranches = [
        {
            "tranche_name": "2022 Term Loan A Facility",
            "tranche_type": "term_loan",
            "rate_type": "floating",
            "reference_rate": "LIBOR",
            "spread_bps": 425,  # LIBOR + 4.25%
            "rate_floor_pct": None,
            "fixed_rate_pct": None,
            "original_balance": None,  # not clearly isolated in the extracted table - verify in filing
            "as_of_date": "2021-06-30",
            "maturity_date": None,  # disclosed as "3 years" from a 2020 amendment - verify exact date
            "seniority_rank": 1,
            "source_accession": "SEC 10-Q filed re: quarter ended Jun 30 2021, CIK 0000028823",
        },
        {
            "tranche_name": "Term Loan B (USD)",
            "tranche_type": "term_loan",
            "rate_type": "floating",
            "reference_rate": "LIBOR",
            "spread_bps": 275,  # LIBOR + 2.75%
            "rate_floor_pct": None,
            "fixed_rate_pct": None,
            "original_balance": 381_000_000,  # balance as of Dec 31, 2021 per FY2022 10-K
            "as_of_date": "2021-12-31",
            "maturity_date": None,
            "seniority_rank": 1,
            "source_accession": "SEC 10-K FY2022, CIK 0000028823 (balance fully repaid by Dec 2022)",
        },
        {
            "tranche_name": "Term Loan B (EUR)",
            "tranche_type": "term_loan",
            "rate_type": "floating",
            "reference_rate": "EURIBOR",
            "spread_bps": 300,  # EURIBOR + 3.00%
            "rate_floor_pct": None,
            "fixed_rate_pct": None,
            "original_balance": 375_600_000,  # balance as of Dec 31, 2021 per FY2022 10-K
            "as_of_date": "2021-12-31",
            "maturity_date": None,
            "seniority_rank": 1,
            "source_accession": "SEC 10-K FY2022, CIK 0000028823 (balance fully repaid by Dec 2022)",
        },
        {
            "tranche_name": "2025 New Term Loan B Facility (USD)",
            "tranche_type": "term_loan",
            "rate_type": "floating",
            "reference_rate": "SOFR",  # post-LIBOR transition facility - confirm exact reference rate/spread in filing
            "spread_bps": None,  # not isolated in extracted table - verify in filing text
            "rate_floor_pct": None,
            "fixed_rate_pct": None,
            "original_balance": 529_500_000,  # balance as of Dec 31, 2022 per FY2023 10-Q
            "as_of_date": "2022-12-31",
            "maturity_date": None,
            "seniority_rank": 1,
            "source_accession": "SEC 10-Q filed re: quarter ended Jun 30 2023, CIK 0000028823",
        },
        {
            "tranche_name": "2026 2L Notes",
            "tranche_type": "sub_notes",
            "rate_type": "fixed",
            "reference_rate": None,
            "spread_bps": None,
            "rate_floor_pct": None,
            "fixed_rate_pct": None,  # coupon not isolated in extracted table - verify in filing
            "original_balance": 333_600_000,
            "as_of_date": "2022-12-31",
            "maturity_date": "2026-01-01",  # approximate from name - verify exact date
            "seniority_rank": 2,
            "source_accession": "SEC 10-Q filed re: quarter ended Jun 30 2023, CIK 0000028823",
        },
    ]

    for t in tranches:
        conn.execute(
            """INSERT INTO debt_tranches
               (company_id, tranche_name, tranche_type, rate_type, reference_rate,
                spread_bps, rate_floor_pct, fixed_rate_pct, original_balance,
                as_of_date, maturity_date, seniority_rank, source_accession)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                company_id, t["tranche_name"], t["tranche_type"], t["rate_type"],
                t["reference_rate"], t["spread_bps"], t["rate_floor_pct"], t["fixed_rate_pct"],
                t["original_balance"], t["as_of_date"], t["maturity_date"],
                t["seniority_rank"], t["source_accession"],
            ),
        )
    print(f"Inserted {len(tranches)} debt tranches for company_id={company_id}")


def seed_diebold_covenants(conn, company_id):
    """
    Real disclosed covenant step schedule from Diebold's FY2021 10-Q. This
    is a genuine "amend and extend" style covenant relief schedule - exactly
    the mechanic your simulation engine needs to test against.

    Note: the source XBRL table had some ambiguous column alignment between
    "current" and "subsequent event" (i.e. forward-scheduled) values - the
    dates below are my best reconstruction. Verify against the actual filed
    credit agreement amendment before treating these as exact.
    """
    conn.execute("DELETE FROM covenant_terms WHERE company_id = ?", (company_id,))

    covenants = [
        # Interest coverage ratio (minimum) - stepping UP over time (less lenient)
        {"covenant_type": "interest_coverage", "threshold_value": 1.5, "effective_date": "2021-06-30", "expiry_date": "2021-12-30"},
        {"covenant_type": "interest_coverage", "threshold_value": 1.625, "effective_date": "2021-12-31", "expiry_date": "2022-09-29"},
        {"covenant_type": "interest_coverage", "threshold_value": 1.75, "effective_date": "2022-09-30", "expiry_date": None},
        # Leverage ratio (maximum) - stepping DOWN over time (less lenient)
        {"covenant_type": "leverage_ratio", "threshold_value": 6.0, "effective_date": "2021-06-30", "expiry_date": "2021-12-30"},
        {"covenant_type": "leverage_ratio", "threshold_value": 5.75, "effective_date": "2021-12-31", "expiry_date": "2022-09-29"},
        {"covenant_type": "leverage_ratio", "threshold_value": 5.5, "effective_date": "2022-09-30", "expiry_date": "2022-12-30"},
        {"covenant_type": "leverage_ratio", "threshold_value": 5.25, "effective_date": "2022-12-31", "expiry_date": None},
    ]

    for c in covenants:
        conn.execute(
            """INSERT INTO covenant_terms
               (company_id, tranche_id, covenant_type, threshold_value, effective_date, expiry_date)
               VALUES (?, NULL, ?, ?, ?, ?)""",
            (company_id, c["covenant_type"], c["threshold_value"], c["effective_date"], c["expiry_date"]),
        )
    print(f"Inserted {len(covenants)} covenant terms for company_id={company_id}")


def seed_bhc_debt_tranches(conn, company_id):
    """
    Real disclosed tranches for Bausch Health Companies Inc. (BHC, parent
    entity only), transcribed from its FY2025/FY2026 10-Q and 10-K debt
    footnotes (CIK 0000885590). IMPORTANT: Bausch + Lomb Corporation is a
    separate, ~52.5%-owned, SEPARATELY SEC-reporting subsidiary with its own
    distinct credit facilities (its own "2030 Term Loan B", its own "2030
    Revolving Credit Facility", etc). Those are intentionally NOT included
    here - do not merge B+L's numbers into BHC's capital structure, they are
    two different companies with two different cap tables.

    No maintenance financial covenant (leverage/coverage ratio tested each
    quarter) was found in what was researched - plausible, since many
    current-market Term Loan B facilities are covenant-lite. Verify directly
    in the credit agreement before assuming there is or isn't one.
    """
    conn.execute("DELETE FROM debt_tranches WHERE company_id = ?", (company_id,))

    tranches = [
        {
            "tranche_name": "2030 Revolving Credit Facility",
            "tranche_type": "revolver",
            "rate_type": "floating",
            "reference_rate": "SOFR",
            "spread_bps": None,  # applicable rate for SOFR draws not fully confirmed - verify in 10-K
            "rate_floor_pct": 0.0,
            "fixed_rate_pct": None,
            "original_balance": 500_000_000,
            "as_of_date": "2025-04-08",
            "maturity_date": "2030-04-08",
            "seniority_rank": 1,
            "source_accession": "BHC 8-K filed 2025-04-09 and FY2026 10-Q, CIK 0000885590",
        },
        {
            "tranche_name": "2030 Term Loan B Facility",
            "tranche_type": "term_loan",
            "rate_type": "floating",
            "reference_rate": "SOFR",
            "spread_bps": 625,  # confirmed: Applicable Rate 6.25% for SOFR borrowings, 5.25% for ABR
            "rate_floor_pct": 0.0,
            "fixed_rate_pct": None,
            "original_balance": 3_000_000_000,
            "as_of_date": "2025-04-08",
            "maturity_date": "2030-10-08",
            "seniority_rank": 1,
            "source_accession": "BHC FY2026 10-Q (quarter ended Mar 31 2026), CIK 0000885590",
        },
        {
            "tranche_name": "2032 Senior Secured Notes",
            "tranche_type": "senior_notes",
            "rate_type": "fixed",
            "reference_rate": None,
            "spread_bps": None,
            "rate_floor_pct": None,
            "fixed_rate_pct": 10.0,
            "original_balance": 6_000_000_000,  # $4,400M (Apr 2025) + $1,600M folded in via Dec 2025 exchange
            "as_of_date": "2025-12-26",
            "maturity_date": "2032-04-15",
            "seniority_rank": 2,  # simplifying assumption: ranks behind revolver/TLB in the model's cash sweep - verify actual priority
            "source_accession": "BHC 8-K filed 2025-04-09; FY2025 10-K re: December 2025 Exchange, CIK 0000885590",
        },
    ]

    for t in tranches:
        conn.execute(
            """INSERT INTO debt_tranches
               (company_id, tranche_name, tranche_type, rate_type, reference_rate,
                spread_bps, rate_floor_pct, fixed_rate_pct, original_balance,
                as_of_date, maturity_date, seniority_rank, source_accession)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                company_id, t["tranche_name"], t["tranche_type"], t["rate_type"],
                t["reference_rate"], t["spread_bps"], t["rate_floor_pct"], t["fixed_rate_pct"],
                t["original_balance"], t["as_of_date"], t["maturity_date"],
                t["seniority_rank"], t["source_accession"],
            ),
        )
    print(f"Inserted {len(tranches)} debt tranches for company_id={company_id}")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    ids = seed_companies(conn)
    seed_diebold_debt_tranches(conn, ids["DBD"])
    seed_diebold_covenants(conn, ids["DBD"])
    seed_bhc_debt_tranches(conn, ids["BHC"])

    conn.commit()
    conn.close()
    print("\nDone. Diebold Nixdorf and Bausch Health now have real, worked debt tranche data")
    print("(Diebold also has a covenant schedule; BHC appears covenant-lite - verify).")
    print("Community Health Systems and Party City are seeded as companies only - research")
    print("and add their debt_tranches/covenant_terms rows the same way.")
