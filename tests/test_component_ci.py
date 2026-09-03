from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import component_ci  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_blob(repo_path: str) -> bytes:
    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout.decode("ascii", errors="strict").strip()
    return subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{head}:{repo_path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


class ComponentScopedChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        registry = load_json(ROOT / "components" / "registry.json")
        cls.extension_ids = [
            entry["id"]
            for entry in registry["components"]
            if entry["type"] == "QUPATH_EXTENSION"
        ]

    def test_every_registered_extension_passes_the_scoped_check(self):
        self.assertEqual(len(self.extension_ids), 12)
        for component_id in self.extension_ids:
            with self.subTest(component=component_id):
                result = component_ci.check_component(ROOT, component_id)
                self.assertEqual(result["component_id"], component_id)
                self.assertTrue(result["versions"])
                self.assertIn("audit snapshots verified", result["audit"])

    def test_instanseg_scoped_check_verifies_materialized_distribution(self):
        result = component_ci.check_component(ROOT, "instanseg")
        version = next(
            entry
            for entry in result["versions"]
            if entry["qupath_version"] == "0.7.0"
        )
        spanish = next(
            entry
            for entry in version["localizations"]
            if entry["locale"] == "es"
        )
        self.assertTrue(spanish["materialized"])
        self.assertEqual(
            spanish["dist_sha256"],
            "D2405B02E4284BF5AA7F8C51EDB61E3C3B3364C064DC393E1B0D2C23C6E0E06A",
        )
        self.assertEqual(
            result["protected_inventory_revisions"],
            ["v0.1.7"],
        )

    def test_cellpose_scoped_check_keeps_not_started_localization_unmaterialized(self):
        result = component_ci.check_component(ROOT, "cellpose")
        version = next(
            entry
            for entry in result["versions"]
            if entry["qupath_version"] == "0.7.0"
        )
        spanish = next(
            entry
            for entry in version["localizations"]
            if entry["locale"] == "es"
        )
        self.assertFalse(spanish["materialized"])
        self.assertIsNone(spanish["dist_sha256"])

    def test_qupath_core_is_not_an_extension_matrix_target(self):
        with self.assertRaises(component_ci.ComponentCheckError):
            component_ci.check_component(ROOT, "qupath-core")

    def test_unknown_component_is_rejected(self):
        with self.assertRaises(component_ci.ComponentCheckError):
            component_ci.check_component(ROOT, "does-not-exist")

    def test_new_ci_tools_are_strict_utf8_lf_blobs(self):
        for repo_path in (
            "tools/ci_component_matrix.py",
            "tools/component_ci.py",
            "tests/test_ci_component_matrix.py",
            "tests/test_component_ci.py",
        ):
            with self.subTest(path=repo_path):
                raw = git_blob(repo_path)
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                raw.decode("utf-8", errors="strict")
                self.assertNotIn(b"\r", raw)
                self.assertTrue(raw.endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
