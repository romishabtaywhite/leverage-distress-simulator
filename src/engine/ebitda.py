"""
Reusable EBITDA proxy calculation, pulled from SEC EDGAR's real disclosed
financials.

Real-world wrinkle handled here: some companies (especially ones with large
intangible assets, like pharma companies) report a single combined
"Depreciation and Amortization" figure, while others report Depreciation
and Amortization of Intangible Assets as two SEPARATE line items. We try
the combined tags first; if none exist for a given year, we fall back to
summing the two separate pieces for that same year.
"""

import pandas as pd

from data_ingest.edgar_client import CANDIDATE_TAGS, extract_concept_series, get_company_facts


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


def _annual_by_end_date(facts, tags):
    """For a list of candidate tags, returns {end_date: record} keeping
    only genuine full-year periods and the most recently filed version
    of each."""
    best_by_end = {}
    for tag in tags:
        for r in extract_concept_series(facts, tag):
            if r.get("fp") != "FY" or r.get("val") is None:
                continue
            if not _is_full_year_period(r):
                continue
            end = r["end"]
            if end not in best_by_end or r["filed"] > best_by_end[end]["filed"]:
                best_by_end[end] = r
    return best_by_end


def _dna_by_end_date(facts):
    """
    D&A specifically, with the split-tag fallback. Returns
    {end_date: {"val": ..., "tag": ..., "filed": ...}}.
    """
    combined = _annual_by_end_date(facts, CANDIDATE_TAGS["depreciation_amortization"])
    depreciation = _annual_by_end_date(facts, CANDIDATE_TAGS["depreciation_only"])
    amortization = _annual_by_end_date(facts, CANDIDATE_TAGS["amortization_only"])

    result = {}
    for end, r in combined.items():
        result[end] = {"val": r["val"], "tag": "combined", "filed": r["filed"]}

    # Fallback: for any year the combined tag DIDN'T cover, try summing
    # the two separate pieces instead.
    split_years = set(depreciation) & set(amortization)
    for end in split_years - set(result):
        val = depreciation[end]["val"] + amortization[end]["val"]
        filed = max(depreciation[end]["filed"], amortization[end]["filed"])
        result[end] = {"val": val, "tag": "split (Depreciation + AmortizationOfIntangibleAssets)", "filed": filed}

    return result


def _impairment_addback_by_end_date(facts):
    """
    Sums one-time, non-cash impairment charges by fiscal year end.

    IMPORTANT lesson learned the hard way: goodwill impairment and
    intangible-asset impairment are well-standardized, genuinely SEPARATE
    GAAP concepts that companies tag consistently, so those two are safe
    to add together. The generic "AssetImpairmentCharges" /
    "ImpairmentOfLongLivedAssetsHeldForUse" tags are vaguer catch-alls
    used inconsistently across filers - sometimes a genuinely distinct
    number, sometimes a DUPLICATE rollup of the same goodwill/intangible
    charge counted again. Summing everything blindly caused real bugs:
    one company's goodwill charge got double-counted through the generic
    tag, and another company's generic tag had an inverted sign
    convention entirely. The fix: use the two specific, reliable tags as
    the primary source, and only fall back to the generic catch-all tags
    when the specific ones find NOTHING at all for that year. Negative
    values are also discarded outright - a real impairment charge is
    never negative, so a negative figure signals a sign-convention
    mismatch, not a genuine credit.
    """
    combined_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["impairment_combined"])
    goodwill_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["impairment_goodwill"])
    intangibles_indefinite_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["impairment_intangibles_indefinite"])
    intangibles_finite_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["impairment_intangibles_finite"])
    intangibles_generic_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["impairment_intangibles"])
    generic_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["impairment_other"])

    all_ends = (
        set(combined_by_end) | set(goodwill_by_end) | set(intangibles_indefinite_by_end)
        | set(intangibles_finite_by_end) | set(intangibles_generic_by_end) | set(generic_by_end)
    )
    totals_by_end = {}

    for end in all_ends:
        # Priority 1: a single combined "Goodwill and intangible asset
        # impairment" tag - this is what actually appears as one line on
        # the audited income statement, so it's the most reliable single
        # source when present. Use it ALONE if found - don't also add the
        # granular pieces on top, since those are footnote-level detail
        # for the SAME total, not additional separate charges.
        if end in combined_by_end:
            total = combined_by_end[end]["val"]
            if total > 0:
                totals_by_end[end] = total
            continue

        goodwill_val = goodwill_by_end[end]["val"] if end in goodwill_by_end else None

        # Intangibles: prefer the SPLIT tags (indefinite-lived + finite-lived
        # are genuinely separate GAAP concepts, safe to sum) - only fall back
        # to the single generic combined tag if NEITHER split tag was found,
        # to avoid double-counting the same charge under both.
        indefinite_val = intangibles_indefinite_by_end[end]["val"] if end in intangibles_indefinite_by_end else None
        finite_val = intangibles_finite_by_end[end]["val"] if end in intangibles_finite_by_end else None

        if indefinite_val is not None or finite_val is not None:
            intangibles_val = (indefinite_val or 0) + (finite_val or 0)
        elif end in intangibles_generic_by_end:
            intangibles_val = intangibles_generic_by_end[end]["val"]
        else:
            intangibles_val = None

        specific_total = (goodwill_val or 0) + (intangibles_val or 0)

        if goodwill_val is not None or intangibles_val is not None:
            # At least one specific, reliable tag was found - use their sum,
            # and deliberately IGNORE the generic tag to avoid double-counting.
            total = specific_total
        elif end in generic_by_end:
            # No specific tag at all - fall back to the generic one.
            total = generic_by_end[end]["val"]
        else:
            continue

        if total > 0:  # discard negative/zero values - not a genuine charge
            totals_by_end[end] = total

    return totals_by_end


