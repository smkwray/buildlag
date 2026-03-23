import json
import shutil
import tempfile
import unittest
from pathlib import Path

from underbuilt_overpriced.bundle import build_fixture_bundle


class BundleTests(unittest.TestCase):
    def test_bundle_outputs_exist(self):
        source_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            shutil.copytree(source_root / "data" / "fixtures", project_root / "data" / "fixtures")
            shutil.copytree(source_root / "docs", project_root / "docs")
            (project_root / "site").mkdir(parents=True, exist_ok=True)
            build_fixture_bundle(project_root)

            expected = [
                project_root / "site" / "data" / "metro_panel.json",
                project_root / "site" / "data" / "metro_points.geojson",
                project_root / "site" / "data" / "detail" / "12420_zips.geojson",
                project_root / "site" / "data" / "detail_contexts.json",
                project_root / "site" / "data" / "detail_counties.json",
                project_root / "site" / "data" / "detail_index.json",
                project_root / "site" / "data" / "meta.json",
            ]

            for path in expected:
                self.assertTrue(path.exists(), f"Missing expected file: {path}")

            payload = json.loads((project_root / "site" / "data" / "meta.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["fixture_mode"])
            self.assertEqual(payload["detail_metro_code"], "12420")
            self.assertEqual(payload["detail_mode"], "fixture")


if __name__ == "__main__":
    unittest.main()
