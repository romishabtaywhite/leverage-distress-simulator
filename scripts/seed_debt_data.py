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
    Real disclosed CURRENT (post-emergence) tranche for Diebold Nixdorf,
    transcribed from law-firm summaries of its Aug 2023 Chapter 11
    emergence and its FY2025 10-Q (CIK 0000028823).

    IMPORTANT CORRECTION from earlier research: Diebold's PRE-bankruptcy
    capital structure (LIBOR/EURIBOR term loans, described in comments
    further down near the covenant function) was entirely extinguished at
    emergence - it is NOT still outstanding, so it is deliberately NOT
    seeded here. Mixing pre- and post-restructuring tranches into the same
    "current capital structure" would double-count debt that no longer
    exists. Only the real, current, post-emergence structure is seeded.
    """
    conn.execute("DELETE FROM debt_tranches WHERE company_id = ?", (company_id,))

    tranches = [
        {
            "tranche_name": "Exit Term Loan Facility",
            "tranche_type": "term_loan",
            "rate_type": "floating",
            "reference_rate": "SOFR",
            "spread_bps": 750,  # confirmed: SOFR + 7.50%
            "rate_floor_pct": 0.0,  # standard market convention post-LIBOR - verify exact figure in credit agreement
            "fixed_rate_pct": None,
            "original_balance": 1_250_000_000,  # confirmed: $1.25B DIP converted to Exit Facility at emergence
            "as_of_date": "2023-08-11",  # plan effective date
            "maturity_date": "2028-08-11",  # 5-year term from effective date, per law firm summaries
            "seniority_rank": 1,
            "source_accession": "Jones Day / Loyens & Loeff / Davis Polk deal summaries re: Aug 2023 "
                                 "emergence; DBD 8-K filed Aug 11 2023, CIK 0000028823",
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
    HISTORICAL covenant schedule from Diebold's PRE-bankruptcy credit
    agreement (disclosed in its FY2021 10-Q, back when it still carried
    LIBOR/EURIBOR term loans - see the correction note in
    seed_diebold_debt_tranches above). This is a genuine "amend and
    extend" style covenant relief schedule: lenders progressively loosened
    then re-tightened the rules as a first response to distress.

    All rows are given an expiry_date of 2023-06-01 (the Chapter 11 filing
    date) because this entire credit agreement - covenants included - was
    extinguished at emergence two months later. The real story arc: this
    covenant relief mechanism was tried first, proved insufficient, and
    the company proceeded to a full debt-for-equity Chapter 11
    restructuring instead. The new Exit Term Loan Facility that replaced
    it was deliberately structured covenant-lite (no financial maintenance
    covenants at all) - so there is intentionally no "current" covenant
    row for Diebold below this point. That absence is itself a real,
    meaningful finding, not a data gap.

    Note: the source XBRL table had some ambiguous column alignment between
    "current" and "subsequent event" (forward-scheduled) values - the
    dates below are a best reconstruction. Verify against the actual filed
    credit agreement amendment before treating these as exact.
    """
    conn.execute("DELETE FROM covenant_terms WHERE company_id = ?", (company_id,))

    covenants = [
        # Interest coverage ratio (minimum) - stepping UP over time (less lenient)
        {"covenant_type": "interest_coverage", "threshold_value": 1.5, "effective_date": "2021-06-30", "expiry_date": "2021-12-30"},
        {"covenant_type": "interest_coverage", "threshold_value": 1.625, "effective_date": "2021-12-31", "expiry_date": "2022-09-29"},
        {"covenant_type": "interest_coverage", "threshold_value": 1.75, "effective_date": "2022-09-30", "expiry_date": "2023-06-01"},
        # Leverage ratio (maximum) - stepping DOWN over time (less lenient)
        {"covenant_type": "leverage_ratio", "threshold_value": 6.0, "effective_date": "2021-06-30", "expiry_date": "2021-12-30"},
        {"covenant_type": "leverage_ratio", "threshold_value": 5.75, "effective_date": "2021-12-31", "expiry_date": "2022-09-29"},
        {"covenant_type": "leverage_ratio", "threshold_value": 5.5, "effective_date": "2022-09-30", "expiry_date": "2022-12-30"},
        {"covenant_type": "leverage_ratio", "threshold_value": 5.25, "effective_date": "2022-12-31", "expiry_date": "2023-06-01"},
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


def seed_chs_debt_tranches(conn, company_id):
    """
    Real disclosed tranches for Community Health Systems, Inc. (CYH, CIK
    0001108109), transcribed from FY2025/FY2026 10-K/10-Q filings and 8-Ks.
    CHS has a large, frequently-refinanced note stack; this is a
    representative subset, not the full capital structure - there are
    additional smaller note series outstanding. Verify current balances
    directly in the FY2025 10-K debt footnote before relying on these.
    """
    conn.execute("DELETE FROM debt_tranches WHERE company_id = ?", (company_id,))

    tranches = [
        {
            "tranche_name": "ABL Facility",
            "tranche_type": "revolver",
            "rate_type": "floating",
            "reference_rate": "SOFR",
            "spread_bps": 200,  # tiered 175/200/225 bps based on excess availability - using midpoint
            "rate_floor_pct": None,
            "fixed_rate_pct": None,
            "original_balance": 1_000_000_000,  # max commitment, not necessarily fully drawn
            "as_of_date": "2026-03-31",
            "maturity_date": None,  # not confirmed in research - verify
            "seniority_rank": 1,
            "source_accession": "CHS FY2026 10-Q (quarter ended Mar 31 2026), CIK 0001108109",
        },
        {
            "tranche_name": "10.875% Senior Secured Notes due 2032",
            "tranche_type": "senior_notes",
            "rate_type": "fixed",
            "reference_rate": None,
            "spread_bps": None,
            "rate_floor_pct": None,
            "fixed_rate_pct": 10.875,
            "original_balance": 2_002_500_000,  # confirmed remaining balance after Dec 2025 partial redemption
            "as_of_date": "2025-12-15",
            "maturity_date": "2032-01-01",  # approximate - verify exact date
            "seniority_rank": 2,
            "source_accession": "CHS press release re: note redemptions, Dec 15 2025, CIK 0001108109",
        },
        {
            "tranche_name": "10.750% Senior-Priority Secured Notes due 2033",
            "tranche_type": "senior_notes",
            "rate_type": "fixed",
            "reference_rate": None,
            "spread_bps": None,
            "rate_floor_pct": None,
            "fixed_rate_pct": 10.75,
            "original_balance": None,  # amount not confirmed in research - verify in 8-K/10-K
            "as_of_date": "2025-05-08",
            "maturity_date": "2033-01-01",  # approximate - verify exact date
            "seniority_rank": 2,
            "source_accession": "CHS 8-K filed May 8-9 2025, CIK 0001108109",
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


def seed_party_city_debt_tranches(conn, company_id):
    """
    Real disclosed tranches for Party City Holdco Inc. (PRTYQ, CIK
    0001592058), transcribed from its FY2021 10-K debt footnote - the
    capital structure in place shortly before its first Chapter 11 filing
    (January 2023). NOTABLE FINDING: both surviving tranches by this point
    were FIXED rate - the company had refinanced out of its floating-rate
    Term Loan Credit Agreement in Feb 2021, more than a year before its
    bankruptcy filing. This makes Party City a useful contrast case: its
    distress was demand/liquidity-driven, not floating-rate-driven, unlike
    Diebold or CHS. Worth stating explicitly in your write-up rather than
    assuming every distress case in the dataset is rate-cycle-driven.
    """
    conn.execute("DELETE FROM debt_tranches WHERE company_id = ?", (company_id,))

    tranches = [
        {
            "tranche_name": "8.750% Senior Secured First Lien Notes due 2026",
            "tranche_type": "senior_notes",
            "rate_type": "fixed",
            "reference_rate": None,
            "spread_bps": None,
            "rate_floor_pct": None,
            "fixed_rate_pct": 8.75,
            "original_balance": 750_000_000,
            "as_of_date": "2021-02-19",
            "maturity_date": "2026-02-15",
            "seniority_rank": 1,
            "source_accession": "Party City 8-K filed Feb 22 2021; FY2021 10-K, CIK 0001592058",
        },
        {
            "tranche_name": "6.125% Senior Notes due 2023",
            "tranche_type": "sub_notes",
            "rate_type": "fixed",
            "reference_rate": None,
            "spread_bps": None,
            "rate_floor_pct": None,
            "fixed_rate_pct": 6.125,
            "original_balance": None,  # amount not isolated in extracted text - verify in FY2021 10-K
            "as_of_date": "2021-12-31",
            "maturity_date": "2023-08-15",
            "seniority_rank": 2,  # unsecured, subordinated to secured debt per filing text
            "source_accession": "Party City FY2022 10-K debt footnote, CIK 0001592058",
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
    seed_chs_debt_tranches(conn, ids["CYH"])
    seed_party_city_debt_tranches(conn, ids["PRTYQ"])

    conn.commit()
    conn.close()
    print("\nDone. All 4 companies now have real, worked debt tranche data.")
    print("Diebold also has a covenant schedule; the others appear covenant-lite or")
    print("weren't confirmed to have maintenance covenants in the research done here - verify.")
