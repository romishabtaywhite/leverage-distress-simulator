"""
Finalized case-study companies, with CIKs verified directly against real SEC
filings (not guessed). Two "recovered/failed" distress cases and two
"currently levered, hasn't defaulted" comparison cases.
"""

CANDIDATES = [
    {
        "ticker": "DBD",
        "name": "Diebold Nixdorf, Incorporated",
        "cik": "0000028823",
        "is_distressed": 1,
        "distress_date": "2023-06-01",  # Chapter 11 filed June 1 2023, emerged Aug 11 2023
        "notes": "Filed Chapter 11 (+ a parallel Dutch WHOA scheme) June 2023, emerged Aug 2023 - "
                 "ONE restructuring event, not two. The pre-filing capital structure (LIBOR/EURIBOR "
                 "term loans, and a covenant schedule that tightened 2021-2022) was entirely "
                 "extinguished at emergence. It was replaced by a new $1.25B Exit Term Loan Facility "
                 "priced at SOFR + 7.50%, deliberately structured with NO financial maintenance "
                 "covenants. Real narrative arc: covenant relief (2021-22) proved insufficient, so "
                 "lenders eventually did a full debt-for-equity restructuring instead - a more severe "
                 "form of discipline than a covenant breach. Both the pre- and post-restructuring "
                 "data are worth keeping, clearly separated, for exactly this contrast.",
    },
    {
        "ticker": "BHC",
        "name": "Bausch Health Companies Inc.",
        "cik": "0000885590",
        "is_distressed": 0,
        "distress_date": None,
        "notes": "Heavily levered (post-Valeant), still operating and current-filing as of 2026. "
                 "Has NOT defaulted - useful as a 'high leverage, still standing' comparison case. "
                 "Verify current debt footnote details yourself before use.",
    },
    {
        "ticker": "CYH",
        "name": "Community Health Systems, Inc.",
        "cik": "0001108109",
        "is_distressed": 0,
        "distress_date": None,
        "notes": "Heavily levered hospital operator, ~$11.4B debt as of late 2024, still operating. "
                 "Good healthcare-sector comparison case. Verify current figures before use.",
    },
    {
        "ticker": "PRTYQ",
        "name": "Party City Holdco Inc.",
        "cik": "0001592058",
        "is_distressed": 1,
        "distress_date": "2024-12-21",  # second Chapter 11 filing, led to full liquidation
        "notes": "Filed Chapter 11 twice (Jan 2023, then again Dec 2024). Fully liquidated in 2025 "
                 "after the second filing failed to produce a turnaround. Use PRE-first-bankruptcy "
                 "10-K debt footnotes (e.g. FY2021/FY2022 filings) as the simulation input, paired "
                 "with the confirmed eventual-liquidation outcome as a clean distress label.",
    },
]
