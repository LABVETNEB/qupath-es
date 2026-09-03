from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
REGISTRY = ROOT / "components" / "registry.json"
COMPONENT_LOCK = ROOT / "versions" / "0.7.0" / "components.lock.json"
LOCALIZATION_LOCK = ROOT / "versions" / "0.7.0" / "localizations.lock.json"
SCHEMA = ROOT / "schemas" / "localizations-lock.schema.json"
SUPPORTED_VERSIONS = ROOT / "versions" / "supported-versions.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import schema_validate  # noqa: E402


ENTRY_FIELDS = {
    "component_id",
    "locale",
    "revision",
    "source_of_truth",
    "dist_bundle",
    "dist_sha256",
    "translation_status",
    "validation_status",
    "distribution_status",
}

LANGUAGE_SPECIFIC_FIELDS = {
    "locale",
    "revision",
    "source_of_truth",
    "dist_bundle",
    "dist_sha256",
    "translation_status",
    "validation_status",
    "distribution_status",
}

PIN_FIELDS_THAT_MUST_NOT_APPEAR = {
    "upstream_tag",
    "upstream_commit",
    "evidence_commit",
    "pin_basis",
    "artifact_name",
    "artifact_url",
    "artifact_sha256",
    "declared_qupath_api",
    "runtime_compatibility",
    "fork_repo",
    "fork_tag",
    "patches",
    "last_audited",
}

