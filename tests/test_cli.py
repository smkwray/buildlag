import unittest

from underbuilt_overpriced.cli import build_parser


class CliValidationTests(unittest.TestCase):
    def _parse_and_validate(self, *args):
        parser = build_parser()
        parsed = parser.parse_args(args)
        if parsed.command == "build-real-panel" and parsed.top_n < 1:
            parser.error("--top-n must be a positive integer (got %d)" % parsed.top_n)
        return parsed

    def test_top_n_zero_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            self._parse_and_validate("build-real-panel", "--top-n", "0")
        self.assertNotEqual(ctx.exception.code, 0)

    def test_top_n_negative_rejected(self):
        with self.assertRaises(SystemExit) as ctx:
            self._parse_and_validate("build-real-panel", "--top-n", "-5")
        self.assertNotEqual(ctx.exception.code, 0)

    def test_top_n_valid(self):
        parsed = self._parse_and_validate("build-real-panel", "--top-n", "10")
        self.assertEqual(parsed.top_n, 10)

    def test_top_n_default(self):
        parsed = self._parse_and_validate("build-real-panel")
        self.assertEqual(parsed.top_n, 75)

    def test_allow_fallback_default_off(self):
        parsed = self._parse_and_validate("build-real-panel")
        self.assertFalse(parsed.allow_fallback)

    def test_allow_fallback_on(self):
        parsed = self._parse_and_validate("build-real-panel", "--allow-fallback")
        self.assertTrue(parsed.allow_fallback)

    def test_fetch_real_sources_defaults(self):
        parsed = self._parse_and_validate("fetch-real-sources")
        self.assertEqual(parsed.bps_year, 2024)
        self.assertEqual(parsed.hud_year, 2026)
        self.assertFalse(parsed.force)

    def test_fetch_acs_defaults(self):
        parsed = self._parse_and_validate("fetch-acs")
        self.assertEqual(parsed.metro_year, 2024)
        self.assertEqual(parsed.county_year, 2024)


if __name__ == "__main__":
    unittest.main()
