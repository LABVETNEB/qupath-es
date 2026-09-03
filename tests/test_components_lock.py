"""Integrity tests for the per-QuPath component lockfile.

The registry owns stable component identity.  A components.lock.json owns the
version-specific relationship between one QuPath target and exact upstream
pins.  These tests deliberately keep those responsibilities separate.
"""
from __future__ import annotations

import json
import re
import unittest
from datetime import date
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "components" / "registry.json"
LOCK = REPO / "versions" / "0.7.0" / "components.lock.json"
SCHEMA = REPO / "schemas" / "components-lock.schema.json"

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")

EXPECTED_FIELDS = {
    "component_id",
    "upstream_tag",
    "upstream_commit",
    "pin_basis",
    "artifact_name",
    "artifact_url",
    "artifact_sha256",
    "declared_qupath_api",
    "runtime_compatibility",
    "localization_revision",
    "audit_status",
    "translation_status",
    "validation_status",
    "distribution_status",
    "fork_repo",
    "fork_tag",
    "patches",
    "last_audited",
}

EXPECTED_PINS = {
    "qupath-core": {
        "tag": None,
        "commit": "04ccfa4fb7d43e9b566393e08e83690b72248d44",
        "basis": "FROZEN_TARGET_COMMIT",
        "api": "0.7.0",
        "compatibility": "FROZEN_TARGET",
    },
    "dl-pixel-classifier": {
        "tag": "v0.8.5",
        "commit": "a1d327888f91d8f18465396028650154e54befcb",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.7.0",
        "compatibility": "NOT_VERIFIED",
    },
    "tiatoolbox": {
        "tag": None,
        "commit": "cb942b774c5b1f7340cfbb036687e0724adaaedd",
        "basis": "AUDITED_COMMIT",
        "api": "0.6.0",
        "compatibility": "NOT_VERIFIED",
    },
    "instanseg": {
        "tag": "v0.1.7",
        "commit": "90b260157f51f137201e11061b912b552c8b444f",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.6.0",
        "compatibility": "NOT_VERIFIED",
    },
    "cell-analysis-tools": {
        "tag": "v0.11.2",
        "commit": "76def4ef4cab2e673d4a247953028562403ce69e",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.7.0",
        "compatibility": "NOT_VERIFIED",
    },
    "training": {
        "tag": "v0.1.0",
        "commit": "8703a810fb7bb1c84a94d436c1bbaf514301891a",
        "basis": "QUPATH_BUNDLED",
        "api": "0.6.0",
        "compatibility": "BUNDLED_WITH_TARGET",
    },
    "stardist": {
        "tag": "v0.6.0",
        "commit": "934b041671217f0f82ae2f2d587352c0972b2364",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.6.0",
        "compatibility": "NOT_VERIFIED",
    },
    "cellpose": {
        "tag": "v0.12.1",
        "commit": "782652ea3357e9f48970d4ac21452c5d2d0df491",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.7.0",
        "compatibility": "NOT_VERIFIED",
    },
    "wsinfer": {
        "tag": "v0.4.0",
        "commit": "f1c652e79780d104e67b7404a9cb7c966cd58e60",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.6.0",
        "compatibility": "NOT_VERIFIED",
    },
    "djl": {
        "tag": "v0.4.2",
        "commit": "cce175dac8bd5981acb641f900cc10744d9dc5ab",
        "basis": "QUPATH_BUNDLED",
        "api": "0.6.0",
        "compatibility": "BUNDLED_WITH_TARGET",
    },
    "bioimageio": {
        "tag": "v0.2.0",
        "commit": "5e6c1069ac46965bf3eec6d6502561fc497843ae",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.8.0-SNAPSHOT",
        "compatibility": "NOT_VERIFIED",
    },
    "sam": {
        "tag": "v0.9.1",
        "commit": "8a286013540eaafa94927a485904a1df6a2dc601",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.6.0",
        "compatibility": "NOT_VERIFIED",
    },
    "image-export-toolkit": {
        "tag": "v1.2.8",
        "commit": "f11426e3f74665fdee41ed5d75d5bd559a3008b9",
        "basis": "UPSTREAM_RELEASE",
        "api": "0.7.0",
        "compatibility": "NOT_VERIFIED",
    },
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ComponentsLockTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_json(REGISTRY)
        self.lock = load_json(LOCK)
        self.schema = load_json(SCHEMA)
        self.components = self.lock["components"]
        self.by_id = {entry["component_id"]: entry for entry in self.components}

    def test_json_files_are_strict_utf8_without_bom(self):
        for path in (LOCK, SCHEMA):
            with self.subTest(path=path):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                raw.decode("utf-8", errors="strict")

    def test_top_level_target_is_frozen_qupath_070(self):
        self.assertEqual(self.lock["schema_version"], 1)
        self.assertEqual(self.lock["qupath_version"], "0.7.0")
        self.assertEqual(
            self.lock["qupath_upstream_commit"],
            "04ccfa4fb7d43e9b566393e08e83690b72248d44",
        )
        self.assertRegex(self.lock["qupath_upstream_commit"], SHA1_RE)

    def test_lock_ids_match_registry_exactly_and_in_order(self):
        registry_ids = [entry["id"] for entry in self.registry["components"]]
        lock_ids = [entry["component_id"] for entry in self.components]
        self.assertEqual(lock_ids, registry_ids)
        self.assertEqual(len(lock_ids), 13)
        self.assertEqual(len(lock_ids), len(set(lock_ids)))

    def test_entries_have_exact_lock_fields(self):
        for entry in self.components:
            with self.subTest(component=entry["component_id"]):
                self.assertEqual(set(entry), EXPECTED_FIELDS)

    def test_pins_are_exactly_the_reviewed_initial_snapshot(self):
        self.assertEqual(set(self.by_id), set(EXPECTED_PINS))
        for component_id, expected in EXPECTED_PINS.items():
            entry = self.by_id[component_id]
            with self.subTest(component=component_id):
                self.assertEqual(entry["upstream_tag"], expected["tag"])
                self.assertEqual(entry["upstream_commit"], expected["commit"])
                self.assertEqual(entry["pin_basis"], expected["basis"])
                self.assertEqual(entry["declared_qupath_api"], expected["api"])
                self.assertEqual(
                    entry["runtime_compatibility"], expected["compatibility"]
                )
                self.assertRegex(entry["upstream_commit"], SHA1_RE)

    def test_core_pin_is_the_frozen_target_not_default_branch(self):
        core = self.by_id["qupath-core"]
        self.assertIsNone(core["upstream_tag"])
        self.assertEqual(core["pin_basis"], "FROZEN_TARGET_COMMIT")
        self.assertEqual(core["upstream_commit"], self.lock["qupath_upstream_commit"])
        self.assertEqual(core["runtime_compatibility"], "FROZEN_TARGET")

    def test_bundled_components_use_versions_shipped_by_qupath_070(self):
        self.assertEqual(self.by_id["training"]["upstream_tag"], "v0.1.0")
        self.assertEqual(self.by_id["djl"]["upstream_tag"], "v0.4.2")
        for component_id in ("training", "djl"):
            with self.subTest(component=component_id):
                entry = self.by_id[component_id]
                self.assertEqual(entry["pin_basis"], "QUPATH_BUNDLED")
                self.assertEqual(entry["runtime_compatibility"], "BUNDLED_WITH_TARGET")
                self.assertIsNone(entry["artifact_name"])

    def test_tiatoolbox_is_commit_only_because_no_release_exists(self):
        entry = self.by_id["tiatoolbox"]
        self.assertIsNone(entry["upstream_tag"])
        self.assertEqual(entry["pin_basis"], "AUDITED_COMMIT")
        self.assertIsNone(entry["artifact_name"])
        self.assertIsNone(entry["artifact_url"])
        self.assertIsNone(entry["artifact_sha256"])

    def test_unmeasured_artifact_hashes_are_null_not_invented(self):
        for entry in self.components:
            with self.subTest(component=entry["component_id"]):
                self.assertIsNone(entry["artifact_url"])
                self.assertIsNone(entry["artifact_sha256"])

    def test_external_extensions_do_not_claim_runtime_validation(self):
        for component_id, entry in self.by_id.items():
            if component_id in {"qupath-core", "training", "djl"}:
                continue
            with self.subTest(component=component_id):
                self.assertEqual(entry["runtime_compatibility"], "NOT_VERIFIED")

    def test_bioimageio_preserves_its_08_snapshot_declaration(self):
        entry = self.by_id["bioimageio"]
        self.assertEqual(entry["declared_qupath_api"], "0.8.0-SNAPSHOT")
        self.assertEqual(entry["runtime_compatibility"], "NOT_VERIFIED")
        self.assertEqual(entry["distribution_status"], "UNSUPPORTED")

    def test_localization_states_match_the_architecture_audit(self):
        core = self.by_id["qupath-core"]
        self.assertEqual(core["audit_status"], "AUDITED")
        self.assertEqual(core["translation_status"], "TRANSLATED")
        self.assertEqual(core["validation_status"], "VALIDATED")
        self.assertEqual(core["distribution_status"], "DISTRIBUTED")

        for component_id, entry in self.by_id.items():
            if component_id == "qupath-core":
                continue
            with self.subTest(component=component_id):
                self.assertEqual(entry["audit_status"], "AUDITED")
                self.assertEqual(entry["translation_status"], "NOT_STARTED")
                self.assertEqual(entry["validation_status"], "NOT_APPLICABLE")
                self.assertEqual(entry["distribution_status"], "UNSUPPORTED")

    def test_no_forks_patches_or_localization_revisions_exist_yet(self):
        for entry in self.components:
            with self.subTest(component=entry["component_id"]):
                self.assertIsNone(entry["fork_repo"])
                self.assertIsNone(entry["fork_tag"])
                self.assertEqual(entry["patches"], [])
                self.assertIsNone(entry["localization_revision"])

    def test_dates_are_iso_dates(self):
        date.fromisoformat(self.lock["locked_at"])
        for entry in self.components:
            with self.subTest(component=entry["component_id"]):
                date.fromisoformat(entry["last_audited"])

    def test_schema_encodes_lockfile_separation_and_closed_world_contract(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)

        component_schema = self.schema["$defs"]["componentPin"]
        self.assertFalse(component_schema["additionalProperties"])
        self.assertEqual(set(component_schema["required"]), EXPECTED_FIELDS)
        self.assertEqual(set(component_schema["properties"]), EXPECTED_FIELDS)

    def test_registry_does_not_absorb_version_specific_lock_fields(self):
        registry_fields = set(self.registry["components"][0])
        lock_only = {
            "upstream_tag",
            "upstream_commit",
            "artifact_sha256",
            "declared_qupath_api",
            "runtime_compatibility",
            "translation_status",
            "validation_status",
            "distribution_status",
        }
        self.assertTrue(registry_fields.isdisjoint(lock_only))


if __name__ == "__main__":
    unittest.main()