SHA256_RE = re.compile(r"^[0-9A-F]{64}$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_upper(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class LanguageAxisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_json(REGISTRY)
        cls.component_lock = load_json(COMPONENT_LOCK)
        cls.localization_lock = load_json(LOCALIZATION_LOCK)
        cls.schema = load_json(SCHEMA)
        cls.supported_versions = load_json(SUPPORTED_VERSIONS)
        cls.entries = cls.localization_lock["localizations"]

    def test_json_files_are_strict_utf8_without_bom_and_use_lf(self):
        for path in (LOCALIZATION_LOCK, SCHEMA):
            with self.subTest(path=path):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                raw.decode("utf-8", errors="strict")
                self.assertNotIn(b"\r", raw)

    def test_schema_is_an_executable_contract(self):
        schema_validate.validate(self.localization_lock, self.schema)
        self.assertFalse(self.schema["additionalProperties"])
        entry_schema = self.schema["$defs"]["localizationState"]
        self.assertFalse(entry_schema["additionalProperties"])
        self.assertEqual(set(entry_schema["required"]), ENTRY_FIELDS)
        self.assertEqual(set(entry_schema["properties"]), ENTRY_FIELDS)

    def test_language_axis_targets_the_same_qupath_version(self):
        self.assertEqual(self.localization_lock["schema_version"], 1)
        self.assertEqual(
            self.localization_lock["qupath_version"],
            self.component_lock["qupath_version"],
        )
        self.assertRegex(
            self.localization_lock["declared_at"],
            r"^\d{4}-\d{2}-\d{2}$",
        )

    def test_component_locale_pairs_are_unique(self):
        pairs = [
            (entry["component_id"], entry["locale"])
            for entry in self.entries
        ]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_spanish_projection_covers_the_registered_corpus_in_order(self):
        registry_ids = [entry["id"] for entry in self.registry["components"]]
        spanish_ids = [
            entry["component_id"]
            for entry in self.entries
            if entry["locale"] == "es"
        ]
        self.assertEqual(spanish_ids, registry_ids)

    def test_locale_contract_is_not_hardcoded_to_spanish(self):
        locale_pattern = self.schema["$defs"]["locale"]["pattern"]
        self.assertIsNotNone(re.fullmatch(locale_pattern, "es"))
        self.assertIsNotNone(re.fullmatch(locale_pattern, "fr"))
        self.assertIsNotNone(re.fullmatch(locale_pattern, "pt-BR"))
        self.assertIsNone(re.fullmatch(locale_pattern, "pt_BR"))

    def test_legacy_component_lock_is_an_exact_spanish_mirror(self):
        spanish = {
            entry["component_id"]: entry
            for entry in self.entries
            if entry["locale"] == "es"
        }

        for component in self.component_lock["components"]:
            component_id = component["component_id"]
            state = spanish[component_id]
            with self.subTest(component=component_id):
                self.assertEqual(
                    state["revision"],
                    component["localization_revision"],
                )
                self.assertEqual(
                    state["translation_status"],
                    component["translation_status"],
                )
                self.assertEqual(
                    state["validation_status"],
                    component["validation_status"],
                )
                self.assertEqual(
                    state["distribution_status"],
                    component["distribution_status"],
                )

    def test_language_axis_does_not_duplicate_component_pins(self):
        for entry in self.entries:
            with self.subTest(
                component=entry["component_id"],
                locale=entry["locale"],
            ):
                self.assertEqual(set(entry), ENTRY_FIELDS)
                self.assertTrue(LANGUAGE_SPECIFIC_FIELDS <= set(entry))
                self.assertTrue(set(entry).isdisjoint(PIN_FIELDS_THAT_MUST_NOT_APPEAR))

    def test_materialization_paths_are_explicit_safe_and_real(self):
        for entry in self.entries:
            with self.subTest(
                component=entry["component_id"],
                locale=entry["locale"],
            ):
                if entry["translation_status"] == "NOT_STARTED":
                    self.assertIsNone(entry["revision"])
                    self.assertIsNone(entry["source_of_truth"])
                    self.assertIsNone(entry["dist_bundle"])
                    self.assertIsNone(entry["dist_sha256"])
                    self.assertEqual(entry["validation_status"], "NOT_APPLICABLE")
                    self.assertEqual(entry["distribution_status"], "UNSUPPORTED")
                    continue

                for field in ("source_of_truth", "dist_bundle"):
                    relative = Path(entry[field])
                    self.assertFalse(relative.is_absolute())
                    self.assertNotIn("..", relative.parts)
                    self.assertTrue((ROOT / relative).is_file())

                self.assertTrue(entry["source_of_truth"].endswith(".tsv"))
                self.assertTrue(entry["dist_bundle"].endswith(".properties"))

    def test_every_materialized_distribution_has_exact_sha256(self):
        materialized = [
            entry
            for entry in self.entries
            if entry["dist_bundle"] is not None
        ]
        self.assertTrue(materialized)

        for entry in materialized:
            with self.subTest(
                component=entry["component_id"],
                locale=entry["locale"],
            ):
                self.assertRegex(entry["dist_sha256"], SHA256_RE)
                self.assertEqual(
                    sha256_upper(ROOT / entry["dist_bundle"]),
                    entry["dist_sha256"],
                )

    def test_core_distribution_fingerprint_matches_release_metadata(self):
        spanish = {
            entry["component_id"]: entry
            for entry in self.entries
            if entry["locale"] == "es"
        }
        core = spanish["qupath-core"]
        release = self.supported_versions["versions"]["0.7.0"]
        self.assertEqual(
            core["dist_sha256"],
            release["spanish_bundle_sha256"],
        )

    def test_existing_spanish_materialization_is_preserved_without_moves(self):
        spanish = {
            entry["component_id"]: entry
            for entry in self.entries
            if entry["locale"] == "es"
        }

        core = spanish["qupath-core"]
        self.assertIsNone(core["revision"])
        self.assertEqual(
            core["source_of_truth"],
            "versions/0.7.0/work/translation.tsv",
        )
        self.assertEqual(
            core["dist_bundle"],
            "versions/0.7.0/dist/qupath-gui-strings_es.properties",
        )
        self.assertEqual(
            core["dist_sha256"],
            "E4A966C90D1CE1368DE9EA21DECC7D9DBB0180087B60D3724690AAD4C128FC19",
        )

        instanseg = spanish["instanseg"]
        self.assertEqual(instanseg["revision"], "v0.1.7")
        self.assertEqual(
            instanseg["source_of_truth"],
            "components/instanseg/l10n/v0.1.7/strings.tsv",
        )
        self.assertEqual(
            instanseg["dist_bundle"],
            "components/instanseg/l10n/v0.1.7/dist/strings_es.properties",
        )
        self.assertEqual(
            instanseg["dist_sha256"],
            "D2405B02E4284BF5AA7F8C51EDB61E3C3B3364C064DC393E1B0D2C23C6E0E06A",
        )


if __name__ == "__main__":
    unittest.main()
