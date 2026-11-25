# Underbuilt vs. Overpriced Atlas

A static, open-source housing pressure dashboard that screens U.S. metros where weak housing supply collides with rent pressure. It is built entirely from free federal data sources, with no API keys, backend, or paywalls. The repository is `buildlag`, the Python package is `underbuilt-overpriced-atlas`, and its command-line tool is `uoa`.

**[View the live atlas →](https://smkwray.github.io/buildlag/)** · **[Download the data](site/data/metro_panel.csv)**

---

## What this project does

The atlas ranks the 75 largest U.S. metros (Core-Based Statistical Areas, or CBSAs) on two dimensions:

- Underbuilt: how thin is new construction relative to the metro's size?
- Overpriced: how high are benchmark rents relative to local incomes?

Each metro receives a composite pressure score from 0 to 100. The site maps these scores nationally, lets you drill into ZIP-level rent benchmarks for any of the 75 metros, and makes every input downloadable so you can check the math.

This is a screening tool, not a causal model or a verdict. It flags metros where permitting is low and rent pressure is high so that researchers, journalists, and advocates can ask better questions; a high score does not prove a housing crisis or assign blame.

## Data sources

All inputs are publicly available federal datasets:

| Source | Vintage | What it provides |
|--------|---------|-----------------|
| [Census Building Permits Survey (BPS)](https://www.census.gov/permits) | 2024 | Annual permitted housing units by metro and county |
| [American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs) | 2024 (1-yr metro, 5-yr county) | Median income, rent, tenure, cost burden |
| [HUD Fair Market Rents (FMRs)](https://www.huduser.gov/portal/datasets/fmr.html) | FY2026 | Metro and county FMR benchmarks |
| [HUD Small Area FMRs (SAFMRs)](https://www.huduser.gov/portal/datasets/fmr.html) | FY2026 | ZIP-level rent benchmarks for detail maps |
| [Census delineation files](https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html) | 2023 | County-to-metro crosswalk |
| Census ZIP Code Tabulation Area (ZCTA) and county boundaries | 2020 / 2023 | Map geometry |

The exact URLs and vintages for the current build are recorded in [`site/data/source_catalog.json`](site/data/source_catalog.json) and [`site/data/meta.json`](site/data/meta.json).

## How the score works

### Underbuilt component

Permits per 1,000 households measures construction intensity. Metros with *fewer* permits per household score higher (inverse percentile rank).

```
permits_per_1000_hh = annual_permitted_units / households × 1000
underbuilt = inverse_percentile(permits_per_1000_hh) × 100
```

### Overpriced component

Two signals are averaged: the ratio of annualized 2BR Fair Market Rent to median household income, and the share of renters paying 35%+ of income on rent.

```
fmr_to_income = (2BR_FMR × 12) / median_household_income
overpriced = mean(percentile(fmr_to_income), percentile(rent_burden_35plus)) × 100
```

### Overall score

```
overall = mean(underbuilt, overpriced)
```

Scored 0–100. Higher means more pressure. Metros are bucketed as:

| Range | Label |
|-------|-------|
| 75–100 | Acute pressure |
| 55–74 | Elevated |
| 35–54 | Watch |
| 0–34 | Lower pressure |

## What the site shows

- National map: circle markers sized by population, colored by pressure score
- Quadrant scatterplot: permits vs. rent burden, colored by score mode
- Ranking table: sortable and filterable, with component decomposition bars
- ZIP detail map: SAFMR rent benchmarks on ZCTA geometry for any of the 75 metros
- County context: permits, income, and burden by county within the selected metro
- Source cards: the exact data vintage behind every number

## Limitations

- Single-year snapshot. There is no time series, so you cannot see whether a metro is getting worse or improving.
- Permits are a noisy proxy for supply. BPS counts authorized units, not completed homes, and permitted units are not necessarily affordable units, so metros with large multifamily pipelines can look well supplied while still having affordability problems.
- FMR is a lagging benchmark, not market rent. It is HUD's backward-looking estimate of what a moderately priced unit costs, set for the voucher program, so metros with fast rent growth may look better than they are.
- No vacancy, household growth, or structure mix. The screen can misread metros with unusual housing stock.
- Mixed survey products and geographies. Metro figures use ACS 1-year estimates (larger metros only) and county figures use ACS 5-year estimates, which have different margins of error and should not be mixed in time-series analysis. Some metros are split into HUD Metro FMR Areas (HMFAs) whose boundaries differ from Census metros.

## Run it locally

The site is fully static. No build step, no Node, no bundler.

```bash
cd site
python3 -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000).

## Rebuild the data from source

Requires Python 3.11+. All data sources are free public APIs, and no API keys are needed.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 1. Download source files (BPS, HUD, delineation, population)
uoa fetch-real-sources

# 2. Pull ACS metro and county profiles
uoa fetch-acs

# 3. Build the panel, maps, and detail bundles
uoa build-real-panel
```

Outputs land in `site/data/`.

## Project structure

```
site/                       Static website (HTML, CSS, JS)
  data/                     Generated data consumed by the site
    metro_panel.json        75-metro national panel
    metro_panel.csv         Downloadable CSV version
    metro_points.geojson    National map point layer
    meta.json               Build metadata and source vintages
    detail_index.json       Index of all 75 metro detail bundles
    source_catalog.json     Source URLs used by the build
    detail_contexts.json    Metro detail contexts, keyed by CBSA code
    detail_counties.json    County geometries, keyed by CBSA code
    detail/<cbsa>_zips.geojson  Per-metro ZIP SAFMR geometry
src/underbuilt_overpriced/  Python pipeline (scoring, fetching, bundling)
config/sources.yaml         Source URL registry
tests/                      Data contract and scoring tests
```

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests validate the scoring logic, bundle format, and data contract of the generated outputs.

## License

[MIT](LICENSE)
