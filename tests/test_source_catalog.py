import unittest

from underbuilt_overpriced.fetch_real_sources import source_specs
from underbuilt_overpriced.source_catalog import catalog


class SourceCatalogConsistencyTests(unittest.TestCase):
    def test_every_spec_url_appears_in_catalog(self):
        """Every download URL from source_specs must appear in the published catalog."""
        specs = source_specs(bps_year=2024, hud_year=2026)
        cat = catalog(
            fixture_mode=False,
            bps_year=2024,
            hud_year=2026,
            acs_metro_year=2024,
            acs_county_year=2024,
        )
        catalog_urls = {entry["url"] for entry in cat["data_sources"]}
        for spec in specs:
            self.assertIn(
                spec.url,
                catalog_urls,
                f"source_specs URL for '{spec.source_id}' not found in catalog",
            )

    def test_catalog_ids_are_unique(self):
        cat = catalog(fixture_mode=False)
        ids = [entry["id"] for entry in cat["data_sources"]]
        self.assertEqual(len(ids), len(set(ids)), f"Duplicate catalog IDs: {ids}")

    def test_catalog_fixture_mode_flag(self):
        self.assertTrue(catalog(fixture_mode=True)["fixture_mode"])
        self.assertFalse(catalog(fixture_mode=False)["fixture_mode"])

    def test_non_default_vintages_propagate(self):
        cat = catalog(
            fixture_mode=False,
            bps_year=2023,
            hud_year=2025,
            acs_metro_year=2023,
            acs_county_year=2022,
        )
        urls = {entry["id"]: entry["url"] for entry in cat["data_sources"]}
        # BPS should use 2023
        self.assertIn("2023", urls["census_bps_cbsa_annual"])
        # HUD should use 2025
        self.assertIn("2025", urls["hud_fmr_county"])
        self.assertIn("2025", urls["hud_safmr_zip"])
        # ACS metro should use 2023, county should use 2022
        self.assertIn("/2023/acs/acs1/", urls[f"acs1_metro_profile_2023"])
        self.assertIn("/2022/acs/acs5/", urls[f"acs5_county_profile_2022"])

    def test_split_acs_years_are_independent(self):
        cat = catalog(
            fixture_mode=False,
            acs_metro_year=2024,
            acs_county_year=2023,
        )
        urls = {entry["id"]: entry["url"] for entry in cat["data_sources"]}
        self.assertIn("/2024/acs/acs1/", urls["acs1_metro_profile_2024"])
        self.assertIn("/2023/acs/acs5/", urls["acs5_county_profile_2023"])


if __name__ == "__main__":
    unittest.main()
