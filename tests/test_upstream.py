import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("upstream", Path(__file__).resolve().parents[1] / "scripts/upstream.py")
upstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream)


class UpstreamTests(unittest.TestCase):
    def test_rejects_prereleases_and_unrelated_tags(self):
        for tag in ("go1.28rc1", "v1.104.5-ohos.1", "garbage", "v1.2.3\n"):
            self.assertIsNone(upstream.stable_version(tag, "go"))

    def test_versions_are_numeric(self):
        config = {"tag_prefix": "v", "qualified_tag": "v1.9.0", "observed_mainline_commit": "a" * 40}
        result = upstream.report(config, [{"name": "v1.10.0"}, {"name": "v1.9.1"}], "b" * 40)
        self.assertEqual(result["latest"], "v1.10.0")
        self.assertTrue(result["new_release"])
        self.assertTrue(result["mainline_changed"])

    def test_no_drift_does_not_claim_upgrade(self):
        config = {"tag_prefix": "go", "qualified_tag": "go1.27.3", "observed_mainline_commit": "a" * 40}
        result = upstream.report(config, [{"name": "go1.27.3"}, {"name": "go1.28rc1"}], "a" * 40)
        self.assertFalse(result["new_release"])
        self.assertFalse(result["mainline_changed"])

    def test_empty_stable_list_is_not_success(self):
        with self.assertRaises(ValueError):
            upstream.report({"tag_prefix": "go"}, [{"name": "go1.28rc1"}], "a" * 40)


if __name__ == "__main__": unittest.main()
