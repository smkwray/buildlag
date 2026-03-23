from __future__ import annotations

from typing import Any, Dict


def catalog(
    *,
    fixture_mode: bool = True,
    data_vintages: Dict[str, str] | None = None,
    bps_year: int = 2024,
    hud_year: int = 2026,
    acs_year: int = 2024,
) -> Dict[str, Any]:
    hud_yy = str(hud_year)[-2:]
    return {
        "fixture_mode": fixture_mode,
        "data_vintages": data_vintages or {},
        "data_sources": [
            {
                "id": "census_bps_home",
                "name": "Census Building Permits Survey",
                "url": "https://www.census.gov/permits",
                "purpose": "Construction permitting data at CBSA, county, and place levels.",
            },
            {
                "id": "census_bps_master",
                "name": "Census BPS master-data directory",
                "url": "https://www2.census.gov/econ/bps/Master%20Data%20Set/",
                "purpose": "Compiled source files for deeper ETL work.",
            },
            {
                "id": f"census_bps_cbsa_annual_{bps_year}",
                "name": f"BPS {bps_year} annual CBSA file",
                "url": f"https://www.census.gov/construction/bps/xls/cbsaannual_{bps_year}99.xls",
                "purpose": "Top-metro annual permit totals.",
            },
            {
                "id": "acs_api_docs",
                "name": "ACS API docs",
                "url": "https://www.census.gov/programs-surveys/acs/data/data-via-api.html",
                "purpose": "Programmatic ACS extraction.",
            },
            {
                "id": "acs_acs1_profile_examples",
                "name": "ACS 1-year profile examples",
                "url": f"https://api.census.gov/data/{acs_year}/acs/acs1/profile/examples.html",
                "purpose": "Geography and endpoint examples for metro pulls.",
            },
            {
                "id": "acs_geography_examples",
                "name": "ACS 1-year geography list",
                "url": f"https://api.census.gov/data/{acs_year}/acs/acs1/geography.html",
                "purpose": "Confirms metro geography support in ACS 1-year.",
            },
            {
                "id": "hud_fmr_docs",
                "name": "HUD FMR docs",
                "url": "https://www.huduser.gov/portal/datasets/fmr.html",
                "purpose": "County FMRs and SAFMR downloads.",
            },
            {
                "id": "hud_fmr_api_docs",
                "name": "HUD FMR API docs",
                "url": "https://www.huduser.gov/portal/dataset/fmr-api.html",
                "purpose": "Alternative API access path for FMR metadata.",
            },
            {
                "id": f"hud_fmr_{hud_year}_county",
                "name": f"HUD FY{hud_year} county FMR file",
                "url": f"https://www.huduser.gov/portal/datasets/fmr/fmr{hud_year}/FY{hud_yy}_FMRs.xlsx",
                "purpose": f"County-level {hud_year} FMR benchmarks.",
            },
            {
                "id": f"hud_safmr_{hud_year}",
                "name": f"HUD FY{hud_year} SAFMR file",
                "url": f"https://www.huduser.gov/portal/datasets/fmr/fmr{hud_year}/fy{hud_year}_safmrs.xlsx",
                "purpose": "ZIP-level selected-metro detail layer.",
            },
            {
                "id": "delineation_2023_list2",
                "name": "Census county-to-CBSA delineation file",
                "url": "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list2_2023.xlsx",
                "purpose": "County-to-CBSA rollup.",
            },
            {
                "id": "delineation_2023_list1",
                "name": "Census county-to-CBSA (List 1) file",
                "url": "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx",
                "purpose": "County-level CBSA membership crosswalk.",
            },
            {
                "id": "metro_population_2024",
                "name": "Census metro population estimates",
                "url": "https://www2.census.gov/programs-surveys/popest/tables/2020-2024/metro/totals/cbsa-met-est2024-pop.xlsx",
                "purpose": "Top-metro selection and normalization.",
            },
            {
                "id": "census_cbsa_gazetteer_2023",
                "name": "Census CBSA Gazetteer",
                "url": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip",
                "purpose": "CBSA internal point latitude/longitude for map rendering.",
            },
            {
                "id": f"census_bps_county_annual_{bps_year}",
                "name": f"BPS {bps_year} county annual file",
                "url": f"https://www2.census.gov/econ/bps/County/co{bps_year}a.txt",
                "purpose": "County-level annual permit counts for county-year workflows.",
            },
            {
                "id": "census_zcta_boundaries_2020",
                "name": "Census ZCTA boundaries",
                "url": "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip",
                "purpose": "Selected-metro SAFMR ZIP geometry joins.",
            },
            {
                "id": "census_county_boundaries_2023",
                "name": "Census county boundaries",
                "url": "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip",
                "purpose": "County outlines for selected-metro context.",
            },
        ],
    }
