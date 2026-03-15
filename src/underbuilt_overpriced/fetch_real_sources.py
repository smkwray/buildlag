from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

import requests


DEFAULT_TIMEOUT_SECONDS = 120
MANIFEST_NAME = "source_manifest.json"


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    url: str
    filename: str
    vintage: str
    description: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".tmp")

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with temp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    handle.write(chunk)

    temp_path.replace(destination)


def source_specs(*, bps_year: int = 2024, hud_year: int = 2026) -> List[SourceSpec]:
    yy = str(hud_year)[-2:]
    return [
        SourceSpec(
            source_id="census_bps_cbsa_annual",
            url=f"https://www.census.gov/construction/bps/xls/cbsaannual_{bps_year}99.xls",
            filename=f"census_bps_cbsaannual_{bps_year}99.xls",
            vintage=str(bps_year),
            description="Census BPS annual CBSA permits",
        ),
        SourceSpec(
            source_id="census_bps_county_annual",
            url=f"https://www2.census.gov/econ/bps/County/co{bps_year}a.txt",
            filename=f"census_bps_county_co{bps_year}a.txt",
            vintage=str(bps_year),
            description="Census BPS annual county permits",
        ),
        SourceSpec(
            source_id="hud_fmr_county",
            url=f"https://www.huduser.gov/portal/datasets/fmr/fmr{hud_year}/FY{yy}_FMRs.xlsx",
            filename=f"hud_fmr_fy{hud_year}_county.xlsx",
            vintage=f"FY{hud_year}",
            description="HUD county-level FMR workbook",
        ),
        SourceSpec(
            source_id="hud_safmr_zip",
            url=f"https://www.huduser.gov/portal/datasets/fmr/fmr{hud_year}/fy{hud_year}_safmrs.xlsx",
            filename=f"hud_safmr_fy{hud_year}_zip.xlsx",
            vintage=f"FY{hud_year}",
            description="HUD ZIP-level SAFMR workbook",
        ),
        SourceSpec(
            source_id="census_delineation_list1",
            url="https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx",
            filename="census_delineation_list1_2023.xlsx",
            vintage="2023",
            description="County-to-CBSA crosswalk (List 1)",
        ),
        SourceSpec(
            source_id="census_delineation_list2",
            url="https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2023/delineation-files/list2_2023.xlsx",
            filename="census_delineation_list2_2023.xlsx",
            vintage="2023",
            description="CBSA principal cities list (List 2)",
        ),
        SourceSpec(
            source_id="census_metro_population_estimates",
            url="https://www2.census.gov/programs-surveys/popest/tables/2020-2024/metro/totals/cbsa-met-est2024-pop.xlsx",
            filename="census_cbsa_met_est2024_pop.xlsx",
            vintage="2024",
            description="Census metro population estimates",
        ),
        SourceSpec(
            source_id="census_cbsa_gazetteer",
            url="https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_cbsa_national.zip",
            filename="census_gazetteer_cbsa_2023.zip",
            vintage="2023",
            description="CBSA point coordinates from Census Gazetteer",
        ),
        SourceSpec(
            source_id="census_zcta_boundaries",
            url="https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_zcta520_500k.zip",
            filename="census_zcta_2020_500k.zip",
            vintage="2020",
            description="Census ZCTA boundaries for SAFMR ZIP geometry joins",
        ),
        SourceSpec(
            source_id="census_county_boundaries",
            url="https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip",
            filename="census_county_2023_500k.zip",
            vintage="2023",
            description="Census county boundaries for selected-metro context map",
        ),
    ]


def fetch_real_sources(
    project_root: Path,
    *,
    bps_year: int = 2024,
    hud_year: int = 2026,
    force: bool = False,
) -> Path:
    raw_dir = project_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    for spec in source_specs(bps_year=bps_year, hud_year=hud_year):
        target = raw_dir / spec.filename
        downloaded = False

        if force or not target.exists():
            _download(spec.url, target)
            downloaded = True

        manifest_entries.append(
            {
                "id": spec.source_id,
                "description": spec.description,
                "url": spec.url,
                "filename": spec.filename,
                "path": str(target.relative_to(project_root)),
                "vintage": spec.vintage,
                "size_bytes": target.stat().st_size,
                "sha256": _sha256(target),
                "downloaded_at_utc": _utc_now_iso() if downloaded else None,
                "downloaded_this_run": downloaded,
            }
        )

    manifest_path = raw_dir / MANIFEST_NAME
    payload = {
        "generated_at_utc": _utc_now_iso(),
        "project": "Underbuilt vs. Overpriced Atlas",
        "source_count": len(manifest_entries),
        "sources": manifest_entries,
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def vintages_from_manifest(manifest: dict) -> dict:
    result = {}
    for entry in manifest.get("sources", []):
        source_id = entry.get("id", "")
        vintage = entry.get("vintage")
        if source_id and vintage:
            result[source_id] = vintage
    return result
