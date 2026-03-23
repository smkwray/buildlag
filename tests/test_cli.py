import argparse
import unittest


class CliValidationTests(unittest.TestCase):
    def _make_parser(self):
        """Replicate the build-real-panel argparse setup without importing heavy deps."""
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command", required=True)
        brp = sub.add_parser("build-real-panel")
        brp.add_argument("--top-n", type=int, default=75)
        brp.add_argument("--allow-fallback", action="store_true")
        return parser

    def _parse_and_validate(self, *args):
        parser = self._make_parser()
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


if __name__ == "__main__":
    unittest.main()
