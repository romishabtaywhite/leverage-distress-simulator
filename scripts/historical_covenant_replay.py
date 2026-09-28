"""
Runs the complete chain - interest expense, EBITDA, leverage ratio, interest
coverage ratio - once per quarter, for Diebold's REAL post-restructuring
capital structure (the $1.25B Exit Term Loan Facility, SOFR + 7.50%).

Window: August 2023 (when this facility was created) through today. We do
NOT run this further back than August 2023, because this exact loan didn't
exist before then - a different, now-extinguished capital structure did.
Running a capital structure backward past the date it actually came into
existence would produce numbers that look real but aren't - this project
draws that line deliberately.

EBITDA simplification: SEC filings disclose EBITDA's ingredients once per
FISCAL YEAR (not smoothly every quarter), so we hold each year's EBITDA
figure constant across all quarters until the next fiscal year's figure is
disclosed. This is standard practice ("most recently reported trailing
figure") but it does mean the EBITDA line moves in yearly steps while the
interest expense line moves in quarterly (or finer) steps.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "db" / "leverage_sim.db"
sys.path.insert(0, str(ROOT / "src"))

from data_ingest.candidate_companies import CANDIDATES  # noqa: E402
from engine.company_interest import get_company_tranches  # noqa: E402
from engine.ebitda import get_annual_ebitda_history  # noqa: E402
from engine.interest import floating_rate_interest  # noqa: E402

TICKER = "DBD"
STRUCTURE_START_DATE = "2023-08-11"  # the date this exact capital structure came into existence


def get_cik_for_ticker(ticker):
    for c in CANDIDATES:
        if c["ticker"] == ticker:
            return c["cik"]
    raise ValueError(f"{ticker} not found in candidate_companies.py")


def get_quarterly_sofr_from(conn, start_date):
    df = pd.read_sql(
        "SELECT obs_date, value FROM rate_series WHERE series_code = 'SOFR' ORDER BY obs_date",
        conn,
        parse_dates=["obs_date"],
    )
    df = df.set_index("obs_date")
    quarterly = df.resample("QE").last().dropna()
    return quarterly[quarterly.index >= pd.Timestamp(start_date)]


def ebitda_as_of(ebitda_history, quarter_date):
    """Finds the most recently disclosed fiscal-year EBITDA as of a given
    quarter date - i.e. what a person looking at public filings on that
    date would actually have known."""
    applicable = [h for h in ebitda_history if pd.Timestamp(h["fiscal_year_end"]) <= quarter_date]
    if not applicable:
        return None
    return max(applicable, key=lambda h: h["fiscal_year_end"])


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)

    tranche = next(t for t in get_company_tranches(conn, TICKER) if t["rate_type"] == "floating")
    quarterly_sofr = get_quarterly_sofr_from(conn, STRUCTURE_START_DATE)

    cik = get_cik_for_ticker(TICKER)
    print(f"Fetching {TICKER}'s full annual EBITDA history from SEC EDGAR...")
    ebitda_history = get_annual_ebitda_history(cik)
    for h in ebitda_history:
        print(f"  FY ending {h['fiscal_year_end']}: EBITDA proxy ${h['ebitda']:,.0f}")
    print()

    header = f"{'Quarter':<10}{'SOFR':>7}{'Interest':>15}{'EBITDA used':>15}{'Leverage':>11}{'Coverage':>11}"
    print(header)
    print("-" * len(header))

    for date, row in quarterly_sofr.iterrows():
        r = floating_rate_interest(
            balance=tranche["original_balance"],
            spread_bps=tranche["spread_bps"],
            reference_rate_pct=row["value"],
            floor_pct=tranche["rate_floor_pct"],
        )
        ebitda_point = ebitda_as_of(ebitda_history, date)
        quarter_label = f"{date.year} Q{date.quarter}"

        if ebitda_point is None:
            print(f"{quarter_label:<10}{row['value']:>6.2f}%{r['quarterly_interest']:>14,.0f}"
                  f"{'no data yet':>15}{'--':>11}{'--':>11}")
            continue

        ebitda = ebitda_point["ebitda"]
        annual_interest = r["quarterly_interest"] * 4

        if ebitda <= 0:
            # Leverage/coverage ratios aren't meaningful against negative
            # earnings - "debt / negative EBITDA" doesn't mean "years to
            # repay," it's just a sign flip. Say so plainly instead of
            # printing a misleading number.
            print(f"{quarter_label:<10}{row['value']:>6.2f}%{r['quarterly_interest']:>14,.0f}"
                  f"{ebitda:>15,.0f}{'undefined':>11}{'undefined':>11}"
                  f"  (EBITDA <= 0 this period - ratio not meaningful)")
            continue

        leverage_ratio = tranche["original_balance"] / ebitda
        coverage_ratio = ebitda / annual_interest

        print(f"{quarter_label:<10}{row['value']:>6.2f}%{r['quarterly_interest']:>14,.0f}"
              f"{ebitda:>15,.0f}{leverage_ratio:>10.2f}x{coverage_ratio:>10.2f}x")

    print()
    print("Note: no covenant test is shown because Diebold's current facility has no")
    print("financial maintenance covenants (deliberately structured that way at emergence).")
    print()
    print("Note on 'undefined' rows: right after the 2023 restructuring, the most recently")
    print("disclosed FULL fiscal year was still 2022 - a genuinely bad, negative-EBITDA year")
    print("from before the restructuring. There's a real lag between when a balance sheet")
    print("changes (instantly, at emergence) and when a clean full-year income statement")
    print("catches up (here, not until FY2024). That lag is a real limitation of using")
    print("annual EBITDA snapshots rather than reconstructed trailing-twelve-month figures -")
    print("worth stating explicitly in your write-up rather than smoothing over.")

    conn.close()
