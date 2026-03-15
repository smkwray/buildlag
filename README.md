# Underbuilt vs. Overpriced Atlas

A static, open-source housing pressure dashboard that screens U.S. metros where weak housing supply collides with rent pressure. Built entirely from free federal data sources — no API keys, no backend, no paywalls.

**[View the live atlas →](https://smkwray.github.io/buildlag/)** · **[Download the data](site/data/metro_panel.csv)**

---

## What this project does

The atlas ranks the 75 largest U.S. metros on two dimensions:

- **Underbuilt** — how thin is new construction relative to the metro's size?
- **Overpriced** — how high are benchmark rents relative to local incomes?

Each metro receives a composite pressure score from 0 to 100. The site maps these scores nationally, lets you drill into ZIP-level rent benchmarks for any of the 75 metros, and makes every input downloadable so you can check the math.

This is a **screening tool**, not a causal model. It surfaces where pressure appears to be accumulating so that researchers, journalists, and advocates can ask better questions.

## Data sources

All inputs are publicly available federal datasets:

| Source | Vintage | What it provides |
|--------|---------|-----------------|
| [Census Building Permits Survey (BPS)](https://www.census.gov/permits) | 2024 | Annual permitted housing units by metro and county |
| [American Community Survey (ACS)](https://www.census.gov/programs-surveys/acs) | 2024 (1-yr metro, 5-yr county) | Median income, rent, tenure, cost burden |
| [HUD Fair Market Rents](https://www.huduser.gov/portal/datasets/fmr.html) | FY2026 | Metro and county FMR benchmarks |
| [HUD Small Area FMRs](https://www.huduser.gov/portal/datasets/fmr.html) | FY2026 | ZIP-level rent benchmarks for detail maps |
| [Census delineation files](https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html) | 2023 | County-to-metro crosswalk |
| Census ZCTA & county boundaries | 2020 / 2023 | Map geometry |

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

- **National map** — circle markers sized by population, colored by pressure score
- **Quadrant scatterplot** — permits vs. rent burden, colored by score mode
- **Ranking table** — sortable, filterable, with component decomposition bars
- **ZIP detail map** — SAFMR rent benchmarks on Census ZCTA geometry for any of the 75 metros
- **County context** — permits, income, and burden by county within the selected metro
- **Source cards** — inspect the exact data vintage behind every number

## Limitations

- **Single-year snapshot.** There is no time series — you cannot see whether a metro is getting worse or improving. A trailing 3-year permitting average would smooth annual volatility and strengthen the underbuilt signal.
- **Permits are a noisy proxy for supply.** Metros with large multifamily pipelines can look well-supplied on permits while still having affordability problems, because permitted units are not necessarily affordable units.
- **FMR is a lagging indicator.** Fair Market Rents are backward-looking and tuned for the voucher program, not real-time market rents. Metros with fast rent growth may appear better than they are.
- **No vacancy, household growth, or structure mix.** These factors shape housing pressure but are not yet included. Their absence means the screen can misread metros with unusual housing stock characteristics.

## Caveats

1. **Permits ≠ completed homes.** BPS counts authorized units, not finished construction.
2. **FMR is a benchmark, not market rent.** It is HUD's estimate of what a moderately priced unit costs, used for voucher programs.
3. **ACS 1-year vs. 5-year.** Metro-level figures use ACS 1-year estimates (larger metros only). County-level figures use ACS 5-year. These products have different margins of error and should not be mixed in time-series analysis.
4. **HUD metro areas may differ from Census metros.** Some metros are split into HUD Metro FMR Areas (HMFAs) with different boundaries.
5. **This is a screen, not a verdict.** A high score means the inputs suggest pressure — it does not prove a housing crisis or assign blame.

## Run it locally

The site is fully static. No build step, no Node, no bundler.

```bash
cd site
python3 -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000).

## Rebuild the data from source

Requires Python 3.11+ and a Census API key (set `CENSUS_API_KEY` in `.env`).

```bash
pip install -e .

# 1. Download source files (BPS, HUD, delineation, population)
uoa fetch-real-sources

# 2. Pull ACS metro and county profiles
uoa fetch-acs

# 3. Build the panel, maps, and detail bundles
uoa build-real-panel
```

Outputs land in `site/data/`. Run the site server to see the results.

## Project structure

```
site/                       Static website (HTML, CSS, JS)
  data/                     Generated data consumed by the site
    metro_panel.json        75-metro national panel
    metro_panel.csv         Downloadable CSV version
    metro_points.geojson    National map point layer
    meta.json               Build metadata and source vintages
    detail_index.json       Index of all 75 metro detail bundles
    source_catalog.json     Authoritative source URLs
    detail/<cbsa>/          Per-metro ZIP and county detail
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

MIT
