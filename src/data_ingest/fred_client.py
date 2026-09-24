"""
FRED data ingestion client - pulls SOFR and credit spread series.

Requires a free FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
Set FRED_API_KEY in your .env file.
"""

import os

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
if not FRED_API_KEY or FRED_API_KEY == "your_fred_api_key_here":
    raise RuntimeError("Set a real FRED_API_KEY in your .env file.")

fred = Fred(api_key=FRED_API_KEY)

# Series you'll want for this project:
SERIES = {
    "SOFR": "Secured Overnight Financing Rate - daily",
    "SOFR90DAYAVG": "90-day compounded average SOFR",
    "BAMLH0A0HYM2": "ICE BofA US High Yield Index Option-Adjusted Spread",
    "BAMLH0A1HYBB": "ICE BofA BB US High Yield Index OAS",
    "BAMLH0A2HYB": "ICE BofA Single-B US High Yield Index OAS",
    "DFF": "Effective Federal Funds Rate - daily",
}


def get_series(series_code: str) -> pd.DataFrame:
    """Returns a DataFrame with columns [obs_date, value] for one FRED series."""
    s = fred.get_series(series_code)
    df = s.reset_index()
    df.columns = ["obs_date", "value"]
    df["series_code"] = series_code
    return df


def get_all_series() -> pd.DataFrame:
    """Pulls every series in SERIES and concatenates into one long DataFrame."""
    frames = [get_series(code) for code in SERIES]
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    df = get_all_series()
    print(df.groupby("series_code")["obs_date"].agg(["min", "max", "count"]))
