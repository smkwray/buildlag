from __future__ import annotations

import argparse
from pathlib import Path





def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser. Importable for testing."""
    parser = argparse.ArgumentParser(description="Underbuilt vs. Overpriced Atlas helper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build-demo", help="Build site-ready outputs from fixture inputs")
    fetch_sources_parser = subparsers.add_parser(
        "fetch-real-sources",
        help="Download reproducible real-source input files into data/raw/",
    )
    fetch_sources_parser.add_argument("--bps-year", type=int, default=2024)
    fetch_sources_parser.add_argument("--hud-year", type=int, default=2026)
    fetch_sources_parser.add_argument("--force", action="store_true")

    fetch_acs_parser = subparsers.add_parser(
        "fetch-acs",
        help="Fetch ACS metro (ACS1) and county (ACS5) context into data/raw/acs/",
    )
    fetch_acs_parser.add_argument("--metro-year", type=int, default=2024)
    fetch_acs_parser.add_argument("--county-year", type=int, default=2024)
    fetch_acs_parser.add_argument("--force", action="store_true")

    build_real_parser = subparsers.add_parser(
        "build-real-panel",
        help="Build a real top-metro panel from BPS + HUD + ACS and write site/data outputs.",
    )
    build_real_parser.add_argument("--top-n", type=int, default=75)
    build_real_parser.add_argument("--bps-year", type=int, default=2024)
    build_real_parser.add_argument("--hud-year", type=int, default=2026)
    build_real_parser.add_argument("--metro-year", type=int, default=2024)
    build_real_parser.add_argument("--county-year", type=int, default=2024)
    build_real_parser.add_argument("--force-fetch", action="store_true")
    build_real_parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow fixture-data fallback if real detail layers fail (marks build as invalid for deploy).",
    )

    return parser


def main() -> None:
    from .acs import AcsVintage, fetch_acs_context
    from .build_real_panel import build_real_panel
    from .bundle import build_fixture_bundle
    from .fetch_real_sources import fetch_real_sources

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "build-real-panel" and args.top_n < 1:
        parser.error("--top-n must be a positive integer (got %d)" % args.top_n)

    if args.command == "build-demo":
        build_fixture_bundle(project_root())
    elif args.command == "fetch-real-sources":
        fetch_real_sources(
            project_root(),
            bps_year=args.bps_year,
            hud_year=args.hud_year,
            force=args.force,
        )
    elif args.command == "fetch-acs":
        fetch_acs_context(
            project_root() / "data" / "raw",
            vintage=AcsVintage(
                metro_acs1_year=args.metro_year,
                county_acs5_year=args.county_year,
            ),
            force=args.force,
        )
    elif args.command == "build-real-panel":
        build_real_panel(
            project_root(),
            top_n=args.top_n,
            bps_year=args.bps_year,
            hud_year=args.hud_year,
            acs_vintage=AcsVintage(
                metro_acs1_year=args.metro_year,
                county_acs5_year=args.county_year,
            ),
            force_fetch=args.force_fetch,
            allow_fallback=args.allow_fallback,
        )


if __name__ == "__main__":
    main()
