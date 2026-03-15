from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import requests


CENSUS_API_BASE = "https://api.census.gov/data"

ACS_PROFILE_VARS = [
    "DP03_0062E",   # median household income
    "DP04_0001E",   # total housing units
    "DP04_0046E",   # renter-occupied housing units
    "DP04_0134E",   # median gross rent
    "DP04_0142PE",  # renter GRAPI 35%+
]

ACS_BASE_VARS = [
    "B01003_001E",  # total population
    "B11001_001E",  # households
]


@dataclass(frozen=True)
class AcsVintage:
    metro_acs1_year: int = 2024
    county_acs5_year: int = 2024


def _to_float(value: object) -> float | None:
    if value is None or value == "" or value == "null":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(round(number))


def _write_csv(path: Path, rows: Iterable[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_census_rows(url: str) -> List[dict]:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    matrix = response.json()
    header = matrix[0]
    rows = []
    for item in matrix[1:]:
        rows.append({header[idx]: value for idx, value in enumerate(item)})
    return rows


def fetch_acs_metro_context(raw_dir: Path, *, year: int = 2024, force: bool = False) -> Path:
    acs_dir = raw_dir / "acs"
    json_path = acs_dir / f"metro_acs1_{year}.json"
    csv_path = acs_dir / f"metro_acs1_{year}.csv"

    if json_path.exists() and csv_path.exists() and not force:
        return json_path

    profile_url = (
        f"{CENSUS_API_BASE}/{year}/acs/acs1/profile?"
        f"get=NAME,{','.join(ACS_PROFILE_VARS)}"
        "&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*"
    )
    base_url = (
        f"{CENSUS_API_BASE}/{year}/acs/acs1?"
        f"get=NAME,{','.join(ACS_BASE_VARS)}"
        "&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*"
    )

    profile_rows = _fetch_census_rows(profile_url)
    base_rows = _fetch_census_rows(base_url)

    profile_by_cbsa = {
        row["metropolitan statistical area/micropolitan statistical area"]: row for row in profile_rows
    }
    base_by_cbsa = {
        row["metropolitan statistical area/micropolitan statistical area"]: row for row in base_rows
    }

    merged = []
    for cbsa_code in sorted(set(profile_by_cbsa.keys()) | set(base_by_cbsa.keys())):
        profile = profile_by_cbsa.get(cbsa_code, {})
        base = base_by_cbsa.get(cbsa_code, {})
        merged.append(
            {
                "cbsa_code": cbsa_code,
                "metro_name": (profile.get("NAME") or base.get("NAME") or "").replace(" Metro Area", "").replace(" Micro Area", ""),
                "population": _to_int(base.get("B01003_001E")),
                "households": _to_int(base.get("B11001_001E")),
                "median_household_income": _to_int(profile.get("DP03_0062E")),
                "total_housing_units": _to_int(profile.get("DP04_0001E")),
                "renter_occupied_units": _to_int(profile.get("DP04_0046E")),
                "median_gross_rent": _to_int(profile.get("DP04_0134E")),
                "rent_burdened_share_pct": _to_float(profile.get("DP04_0142PE")),
                "acs_dataset": "acs1",
                "acs_year": year,
            }
        )

    _write_json(
        json_path,
        {
            "dataset": "acs1",
            "year": year,
            "variables_profile": ACS_PROFILE_VARS,
            "variables_base": ACS_BASE_VARS,
            "rows": merged,
        },
    )
    _write_csv(
        csv_path,
        merged,
        [
            "cbsa_code",
            "metro_name",
            "population",
            "households",
            "median_household_income",
            "total_housing_units",
            "renter_occupied_units",
            "median_gross_rent",
            "rent_burdened_share_pct",
            "acs_dataset",
            "acs_year",
        ],
    )
    return json_path


def fetch_acs_county_context(raw_dir: Path, *, year: int = 2024, force: bool = False) -> Path:
    acs_dir = raw_dir / "acs"
    json_path = acs_dir / f"county_acs5_{year}.json"
    csv_path = acs_dir / f"county_acs5_{year}.csv"

    if json_path.exists() and csv_path.exists() and not force:
        return json_path

    profile_url = (
        f"{CENSUS_API_BASE}/{year}/acs/acs5/profile?"
        f"get=NAME,{','.join(ACS_PROFILE_VARS)}"
        "&for=county:*"
    )
    base_url = (
        f"{CENSUS_API_BASE}/{year}/acs/acs5?"
        f"get=NAME,{','.join(ACS_BASE_VARS)}"
        "&for=county:*"
    )

    profile_rows = _fetch_census_rows(profile_url)
    base_rows = _fetch_census_rows(base_url)

    def county_key(row: dict) -> str:
        return f"{row['state']}{row['county']}"

    profile_by_fips = {county_key(row): row for row in profile_rows}
    base_by_fips = {county_key(row): row for row in base_rows}

    merged = []
    for fips in sorted(set(profile_by_fips.keys()) | set(base_by_fips.keys())):
        profile = profile_by_fips.get(fips, {})
        base = base_by_fips.get(fips, {})
        merged.append(
            {
                "county_fips": fips,
                "county_name": profile.get("NAME") or base.get("NAME") or "",
                "population": _to_int(base.get("B01003_001E")),
                "households": _to_int(base.get("B11001_001E")),
                "median_household_income": _to_int(profile.get("DP03_0062E")),
                "total_housing_units": _to_int(profile.get("DP04_0001E")),
                "renter_occupied_units": _to_int(profile.get("DP04_0046E")),
                "median_gross_rent": _to_int(profile.get("DP04_0134E")),
                "rent_burdened_share_pct": _to_float(profile.get("DP04_0142PE")),
                "acs_dataset": "acs5",
                "acs_year": year,
            }
        )

    _write_json(
        json_path,
        {
            "dataset": "acs5",
            "year": year,
            "variables_profile": ACS_PROFILE_VARS,
            "variables_base": ACS_BASE_VARS,
            "rows": merged,
        },
    )
    _write_csv(
        csv_path,
        merged,
        [
            "county_fips",
            "county_name",
            "population",
            "households",
            "median_household_income",
            "total_housing_units",
            "renter_occupied_units",
            "median_gross_rent",
            "rent_burdened_share_pct",
            "acs_dataset",
            "acs_year",
        ],
    )
    return json_path


def fetch_acs_context(raw_dir: Path, *, vintage: AcsVintage | None = None, force: bool = False) -> Dict[str, Path]:
    selected = vintage or AcsVintage()
    metro_path = fetch_acs_metro_context(raw_dir, year=selected.metro_acs1_year, force=force)
    county_path = fetch_acs_county_context(raw_dir, year=selected.county_acs5_year, force=force)
    project_root = raw_dir.parent.parent

    manifest = {
        "metro": {
            "dataset": "acs1",
            "year": selected.metro_acs1_year,
            "json_path": str(metro_path.relative_to(project_root)),
            "csv_path": str(metro_path.with_suffix(".csv").relative_to(project_root)),
        },
        "county": {
            "dataset": "acs5",
            "year": selected.county_acs5_year,
            "json_path": str(county_path.relative_to(project_root)),
            "csv_path": str(county_path.with_suffix(".csv").relative_to(project_root)),
        },
    }
    manifest_path = raw_dir / "acs" / "manifest.json"
    _write_json(manifest_path, manifest)

    return {
        "metro": metro_path,
        "county": county_path,
        "manifest": manifest_path,
    }
