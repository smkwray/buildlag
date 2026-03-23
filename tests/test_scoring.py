import unittest

from underbuilt_overpriced.scoring import bucket_for_score, enrich_rows


class ScoringTests(unittest.TestCase):
    def test_scores_stay_in_bounds(self):
        rows = [
            {
                "permits_annual": "1000",
                "households": "100000",
                "fmr_2br": "1500",
                "median_household_income": "60000",
                "rent_burdened_share_pct": "20",
            },
            {
                "permits_annual": "500",
                "households": "100000",
                "fmr_2br": "2500",
                "median_household_income": "60000",
                "rent_burdened_share_pct": "35",
            },
        ]
        enrich_rows(rows)
        for row in rows:
            self.assertGreaterEqual(row["overall_score"], 0.0)
            self.assertLessEqual(row["overall_score"], 100.0)

    def test_higher_permits_reduce_underbuilt_component(self):
        rows = [
            {
                "permits_annual": "100",
                "households": "100000",
                "fmr_2br": "1500",
                "median_household_income": "70000",
                "rent_burdened_share_pct": "20",
            },
            {
                "permits_annual": "5000",
                "households": "100000",
                "fmr_2br": "1500",
                "median_household_income": "70000",
                "rent_burdened_share_pct": "20",
            },
        ]
        enrich_rows(rows)
        self.assertGreater(rows[0]["underbuilt_component"], rows[1]["underbuilt_component"])

    def test_bucket_labels(self):
        self.assertEqual(bucket_for_score(80), "acute pressure")
        self.assertEqual(bucket_for_score(60), "elevated pressure")
        self.assertEqual(bucket_for_score(40), "watch")
        self.assertEqual(bucket_for_score(10), "lower pressure")


if __name__ == "__main__":
    unittest.main()
