"""ETL: CDC PLACES county health data + HRSA MUA/P designations -> SQLite.

Usage:  python etl.py
Downloads both sources into data/raw/ (skipped if already present), joins them
at the county level for Washington State, and writes wa_healthcare.db.
"""
import sqlite3
from pathlib import Path

import pandas as pd
import requests

RAW = Path("data/raw")
DB = Path("wa_healthcare.db")
PLACES_FILE = RAW / "places_county_health_wa.csv"
HRSA_FILE = RAW / "mua_mup_dashboard_wa.csv"

# CDC PLACES: county data (long format: one row per county x measure)
PLACES_URL = "https://data.cdc.gov/resource/swc5-untb.csv"
# HRSA Medically Underserved Areas / Populations (MUA/P) detail file
HRSA_URL = "https://data.hrsa.gov/DataDownload/DD_Files/MUA_DET.csv"

MEASURES = {  # PLACES measureid -> column name
    "ACCESS2": "pct_uninsured_adults",
    "DIABETES": "pct_diabetes",
    "OBESITY": "pct_obesity",
    "DEPRESSION": "pct_depression",
    "BPHIGH": "pct_high_blood_pressure",
    "CHECKUP": "pct_annual_checkup",
}


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    if not PLACES_FILE.exists():
        r = requests.get(
            PLACES_URL,
            params={"$where": "stateabbr='WA'", "$limit": 100000},
            timeout=120,
        )
        r.raise_for_status()
        PLACES_FILE.write_bytes(r.content)
    if not HRSA_FILE.exists():
        r = requests.get(HRSA_URL, timeout=300)
        r.raise_for_status()
        HRSA_FILE.write_bytes(r.content)


def find_col(df, *keywords):
    """Return the first column whose lowercase name contains all keywords."""
    for c in df.columns:
        low = c.lower()
        if all(k in low for k in keywords):
            return c
    raise KeyError(f"No column matching {keywords}; columns are {list(df.columns)}")


def load_places():
    df = pd.read_csv(PLACES_FILE, dtype={"locationid": str})
    df = df[df["measureid"].isin(MEASURES)]
    # Use crude prevalence only, so each county x measure appears once
    df = df[df["datavaluetypeid"] == "CrdPrv"]
    # If multiple release years are present, keep the latest per county x measure
    df = df.sort_values("year").drop_duplicates(["locationid", "measureid"], keep="last")
    df["data_value"] = pd.to_numeric(df["data_value"], errors="coerce")
    # Reshape long -> wide: one row per county
    wide = df.pivot(index="locationid", columns="measureid", values="data_value")
    wide = wide.rename(columns=MEASURES)
    names = df.drop_duplicates("locationid").set_index("locationid")[
        ["locationname", "totalpopulation"]
    ]
    out = names.join(wide).reset_index()
    out = out.rename(columns={"locationid": "county_fips", "locationname": "county"})
    out["county_fips"] = out["county_fips"].str.zfill(5)
    out["totalpopulation"] = pd.to_numeric(out["totalpopulation"], errors="coerce")
    return out


def load_hrsa():
    df = pd.read_csv(HRSA_FILE, dtype=str)
    # The HRSA file is national, so filter to Washington first
    df = df[df["State Abbreviation"] == "WA"].copy()
    # Keep only currently designated records (drop withdrawn / proposed-for-withdrawal)
    status = df["MUA/P Status Description"]
    df = df[status.str.contains("Designated", case=False, na=False)
            & ~status.str.contains("Withdrawn|Proposed", case=False, na=False)]
    # 5-digit county FIPS (state + county)
    df["county_fips"] = df["Common State County FIPS Code"].str.zfill(5)
    # Many-to-one: many MUA/P records (often census tracts) fall in one county
    # -> collapse to one row per county
    flags = (df.groupby("county_fips").size()
               .rename("num_mua_p_designations").reset_index())
    flags["is_underserved"] = 1
    return flags


def build():
    places = load_places()
    hrsa = load_hrsa()
    merged = places.merge(hrsa, on="county_fips", how="left")
    merged["is_underserved"] = merged["is_underserved"].fillna(0).astype(int)
    merged["num_mua_p_designations"] = merged["num_mua_p_designations"].fillna(0).astype(int)
    assert merged["county_fips"].is_unique, "duplicate counties after join"
    return merged


def main():
    download()
    merged = build()
    with sqlite3.connect(DB) as con:
        merged.to_sql("county_health", con, if_exists="replace", index=False)
    print(f"Wrote {len(merged)} counties to {DB}")
    if len(merged) != 39:
        print("WARNING: expected 39 Washington counties")


if __name__ == "__main__":
    main()
