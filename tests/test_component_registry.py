"""
Integrity tests for the ecosystem component registry.

The registry is deliberately an identity layer. Version pins, compatibility,
artifacts and localization status belong in per-QuPath lockfiles instead.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = REPO / "components"
REGISTRY = COMPONENTS_DIR / "registry.json"
SCHEMA = REPO / "schemas" / "component-registry.schema.json"

EXPECTED_IDS = (
    "qupath-core",
    "dl-pixel-classifier",
    "tiatoolbox",
    "instanseg",
    "cell-analysis-tools",
    "training",
    "stardist",
    "cellpose",
    "wsinfer",
    "djl",
    "bioimageio",
    "sam",
    "image-export-toolkit",
)

REQUIRED_FIELDS = {
    "id",
    "canonical_name",
    "repository",
    "owner",
    "type",
    "priority",
    "role",
    "license",
    "build_system",
    "entry_point",
    "satellite_fork",
    "first_registered",
}

DYNAMIC_FIELDS_FORBIDDEN_IN_REGISTRY = {
    "qupath_version",
    "qupath_upstream_commit",
    "declared_qupath_api",
    "upstream_version",
    "upstream_tag",
    "upstream_commit",
    "artifact_name",
    "artifact_url",
    "artifact_sha256",
    "localization_revision",
    "audit_status",
    "translation_status",
    "validation_status",
    "distribution_status",
    "fork_tag",
    "patches",
    "last_audited",
}

EXTENSION_ENTRY_POINT = (
    "META-INF/services/qupath.lib.gui.extensions.QuPathExtension"
)

LICENSE_BY_ID = {
    "qupath-core": "GPL-3.0",
    "dl-pixel-classifier": "Apache-2.0",
    "tiatoolbox": "BSD-3-Clause",
    "instanseg": "Apache-2.0",
    "cell-analysis-tools": "Apache-2.0",
    "training": "Apache-2.0",
    "stardist": "Apache-2.0",
    "cellpose": "Apache-2.0",
    "wsinfer": "Apache-2.0",
    "djl": "Apache-2.0",
    "bioimageio": "Apache-2.0",
    "sam": "GPL-3.0",
    "image-export-toolkit": "Apache-2.0",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ComponentRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = read_json(REGISTRY)
        cls.schema = read_json(SCHEMA)
        cls.components = cls.registry["components"]
        cls.by_id = {component["id"]: component for component in cls.components}

    def test_json_files_are_strict_utf8_without_bom(self):
        for path in (REGISTRY, SCHEMA):
            with self.subTest(path=path):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                raw.decode("utf-8", errors="strict")

    def test_schema_version_is_pinned(self):
        self.assertEqual(self.registry["schema_version"], 1)
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)

    def test_component_ids_are_the_frozen_initial_corpus(self):
        self.assertEqual(
            tuple(component["id"] for component in self.components),
            EXPECTED_IDS,
        )

    def test_component_ids_are_unique_kebab_case(self):
        ids = [component["id"] for component in self.components]
        self.assertEqual(len(ids), len(set(ids)))
        for component_id in ids:
            with self.subTest(component_id=component_id):
                self.assertRegex(component_id, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    def test_entries_have_exact_identity_fields(self):
        for component in self.components:
            with self.subTest(component=component["id"]):
                self.assertEqual(set(component), REQUIRED_FIELDS)

    def test_repositories_are_unique_and_owner_matches(self):
        repositories = [component["repository"] for component in self.components]
        self.assertEqual(len(repositories), len(set(repositories)))

        for component in self.components:
            with self.subTest(component=component["id"]):
                owner, repository_name = component["repository"].split("/", 1)
                self.assertEqual(owner, component["owner"])
                self.assertEqual(repository_name, component["canonical_name"])

    def test_core_is_unique_and_not_an_extension(self):
        core = [
            component
            for component in self.components
            if component["type"] == "QUPATH_CORE"
        ]
        self.assertEqual(len(core), 1)
        self.assertEqual(core[0]["id"], "qupath-core")
        self.assertEqual(core[0]["priority"], "BASE")
        self.assertIsNone(core[0]["entry_point"])
        self.assertFalse((COMPONENTS_DIR / "qupath-core").exists())

    def test_extensions_use_the_observed_service_entry_point(self):
        extensions = [
            component
            for component in self.components
            if component["type"] == "QUPATH_EXTENSION"
        ]
        self.assertEqual(len(extensions), 12)

        for component in extensions:
            with self.subTest(component=component["id"]):
                self.assertEqual(component["entry_point"], EXTENSION_ENTRY_POINT)

    def test_priorities_match_the_initial_corpus(self):
        valid = {"BASE", "P0", "P0/P1", "P1"}
        for component in self.components:
            with self.subTest(component=component["id"]):
                self.assertIn(component["priority"], valid)

        self.assertEqual(self.by_id["cellpose"]["priority"], "P0/P1")

    def test_licenses_match_the_audited_identity(self):
        actual = {
            component["id"]: component["license"]
            for component in self.components
        }
        self.assertEqual(actual, LICENSE_BY_ID)

    def test_no_satellite_fork_is_registered_yet(self):
        self.assertTrue(
            all(component["satellite_fork"] is None for component in self.components)
        )

    def test_first_registered_is_iso_date(self):
        for component in self.components:
            with self.subTest(component=component["id"]):
                value = component["first_registered"]
                self.assertRegex(value, r"^\d{4}-\d{2}-\d{2}$")
                dt.date.fromisoformat(value)

    def test_registry_contains_identity_not_version_pins(self):
        for component in self.components:
            with self.subTest(component=component["id"]):
                forbidden = set(component) & DYNAMIC_FIELDS_FORBIDDEN_IN_REGISTRY
                self.assertEqual(forbidden, set())

    def test_schema_requires_the_identity_contract(self):
        component_schema = self.schema["$defs"]["component"]
        self.assertFalse(component_schema["additionalProperties"])
        self.assertEqual(set(component_schema["required"]), REQUIRED_FIELDS)

        id_pattern = component_schema["properties"]["id"]["pattern"]
        self.assertTrue(re.fullmatch(id_pattern, "image-export-toolkit"))
        self.assertIsNone(re.fullmatch(id_pattern, "Image Export Toolkit"))


if __name__ == "__main__":
    unittest.main()
