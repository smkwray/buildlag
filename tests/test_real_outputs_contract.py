import csv
import json
import unittest
from pathlib import Path


class RealOutputContractTests(unittest.TestCase):
    def test_real_panel_contract(self):
        project_root = Path(__file__).resolve().parents[1]
        panel_path = project_root / "data" / "processed" / "metro_panel.csv"
        meta_path = project_root / "site" / "data" / "meta.json"
        detail_index_path = project_root / "site" / "data" / "detail_index.json"

        if not panel_path.exists() or not meta_path.exists():
            self.skipTest("Real outputs are not present; run build-real-panel first.")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("fixture_mode", True):
            self.skipTest("Site outputs are in fixture mode; run build-real-panel to validate real-output contract.")

        with panel_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertGreaterEqual(len(rows), 50)

        required_columns = {
            "cbsa_code",
            "metro_name",
            "population",
            "households",
            "permits_annual",
            "hud_fmr_2br",
            "median_household_income",
            "rent_burdened_share_pct",
            "underbuilt_component",
            "overpriced_component",
            "overall_score",
            "score_bucket",
            "data_vintage_bps",
            "data_vintage_acs",
            "data_vintage_hud",
        }

        self.assertTrue(required_columns.issubset(rows[0].keys()))
        for row in rows:
            self.assertTrue(row["data_vintage_bps"])
            self.assertTrue(row["data_vintage_acs"])
            self.assertTrue(row["data_vintage_hud"])

        self.assertTrue(detail_index_path.exists(), "Missing detail_index.json output")
        detail_index = json.loads(detail_index_path.read_text(encoding="utf-8"))
        self.assertIn("detail_mode", detail_index)
        self.assertGreaterEqual(detail_index.get("supported_detail_count", 0), 1)

        default_cbsa_code = meta["detail_metro_code"]
        supported = {entry["cbsa_code"]: entry for entry in detail_index["supported_details"]}
        self.assertIn(default_cbsa_code, supported)

        default_entry = supported[default_cbsa_code]
        for key in ["zips_path", "counties_path", "context_path"]:
            target = project_root / "site" / default_entry[key]
            self.assertTrue(target.exists(), f"Missing detail asset: {target}")

        context = json.loads((project_root / "site" / default_entry["context_path"]).read_text(encoding="utf-8"))
        self.assertIn("detail_mode", context)
        self.assertIn("cbsa_summary", context)


if __name__ == "__main__":
    unittest.main()
