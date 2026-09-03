"""Integrity tests for the InstanSeg v0.1.7 localization pilot."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT_ID = "instanseg"
EXTENSION_VERSION = "v0.1.7"
UPSTREAM_COMMIT = "90b260157f51f137201e11061b912b552c8b444f"
UPSTREAM_BUNDLE_PATH = (
    "src/main/resources/qupath/ext/instanseg/ui/strings.properties"
)
UPSTREAM_BUNDLE_BLOB_SHA = "72ae3eab9ddc9317efd6d7afc0e5d814f8bcf697"
EXPECTED_KEYS = 97
EXPECTED_KEY_SHA256 = (
    "84407af23fbcb938f05ed4e736ebbe63ae75c85295c2e091e3c3ba035a8029e1"
)
EXPECTED_SOURCE_SIGNATURE_SHA256 = (
    "d728553095cc0f48f99e302fd355cc0a619bd11329299ea8d78c4d35d723ad24"
)
KEEP_EN_KEYS = {
    "title",
    "extension.qupath.version",
    "ui.processing.pane",
}

L10N_DIR = ROOT / "components" / COMPONENT_ID / "l10n" / EXTENSION_VERSION
TSV_PATH = L10N_DIR / "strings.tsv"
DIST_PATH = L10N_DIR / "dist" / "strings_es.properties"
MANIFEST_PATH = ROOT / "components" / COMPONENT_ID / "component.json"
AUDIT_PATH = (
    ROOT
    / "components"
    / COMPONENT_ID
    / "audits"
    / f"{UPSTREAM_COMMIT}.json"
)
LOCK_PATH = ROOT / "versions" / "0.7.0" / "components.lock.json"
PROPERTIES_TOOL = ROOT / "tools" / "properties_audit.py"

TSV_HEADER = [
    "key",
    "en",
    "es",
    "state",
    "batch",
    "reviewer",
    "rev_date",
    "qupath_ver",
    "issues",
    "notes",
]


def load_json(path: Path):
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    return json.loads(data.decode("utf-8"))


def load_tsv() -> list[dict[str, str]]:
    raw = TSV_PATH.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("strings.tsv has a UTF-8 BOM")
    text = raw.decode("utf-8")
    if "\r" in text:
        raise ValueError("strings.tsv must use LF line endings")
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if reader.fieldnames != TSV_HEADER:
        raise ValueError(f"unexpected TSV header: {reader.fieldnames!r}")
    return list(reader)


SPEC = importlib.util.spec_from_file_location(
    "extension_properties_audit",
    PROPERTIES_TOOL,
)
assert SPEC is not None and SPEC.loader is not None
properties_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = properties_audit
SPEC.loader.exec_module(properties_audit)


def printf_tokens(value: str) -> list[str]:
    return properties_audit.PRINTF_RE.findall(value)


class InstanSegExtensionTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_tsv()
        cls.manifest = load_json(MANIFEST_PATH)
        cls.audit = load_json(AUDIT_PATH)
        cls.lock = load_json(LOCK_PATH)
        cls.lock_entry = next(
            item
            for item in cls.lock["components"]
            if item["component_id"] == COMPONENT_ID
        )

        dist_raw = DIST_PATH.read_bytes()
        if dist_raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("strings_es.properties has a UTF-8 BOM")
        cls.dist_text = dist_raw.decode("utf-8")
        if "\r" in cls.dist_text:
            raise ValueError("strings_es.properties must use LF line endings")
        cls.dist_entries = properties_audit.parse_properties(cls.dist_text)

    def test_pilot_paths_exist(self) -> None:
        self.assertTrue(TSV_PATH.is_file())
        self.assertTrue(DIST_PATH.is_file())
        self.assertEqual(L10N_DIR.name, EXTENSION_VERSION)

    def test_tsv_has_canonical_header_and_exact_key_count(self) -> None:
        self.assertEqual(len(self.rows), EXPECTED_KEYS)
        self.assertEqual(len({row["key"] for row in self.rows}), EXPECTED_KEYS)

    def test_source_key_order_is_pinned(self) -> None:
        digest = hashlib.sha256(
            "\n".join(row["key"] for row in self.rows).encode("utf-8")
        ).hexdigest()
        self.assertEqual(digest, EXPECTED_KEY_SHA256)

    def test_source_english_signature_is_pinned(self) -> None:
        payload = "\n".join(
            f"{row['key']}\t{row['en']}" for row in self.rows
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            EXPECTED_SOURCE_SIGNATURE_SHA256,
        )

    def test_states_are_draft_or_explicit_keep_en_only(self) -> None:
        states = Counter(row["state"] for row in self.rows)
        self.assertEqual(states, Counter({"DRAFT": 94, "KEEP_EN": 3}))
        self.assertNotIn("REVIEWED", states)
        actual_keep_en = {
            row["key"] for row in self.rows if row["state"] == "KEEP_EN"
        }
        self.assertEqual(actual_keep_en, KEEP_EN_KEYS)

    def test_metadata_is_pinned_to_the_pilot(self) -> None:
        for row in self.rows:
            with self.subTest(key=row["key"]):
                self.assertEqual(row["batch"], "INSTANSEG-ES-v0.1.7")
                self.assertEqual(row["reviewer"], "ChatGPT")
                self.assertEqual(row["rev_date"], "2026-09-03")
                self.assertEqual(row["qupath_ver"], "0.7.0")
                self.assertEqual(row["issues"], "")
                self.assertTrue(row["es"])

    def test_keep_en_is_identical_and_drafts_are_translated(self) -> None:
        for row in self.rows:
            with self.subTest(key=row["key"]):
                if row["state"] == "KEEP_EN":
                    self.assertEqual(row["es"], row["en"])
                else:
                    self.assertNotEqual(row["es"], row["en"])

    def test_printf_tokens_are_preserved(self) -> None:
        for row in self.rows:
            with self.subTest(key=row["key"]):
                self.assertEqual(
                    printf_tokens(row["es"]),
                    printf_tokens(row["en"]),
                )

    def test_escaped_newline_structure_is_preserved(self) -> None:
        for row in self.rows:
            with self.subTest(key=row["key"]):
                self.assertEqual(
                    row["es"].count(r"\n"),
                    row["en"].count(r"\n"),
                )

    def test_dist_has_exactly_the_tsv_keys_in_order(self) -> None:
        self.assertEqual(len(self.dist_entries), EXPECTED_KEYS)
        self.assertEqual(
            [entry.key for entry in self.dist_entries],
            [row["key"] for row in self.rows],
        )

    def test_dist_values_are_generated_from_tsv_spanish(self) -> None:
        expected = [
            properties_audit.java_unescape(row["es"], 1)
            for row in self.rows
        ]
        self.assertEqual(
            [entry.value for entry in self.dist_entries],
            expected,
        )

    def test_dist_is_strict_utf8_without_bom_or_crlf(self) -> None:
        raw = DIST_PATH.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        raw.decode("utf-8", errors="strict")
        self.assertNotIn(b"\r", raw)

    def test_manifest_points_to_the_same_upstream_commit(self) -> None:
        self.assertEqual(self.manifest["component_id"], COMPONENT_ID)
        self.assertEqual(
            self.manifest["initial_audit"]["upstream_commit"],
            UPSTREAM_COMMIT,
        )
        self.assertEqual(
            self.manifest["audit_policy"]["bundle_paths"],
            [UPSTREAM_BUNDLE_PATH],
        )

    def test_audit_provenance_matches_the_pilot_source(self) -> None:
        self.assertEqual(self.audit["upstream_commit"], UPSTREAM_COMMIT)
        self.assertEqual(self.audit["latest_release_or_tag"], EXTENSION_VERSION)
        bundles = self.audit["resource_bundle_status"]["bundles"]
        self.assertEqual(len(bundles), 1)
        self.assertEqual(bundles[0]["path"], UPSTREAM_BUNDLE_PATH)
        self.assertEqual(bundles[0]["keys"], EXPECTED_KEYS)
        self.assertEqual(
            self.audit["resource_bundle_status"]["total_bundle_keys"],
            EXPECTED_KEYS,
        )
        self.assertRegex(UPSTREAM_BUNDLE_BLOB_SHA, r"^[0-9a-f]{40}$")

    def test_lockfile_pin_tracks_pilot_but_runtime_remains_unverified(self) -> None:
        entry = self.lock_entry
        self.assertEqual(entry["upstream_tag"], EXTENSION_VERSION)
        self.assertEqual(entry["upstream_commit"], UPSTREAM_COMMIT)
        self.assertEqual(entry["runtime_compatibility"], "NOT_VERIFIED")
        self.assertEqual(entry["distribution_status"], "UNSUPPORTED")
        self.assertEqual(entry["localization_revision"], EXTENSION_VERSION)
        self.assertEqual(entry["translation_status"], "IN_PROGRESS")
        self.assertEqual(entry["validation_status"], "NOT_VALIDATED")

    def test_pilot_does_not_claim_external_installability(self) -> None:
        mechanism = self.audit["translation_mechanism"]
        self.assertEqual(
            mechanism["resolution"],
            "PLAIN_RESOURCEBUNDLE_GETBUNDLE",
        )
        self.assertFalse(
            mechanism["reachable_by_external_localization_directory"]
        )
        self.assertFalse(mechanism["display_category_aware"])
        self.assertTrue(self.audit["fork_required"])
        self.assertTrue(self.audit["patch_required"])
        self.assertEqual(
            self.audit["distribution_status"],
            "UNSUPPORTED",
        )

    def test_no_fork_or_patch_is_created_by_the_pilot(self) -> None:
        self.assertIsNone(self.lock_entry["fork_repo"])
        self.assertIsNone(self.lock_entry["fork_tag"])
        self.assertEqual(self.lock_entry["patches"], [])
        self.assertFalse((ROOT / "components" / COMPONENT_ID / "patches").exists())

    def test_l10n_directory_contains_only_pilot_artifacts(self) -> None:
        files = {
            path.relative_to(L10N_DIR).as_posix()
            for path in L10N_DIR.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            files,
            {"strings.tsv", "dist/strings_es.properties"},
        )


if __name__ == "__main__":
    unittest.main()
