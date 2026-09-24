"""
SEC EDGAR data ingestion client.

No API key required, but SEC requires a descriptive User-Agent header
identifying you, and asks that automated access stay within reasonable
rate limits. Set SEC_EDGAR_USER_AGENT in your .env file.

Key endpoints used:
- https://www.sec.gov/files/company_tickers.json          (ticker -> CIK lookup)
- https://data.sec.gov/submissions/CIK##########.json     (filing history)
- https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json  (all XBRL facts)
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT")
if not USER_AGENT or "your.email" in USER_AGENT:
    raise RuntimeError(
        "Set a real SEC_EDGAR_USER_AGENT in your .env file "
        "(e.g. 'Jane Smith jane.smith@email.com'). SEC will block requests "
        "with missing or placeholder User-Agent headers."
    )

HEADERS = {"User-Agent": USER_AGENT}

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Be a good citizen: SEC's own guidance allows up to ~10 req/sec, but for a
# small personal project there's no reason to push that. This keeps you
# comfortably under any rate limiting.
REQUEST_DELAY_SECONDS = 0.3


def _get_json(url: str) -> dict:
    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def load_ticker_to_cik_map(force_refresh: bool = False) -> dict:
    """
    Returns a dict mapping uppercase ticker -> zero-padded 10-digit CIK string.
    Caches locally since this file covers ~13,000 companies and rarely changes.
    """
    cache_path = CACHE_DIR / "company_tickers.json"

    if cache_path.exists() and not force_refresh:
        raw = json.loads(cache_path.read_text())
    else:
        raw = _get_json("https://www.sec.gov/files/company_tickers.json")
        cache_path.write_text(json.dumps(raw))

    # raw is a dict of dicts like {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    return {
        entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
        for entry in raw.values()
    }


def get_cik_for_ticker(ticker: str) -> str:
    mapping = load_ticker_to_cik_map()
    cik = mapping.get(ticker.upper())
    if cik is None:
        raise ValueError(f"Ticker '{ticker}' not found in SEC's ticker list.")
    return cik


def get_company_facts(cik: str) -> dict:
    """
    Full XBRL company facts for one CIK (zero-padded 10-digit string).
    Contains every disclosed concept (revenue, interest expense, debt, etc.)
    across all filed periods.
    """
    cache_path = CACHE_DIR / f"companyfacts_{cik}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    data = _get_json(url)
    cache_path.write_text(json.dumps(data))
    return data


def extract_concept_series(company_facts: dict, concept: str, taxonomy: str = "us-gaap") -> list:
    """
    Pulls one concept (e.g. 'InterestExpense', 'Revenues', 'OperatingIncomeLoss')
    out of a company_facts blob into a flat list of {end, val, form, fy, fp, filed} dicts.
    Returns [] if the company never disclosed this exact tag (common - companies vary
    in which tags they use, you'll need to try a few candidates per metric).
    """
    try:
        units = company_facts["facts"][taxonomy][concept]["units"]
    except KeyError:
        return []

    records = []
    for unit_type, entries in units.items():
        for e in entries:
            records.append(
                {
                    "unit": unit_type,
                    "end": e.get("end"),
                    "val": e.get("val"),
                    "form": e.get("form"),
                    "fy": e.get("fy"),
                    "fp": e.get("fp"),
                    "filed": e.get("filed"),
                    "frame": e.get("frame"),
                }
            )
    return records


# Candidate us-gaap tags to try for each metric you'll need. Companies are
# inconsistent about which exact tag they use, so check what's actually
# present for each company_facts blob before assuming a tag is missing.
CANDIDATE_TAGS = {
    "interest_expense": ["InterestExpense", "InterestExpenseDebt", "InterestIncomeExpenseNet"],
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation_amortization": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "current_debt": ["LongTermDebtCurrent", "DebtCurrent"],
}


if __name__ == "__main__":
    # Quick smoke test - run this file directly to confirm your setup works.
    cik = get_cik_for_ticker("AAPL")
    print(f"AAPL CIK: {cik}")
    facts = get_company_facts(cik)
    revenue = extract_concept_series(facts, "Revenues")
    print(f"Found {len(revenue)} disclosed Revenue data points for AAPL.")
