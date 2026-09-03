from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
CATALOG = ROOT / "catalog" / "catalog.json"
CATALOG_SCHEMA = ROOT / "schemas" / "extension-catalog.schema.json"
REGISTRY = ROOT / "components" / "registry.json"
COMPONENTS_LOCK = ROOT / "versions" / "0.7.0" / "components.lock.json"
LOCALIZATIONS_LOCK = ROOT / "versions" / "0.7.0" / "localizations.lock.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import catalog_projection  # noqa: E402
import schema_validate  # noqa: E402


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def entry_by(items, key, value):
    matches = [item for item in items if item[key] == value]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {key}={value!r}, got {len(matches)}")
    return matches[0]


class CatalogProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_json(REGISTRY)
        cls.components_lock = load_json(COMPONENTS_LOCK)
        cls.localizations_lock = load_json(LOCALIZATIONS_LOCK)
        cls.schema = load_json(CATALOG_SCHEMA)

    def project(self, registry=None, components_lock=None, localizations_lock=None):
        return catalog_projection.project_catalog(
            registry if registry is not None else copy.deepcopy(self.registry),
            components_lock if components_lock is not None else copy.deepcopy(self.components_lock),
            localizations_lock if localizations_lock is not None else copy.deepcopy(self.localizations_lock),
            qupath_version="0.7.0",
            locale="es",
        )

    def promoted_instanseg(self):
        components_lock = copy.deepcopy(self.components_lock)
        localizations_lock = copy.deepcopy(self.localizations_lock)

        pin = entry_by(components_lock["components"], "component_id", "instanseg")
        pin["runtime_compatibility"] = "BUNDLED_WITH_TARGET"

        state = entry_by(localizations_lock["localizations"], "component_id", "instanseg")
        state["translation_status"] = "TRANSLATED"
        state["validation_status"] = "VALIDATED"
        state["distribution_status"] = "DISTRIBUTED"

        return components_lock, localizations_lock

    def test_catalog_json_is_strict_utf8_lf_and_exact_projection(self):
        raw = CATALOG.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", raw)
        raw.decode("utf-8", errors="strict")

        result = catalog_projection.build_projection(
            ROOT,
            qupath_version="0.7.0",
            locale="es",
        )
        self.assertEqual(raw, catalog_projection.canonical_json_bytes(result.catalog))

    def test_current_catalog_is_valid_and_empty_for_extensions(self):
        catalog = load_json(CATALOG)
        schema_validate.validate(catalog, self.schema)
        self.assertEqual(catalog["extensions"], [])

        result = self.project()
        extension_ids = [
            entry["id"]
            for entry in self.registry["components"]
            if entry["type"] == "QUPATH_EXTENSION"
        ]
        self.assertEqual(set(result.excluded), set(extension_ids))
        self.assertEqual(len(extension_ids), 12)
        self.assertNotIn("qupath-core", result.excluded)

    def test_instanseg_is_excluded_by_current_authoritative_states(self):
        result = self.project()
        self.assertEqual(
            result.excluded["instanseg"],
            (
                "translation_not_translated",
                "localization_not_validated",
                "localization_not_distributed",
                "runtime_not_verified",
            ),
        )

    def test_runtime_not_verified_blocks_otherwise_distributed_extension(self):
        components_lock, localizations_lock = self.promoted_instanseg()
        pin = entry_by(components_lock["components"], "component_id", "instanseg")
        pin["runtime_compatibility"] = "NOT_VERIFIED"

        result = self.project(
            components_lock=components_lock,
            localizations_lock=localizations_lock,
        )
        self.assertEqual(result.catalog["extensions"], [])
        self.assertEqual(result.excluded["instanseg"], ("runtime_not_verified",))

    def test_promoted_extension_projects_to_exact_target_version(self):
        components_lock, localizations_lock = self.promoted_instanseg()
        result = self.project(
            components_lock=components_lock,
            localizations_lock=localizations_lock,
        )

        self.assertEqual(len(result.catalog["extensions"]), 1)
        extension = result.catalog["extensions"][0]
        self.assertEqual(extension["name"], "qupath-extension-instanseg")
        self.assertEqual(extension["author"], "qupath")
        self.assertEqual(
            extension["homepage"],
            "https://github.com/qupath/qupath-extension-instanseg",
        )
        self.assertFalse(extension["starred"])

        self.assertEqual(len(extension["releases"]), 1)
        release = extension["releases"][0]
        self.assertEqual(release["name"], "v0.1.7")
        self.assertEqual(
            release["main_url"],
            "https://github.com/qupath/qupath-extension-instanseg/releases/download/"
            "v0.1.7/qupath-extension-instanseg-0.1.7.jar",
        )
        self.assertEqual(
            release["version_range"],
            {"min": "v0.7.0", "max": "v0.7.0"},
        )
        schema_validate.validate(result.catalog, self.schema)

    def test_distributed_candidate_requires_pinned_release_asset(self):
        components_lock, localizations_lock = self.promoted_instanseg()
        pin = entry_by(components_lock["components"], "component_id", "instanseg")
        pin["artifact_url"] = None

        with self.assertRaisesRegex(
            catalog_projection.CatalogProjectionError,
            "lacks artifact_url",
        ):
            self.project(
                components_lock=components_lock,
                localizations_lock=localizations_lock,
            )

    def test_distributed_candidate_rejects_wrong_repository_url(self):
        components_lock, localizations_lock = self.promoted_instanseg()
        pin = entry_by(components_lock["components"], "component_id", "instanseg")
        pin["artifact_url"] = (
            "https://github.com/example/wrong/releases/download/"
            "v0.1.7/qupath-extension-instanseg-0.1.7.jar"
        )

        with self.assertRaisesRegex(
            catalog_projection.CatalogProjectionError,
            "does not belong to",
        ):
            self.project(
                components_lock=components_lock,
                localizations_lock=localizations_lock,
            )

    def test_satellite_fork_cannot_reuse_upstream_asset_implicitly(self):
        components_lock, localizations_lock = self.promoted_instanseg()
        pin = entry_by(components_lock["components"], "component_id", "instanseg")
        pin["fork_repo"] = "LABVETNEB/qupath-extension-instanseg-es"
        pin["fork_tag"] = "v0.1.7-es.1"

        with self.assertRaisesRegex(
            catalog_projection.CatalogProjectionError,
            "explicit fork artifact provenance",
        ):
            self.project(
                components_lock=components_lock,
                localizations_lock=localizations_lock,
            )

    def test_core_is_never_projected_as_extension(self):
        result = self.project()
        names = [entry["name"] for entry in result.catalog["extensions"]]
        self.assertNotIn("qupath", names)

    def test_duplicate_registry_id_fails_closed(self):
        registry = copy.deepcopy(self.registry)
        registry["components"].append(copy.deepcopy(registry["components"][1]))

        with self.assertRaisesRegex(
            catalog_projection.CatalogProjectionError,
            "duplicate id",
        ):
            self.project(registry=registry)

    def test_schema_is_closed_and_matches_upstream_field_names(self):
        self.assertFalse(self.schema["additionalProperties"])
        self.assertFalse(self.schema["$defs"]["extension"]["additionalProperties"])
        self.assertFalse(self.schema["$defs"]["release"]["additionalProperties"])
        self.assertFalse(self.schema["$defs"]["versionRange"]["additionalProperties"])

        release_properties = self.schema["$defs"]["release"]["properties"]
        self.assertIn("main_url", release_properties)
        self.assertIn("required_dependency_urls", release_properties)
        self.assertIn("optional_dependency_urls", release_properties)
        self.assertIn("javadoc_urls", release_properties)
        self.assertIn("version_range", release_properties)

    def test_upstream_model_provenance_is_pinned(self):
        self.assertEqual(
            catalog_projection.MODEL_REPOSITORY,
            "qupath/extension-catalog-model",
        )
        self.assertEqual(
            catalog_projection.MODEL_COMMIT,
            "89dd551c81db0b16455fc172a05ada694ac013ae",
        )


if __name__ == "__main__":
    unittest.main()
