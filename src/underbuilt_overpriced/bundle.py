from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Sequence

from .scoring import enrich_rows
from .source_catalog import catalog


def read_csv_rows(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def square_polygon(center_lon: float, center_lat: float, half_width_deg: float, half_height_deg: float) -> list:
    return [[
        [center_lon - half_width_deg, center_lat - half_height_deg],
        [center_lon + half_width_deg, center_lat - half_height_deg],
        [center_lon + half_width_deg, center_lat + half_height_deg],
        [center_lon - half_width_deg, center_lat + half_height_deg],
        [center_lon - half_width_deg, center_lat - half_height_deg],
    ]]


def metro_points_geojson(rows: Iterable[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["lon"]), float(row["lat"])],
                },
                "properties": {
                    key: row[key]
                    for key in row.keys()
                    if key not in {"lat", "lon"}
                },
            }
            for row in rows
        ],
    }


def polygon_geojson(rows: Iterable[dict], *, id_field: str) -> dict:
    features = []
    for row in rows:
        features.append(
            {
                "type": "Feature",
                "id": row[id_field],
                "geometry": {
                    "type": "Polygon",
                    "coordinates": square_polygon(
                        float(row["center_lon"]),
                        float(row["center_lat"]),
                        float(row["half_width_deg"]),
                        float(row["half_height_deg"]),
                    ),
                },
                "properties": {
                    key: row[key]
                    for key in row.keys()
                    if key not in {"center_lon", "center_lat", "half_width_deg", "half_height_deg"}
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def build_fixture_bundle(project_root: Path) -> None:
    fixture_dir = project_root / "data" / "fixtures"
    site_data_dir = project_root / "site" / "data"
    processed_dir = project_root / "data" / "processed"

    site_docs_dir = project_root / "site" / "docs"
    site_docs_dir.mkdir(parents=True, exist_ok=True)
    methodology_src = project_root / "docs" / "methodology.md"
    if methodology_src.exists():
        shutil.copyfile(methodology_src, site_docs_dir / "methodology.md")

    metro_rows = read_csv_rows(fixture_dir / "metro_inputs.csv")
    enriched = enrich_rows(metro_rows)
    enriched = sorted(enriched, key=lambda row: float(row["overall_score"]), reverse=True)

    fieldnames = [
        "cbsa_code",
        "metro_name",
        "state_abbrs",
        "lat",
        "lon",
        "population",
        "households",
        "permits_annual",
        "fmr_2br",
        "median_household_income",
        "rent_burdened_share_pct",
        "permits_per_1000_households",
        "fmr_to_income",
        "underbuilt_component",
        "overpriced_component",
        "overall_score",
        "score_bucket",
    ]

    write_csv_rows(site_data_dir / "metro_panel.csv", enriched, fieldnames)
    write_csv_rows(processed_dir / "metro_panel.csv", enriched, fieldnames)
    write_json(site_data_dir / "metro_panel.json", enriched)
    write_json(processed_dir / "metro_panel.json", enriched)
    write_json(site_data_dir / "metro_points.geojson", metro_points_geojson(enriched))

    austin_zip_rows = read_csv_rows(fixture_dir / "austin_zip_inputs.csv")
    austin_county_rows = read_csv_rows(fixture_dir / "austin_county_inputs.csv")
    detail_dir = site_data_dir / "detail"
    detail_dir.mkdir(parents=True, exist_ok=True)
    write_json(detail_dir / "12420_zips.geojson", polygon_geojson(austin_zip_rows, id_field="zip_code"))
    write_json(site_data_dir / "detail_counties.json", {
        "12420": polygon_geojson(austin_county_rows, id_field="county_name"),
    })
    write_json(site_data_dir / "detail_contexts.json", {
        "12420": {
            "detail_mode": "fixture",
            "detail_cbsa_code": "12420",
            "detail_metro_name": "Austin-Round Rock-Georgetown",
            "cbsa_summary": {"zip_count": len(austin_zip_rows), "county_count": len(austin_county_rows)},
        },
    })
    write_json(site_data_dir / "detail_index.json", {
        "detail_mode": "fixture",
        "default_cbsa_code": "12420",
        "default_metro_name": "Austin-Round Rock-Georgetown",
        "supported_detail_count": 1,
        "supported_details": [{
            "cbsa_code": "12420",
            "metro_name": "Austin-Round Rock-Georgetown",
            "detail_mode": "fixture",
            "zip_count": len(austin_zip_rows),
            "county_count": len(austin_county_rows),
            "zips_path": "data/detail/12420_zips.geojson",
        }],
    })

    metadata = {
        "project": "Underbuilt vs. Overpriced Atlas",
        "fixture_mode": True,
        "detail_mode": "fixture",
        "detail_metro_code": "12420",
        "detail_metro_name": "Austin-Round Rock-Georgetown",
        "built_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "national_metro_count": len(enriched),
        "selected_metro_counties": len(austin_county_rows),
        "selected_metro_zip_features": len(austin_zip_rows),
        "supported_detail_count": 1,
        "download_path": "data/metro_panel.csv",
    }
    write_json(site_data_dir / "meta.json", metadata)
    write_json(processed_dir / "source_catalog.json", catalog(fixture_mode=True))
    write_json(site_data_dir / "source_catalog.json", catalog(fixture_mode=True))
