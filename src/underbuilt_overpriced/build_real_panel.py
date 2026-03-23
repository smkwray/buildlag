from __future__ import annotations

import csv
import io
import re
import shutil
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd
import shapefile

from .acs import AcsVintage, fetch_acs_context
from .bundle import (
    metro_points_geojson,
    polygon_geojson,
    read_csv_rows,
    write_csv_rows,
    write_json,
)
from .fetch_real_sources import MANIFEST_NAME, fetch_real_sources, load_manifest, vintages_from_manifest
from .scoring import enrich_rows
from .source_catalog import catalog


PREFERRED_DETAIL_CBSA = "12420"  # Austin-Round Rock-Georgetown


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_int_string(value: object, width: int = 0) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        integer = int(float(value))
    except (TypeError, ValueError):
        return ""
    text = str(integer)
    if width:
        text = text.zfill(width)
    return text


def _as_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_metro_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    text = text.replace("\u2019", "'").strip()
    text = re.sub(r"^\.+", "", text)
    text = re.sub(r"\s+(Metro|Micro) Area$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _state_suffix_from_metro_name(name: str) -> str:
    if "," not in name:
        return ""
    return name.split(",")[-1].strip()


def _extract_cbsa_code(hud_area_code: object) -> str:
    text = str(hud_area_code or "")
    match = re.search(r"METRO(\d{5})M", text)
    return match.group(1) if match else ""


def _strip_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _pressure_band(safmr_2br: float) -> str:
    if safmr_2br >= 2250:
        return "very high"
    if safmr_2br >= 2100:
        return "high"
    if safmr_2br >= 1950:
        return "moderate"
    return "lower"


def load_bps_cbsa(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="CBSA Units Ann", skiprows=5)
    df = _strip_columns(df)
    df = df[df["CBSA"].notna() & df["Total"].notna()].copy()

    df["cbsa_code"] = df["CBSA"].map(lambda v: _as_int_string(v, 5))
    df["metro_name"] = df["Name"].astype(str).str.strip()
    df["state_abbrs"] = df["metro_name"].map(_state_suffix_from_metro_name)
    df["permits_annual"] = pd.to_numeric(df["Total"], errors="coerce")
    df["metro_micro_code"] = pd.to_numeric(df["Metro /Micro Code"], errors="coerce")

    # Keep metro rows (codes 2 and 4); drop micropolitan rows (5).
    df = df[df["metro_micro_code"] != 5]
    df = df[["cbsa_code", "metro_name", "state_abbrs", "permits_annual"]]
    df = df.dropna(subset=["permits_annual"])
    return df.drop_duplicates(subset=["cbsa_code"]).reset_index(drop=True)


def load_bps_county(path: Path) -> pd.DataFrame:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        for record in reader:
            if not record:
                continue
            if not str(record[0]).strip().isdigit():
                continue
            if len(record) < 17:
                continue

            state_fips = _as_int_string(record[1], 2)
            county_fips_part = _as_int_string(record[2], 3)
            county_fips = f"{state_fips}{county_fips_part}"
            county_name = str(record[5]).strip()
            permits_annual = (
                _as_float(record[7]) + _as_float(record[10]) + _as_float(record[13]) + _as_float(record[16])
            )
            rows.append(
                {
                    "county_fips": county_fips,
                    "county_name_bps": county_name,
                    "permits_annual_county": int(round(permits_annual)),
                }
            )

    return pd.DataFrame(rows).drop_duplicates(subset=["county_fips"])


def load_hud_fmr(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="FY26_FMRs")
    df = _strip_columns(df)
    df["cbsa_code"] = df["hud_area_code"].map(_extract_cbsa_code)
    df["fmr_2"] = pd.to_numeric(df["fmr_2"], errors="coerce")
    df["weight"] = pd.to_numeric(df["pop2023"], errors="coerce").fillna(1).clip(lower=1)
    df["metro"] = pd.to_numeric(df["metro"], errors="coerce")

    df = df[(df["metro"] == 1) & (df["cbsa_code"] != "") & df["fmr_2"].notna()].copy()

    weighted = (
        df.groupby("cbsa_code")
        .apply(lambda g: (g["fmr_2"] * g["weight"]).sum() / g["weight"].sum(), include_groups=False)
        .reset_index(name="hud_fmr_2br")
    )
    weighted["hud_fmr_2br"] = weighted["hud_fmr_2br"].round(0)
    return weighted


def load_hud_safmr(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="SAFMRs")
    df.columns = [re.sub(r"\s+", " ", str(col).replace("\n", " ")).strip() for col in df.columns]
    df["cbsa_code"] = df["HUD Area Code"].map(_extract_cbsa_code)
    df["zip_code"] = df["ZIP Code"].map(lambda value: _as_int_string(value, 5))
    df["safmr_2br"] = pd.to_numeric(df["SAFMR 2BR"], errors="coerce")

    cols = ["cbsa_code", "zip_code", "HUD Fair Market Rent Area Name", "safmr_2br"]
    df = df[df["cbsa_code"] != ""].copy()
    df = df[cols].rename(columns={"HUD Fair Market Rent Area Name": "hud_area_name"})
    df = df.dropna(subset=["safmr_2br"])
    return df.drop_duplicates(subset=["cbsa_code", "zip_code"])


def load_acs_metro(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["cbsa_code"] = df["cbsa_code"].map(lambda v: _as_int_string(v, 5))
    numeric_cols = [
        "population",
        "households",
        "median_household_income",
        "total_housing_units",
        "renter_occupied_units",
        "median_gross_rent",
        "rent_burdened_share_pct",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_acs_county(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["county_fips"] = df["county_fips"].map(lambda v: _as_int_string(v, 5))
    numeric_cols = [
        "population",
        "households",
        "median_household_income",
        "total_housing_units",
        "renter_occupied_units",
        "median_gross_rent",
        "rent_burdened_share_pct",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_delineation_list1(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, skiprows=2)
    df = _strip_columns(df)
    df["cbsa_code"] = df["CBSA Code"].map(lambda v: _as_int_string(v, 5))
    df["state_fips"] = df["FIPS State Code"].map(lambda v: _as_int_string(v, 2))
    df["county_fips_part"] = df["FIPS County Code"].map(lambda v: _as_int_string(v, 3))
    df["county_fips"] = df["state_fips"] + df["county_fips_part"]
    return df[["cbsa_code", "county_fips", "County/County Equivalent", "State Name"]].rename(
        columns={"County/County Equivalent": "county_name", "State Name": "state_name"}
    )


def load_cbsa_gazetteer(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith(".txt"))
        content = archive.read(member)

    df = pd.read_csv(io.BytesIO(content), sep="\t")
    df = _strip_columns(df)
    df["cbsa_code"] = df["GEOID"].map(lambda v: _as_int_string(v, 5))
    df["lat"] = pd.to_numeric(df["INTPTLAT"], errors="coerce")
    df["lon"] = pd.to_numeric(df["INTPTLONG"], errors="coerce")
    return df[["cbsa_code", "lat", "lon", "NAME", "CBSA_TYPE"]].rename(columns={"NAME": "gazetteer_name"})


def load_population_estimates(path: Path) -> Dict[str, int]:
    df = pd.read_excel(path, sheet_name=0, skiprows=3)
    first_col = str(df.columns[0])

    year_col = 2024 if 2024 in df.columns else str(2024)
    if year_col not in df.columns:
        return {}

    pop_map: Dict[str, int] = {}
    for _, row in df.iterrows():
        raw_name = row.get(first_col)
        if not isinstance(raw_name, str):
            continue
        cleaned = raw_name.strip()
        if not cleaned.startswith("."):
            continue
        if "Metro Area" not in cleaned:
            continue

        metro_base = cleaned.lstrip(".").replace(" Metro Area", "").strip()
        population = row.get(year_col)
        if pd.isna(population):
            continue
        pop_map[_normalize_metro_name(metro_base)] = int(round(float(population)))

    return pop_map


def build_county_context_interim(project_root: Path, county_acs: pd.DataFrame, delineation: pd.DataFrame, *, year: int) -> Path:
    merged = delineation.merge(county_acs, on="county_fips", how="left")
    output_path = project_root / "data" / "interim" / f"county_acs5_{year}_with_cbsa.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return output_path


def _extract_shapefile_geometries(
    zip_path: Path,
    *,
    key_field: str,
    requested_ids: set[str],
    property_fields: List[str] | None = None,
) -> Dict[str, dict]:
    if not requested_ids:
        return {}

    props = property_fields or []
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(temp_dir)

        shp_path = next(Path(temp_dir).glob("*.shp"))
        reader = shapefile.Reader(str(shp_path))
        field_names = [field[0] for field in reader.fields[1:]]
        key_idx = field_names.index(key_field)
        prop_indices = {name: field_names.index(name) for name in props if name in field_names}

        result: Dict[str, dict] = {}
        for shape_record in reader.iterShapeRecords():
            key = str(shape_record.record[key_idx]).strip()
            if key_field.startswith("ZCTA"):
                key = key.zfill(5)
            if key not in requested_ids:
                continue

            result[key] = {
                "geometry": shape_record.shape.__geo_interface__,
                "properties": {
                    prop_name: shape_record.record[prop_idx]
                    for prop_name, prop_idx in prop_indices.items()
                },
            }
            if len(result) == len(requested_ids):
                break

    return result


def _prepare_scoring_rows(df: pd.DataFrame) -> List[dict]:
    rows: List[dict] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "cbsa_code": row["cbsa_code"],
                "metro_name": row["metro_name"],
                "state_abbrs": row["state_abbrs"],
                "lat": round(float(row["lat"]), 6),
                "lon": round(float(row["lon"]), 6),
                "population": int(round(float(row["population"]))),
                "households": int(round(float(row["households"]))),
                "permits_annual": int(round(float(row["permits_annual"]))),
                "hud_fmr_2br": int(round(float(row["hud_fmr_2br"]))),
                "fmr_2br": int(round(float(row["hud_fmr_2br"]))),
                "median_household_income": int(round(float(row["median_household_income"]))),
                "rent_burdened_share_pct": round(float(row["rent_burdened_share_pct"]), 1),
                "median_gross_rent_acs": int(round(float(row["median_gross_rent"]))),
                "renter_occupied_units": int(round(float(row["renter_occupied_units"]))),
                "total_housing_units": int(round(float(row["total_housing_units"]))),
            }
        )
    return rows


def _detail_paths_for_cbsa(cbsa_code: str) -> dict:
    return {
        "zips_path": f"data/detail/{cbsa_code}/zips.geojson",
        "counties_path": f"data/detail/{cbsa_code}/counties.geojson",
        "context_path": f"data/detail/{cbsa_code}/context.json",
    }


def _write_detail_fallback(site_data_dir: Path, project_root: Path, *, detail_cbsa_code: str, detail_metro_name: str) -> dict:
    fixture_dir = project_root / "data" / "fixtures"
    detail_dir = site_data_dir / "detail" / detail_cbsa_code
    detail_dir.mkdir(parents=True, exist_ok=True)
    austin_zip_rows = read_csv_rows(fixture_dir / "austin_zip_inputs.csv")
    austin_county_rows = read_csv_rows(fixture_dir / "austin_county_inputs.csv")
    write_json(detail_dir / "zips.geojson", polygon_geojson(austin_zip_rows, id_field="zip_code"))
    write_json(detail_dir / "counties.geojson", polygon_geojson(austin_county_rows, id_field="county_name"))

    detail_context = {
        "detail_mode": "fixture_fallback",
        "detail_cbsa_code": detail_cbsa_code,
        "detail_metro_name": detail_metro_name,
        "cbsa_summary": {
            "zip_count": len(austin_zip_rows),
            "county_count": len(austin_county_rows),
        },
        "counties": [
            {
                "county_name": row.get("county_name"),
                "permits_annual": row.get("permits_annual", row.get("permits_2024")),
                "permits_per_1000_households": row.get("permits_per_1000_households"),
            }
            for row in austin_county_rows
        ],
    }
    write_json(detail_dir / "context.json", detail_context)

    detail_paths = _detail_paths_for_cbsa(detail_cbsa_code)
    detail_index = {
        "detail_mode": "fixture_fallback",
        "default_cbsa_code": detail_cbsa_code,
        "default_metro_name": detail_metro_name,
        "supported_detail_count": 1,
        "supported_details": [
            {
                "cbsa_code": detail_cbsa_code,
                "metro_name": detail_metro_name,
                "detail_mode": "fixture_fallback",
                "zip_count": len(austin_zip_rows),
                "county_count": len(austin_county_rows),
                **detail_paths,
            }
        ],
    }
    write_json(site_data_dir / "detail_index.json", detail_index)

    return {
        "detail_mode": "fixture_fallback",
        "default_cbsa_code": detail_cbsa_code,
        "default_metro_name": detail_metro_name,
        "selected_metro_zip_features": len(austin_zip_rows),
        "selected_metro_counties": len(austin_county_rows),
        "supported_detail_count": 1,
    }


def _build_real_detail_layers(
    *,
    site_data_dir: Path,
    raw_dir: Path,
    safmr_df: pd.DataFrame,
    delineation_df: pd.DataFrame,
    acs_county_df: pd.DataFrame,
    bps_county_df: pd.DataFrame,
    scored_rows: List[dict],
    default_cbsa_code: str,
) -> dict:
    scored_by_cbsa = {row["cbsa_code"]: row for row in scored_rows}
    supported_cbsa_codes = [row["cbsa_code"] for row in scored_rows if row["cbsa_code"] in set(safmr_df["cbsa_code"].unique())]
    if not supported_cbsa_codes:
        raise ValueError("No SAFMR-supported metros found in scored rows")

    all_safmr = safmr_df[safmr_df["cbsa_code"].isin(supported_cbsa_codes)].copy()
    zip_codes = {str(code).zfill(5) for code in all_safmr["zip_code"].tolist()}
    zcta_geometries = _extract_shapefile_geometries(
        raw_dir / "census_zcta_2020_500k.zip",
        key_field="ZCTA5CE20",
        requested_ids=zip_codes,
    )
    all_detail_counties = delineation_df[delineation_df["cbsa_code"].isin(supported_cbsa_codes)].copy()
    county_fips_set = set(all_detail_counties["county_fips"].tolist())
    county_geometries = _extract_shapefile_geometries(
        raw_dir / "census_county_2023_500k.zip",
        key_field="GEOID",
        requested_ids=county_fips_set,
    )

    county_context_df = (
        all_detail_counties.merge(acs_county_df, on="county_fips", how="left", suffixes=("", "_acs"))
        .merge(bps_county_df, on="county_fips", how="left", suffixes=("", "_bps"))
    )
    if "county_name" not in county_context_df.columns:
        for alt in ["county_name_x", "county_name_acs", "county_name_bps"]:
            if alt in county_context_df.columns:
                county_context_df["county_name"] = county_context_df[alt]
                break
    county_context_df["permits_annual_county"] = pd.to_numeric(
        county_context_df["permits_annual_county"], errors="coerce"
    ).fillna(0)
    county_context_df["households"] = pd.to_numeric(county_context_df["households"], errors="coerce")
    county_context_df["permits_per_1000_households"] = (
        county_context_df["permits_annual_county"] / county_context_df["households"] * 1000
    ).replace([float("inf"), -float("inf")], pd.NA)

    detail_root = site_data_dir / "detail"
    if detail_root.exists():
        shutil.rmtree(detail_root)
    detail_root.mkdir(parents=True, exist_ok=True)

    supported_details = []
    for cbsa_code in supported_cbsa_codes:
        metro_name = scored_by_cbsa[cbsa_code]["metro_name"]
        detail_dir = detail_root / cbsa_code
        detail_dir.mkdir(parents=True, exist_ok=True)

        safmr_selected = all_safmr[all_safmr["cbsa_code"] == cbsa_code].copy()
        zip_features = []
        for _, row in safmr_selected.sort_values("zip_code").iterrows():
            zip_code = str(row["zip_code"]).zfill(5)
            geometry_payload = zcta_geometries.get(zip_code)
            if not geometry_payload:
                continue
            safmr_2br = float(row["safmr_2br"])
            zip_features.append(
                {
                    "type": "Feature",
                    "id": zip_code,
                    "geometry": geometry_payload["geometry"],
                    "properties": {
                        "zip_code": zip_code,
                        "label": str(row["hud_area_name"]),
                        "safmr_2br": round(safmr_2br, 0),
                        "pressure_band": _pressure_band(safmr_2br),
                        "cbsa_code": cbsa_code,
                    },
                }
            )
        if not zip_features:
            continue

        county_features = []
        county_context_rows = []
        metro_county_rows = county_context_df[county_context_df["cbsa_code"] == cbsa_code].copy()
        for _, row in metro_county_rows.sort_values("county_name").iterrows():
            county_fips = str(row["county_fips"]).zfill(5)
            geometry_payload = county_geometries.get(county_fips)
            if not geometry_payload:
                continue

            permits_per_1000 = row.get("permits_per_1000_households")
            county_properties = {
                "county_fips": county_fips,
                "county_name": row.get("county_name"),
                "state_name": row.get("state_name"),
                "population": int(round(_as_float(row.get("population")))) if pd.notna(row.get("population")) else None,
                "households": int(round(_as_float(row.get("households")))) if pd.notna(row.get("households")) else None,
                "permits_annual": int(round(_as_float(row.get("permits_annual_county")))),
                "permits_per_1000_households": round(float(permits_per_1000), 2) if pd.notna(permits_per_1000) else None,
                "median_household_income": int(round(_as_float(row.get("median_household_income")))) if pd.notna(row.get("median_household_income")) else None,
                "rent_burdened_share_pct": round(float(row.get("rent_burdened_share_pct")), 1) if pd.notna(row.get("rent_burdened_share_pct")) else None,
            }
            county_features.append(
                {
                    "type": "Feature",
                    "id": county_fips,
                    "geometry": geometry_payload["geometry"],
                    "properties": county_properties,
                }
            )
            county_context_rows.append(county_properties)

        safmr_series = pd.Series([feature["properties"]["safmr_2br"] for feature in zip_features])
        detail_context = {
            "detail_mode": "real_safmr_zcta",
            "detail_cbsa_code": cbsa_code,
            "detail_metro_name": metro_name,
            "cbsa_summary": {
                "zip_count": len(zip_features),
                "county_count": len(county_context_rows),
                "safmr_2br_min": round(float(safmr_series.min()), 0),
                "safmr_2br_median": round(float(safmr_series.median()), 0),
                "safmr_2br_max": round(float(safmr_series.max()), 0),
                "safmr_2br_mean": round(float(safmr_series.mean()), 0),
            },
            "counties": county_context_rows,
        }
        write_json(detail_dir / "zips.geojson", {"type": "FeatureCollection", "features": zip_features})
        write_json(detail_dir / "counties.geojson", {"type": "FeatureCollection", "features": county_features})
        write_json(detail_dir / "context.json", detail_context)

        supported_details.append(
            {
                "cbsa_code": cbsa_code,
                "metro_name": metro_name,
                "detail_mode": "real_safmr_zcta",
                "zip_count": len(zip_features),
                "county_count": len(county_context_rows),
                **_detail_paths_for_cbsa(cbsa_code),
            }
        )

    if not supported_details:
        raise ValueError("No detail bundles were produced from available SAFMR and geometry inputs")

    default_entry = next(
        (entry for entry in supported_details if entry["cbsa_code"] == default_cbsa_code),
        supported_details[0],
    )
    detail_index = {
        "detail_mode": "multi_metro_real_safmr_zcta",
        "default_cbsa_code": default_entry["cbsa_code"],
        "default_metro_name": default_entry["metro_name"],
        "supported_detail_count": len(supported_details),
        "supported_details": supported_details,
    }
    write_json(site_data_dir / "detail_index.json", detail_index)

    return {
        "detail_mode": "multi_metro_real_safmr_zcta",
        "default_cbsa_code": default_entry["cbsa_code"],
        "default_metro_name": default_entry["metro_name"],
        "selected_metro_zip_features": default_entry["zip_count"],
        "selected_metro_counties": default_entry["county_count"],
        "supported_detail_count": len(supported_details),
    }


def build_real_panel(
    project_root: Path,
    *,
    top_n: int = 75,
    bps_year: int = 2024,
    hud_year: int = 2026,
    acs_vintage: AcsVintage | None = None,
    force_fetch: bool = False,
    allow_fallback: bool = False,
) -> None:
    raw_dir = project_root / "data" / "raw"
    processed_dir = project_root / "data" / "processed"
    site_data_dir = project_root / "site" / "data"

    manifest_path = raw_dir / MANIFEST_NAME
    if not manifest_path.exists() or force_fetch:
        manifest_path = fetch_real_sources(
            project_root,
            bps_year=bps_year,
            hud_year=hud_year,
            force=force_fetch,
        )

    acs_paths = fetch_acs_context(raw_dir, vintage=acs_vintage, force=force_fetch)
    acs_selected = acs_vintage or AcsVintage()

    bps_df = load_bps_cbsa(raw_dir / f"census_bps_cbsaannual_{bps_year}99.xls")
    bps_county_df = load_bps_county(raw_dir / f"census_bps_county_co{bps_year}a.txt")
    hud_df = load_hud_fmr(raw_dir / f"hud_fmr_fy{hud_year}_county.xlsx")
    hud_safmr_df = load_hud_safmr(raw_dir / f"hud_safmr_fy{hud_year}_zip.xlsx")
    acs_metro_df = load_acs_metro(acs_paths["metro"].with_suffix(".csv"))
    acs_county_df = load_acs_county(acs_paths["county"].with_suffix(".csv"))
    delineation_df = load_delineation_list1(raw_dir / "census_delineation_list1_2023.xlsx")
    gaz_df = load_cbsa_gazetteer(raw_dir / "census_gazetteer_cbsa_2023.zip")
    pop_map = load_population_estimates(raw_dir / "census_cbsa_met_est2024_pop.xlsx")

    build_county_context_interim(
        project_root,
        acs_county_df,
        delineation_df,
        year=acs_selected.county_acs5_year,
    )

    panel_df = (
        bps_df.merge(hud_df, on="cbsa_code", how="inner")
        .merge(acs_metro_df, on="cbsa_code", how="inner", suffixes=("", "_acs"))
        .merge(gaz_df[["cbsa_code", "lat", "lon"]], on="cbsa_code", how="left")
    )

    panel_df = panel_df.dropna(
        subset=[
            "permits_annual",
            "hud_fmr_2br",
            "population",
            "households",
            "median_household_income",
            "rent_burdened_share_pct",
            "lat",
            "lon",
        ]
    )

    # Use official Census population estimates when names line up; fall back to ACS population otherwise.
    panel_df["population"] = panel_df.apply(
        lambda row: pop_map.get(_normalize_metro_name(row["metro_name"]), int(row["population"])),
        axis=1,
    )

    top_df = panel_df.sort_values("population", ascending=False).head(top_n).copy()
    rows = _prepare_scoring_rows(top_df)
    scored_rows = enrich_rows(rows)

    for row in scored_rows:
        row["data_vintage_bps"] = str(bps_year)
        row["data_vintage_acs"] = f"{acs_selected.metro_acs1_year} ACS1 / {acs_selected.county_acs5_year} ACS5"
        row["data_vintage_hud"] = f"FY{hud_year}"

    scored_rows = sorted(scored_rows, key=lambda item: float(item["overall_score"]), reverse=True)

    fieldnames = [
        "cbsa_code",
        "metro_name",
        "state_abbrs",
        "lat",
        "lon",
        "population",
        "households",
        "permits_annual",
        "hud_fmr_2br",
        "fmr_2br",
        "median_household_income",
        "median_gross_rent_acs",
        "renter_occupied_units",
        "total_housing_units",
        "rent_burdened_share_pct",
        "permits_per_1000_households",
        "fmr_to_income",
        "underbuilt_component",
        "overpriced_component",
        "overall_score",
        "score_bucket",
        "data_vintage_bps",
        "data_vintage_acs",
        "data_vintage_hud",
    ]

    write_csv_rows(processed_dir / "metro_panel.csv", scored_rows, fieldnames)
    write_json(processed_dir / "metro_panel.json", scored_rows)
    write_csv_rows(site_data_dir / "metro_panel.csv", scored_rows, fieldnames)
    write_json(site_data_dir / "metro_panel.json", scored_rows)
    write_json(site_data_dir / "metro_points.geojson", metro_points_geojson(scored_rows))

    manifest = load_manifest(manifest_path)
    manifest_vintages = vintages_from_manifest(manifest)
    vintages = {
        "bps": manifest_vintages.get("census_bps_cbsa_annual", str(bps_year)),
        "hud": manifest_vintages.get("hud_fmr_county", f"FY{hud_year}"),
        "hud_safmr": manifest_vintages.get("hud_safmr_zip", f"FY{hud_year}"),
        "delineation": manifest_vintages.get("census_delineation_list1", "2023"),
        "population": manifest_vintages.get("census_metro_population_estimates", "2024"),
        "gazetteer": manifest_vintages.get("census_cbsa_gazetteer", "2023"),
        "zcta_boundaries": manifest_vintages.get("census_zcta_boundaries", "2020"),
        "county_boundaries": manifest_vintages.get("census_county_boundaries", "2023"),
        "acs_metro": str(acs_selected.metro_acs1_year),
        "acs_county": str(acs_selected.county_acs5_year),
    }

    scored_by_cbsa = {row["cbsa_code"]: row for row in scored_rows}
    safmr_cbsa_set = set(hud_safmr_df["cbsa_code"].unique())
    candidate_codes = [row["cbsa_code"] for row in scored_rows if row["cbsa_code"] in safmr_cbsa_set]

    detail_cbsa_code = PREFERRED_DETAIL_CBSA
    if detail_cbsa_code not in scored_by_cbsa or detail_cbsa_code not in safmr_cbsa_set:
        detail_cbsa_code = candidate_codes[0] if candidate_codes else scored_rows[0]["cbsa_code"]
    detail_metro_name = scored_by_cbsa[detail_cbsa_code]["metro_name"]

    if allow_fallback:
        try:
            detail_result = _build_real_detail_layers(
                site_data_dir=site_data_dir,
                raw_dir=raw_dir,
                safmr_df=hud_safmr_df,
                delineation_df=delineation_df,
                acs_county_df=acs_county_df,
                bps_county_df=bps_county_df,
                scored_rows=scored_rows,
                default_cbsa_code=detail_cbsa_code,
            )
        except Exception:
            import logging
            import traceback

            logging.warning(
                "Detail layer build failed; falling back to fixture data.\n%s",
                traceback.format_exc(),
            )
            detail_result = _write_detail_fallback(
                site_data_dir,
                project_root,
                detail_cbsa_code=detail_cbsa_code,
                detail_metro_name=detail_metro_name,
            )
    else:
        detail_result = _build_real_detail_layers(
            site_data_dir=site_data_dir,
            raw_dir=raw_dir,
            safmr_df=hud_safmr_df,
            delineation_df=delineation_df,
            acs_county_df=acs_county_df,
            bps_county_df=bps_county_df,
            scored_rows=scored_rows,
            default_cbsa_code=detail_cbsa_code,
        )

    metadata = {
        "project": "Underbuilt vs. Overpriced Atlas",
        "fixture_mode": False,
        "detail_mode": detail_result["detail_mode"],
        "detail_metro_code": detail_result["default_cbsa_code"],
        "detail_metro_name": detail_result["default_metro_name"],
        "built_at_utc": _utc_now_iso(),
        "national_metro_count": len(scored_rows),
        "selected_metro_counties": detail_result["selected_metro_counties"],
        "selected_metro_zip_features": detail_result["selected_metro_zip_features"],
        "supported_detail_count": detail_result["supported_detail_count"],
        "download_path": "data/metro_panel.csv",
        "data_vintages": vintages,
        "source_manifest_path": "../data/raw/source_manifest.json",
        "acs_manifest_path": "../data/raw/acs/manifest.json",
        "detail_index_path": "data/detail_index.json",
        "top_n": top_n,
    }
    write_json(site_data_dir / "meta.json", metadata)

    source_catalog_payload = catalog(
        fixture_mode=False,
        data_vintages=vintages,
        bps_year=bps_year,
        hud_year=hud_year,
        acs_year=acs_selected.metro_acs1_year,
    )
    write_json(processed_dir / "source_catalog.json", source_catalog_payload)
    write_json(site_data_dir / "source_catalog.json", source_catalog_payload)

    build_summary = {
        "built_at_utc": _utc_now_iso(),
        "top_n": top_n,
        "rows_after_joins": int(len(panel_df)),
        "rows_scored": int(len(scored_rows)),
        "detail_mode": detail_result["detail_mode"],
        "detail_cbsa_code": detail_result["default_cbsa_code"],
        "detail_metro_name": detail_result["default_metro_name"],
        "detail_zip_features": detail_result["selected_metro_zip_features"],
        "detail_county_features": detail_result["selected_metro_counties"],
        "supported_detail_count": detail_result["supported_detail_count"],
        "inputs": {
            "bps_cbsa": str((raw_dir / f"census_bps_cbsaannual_{bps_year}99.xls").relative_to(project_root)),
            "bps_county": str((raw_dir / f"census_bps_county_co{bps_year}a.txt").relative_to(project_root)),
            "hud_fmr": str((raw_dir / f"hud_fmr_fy{hud_year}_county.xlsx").relative_to(project_root)),
            "hud_safmr": str((raw_dir / f"hud_safmr_fy{hud_year}_zip.xlsx").relative_to(project_root)),
            "acs_metro": str(acs_paths["metro"].relative_to(project_root)),
            "acs_county": str(acs_paths["county"].relative_to(project_root)),
            "delineation": str((raw_dir / "census_delineation_list1_2023.xlsx").relative_to(project_root)),
            "gazetteer": str((raw_dir / "census_gazetteer_cbsa_2023.zip").relative_to(project_root)),
            "zcta_boundaries": str((raw_dir / "census_zcta_2020_500k.zip").relative_to(project_root)),
            "county_boundaries": str((raw_dir / "census_county_2023_500k.zip").relative_to(project_root)),
            "population": str((raw_dir / "census_cbsa_met_est2024_pop.xlsx").relative_to(project_root)),
        },
    }
    write_json(processed_dir / "build_real_panel_summary.json", build_summary)
