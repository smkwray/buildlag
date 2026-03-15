from __future__ import annotations

from typing import Iterable, List, MutableSequence


def _as_float(value: object) -> float:
    return float(value)


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def percentile_ranks(values: Iterable[float], *, invert: bool = False) -> List[float]:
    seq = [_as_float(v) for v in values]
    n = len(seq)
    if n == 0:
        return []
    if n == 1:
        return [1.0 if invert else 0.0]

    sorted_values = sorted(seq)
    results: List[float] = []
    for value in seq:
        first = sorted_values.index(value)
        last = n - 1 - sorted_values[::-1].index(value)
        average_rank = (first + last) / 2.0
        pct = average_rank / (n - 1)
        results.append(1.0 - pct if invert else pct)
    return results


def bucket_for_score(score: float) -> str:
    if score >= 75:
        return "acute pressure"
    if score >= 55:
        return "elevated pressure"
    if score >= 35:
        return "watch"
    return "lower pressure"


def enrich_rows(rows: MutableSequence[dict]) -> MutableSequence[dict]:
    permits_per_1000 = [
        safe_ratio(float(row["permits_2024"]), float(row["households_2024"])) * 1000.0
        for row in rows
    ]
    fmr_to_income = [
        safe_ratio(float(row["fmr_2br"]) * 12.0, float(row["median_household_income"]))
        for row in rows
    ]
    burden = [float(row["rent_burdened_share_pct"]) for row in rows]

    underbuilt = percentile_ranks(permits_per_1000, invert=True)
    fmr_rank = percentile_ranks(fmr_to_income)
    burden_rank = percentile_ranks(burden)

    for idx, row in enumerate(rows):
        overpriced = (fmr_rank[idx] + burden_rank[idx]) / 2.0
        overall = ((underbuilt[idx] + overpriced) / 2.0) * 100.0
        row["permits_per_1000_households"] = round(permits_per_1000[idx], 2)
        row["fmr_to_income"] = round(fmr_to_income[idx], 4)
        row["underbuilt_component"] = round(underbuilt[idx] * 100.0, 1)
        row["overpriced_component"] = round(overpriced * 100.0, 1)
        row["overall_score"] = round(overall, 1)
        row["score_bucket"] = bucket_for_score(overall)
    return rows
