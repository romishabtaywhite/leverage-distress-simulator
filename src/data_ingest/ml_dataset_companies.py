"""
Broader set of real, public companies for the Phase 4 ML dataset -
lighter-weight than the deep tranche-level research done for the 4 core
case-study companies (see candidate_companies.py). Here we only need
standard XBRL-tagged figures (total debt, interest expense, EBITDA
ingredients), not hand-read debt footnotes.

IMPORTANT LESSON from the first attempt: SEC's ticker-to-CIK lookup file
(company_tickers.json) only includes CURRENTLY actively-traded tickers -
once a company delists (goes private, gets acquired, or fully
liquidates), its ticker disappears from that file even though its CIK
and historical filings remain permanently in EDGAR. Since almost every
genuinely distressed company eventually delists, this hit hardest exactly
where it mattered most. Fix: CIKs are hardcoded directly below for
delisted/private companies, verified via direct EDGAR filing search
rather than the ticker file, bypassing this problem entirely - the same
pattern already used for the 4 original case-study companies.

Three companies from the original candidate list (Yellow Corporation,
EchoStar, Anywhere Real Estate) were DROPPED here rather than kept with a
guessed CIK, since their CIKs couldn't be confirmed cleanly enough to
trust.
"""

DISTRESSED_COMPANIES = [
    {"ticker": "HTZ", "cik": None, "name": "Hertz Global Holdings, Inc.",
     "is_distressed": 1, "distress_date": "2020-05-22",
     "notes": "Chapter 11 May 2020 (pandemic-driven travel collapse), emerged June 2021. "
              "Ticker still active, resolves fine, but standard debt/EBITDA tags didn't match - "
              "likely uses non-standard tags for its vehicle-fleet-financing-heavy balance sheet."},
    {"ticker": "JCPN", "cik": "0000077182", "name": "J.C. Penney Company, Inc.",
     "is_distressed": 1, "distress_date": "2020-05-15",
     "notes": "Chapter 11 May 2020, went private post-emergence. CIK verified directly via "
              "EDGAR filings (ticker no longer in the active ticker file)."},
    {"ticker": "REV", "cik": "0000887921", "name": "Revlon, Inc.",
     "is_distressed": 1, "distress_date": "2022-06-15",
     "notes": "Chapter 11 June 2022, emerged 2023 as a private company owned by former creditors."},
    {"ticker": "WE", "cik": "0001813756", "name": "WeWork Inc.",
     "is_distressed": 1, "distress_date": "2023-11-06",
     "notes": "Chapter 11 November 2023."},
    {"ticker": "RAD", "cik": "0000084129", "name": "Rite Aid Corporation",
     "is_distressed": 1, "distress_date": "2025-05-05",
     "notes": "Chapter 11 twice: October 2023, then again May 2025 leading to full liquidation - "
              "same pattern as Party City in this dataset."},
    {"ticker": "BIG", "cik": "0000768835", "name": "Big Lots, Inc.",
     "is_distressed": 1, "distress_date": "2024-09-09",
     "notes": "Chapter 11 September 2024."},
    {"ticker": "JOAN", "cik": "0001834585", "name": "Joann Inc.",
     "is_distressed": 1, "distress_date": "2024-03-18",
     "notes": "Chapter 11 twice: March 2024, then again January 2025, fully liquidated by May 2025."},
    {"ticker": "ME", "cik": "0001804591", "name": "23andMe Holding Co.",
     "is_distressed": 1, "distress_date": "2025-03-23",
     "notes": "Chapter 11 March 2025."},
    {"ticker": "CHK", "cik": "0000895126", "name": "Chesapeake Energy Corporation",
     "is_distressed": 1, "distress_date": "2020-06-28",
     "notes": "Chapter 11 June 2020, emerged 2021. Same CIK now files as Expand Energy "
              "Corporation after a 2024 merger - historical CHK-era data still under this CIK."},
    {"ticker": "FYBR", "cik": "0000020520", "name": "Frontier Communications Parent, Inc.",
     "is_distressed": 1, "distress_date": "2020-04-14",
     "notes": "Chapter 11 April 2020, emerged April 2021."},
    {"ticker": "AVYA", "cik": "0001418100", "name": "Avaya Holdings Corp.",
     "is_distressed": 1, "distress_date": "2023-02-14",
     "notes": "Chapter 11 February 2023 (second bankruptcy; first was 2017). Went fully private "
              "afterward - likely sparse post-filing data."},
    {"ticker": "YELLQ", "cik": "0000716006", "name": "Yellow Corporation",
     "is_distressed": 1, "distress_date": "2023-08-06",
     "notes": "Chapter 11 August 2023 (trucking), fully liquidated. CIK confirmed directly "
              "via EDGAR filings (delisted from NASDAQ, no longer in the active ticker file)."},
]

NOT_DISTRESSED_COMPANIES = [
    {"ticker": "CHTR", "cik": None, "name": "Charter Communications, Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Heavily levered cable/broadband operator, no default history."},
    {"ticker": "CCL", "cik": None, "name": "Carnival Corporation & plc",
     "is_distressed": 0, "distress_date": None,
     "notes": "Took on very heavy debt during COVID-19 travel shutdown, has not defaulted."},
    {"ticker": "AAL", "cik": None, "name": "American Airlines Group Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "One of the most heavily levered major airlines, has not defaulted."},
    {"ticker": "UAL", "cik": None, "name": "United Airlines Holdings, Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Heavily levered post-COVID, has not defaulted."},
    {"ticker": "OXY", "cik": None, "name": "Occidental Petroleum Corporation",
     "is_distressed": 0, "distress_date": None,
     "notes": "Took on significant leverage from the 2019 Anadarko acquisition, has not defaulted."},
    {"ticker": "CCO", "cik": None, "name": "Clear Channel Outdoor Holdings, Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Heavily levered outdoor advertising company, has not defaulted."},
    {"ticker": "AVTR", "cik": None, "name": "Avantor, Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Levered from its PE-sponsored history, has not defaulted."},
    {"ticker": "HLF", "cik": None, "name": "Herbalife Ltd.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Carries meaningful leverage, has not defaulted."},
    {"ticker": "KHC", "cik": None, "name": "The Kraft Heinz Company",
     "is_distressed": 0, "distress_date": None,
     "notes": "Levered from its 3G Capital-driven merger history, has not defaulted."},
    {"ticker": "QSR", "cik": None, "name": "Restaurant Brands International Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Levered from its 3G Capital-sponsored history, has not defaulted."},
    {"ticker": "ECHO", "cik": None, "name": "EchoStar Corporation",
     "is_distressed": 0, "distress_date": None,
     "notes": "Surviving entity of the 2023 DISH Network / EchoStar merger, heavily levered, "
              "has not defaulted. Current ticker confirmed as ECHO (formerly SATS)."},
    {"ticker": "HOUS", "cik": "0001563190", "name": "Anywhere Real Estate Inc.",
     "is_distressed": 0, "distress_date": None,
     "notes": "Formerly Realogy Holdings, carries meaningful leverage, has not defaulted. "
              "Delisted after 2025 Compass acquisition - CIK confirmed directly via EDGAR."},
]

ML_DATASET_COMPANIES = DISTRESSED_COMPANIES + NOT_DISTRESSED_COMPANIES
