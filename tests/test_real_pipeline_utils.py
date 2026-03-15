import unittest

from underbuilt_overpriced.build_real_panel import _extract_cbsa_code, _normalize_metro_name


class RealPipelineUtilsTests(unittest.TestCase):
    def test_extract_cbsa_code_from_hud_area_code(self):
        self.assertEqual(_extract_cbsa_code("METRO33860M33860"), "33860")
        self.assertEqual(_extract_cbsa_code("NCNTY01005N01005"), "")

    def test_normalize_metro_name(self):
        self.assertEqual(_normalize_metro_name(".Nashville-Davidson--Murfreesboro--Franklin, TN Metro Area"), "nashville-davidson--murfreesboro--franklin, tn")
        self.assertEqual(_normalize_metro_name("Aguadilla, PR Metro Area"), "aguadilla, pr")


if __name__ == "__main__":
    unittest.main()
