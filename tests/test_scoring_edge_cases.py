import unittest

from underbuilt_overpriced.scoring import bucket_for_score, enrich_rows, percentile_ranks, safe_ratio


class ZeroAndBlankInputTests(unittest.TestCase):
    def test_zero_households_does_not_raise(self):
        rows = [
            {
                "permits_annual": "100",
                "households": "0",
                "fmr_2br": "1500",
                "median_household_income": "60000",
                "rent_burdened_share_pct": "40",
            },
            {
                "permits_annual": "200",
                "households": "50000",
                "fmr_2br": "1500",
                "median_household_income": "60000",
                "rent_burdened_share_pct": "40",
            },
        ]
        enrich_rows(rows)
        self.assertEqual(rows[0]["permits_per_1000_households"], 0.0)
        for row in rows:
            self.assertGreaterEqual(row["overall_score"], 0.0)
            self.assertLessEqual(row["overall_score"], 100.0)

    def test_zero_income_does_not_raise(self):
        rows = [
            {
                "permits_annual": "100",
                "households": "50000",
                "fmr_2br": "1500",
                "median_household_income": "0",
                "rent_burdened_share_pct": "40",
            },
            {
                "permits_annual": "200",
                "households": "50000",
                "fmr_2br": "1500",
                "median_household_income": "80000",
                "rent_burdened_share_pct": "40",
            },
        ]
        enrich_rows(rows)
        self.assertEqual(rows[0]["fmr_to_income"], 0.0)
        for row in rows:
            self.assertGreaterEqual(row["overall_score"], 0.0)
            self.assertLessEqual(row["overall_score"], 100.0)

    def test_zero_permits_scores_high_underbuilt(self):
        rows = [
            {
                "permits_annual": "0",
                "households": "100000",
                "fmr_2br": "1500",
                "median_household_income": "70000",
                "rent_burdened_share_pct": "40",
            },
            {
                "permits_annual": "5000",
                "households": "100000",
                "fmr_2br": "1500",
                "median_household_income": "70000",
                "rent_burdened_share_pct": "40",
            },
        ]
        enrich_rows(rows)
        self.assertGreater(rows[0]["underbuilt_component"], rows[1]["underbuilt_component"])


class TiedValuesTests(unittest.TestCase):
    def test_identical_rows_get_equal_scores(self):
        base = {
            "permits_annual": "1000",
            "households": "100000",
            "fmr_2br": "1500",
            "median_household_income": "70000",
            "rent_burdened_share_pct": "42",
        }
        rows = [{**base}, {**base}, {**base}]
        enrich_rows(rows)
        scores = [row["overall_score"] for row in rows]
        self.assertEqual(len(set(scores)), 1, f"Tied rows should have equal scores: {scores}")

    def test_percentile_ranks_with_all_ties(self):
        values = [5.0, 5.0, 5.0, 5.0]
        ranks = percentile_ranks(values)
        self.assertTrue(all(r == ranks[0] for r in ranks))

    def test_percentile_ranks_with_partial_ties(self):
        values = [10.0, 20.0, 20.0, 30.0]
        ranks = percentile_ranks(values)
        self.assertEqual(ranks[1], ranks[2], "Tied values should get equal rank")
        self.assertLess(ranks[0], ranks[1])
        self.assertGreater(ranks[3], ranks[2])


class OneRowPanelTests(unittest.TestCase):
    def test_single_row_does_not_raise(self):
        rows = [
            {
                "permits_annual": "1000",
                "households": "100000",
                "fmr_2br": "1500",
                "median_household_income": "70000",
                "rent_burdened_share_pct": "42",
            },
        ]
        enrich_rows(rows)
        self.assertGreaterEqual(rows[0]["overall_score"], 0.0)
        self.assertLessEqual(rows[0]["overall_score"], 100.0)
        self.assertIn(rows[0]["score_bucket"], {
            "acute pressure", "elevated pressure", "watch", "lower pressure",
        })

    def test_percentile_ranks_single_value(self):
        self.assertEqual(percentile_ranks([42.0]), [0.0])
        self.assertEqual(percentile_ranks([42.0], invert=True), [1.0])

    def test_percentile_ranks_empty(self):
        self.assertEqual(percentile_ranks([]), [])


class SafeRatioTests(unittest.TestCase):
    def test_zero_denominator_returns_zero(self):
        self.assertEqual(safe_ratio(100.0, 0.0), 0.0)

    def test_normal_division(self):
        self.assertAlmostEqual(safe_ratio(10.0, 4.0), 2.5)


class BucketBoundaryTests(unittest.TestCase):
    def test_exact_boundaries(self):
        self.assertEqual(bucket_for_score(75.0), "acute pressure")
        self.assertEqual(bucket_for_score(74.9), "elevated pressure")
        self.assertEqual(bucket_for_score(55.0), "elevated pressure")
        self.assertEqual(bucket_for_score(54.9), "watch")
        self.assertEqual(bucket_for_score(35.0), "watch")
        self.assertEqual(bucket_for_score(34.9), "lower pressure")
        self.assertEqual(bucket_for_score(0.0), "lower pressure")
        self.assertEqual(bucket_for_score(100.0), "acute pressure")


if __name__ == "__main__":
    unittest.main()
