# Data sources

This project uses official free public data only.

## 1) Census Building Permits Survey (BPS)

Primary use:

- annual construction intensity by county and CBSA
- potential later place-level detail

Preferred first production files:

- annual CBSA permit file
- annual county permit file or compiled master-data directory

Why BPS belongs here:

- nationally consistent
- directly policy relevant
- visual and intuitive for supply screening

Key caution:

- BPS measures **housing units authorized by permits**, not completions or absorption.

## 2) ACS

Primary use:

- rent benchmarks
- income context
- tenure and housing stock structure
- renter burden

Recommended split:

- ACS 1-year for metro summaries where available
- ACS 5-year for smaller counties and local structural context

Suggested variable set for first production version:

- median household income
- total housing units
- renter-occupied housing units
- median gross rent
- share of renters paying 35%+ of income toward gross rent

## 3) HUD Fair Market Rents / Small Area FMRs

Primary use:

- metro-level affordability benchmark
- ZIP-level selected-metro detail map

Why HUD belongs here:

- highly legible to housing and policy audiences
- consistent national benchmark
- useful even when ACS local detail is noisy

Key caution:

- HUD FMR areas can differ from OMB metro geography because of HMFAs.

## 4) Census metro delineation files

Primary use:

- roll county data to CBSAs
- keep joins transparent and reproducible

## 5) Census metro population estimates

Primary use:

- define “top metros” for the MVP
- create per-capita or per-household normalization when ACS household counts are not yet staged

## Join strategy

The intended production join path is:

1. county-level BPS
2. county-level ACS / county-level HUD FMR relationships
3. Census county-to-CBSA delineation file
4. metro-level aggregation
5. selected-metro ZIP / ZCTA detail for SAFMR map

## Production readiness checklist

Before the first public release, confirm:

- source vintages are shown in the UI
- ACS variables are finalized and verified
- HMFA edge cases are documented
- score components are individually downloadable
- fixture banner is removed only after real-source build lands
