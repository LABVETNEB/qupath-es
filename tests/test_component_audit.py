from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "components" / "registry.json"
LOCK_PATH = ROOT / "versions" / "0.7.0" / "components.lock.json"
SOURCE_REPORT_PATH = (
    ROOT
    / "versions"
    / "0.7.0"
    / "reports"
    / "ecosystem-repository-architecture-audit.json"
)
TOOL_PATH = ROOT / "tools" / "component_audit.py"


def load_json(path: Path):
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise AssertionError(f"{path} has a UTF-8 BOM")
    return json.loads(data.decode("utf-8"))


def load_tool_module():
    spec = importlib.util.spec_from_file_location("component_audit", TOOL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load component_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComponentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_json(REGISTRY_PATH)
        cls.lock = load_json(LOCK_PATH)
        cls.source_report = load_json(SOURCE_REPORT_PATH)
        cls.tool = load_tool_module()

        cls.registry_by_id = {
            item["id"]: item for item in cls.registry["components"]
        }
        cls.audit_by_id = {
            item["id"]: item for item in cls.source_report["components"]
        }
        cls.lock_by_id = {
            item["component_id"]: item for item in cls.lock["components"]
        }
        cls.extension_ids = [
            item["id"]
            for item in cls.registry["components"]
            if item["type"] == "QUPATH_EXTENSION"
        ]

    def component_dir(self, component_id: str) -> Path:
        return ROOT / "components" / component_id

    def manifest(self, component_id: str):
        return load_json(self.component_dir(component_id) / "component.json")

    def snapshot(self, component_id: str):
        commit = self.audit_by_id[component_id]["audited_commit"]
        return load_json(
            self.component_dir(component_id)
            / "audits"
            / f"{commit}.json"
        )

    def test_12_extensions_have_directories_and_core_does_not(self):
        self.assertEqual(12, len(self.extension_ids))
        for component_id in self.extension_ids:
            self.assertTrue(self.component_dir(component_id).is_dir())
        self.assertFalse(self.component_dir("qupath-core").exists())

    def test_each_extension_has_manifest_and_exact_initial_snapshot(self):
        for component_id in self.extension_ids:
            registry_entry = self.registry_by_id[component_id]
            audit_entry = self.audit_by_id[component_id]
            component_dir = self.component_dir(component_id)
            manifest_path = component_dir / "component.json"
            snapshot_path = (
                component_dir
                / "audits"
                / f"{audit_entry['audited_commit']}.json"
            )
            self.assertTrue(manifest_path.is_file())
            self.assertTrue(snapshot_path.is_file())
            self.assertEqual(
                self.tool.build_manifest(registry_entry, audit_entry),
                load_json(manifest_path),
            )
            self.assertEqual(
                self.tool.build_snapshot(
                    registry_entry, audit_entry, self.source_report
                ),
                load_json(snapshot_path),
            )

    def test_snapshot_filename_is_the_40_hex_upstream_commit(self):
        sha1 = re.compile(r"^[0-9a-f]{40}$")
        for component_id in self.extension_ids:
            commit = self.audit_by_id[component_id]["audited_commit"]
            self.assertRegex(commit, sha1)
            snapshots = sorted(
                (self.component_dir(component_id) / "audits").glob("*.json")
            )
            self.assertEqual(1, len(snapshots))
            self.assertEqual(f"{commit}.json", snapshots[0].name)

    def test_manifest_identity_matches_registry(self):
        for component_id in self.extension_ids:
            registry_entry = self.registry_by_id[component_id]
            manifest = self.manifest(component_id)
            self.assertEqual(component_id, manifest["component_id"])
            self.assertEqual(registry_entry["repository"], manifest["repository"])
            self.assertEqual("COMPONENT_MANIFEST", manifest["manifest_role"])
            self.assertEqual(1, manifest["schema_version"])

    def test_manifest_bundle_paths_match_audit_evidence(self):
        for component_id in self.extension_ids:
            audit_entry = self.audit_by_id[component_id]
            expected = [
                bundle["path"]
                for bundle in audit_entry["resource_bundle_status"]["bundles"]
            ]
            actual = self.manifest(component_id)["audit_policy"]["bundle_paths"]
            self.assertEqual(expected, actual)

    def test_manifest_declares_protected_identifier_categories(self):
        minimum = {
            "JAVA_CLASS",
            "JAVA_PACKAGE",
            "METHOD",
            "VARIABLE",
            "SERIALIZED_KEY",
            "CONFIGURATION_KEY",
            "MODEL_IDENTIFIER",
            "MEASUREMENT_NAME",
            "PATHCLASS",
            "PARAMETER_KEY",
            "URL",
            "HASH",
            "ARTIFACT_NAME",
            "TENSOR_NAME",
            "MODEL_IO_NODE",
        }
        for component_id in self.extension_ids:
            policy = self.manifest(component_id)["audit_policy"]
            self.assertTrue(minimum <= set(policy["protected_identifier_categories"]))
            self.assertEqual([], policy["explicit_protected_identifiers"])
            self.assertEqual(
                "NOT_ENUMERATED_IN_INITIAL_AUDIT",
                policy["explicit_identifier_inventory_status"],
            )

    def test_initial_manifest_does_not_invent_explicit_identifiers(self):
        for component_id in self.extension_ids:
            self.assertEqual(
                [],
                self.manifest(component_id)["audit_policy"][
                    "explicit_protected_identifiers"
                ],
            )

    def test_fork_policy_never_vendors_upstream_source(self):
        for component_id in self.extension_ids:
            registry_entry = self.registry_by_id[component_id]
            policy = self.manifest(component_id)["fork_policy"]
            self.assertEqual("SATELLITE_ONLY_IF_REQUIRED", policy["strategy"])
            self.assertEqual(registry_entry["satellite_fork"], policy["repository"])
            self.assertTrue(policy["patches_live_in_qupath_es"])
            self.assertFalse(policy["source_code_vendored_here"])

    def test_snapshots_preserve_source_report_provenance(self):
        for component_id in self.extension_ids:
            source = self.snapshot(component_id)["source_report"]
            self.assertEqual(
                "versions/0.7.0/reports/"
                "ecosystem-repository-architecture-audit.json",
                source["path"],
            )
            self.assertEqual(
                self.source_report["repository_head"], source["repository_head"]
            )
            self.assertEqual(
                self.source_report["generated_at"], source["audit_generated_at"]
            )

    def test_snapshots_do_not_claim_new_runtime_validation(self):
        for component_id in self.extension_ids:
            audit_entry = self.audit_by_id[component_id]
            actual = self.snapshot(component_id)["qupath_compatibility"][
                "verified_against_0_7_0_at_runtime"
            ]
            expected = audit_entry["qupath_compatibility"][
                "verified_against_0_7_0_at_runtime"
            ]
            self.assertEqual(expected, actual)
            self.assertEqual("NOT_VERIFIED", actual)

    def test_resource_bundle_counts_are_preserved_exactly(self):
        for component_id in self.extension_ids:
            self.assertEqual(
                self.audit_by_id[component_id]["resource_bundle_status"],
                self.snapshot(component_id)["resource_bundle_status"],
            )

    def test_three_hardcoded_extensions_still_have_no_bundle(self):
        for component_id in ("stardist", "cellpose", "sam"):
            snapshot = self.snapshot(component_id)
            self.assertFalse(snapshot["resource_bundle_status"]["has_resource_bundle"])
            self.assertEqual("FULLY_HARDCODED", snapshot["hardcoded_ui_status"])
            self.assertEqual(
                "TRANSLATABLE_ONLY_AFTER_STRING_EXTERNALISATION",
                snapshot["localization_strategy_class"],
            )

    def test_bundle_based_extensions_remain_not_externally_localizable(self):
        for component_id in self.extension_ids:
            snapshot = self.snapshot(component_id)
            if not snapshot["resource_bundle_status"]["has_resource_bundle"]:
                continue
            mechanism = snapshot["translation_mechanism"]
            self.assertEqual("PLAIN_RESOURCEBUNDLE_GETBUNDLE", mechanism["resolution"])
            self.assertFalse(
                mechanism["reachable_by_external_localization_directory"]
            )
            self.assertFalse(mechanism["display_category_aware"])

    def test_core_remains_outside_component_axis_but_in_audit_and_lock(self):
        audit_core = self.audit_by_id["qupath-core"]
        lock_core = self.lock_by_id["qupath-core"]
        self.assertFalse(self.component_dir("qupath-core").exists())
        self.assertEqual(
            "67cbf619996582f8737550080cd05c6e52b37b13",
            audit_core["audited_commit"],
        )
        self.assertNotEqual(audit_core["audited_commit"], lock_core["upstream_commit"])
        self.assertIn(
            "0.8.0-SNAPSHOT",
            audit_core["resource_bundle_status"]["branch_note"],
        )

    def test_bundled_training_and_djl_snapshots_are_not_lock_pins(self):
        for component_id in ("training", "djl"):
            snapshot = self.snapshot(component_id)
            lock = self.lock_by_id[component_id]
            self.assertNotEqual(snapshot["upstream_commit"], lock["upstream_commit"])
            self.assertIsNotNone(
                snapshot["qupath_compatibility"][
                    "bundled_in_qupath_0_7_0_install"
                ]
            )

    def test_registry_lock_and_audit_have_same_component_set(self):
        registry_ids = [item["id"] for item in self.registry["components"]]
        audit_ids = [item["id"] for item in self.source_report["components"]]
        lock_ids = [item["component_id"] for item in self.lock["components"]]
        self.assertEqual(set(registry_ids), set(audit_ids))
        self.assertEqual(registry_ids, lock_ids)

    def test_component_json_does_not_absorb_qupath_version_pins(self):
        forbidden = {
            "upstream_tag",
            "artifact_name",
            "artifact_url",
            "artifact_sha256",
            "declared_qupath_api",
            "validation_status",
            "distribution_status",
        }
        for component_id in self.extension_ids:
            self.assertTrue(forbidden.isdisjoint(self.manifest(component_id)))

    def test_json_files_are_strict_utf8_without_bom(self):
        for component_id in self.extension_ids:
            audit_entry = self.audit_by_id[component_id]
            paths = [
                self.component_dir(component_id) / "component.json",
                self.component_dir(component_id)
                / "audits"
                / f"{audit_entry['audited_commit']}.json",
            ]
            for path in paths:
                data = path.read_bytes()
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"), path)
                data.decode("utf-8")

    def test_tool_check_succeeds_offline(self):
        result = subprocess.run(
            [sys.executable, str(TOOL_PATH), "--check"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("OK: 12 extension audit snapshots verified", result.stdout)

    def test_tool_rejects_core_as_component_directory_target(self):
        result = subprocess.run(
            [
                sys.executable,
                str(TOOL_PATH),
                "--check",
                "--component",
                "qupath-core",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("extension-only", result.stderr)

    def test_tool_expected_files_match_existing_training_snapshot(self):
        expected = self.tool.expected_files({"training"})
        snapshot_path = next(
            path for path in expected if path.parent.name == "audits"
        )
        self.assertTrue(snapshot_path.is_file())
        self.assertEqual(expected[snapshot_path], load_json(snapshot_path))


if __name__ == "__main__":
    unittest.main()