def get_ebitda_proxy(cik):
    """
    Returns (ebitda, adjusted_ebitda, details) for the most recent full
    fiscal year.

    - ebitda: the raw proxy (Operating Income + D&A), straight from GAAP
      figures, no adjustments.
    - adjusted_ebitda: ebitda with one-time, non-cash impairment charges
      added back (since a real lender's covenant calculation would
      normally exclude these too) - equal to ebitda when no impairment
      was disclosed for that year.

    details shows exactly which XBRL tags and fiscal year were used, and
    the impairment add-back amount if any, for full transparency.
    """
    facts = get_company_facts(cik)

    op_income_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["operating_income"])
    dna_by_end = _dna_by_end_date(facts)
    impairment_by_end = _impairment_addback_by_end_date(facts)

    common_ends = sorted(set(op_income_by_end) & set(dna_by_end))
    if not common_ends:
        return None, None, {"operating_income_date": None, "depreciation_amortization_tag": None}

    latest_end = common_ends[-1]
    op_income = op_income_by_end[latest_end]["val"]
    d_and_a = dna_by_end[latest_end]["val"]
    impairment_addback = impairment_by_end.get(latest_end, 0.0)

    ebitda = op_income + d_and_a
    adjusted_ebitda = ebitda + impairment_addback

    details = {
        "operating_income": op_income,
        "operating_income_date": latest_end,
        "depreciation_amortization": d_and_a,
        "depreciation_amortization_tag": dna_by_end[latest_end]["tag"],
        "impairment_addback": impairment_addback,
    }

    return ebitda, adjusted_ebitda, details


def get_annual_ebitda_history(cik):
    """
    Returns EBITDA proxy for EVERY genuine full fiscal year disclosed
    (stub periods around events like bankruptcy emergence are filtered
    out). Returns a list of dicts sorted oldest-to-newest:
    [{"fiscal_year_end": date_str, "ebitda": val}, ...]

    Also handles a real messiness in XBRL data: companies sometimes
    re-file the same fiscal year's figures more than once (restatements,
    amended filings). We keep only the MOST RECENTLY FILED value for each
    unique fiscal year end date, so we're not using stale restated numbers.
    """
    facts = get_company_facts(cik)

    op_income_by_end = _annual_by_end_date(facts, CANDIDATE_TAGS["operating_income"])
    dna_by_end = _dna_by_end_date(facts)

    history = []
    for end_date in sorted(set(op_income_by_end) & set(dna_by_end)):
        ebitda = op_income_by_end[end_date]["val"] + dna_by_end[end_date]["val"]
        history.append({"fiscal_year_end": end_date, "ebitda": ebitda})

    return history
