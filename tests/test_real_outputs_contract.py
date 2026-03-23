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

        # Reject fixture_fallback in real-mode outputs
        self.assertNotEqual(
            detail_index.get("detail_mode"),
            "fixture_fallback",
            "detail_index.json has detail_mode=fixture_fallback — real detail layers did not build.",
        )
        self.assertNotEqual(
            meta.get("detail_mode"),
            "fixture_fallback",
            "meta.json has detail_mode=fixture_fallback — real detail layers did not build.",
        )

        # Consistency: meta.json and detail_index.json must agree
        self.assertEqual(
            meta.get("detail_mode"),
            detail_index.get("detail_mode"),
            "detail_mode mismatch between meta.json and detail_index.json",
        )
        self.assertEqual(
            meta.get("supported_detail_count"),
            detail_index.get("supported_detail_count"),
            "supported_detail_count mismatch between meta.json and detail_index.json",
        )

        default_cbsa_code = meta["detail_metro_code"]
        supported = {entry["cbsa_code"]: entry for entry in detail_index["supported_details"]}
        self.assertIn(default_cbsa_code, supported)

        # Check consolidated files exist
        contexts_path = project_root / "site" / "data" / "detail_contexts.json"
        counties_path = project_root / "site" / "data" / "detail_counties.json"
        self.assertTrue(contexts_path.exists(), "Missing consolidated detail_contexts.json")
        self.assertTrue(counties_path.exists(), "Missing consolidated detail_counties.json")

        contexts = json.loads(contexts_path.read_text(encoding="utf-8"))
        counties = json.loads(counties_path.read_text(encoding="utf-8"))

        # Verify every supported detail entry has valid assets
        for cbsa_code, entry in supported.items():
            self.assertIn(cbsa_code, contexts, f"detail_contexts.json missing CBSA {cbsa_code}")
            self.assertIn("detail_mode", contexts[cbsa_code])
            self.assertIn("cbsa_summary", contexts[cbsa_code])
            self.assertIn(cbsa_code, counties, f"detail_counties.json missing CBSA {cbsa_code}")
            zips_target = project_root / "site" / entry["zips_path"]
            self.assertTrue(zips_target.exists(), f"Missing detail zip asset: {zips_target}")

    def test_source_catalog_consistency(self):
        project_root = Path(__file__).resolve().parents[1]
        meta_path = project_root / "site" / "data" / "meta.json"
        catalog_path = project_root / "site" / "data" / "source_catalog.json"

        if not meta_path.exists() or not catalog_path.exists():
            self.skipTest("Real outputs are not present.")

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("fixture_mode", True):
            self.skipTest("Fixture mode; skipping catalog consistency check.")

        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

        self.assertEqual(
            meta.get("data_vintages"),
            catalog.get("data_vintages"),
            "data_vintages mismatch between meta.json and source_catalog.json",
        )
        self.assertFalse(catalog.get("fixture_mode"), "source_catalog.json should not be in fixture mode")
        self.assertGreater(len(catalog.get("data_sources", [])), 0, "source_catalog.json has no data_sources")


if __name__ == "__main__":
    unittest.main()
