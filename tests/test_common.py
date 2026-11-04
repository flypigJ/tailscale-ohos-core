import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/common.py"
spec = importlib.util.spec_from_file_location("common", SCRIPT)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


class BuildSafetyTests(unittest.TestCase):
    def test_manifest_rejects_paths_outside_root(self):
        with tempfile.TemporaryDirectory() as directory:
            for path in ("../state", "/tmp/state", "C:/secret", "..\\state", "."):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    common.child(directory, path)

    def test_environment_isolation(self):
        with patch.dict(os.environ, {"GOOS": "android", "GOTOOLCHAIN": "auto", "GOFLAGS": "-race",
                                     "GOROOT": "wrong", "CC": "wrong", "CGO_LDFLAGS": "wrong"}):
            env = common.clean_env()
        for name in ("GOOS", "GOROOT", "GOFLAGS", "CC", "CGO_LDFLAGS"):
            self.assertNotIn(name, env)
        self.assertEqual(env["GOTOOLCHAIN"], "local")
        self.assertEqual(env["GOENV"], "off")

    def test_modified_and_duplicate_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.go"
            path.write_text("original")
            files = [{"path": "source.go", "sha256": common.digest(path)}]
            common.verify_files(directory, files)
            with self.assertRaises(ValueError):
                common.verify_files(directory, files * 2)
            path.write_text("changed")
            with self.assertRaises(ValueError):
                common.verify_files(directory, files)

    def test_atomic_receipt_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            common.write(path, {"status": "first"})
            common.write(path, {"status": "second"})
            self.assertEqual(common.read(path), {"status": "second"})
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_untracked_build_input_cannot_escape_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            common.run(["git", "init", "--quiet", directory])
            source = Path(directory) / "tracked.go"
            source.write_text("package main\n")
            common.run(["git", "add", "tracked.go"], cwd=directory)
            before, files = common.tracked_digest(directory, ["*.go"])
            self.assertEqual(len(files), 1)
            added = Path(directory) / "unrecorded.go"
            added.write_text("package main\n")
            with self.assertRaisesRegex(ValueError, "untracked build inputs"):
                common.tracked_digest(directory, ["*.go"])
            common.run(["git", "add", "unrecorded.go"], cwd=directory)
            after, files = common.tracked_digest(directory, ["*.go"])
            self.assertNotEqual(before, after)
            self.assertEqual(len(files), 2)

    def test_sdk_version_gate_precedes_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            common.write(Path(directory) / "oh-uni-package.json", {"apiVersion": 25, "releaseType": "Release"})
            with self.assertRaisesRegex(ValueError, "API 26"):
                common.native_sdk(directory)


if __name__ == "__main__":
    unittest.main()
