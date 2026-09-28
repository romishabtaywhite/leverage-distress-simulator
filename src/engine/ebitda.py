"""
Reusable EBITDA proxy calculation, pulled from SEC EDGAR's real disclosed
financials. Same logic as in demo_interest_coverage.py, moved here so we
don't copy-paste it into every new script that needs EBITDA.
"""

import pandas as pd

from data_ingest.edgar_client import CANDIDATE_TAGS, extract_concept_series, get_company_facts


def _get_latest_annual_value(records):
    annual = [r for r in records if r.get("fp") == "FY" and r.get("val") is not None]
    if not annual:
        return None
    annual.sort(key=lambda r: r["end"], reverse=True)
    return annual[0]


def _get_latest_annual_metric(facts, metric_name):
    for tag in CANDIDATE_TAGS[metric_name]:
        records = extract_concept_series(facts, tag)
        latest = _get_latest_annual_value(records)
        if latest is not None:
            return latest["val"], tag, latest["end"]
    return None, None, None


def get_ebitda_proxy(cik):
    """
    Returns (ebitda, details) where details is a dict showing exactly which
    XBRL tags and fiscal year were used, for transparency - never just a
    bare number with no way to trace where it came from.
    """
    facts = get_company_facts(cik)

    op_income, op_income_tag, op_income_date = _get_latest_annual_metric(facts, "operating_income")
    d_and_a, d_and_a_tag, d_and_a_date = _get_latest_annual_metric(facts, "depreciation_amortization")

    details = {
        "operating_income": op_income,
        "operating_income_tag": op_income_tag,
        "operating_income_date": op_income_date,
        "depreciation_amortization": d_and_a,
        "depreciation_amortization_tag": d_and_a_tag,
        "depreciation_amortization_date": d_and_a_date,
    }

    if op_income is None or d_and_a is None:
        return None, details

    return op_income + d_and_a, details


def _is_full_year_period(record, min_days=300):
    """
    Real full fiscal years run close to 365 days. Around bankruptcy
    emergences (and some other corporate events), companies file
    "stub period" figures - a few months long - but XBRL still labels
    them fp="FY". This checks the ACTUAL length of the period rather
    than trusting that label, so we don't treat a 5-week stub as if it
    were a normal year's EBITDA.
    """
    start = record.get("start")
    end = record.get("end")
    if start is None or end is None:
        return False
    days = (pd.Timestamp(end) - pd.Timestamp(start)).days
    return days >= min_days


def annual_by_end_date(metric_name, facts):
    best_by_end = {}
    for tag in CANDIDATE_TAGS[metric_name]:
        for r in extract_concept_series(facts, tag):
            if r.get("fp") != "FY" or r.get("val") is None:
                continue
            if not _is_full_year_period(r):
                continue
            end = r["end"]
            if end not in best_by_end or r["filed"] > best_by_end[end]["filed"]:
                best_by_end[end] = r
    return best_by_end


def get_annual_ebitda_history(cik):
    """
    Returns EBITDA proxy for EVERY genuine full fiscal year disclosed
    (stub periods around events like bankruptcy emergence are filtered
    out - see _is_full_year_period). Returns a list of dicts sorted
    oldest-to-newest: [{"fiscal_year_end": date_str, "ebitda": val}, ...]

    Also handles a real messiness in XBRL data: companies sometimes
    re-file the same fiscal year's figures more than once (restatements,
    amended filings). We keep only the MOST RECENTLY FILED value for each
    unique fiscal year end date, so we're not using stale restated numbers.
    """
    facts = get_company_facts(cik)

    op_income_by_end = annual_by_end_date("operating_income", facts)
    d_and_a_by_end = annual_by_end_date("depreciation_amortization", facts)

    history = []
    for end_date in sorted(set(op_income_by_end) & set(d_and_a_by_end)):
        ebitda = op_income_by_end[end_date]["val"] + d_and_a_by_end[end_date]["val"]
        history.append({"fiscal_year_end": end_date, "ebitda": ebitda})

    return history
