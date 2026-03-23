from __future__ import annotations

from typing import Any, Dict, List

# Purpose descriptions for download sources, keyed by source_id from source_specs().
_DOWNLOAD_PURPOSES: Dict[str, str] = {
    "census_bps_cbsa_annual": "Top-metro annual permit totals.",
    "census_bps_county_annual": "County-level annual permit counts for county-year workflows.",
    "hud_fmr_county": "County-level FMR benchmarks.",
    "hud_safmr_zip": "ZIP-level selected-metro detail layer.",
    "census_delineation_list1": "County-to-CBSA membership crosswalk used for county rollups.",
    "census_delineation_list2": "Principal-city membership within each CBSA.",
    "census_metro_population_estimates": "Top-metro selection and normalization.",
    "census_cbsa_gazetteer": "CBSA internal point latitude/longitude for map rendering.",
    "census_zcta_boundaries": "Selected-metro SAFMR ZIP geometry joins.",
    "census_county_boundaries": "County outlines for selected-metro context.",
}


def _reference_sources() -> List[Dict[str, str]]:
    """Entries for documentation/reference pages (not downloaded by the pipeline)."""
    return [
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
    ]


def _acs_sources(*, acs_metro_year: int, acs_county_year: int) -> List[Dict[str, str]]:
    """ACS query URL entries (fetched by acs.py, not source_specs)."""
    return [
        {
            "id": f"acs1_metro_profile_{acs_metro_year}",
            "name": f"ACS 1-year {acs_metro_year} metro profile query",
            "url": f"https://api.census.gov/data/{acs_metro_year}/acs/acs1/profile?get=NAME,DP03_0062E,DP04_0001E,DP04_0046E,DP04_0134E,DP04_0142PE&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*",
            "purpose": "Metro-level income, housing, and rent burden data.",
        },
        {
            "id": f"acs1_metro_base_{acs_metro_year}",
            "name": f"ACS 1-year {acs_metro_year} metro base query",
            "url": f"https://api.census.gov/data/{acs_metro_year}/acs/acs1?get=NAME,B01003_001E,B11001_001E&for=metropolitan%20statistical%20area/micropolitan%20statistical%20area:*",
            "purpose": "Metro-level population and household counts.",
        },
        {
            "id": f"acs5_county_profile_{acs_county_year}",
            "name": f"ACS 5-year {acs_county_year} county profile query",
            "url": f"https://api.census.gov/data/{acs_county_year}/acs/acs5/profile?get=NAME,DP03_0062E,DP04_0001E,DP04_0046E,DP04_0134E,DP04_0142PE&for=county:*",
            "purpose": "County-level income, housing, and rent burden data.",
        },
        {
            "id": f"acs5_county_base_{acs_county_year}",
            "name": f"ACS 5-year {acs_county_year} county base query",
            "url": f"https://api.census.gov/data/{acs_county_year}/acs/acs5?get=NAME,B01003_001E,B11001_001E&for=county:*",
            "purpose": "County-level population and household counts.",
        },
    ]


def catalog(
    *,
    fixture_mode: bool = True,
    data_vintages: Dict[str, str] | None = None,
    bps_year: int = 2024,
    hud_year: int = 2026,
    acs_metro_year: int = 2024,
    acs_county_year: int = 2024,
) -> Dict[str, Any]:
    from .fetch_real_sources import source_specs

    # Download sources — single source of truth for URLs is source_specs()
    specs = source_specs(bps_year=bps_year, hud_year=hud_year)
    download_sources = [
        {
            "id": spec.source_id,
            "name": spec.description,
            "url": spec.url,
            "purpose": _DOWNLOAD_PURPOSES.get(spec.source_id, spec.description),
        }
        for spec in specs
    ]

    return {
        "fixture_mode": fixture_mode,
        "data_vintages": data_vintages or {},
        "data_sources": (
            _reference_sources()
            + _acs_sources(acs_metro_year=acs_metro_year, acs_county_year=acs_county_year)
            + download_sources
        ),
    }
