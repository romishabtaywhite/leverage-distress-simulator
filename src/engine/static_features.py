"""
Static, single-point-in-time financial features for the broader ML
dataset - total debt, interest expense, EBITDA - pulled directly from
standardized SEC EDGAR XBRL tags. Lighter-weight than the deep
tranche-level research done for the 4 core case-study companies: no
manual reading of debt footnotes here. This trades some precision for
being able to cover many more companies, which is what a real
cross-sectional ML dataset needs.
"""

from data_ingest.edgar_client import CANDIDATE_TAGS, extract_concept_series, get_company_facts
from engine.ebitda import _annual_by_end_date, get_ebitda_proxy  # noqa: F401 (reused below)


def _instant_annual_by_end_date(facts, tags):
    """
    For BALANCE SHEET (instant) concepts like debt balances - these only
    have an 'end' date, no 'start', since they're a snapshot, not a
    period. Different from _annual_by_end_date (used for duration
    concepts like revenue or interest expense), which checks period
    LENGTH to filter out bankruptcy-emergence stub periods - that check
    doesn't apply to instant snapshots, which are just "true as of that
    one date" regardless of how long since the prior snapshot.
    """
    best_by_end = {}
    for tag in tags:
        for r in extract_concept_series(facts, tag):
            if r.get("fp") != "FY" or r.get("val") is None:
                continue
            end = r["end"]
            if end not in best_by_end or r["filed"] > best_by_end[end]["filed"]:
                best_by_end[end] = r
    return best_by_end


def get_total_debt(cik):
    """
    Returns (total_debt, fiscal_year_end) using the most recent fiscal
    year where a debt figure is disclosed.

    Priority order (same overlap-avoidance pattern learned from the
    impairment double-counting bug): try the SPECIFIC split tags
    (long-term + current debt) first, since those are standard and safe
    to add together. Only if NEITHER split tag has any data at all, fall
    back to a single COMBINED tag some companies use instead - never mix
    both sources for the same company, to avoid double-counting.
    """
    facts = get_company_facts(cik)
    ltd_by_end = _instant_annual_by_end_date(facts, CANDIDATE_TAGS["long_term_debt"])
    cur_by_end = _instant_annual_by_end_date(facts, CANDIDATE_TAGS["current_debt"])

    if ltd_by_end:
        latest_end = max(ltd_by_end.keys())
        current_piece = cur_by_end.get(latest_end, {}).get("val", 0) or 0
        total = ltd_by_end[latest_end]["val"] + current_piece
        return total, latest_end

    combined_by_end = _instant_annual_by_end_date(facts, CANDIDATE_TAGS["total_debt_combined"])
    if combined_by_end:
        latest_end = max(combined_by_end.keys())
        return combined_by_end[latest_end]["val"], latest_end

    return None, None


def get_interest_expense(cik):
    """
    Most recent full fiscal year's interest expense, using the same
    stub-period-safe logic as EBITDA.

    IMPORTANT priority order (learned from a real bug): tags are tried in
    order of how likely they are to represent the FULL interest expense,
    not as interchangeable alternatives. A tag named "...Other" almost
    certainly represents a minor sub-component, not the total - treating
    it as equally valid caused a real bug (QSR came back with an absurd
    962x coverage ratio, because a tiny "other" sub-component got picked
    over the real total simply because it happened to be filed more
    recently). So the comprehensive-sounding tags are tried FIRST, and
    "Other"-style tags are used only as an absolute last resort, one at
    a time, never blended with the others.

    Sign-convention fix retained from before: some filers report this as
    a negative number: we take the absolute value.
    """
    facts = get_company_facts(cik)

    primary_tags = ["InterestExpense", "InterestExpenseDebt", "InterestIncomeExpenseNet",
                    "InterestAndDebtExpense"]
    fallback_tags = ["InterestExpenseOther"]

    ie_by_end = _annual_by_end_date(facts, primary_tags)
    if not ie_by_end:
        ie_by_end = _annual_by_end_date(facts, fallback_tags)
    if not ie_by_end:
        return None, None

    latest_end = max(ie_by_end.keys())
    return abs(ie_by_end[latest_end]["val"]), latest_end
