"""
Builds the Phase 4 ML dataset: pulls standardized total debt, interest
expense, and EBITDA for all 28 companies (the original 4 deep case
studies + 24 more researched for this broader dataset), computes
leverage and interest coverage ratios, and stores everything in the
ml_dataset table.

Note: for the original 4 companies, this uses the STANDARDIZED XBRL total
debt figure rather than our hand-researched tranche-level total - which
actually fixes the known CYH understatement from Phase 2 (that only
captured 3 of its disclosed tranches), since the standardized tag
captures the company's FULL disclosed debt. The two datasets serve
different purposes: tranche-level detail for the deep single-company
simulation work, this standardized version for a consistent, comparable
cross-sectional classifier dataset.
"""

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from data_ingest.edgar_client import get_cik_for_ticker  # noqa: E402
from data_ingest.ml_dataset_companies import ML_DATASET_COMPANIES  # noqa: E402
from engine.ebitda import get_ebitda_proxy  # noqa: E402
from engine.static_features import get_interest_expense, get_total_debt  # noqa: E402

ALL_COMPANIES = CANDIDATES + ML_DATASET_COMPANIES


def resolve_cik(company):
    if company.get("cik"):
        return company["cik"]
    return get_cik_for_ticker(company["ticker"])


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    complete_count = 0
    incomplete_count = 0

    for company in ALL_COMPANIES:
        ticker = company["ticker"]
        try:
            cik = resolve_cik(company)
        except Exception as e:
            print(f"{ticker:<8} SKIPPED - couldn't resolve ticker to a CIK ({e})")
            incomplete_count += 1
            continue

        try:
            total_debt, debt_end = get_total_debt(cik)
            interest_expense, ie_end = get_interest_expense(cik)
            _, adjusted_ebitda, ebitda_details = get_ebitda_proxy(cik)
        except Exception as e:
            print(f"{ticker:<8} SKIPPED - error fetching EDGAR data ({e})")
            incomplete_count += 1
            continue

        leverage = None
        coverage = None
        data_complete = 0

        if total_debt is not None and adjusted_ebitda and adjusted_ebitda > 0:
            leverage = total_debt / adjusted_ebitda
        if interest_expense and interest_expense > 0 and adjusted_ebitda and adjusted_ebitda > 0:
            coverage = adjusted_ebitda / interest_expense

        # Sanity check: a coverage ratio this high almost certainly means the
        # "interest expense" figure found is a small residual sub-component,
        # not the company's real total interest burden - a data artifact, not
        # a real result (no genuine company sustains 50x+ coverage). Caught
        # this exact case with QSR after three attempts to find the right
        # tag - rather than keep chasing an exact tag name with diminishing
        # returns, flag anything this implausible and exclude it honestly.
        implausible = coverage is not None and coverage > 50

        if leverage is not None and coverage is not None and not implausible:
            data_complete = 1
            complete_count += 1
            status = f"leverage {leverage:.2f}x, coverage {coverage:.2f}x"
        elif implausible:
            incomplete_count += 1
            leverage, coverage = None, None
            status = (f"INCOMPLETE - coverage ratio implausibly high (data artifact, "
                      f"likely wrong interest expense tag matched) - excluded")
        else:
            incomplete_count += 1
            reasons = list(filter(None, [
                "no total debt" if total_debt is None else None,
                "no interest expense" if not interest_expense else None,
                "no/negative EBITDA" if not adjusted_ebitda or adjusted_ebitda <= 0 else None,
            ]))
            if not reasons:
                # Fallback: none of the specific checks explained it - show the
                # actual raw values so the real cause is visible, not hidden.
                reasons = [f"unexplained gap (raw values: total_debt={total_debt}, "
                           f"interest_expense={interest_expense}, adjusted_ebitda={adjusted_ebitda}, "
                           f"leverage={leverage}, coverage={coverage})"]
            status = "INCOMPLETE - " + ", ".join(reasons)

        fiscal_year_end = debt_end or ie_end or ebitda_details.get("operating_income_date")

        conn.execute(
            """INSERT OR REPLACE INTO ml_dataset
               (ticker, name, is_distressed, total_debt, adjusted_ebitda, interest_expense,
                leverage_ratio, interest_coverage_ratio, fiscal_year_end, data_complete, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, company["name"], company["is_distressed"], total_debt, adjusted_ebitda,
             interest_expense, leverage, coverage, fiscal_year_end, data_complete,
             company.get("notes")),
        )
        conn.commit()

        distressed_flag = "DISTRESSED" if company["is_distressed"] else "not distressed"
        print(f"{ticker:<8} ({distressed_flag:<14}) {status}")

        time.sleep(0.2)  # be polite to the EDGAR API across this many companies

    print()
    print(f"Complete (usable for the model): {complete_count}")
    print(f"Incomplete (missing data, excluded): {incomplete_count}")
    print(f"Total: {complete_count + incomplete_count}")

    conn.close()
