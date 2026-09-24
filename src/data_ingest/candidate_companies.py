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
        "distress_date": "2023-06-01",  # approximate - filed Chapter 11 June 2023
        "notes": "Filed Chapter 11 June 2023, successfully reorganized, still trades as DBD. "
                 "Real disclosed floating-rate Term Loan A/B facilities (LIBOR + spread) and a "
                 "leverage-ratio/interest-coverage covenant step schedule pre-filing - excellent "
                 "worked example of exactly the covenant mechanics this project models. "
                 "A 'survived distress' case, useful contrast against Party City.",
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
