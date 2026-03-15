# Methodology

## Framing

This project is a **screening tool** for housing pressure, not a causal rent model.

It is meant to help people ask better questions about:

- where supply additions look thin relative to metro size
- where benchmark rents look high relative to incomes
- where affordability stress appears to be accumulating

## Current production-mode vintages

The current real-data build uses:

- BPS annual permits: **2024**
- ACS metro context: **2024 ACS 1-year**
- ACS county context: **2024 ACS 5-year**
- HUD FMR and SAFMR: **FY2026**
- County-to-CBSA delineation: **2023 List 1**
- Detail geometry:
  - ZCTA polygons: **Census 2020 generalized boundaries**
  - County polygons: **Census 2023 generalized boundaries**

The site metadata file (`site/data/meta.json`) is the authoritative source for the active run's vintages.

## Intended production grain

Primary warehouse grain: **county-year**

Published summary grain for MVP: **CBSA-year**

Selected detail grain for second map: **ZIP / ZCTA within one metro**

## Suggested v1 score

### Underbuilt component

Use a transparent supply intensity measure:

```text
permits_per_1000_households = annual_permitted_units / households * 1000
underbuilt_component = inverse_percentile(permits_per_1000_households)
```

This means metros with weaker permitting intensity receive higher underbuilt scores.

### Overpriced component

Use two inputs:

```text
fmr_to_income = (2BR_FMR * 12) / median_household_income
overpriced_component = mean(
  percentile(fmr_to_income),
  percentile(rent_burdened_share_35_plus)
)
```

### Overall score

```text
overall_score = mean(underbuilt_component, overpriced_component) * 100
```

## Why this works for an MVP

- easy to explain
- easy to debug
- no black-box regression required
- every component is downloadable
- policy users can inspect the raw ingredients

## Caveats that should stay visible on the website

1. BPS permits are authorizations, not completed homes.
2. FMR is a benchmark, not the observed asking rent for every unit.
3. ACS 1-year and 5-year products behave differently and should not be mixed casually in time-series claims.
4. Some metros split into HUD Metro FMR Areas.
5. Rankings should be interpreted as screening signals, not causal findings.
6. The selected-metro ZIP detail is currently generated for one metro at a time from SAFMR ZIP benchmarks joined to Census ZCTA geometry.

## Recommended future enhancements

- add a trailing 3-year permitting average
- compare permits to household growth, not just household stock
- add vacancy and structure mix terms
- add sensitivity analysis by metro size bucket
- surface confidence and missingness flags
