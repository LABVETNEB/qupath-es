"""Generic conformance tests for extension localization revisions."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unittest
from collections import Counter
from dataclasses import dataclass
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = ROOT / "components"
VERSIONS_DIR = ROOT / "versions"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "extension_localizations"
TOOLS_DIR = ROOT / "tools"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import properties_audit  # noqa: E402
import translation_generator  # noqa: E402
import translation_validator  # noqa: E402


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

ALLOWED_STATES = {
    "PENDING",
    "DRAFT",
    "REVIEWED",
    "KEEP_EN",
    "BLOCKED",
}

FIXTURE_FIELDS = {
    "schema_version",
    "component_id",
    "revision",
    "source_bundle_path",
    "dist_bundle",
    "expected_keys",
    "expected_key_sha256",
    "expected_source_signature_sha256",
    "expected_state_counts",
    "expected_keep_en_keys",
    "expected_row_metadata",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class LockRef:
    qupath_version: str
    lock_path: Path
    entry: dict


def load_json(path: Path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    return json.loads(raw.decode("utf-8", errors="strict"))


def read_utf8_lf(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    text = raw.decode("utf-8", errors="strict")
    if b"\r" in raw:
        raise ValueError(f"{path} must use LF line endings")
    return raw, text


def load_tsv(path: Path) -> list[dict[str, str]]:
    _raw, text = read_utf8_lf(path)
    reader = csv.DictReader(StringIO(text, newline=""), delimiter="\t")
    if reader.fieldnames != TSV_HEADER:
        raise ValueError(
            f"{path}: unexpected TSV header {reader.fieldnames!r}"
        )
    return list(reader)


def discover_lock_refs() -> dict[tuple[str, str], list[LockRef]]:
    declared: dict[tuple[str, str], list[LockRef]] = {}

    for lock_path in sorted(VERSIONS_DIR.glob("*/components.lock.json")):
        lock = load_json(lock_path)
        qupath_version = lock["qupath_version"]

        for entry in lock["components"]:
            revision = entry["localization_revision"]
            if revision is None:
                continue

            key = (entry["component_id"], revision)
            declared.setdefault(key, []).append(
                LockRef(
                    qupath_version=qupath_version,
                    lock_path=lock_path,
                    entry=entry,
                )
            )

    return declared


def discover_materialized_localizations() -> dict[tuple[str, str], Path]:
    materialized: dict[tuple[str, str], Path] = {}

    for l10n_root in sorted(COMPONENTS_DIR.glob("*/l10n")):
        if not l10n_root.is_dir():
            continue

        component_id = l10n_root.parent.name
        for revision_dir in sorted(
            path for path in l10n_root.iterdir() if path.is_dir()
        ):
            key = (component_id, revision_dir.name)
            materialized[key] = revision_dir

    return materialized


def discover_fixtures() -> dict[tuple[str, str], tuple[Path, dict]]:
    fixtures: dict[tuple[str, str], tuple[Path, dict]] = {}

    for fixture_path in sorted(FIXTURE_DIR.glob("*.json")):
        fixture = load_json(fixture_path)
        component_id = fixture.get("component_id")
        revision = fixture.get("revision")
        key = (component_id, revision)

        if key in fixtures:
            raise ValueError(f"duplicate localization fixture for {key}")

        fixtures[key] = (fixture_path, fixture)

    return fixtures


class ExtensionLocalizationConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.declared = discover_lock_refs()
        cls.materialized = discover_materialized_localizations()
        cls.fixtures = discover_fixtures()

    def iter_cases(self):
        common = (
            set(self.materialized)
            & set(self.declared)
            & set(self.fixtures)
        )
        for key in sorted(common):
            fixture_path, fixture = self.fixtures[key]
            yield (
                key,
                self.materialized[key],
                self.declared[key],
                fixture_path,
                fixture,
            )

    def test_declared_revisions_match_materialized_tree(self) -> None:
        self.assertTrue(
            self.declared,
            "at least one extension localization revision must be declared",
        )
        self.assertEqual(set(self.declared), set(self.materialized))

    def test_every_materialized_revision_has_one_data_fixture(self) -> None:
        self.assertEqual(set(self.materialized), set(self.fixtures))

    def test_fixture_contract_is_closed_and_well_formed(self) -> None:
        for key, _l10n_dir, _refs, fixture_path, fixture in self.iter_cases():
            with self.subTest(component=key[0], revision=key[1]):
                self.assertEqual(set(fixture), FIXTURE_FIELDS)
                self.assertEqual(fixture["schema_version"], 1)
                self.assertEqual(
                    (fixture["component_id"], fixture["revision"]),
                    key,
                )
                self.assertIsInstance(fixture["source_bundle_path"], str)
                self.assertTrue(fixture["source_bundle_path"])
                self.assertIsInstance(fixture["dist_bundle"], str)
                self.assertTrue(fixture["dist_bundle"].startswith("dist/"))
                self.assertTrue(fixture["dist_bundle"].endswith(".properties"))
                self.assertNotIn("..", Path(fixture["dist_bundle"]).parts)
                self.assertGreater(fixture["expected_keys"], 0)
                self.assertRegex(
                    fixture["expected_key_sha256"],
                    SHA256_RE,
                )
                self.assertRegex(
                    fixture["expected_source_signature_sha256"],
                    SHA256_RE,
                )
                self.assertEqual(
                    sum(fixture["expected_state_counts"].values()),
                    fixture["expected_keys"],
                )
                self.assertTrue(
                    set(fixture["expected_state_counts"]) <= ALLOWED_STATES
                )
                self.assertEqual(
                    len(fixture["expected_keep_en_keys"]),
                    len(set(fixture["expected_keep_en_keys"])),
                )
                self.assertTrue(
                    set(fixture["expected_row_metadata"]) <= set(TSV_HEADER)
                )
                self.assertNotIn("key", fixture["expected_row_metadata"])
                self.assertTrue(fixture_path.is_file())

    def test_localization_tree_has_only_declared_artifacts(self) -> None:
        for key, l10n_dir, _refs, _fixture_path, fixture in self.iter_cases():
            with self.subTest(component=key[0], revision=key[1]):
                expected_files = {
                    "strings.tsv",
                    fixture["dist_bundle"],
                }
                actual_files = {
                    path.relative_to(l10n_dir).as_posix()
                    for path in l10n_dir.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(actual_files, expected_files)
                self.assertEqual(l10n_dir.name, fixture["revision"])

    def test_tsv_is_strict_utf8_lf_and_matches_fixture(self) -> None:
        for key, l10n_dir, _refs, _fixture_path, fixture in self.iter_cases():
            rows = load_tsv(l10n_dir / "strings.tsv")
            with self.subTest(component=key[0], revision=key[1]):
                self.assertEqual(len(rows), fixture["expected_keys"])

                keys = [row["key"] for row in rows]
                self.assertTrue(all(keys))
                self.assertEqual(len(keys), len(set(keys)))

                key_digest = hashlib.sha256(
                    "\n".join(keys).encode("utf-8")
                ).hexdigest()
                self.assertEqual(
                    key_digest,
                    fixture["expected_key_sha256"],
                )

                source_payload = "\n".join(
                    f"{row['key']}\t{row['en']}" for row in rows
                ).encode("utf-8")
                self.assertEqual(
                    hashlib.sha256(source_payload).hexdigest(),
                    fixture["expected_source_signature_sha256"],
                )

                states = Counter(row["state"] for row in rows)
                self.assertEqual(
                    states,
                    Counter(fixture["expected_state_counts"]),
                )
                self.assertTrue(set(states) <= ALLOWED_STATES)

                actual_keep_en = {
                    row["key"]
                    for row in rows
                    if row["state"] == "KEEP_EN"
                }
                self.assertEqual(
                    actual_keep_en,
                    set(fixture["expected_keep_en_keys"]),
                )

                for row in rows:
                    with self.subTest(
                        component=key[0],
                        revision=key[1],
                        row=row["key"],
                    ):
                        self.assertTrue(row["key"])
                        if row["en"].strip():
                            self.assertTrue(row["es"].strip())

                        en_value = translation_generator.decode_work_text(
                            row["en"]
                        )
                        es_value = translation_generator.decode_work_text(
                            row["es"]
                        )

                        if row["state"] == "KEEP_EN":
                            self.assertEqual(es_value, en_value)
                        elif row["state"] in {"DRAFT", "REVIEWED"}:
                            self.assertNotEqual(es_value, en_value)

                        for field, expected in fixture[
                            "expected_row_metadata"
                        ].items():
                            self.assertEqual(row[field], expected)

    def test_tsv_placeholders_and_structural_escapes_are_preserved(self) -> None:
        for key, l10n_dir, _refs, _fixture_path, _fixture in self.iter_cases():
            rows = load_tsv(l10n_dir / "strings.tsv")

            for row in rows:
                with self.subTest(
                    component=key[0],
                    revision=key[1],
                    row=row["key"],
                ):
                    en_value = translation_generator.decode_work_text(row["en"])
                    es_value = translation_generator.decode_work_text(row["es"])

                    self.assertEqual(
                        Counter(
                            translation_validator.message_format_tokens(
                                en_value
                            )
                        ),
                        Counter(
                            translation_validator.message_format_tokens(
                                es_value
                            )
                        ),
                    )
                    self.assertEqual(
                        Counter(
                            translation_validator.message_format_effective_tokens(
                                en_value
                            )
                        ),
                        Counter(
                            translation_validator.message_format_effective_tokens(
                                es_value
                            )
                        ),
                    )

                    en_printf = translation_validator.printf_tokens(en_value)
                    es_printf = translation_validator.printf_tokens(es_value)
                    if en_printf != es_printf:
                        self.assertTrue(
                            translation_validator.format_tokens_are_positional(
                                en_printf
                            )
                        )
                        self.assertEqual(
                            Counter(en_printf),
                            Counter(es_printf),
                        )

                    self.assertEqual(
                        translation_validator.brace_balance(en_value),
                        translation_validator.brace_balance(es_value),
                    )
                    self.assertEqual(
                        en_value.count("\n"),
                        es_value.count("\n"),
                    )
                    self.assertEqual(
                        en_value.count("\t"),
                        es_value.count("\t"),
                    )
                    self.assertNotIn(
                        translation_validator.REPLACEMENT_CHARACTER,
                        es_value,
                    )
                    self.assertIsNone(
                        translation_validator.DISALLOWED_CONTROL_RE.search(
                            es_value
                        )
                    )

    def test_dist_is_strict_utf8_lf_and_derived_from_tsv(self) -> None:
        for key, l10n_dir, _refs, _fixture_path, fixture in self.iter_cases():
            rows = load_tsv(l10n_dir / "strings.tsv")
            dist_path = l10n_dir / fixture["dist_bundle"]
            _raw, dist_text = read_utf8_lf(dist_path)
            entries = properties_audit.parse_properties(dist_text)

            with self.subTest(component=key[0], revision=key[1]):
                dist_keys = [entry.key for entry in entries]
                tsv_keys = [row["key"] for row in rows]

                self.assertEqual(len(dist_keys), fixture["expected_keys"])
                self.assertEqual(len(dist_keys), len(set(dist_keys)))
                self.assertEqual(dist_keys, tsv_keys)
                self.assertEqual(
                    [entry.value for entry in entries],
                    [
                        translation_generator.decode_work_text(row["es"])
                        for row in rows
                    ],
                )

    def test_bundle_names_and_counts_match_component_evidence(self) -> None:
        for key, l10n_dir, refs, _fixture_path, fixture in self.iter_cases():
            component_id, _revision = key
            manifest_path = COMPONENTS_DIR / component_id / "component.json"
            manifest = load_json(manifest_path)

            with self.subTest(component=component_id):
                self.assertEqual(manifest["component_id"], component_id)
                self.assertIn(
                    fixture["source_bundle_path"],
                    manifest["audit_policy"]["bundle_paths"],
                )

            for ref in refs:
                audit_path = (
                    COMPONENTS_DIR
                    / component_id
                    / "audits"
                    / f"{ref.entry['evidence_commit']}.json"
                )
                audit = load_json(audit_path)
                bundles = [
                    bundle
                    for bundle in audit["resource_bundle_status"]["bundles"]
                    if bundle["path"] == fixture["source_bundle_path"]
                ]

                with self.subTest(
                    component=component_id,
                    qupath_version=ref.qupath_version,
                ):
                    self.assertEqual(len(bundles), 1)
                    self.assertEqual(
                        bundles[0]["keys"],
                        fixture["expected_keys"],
                    )
                    self.assertEqual(
                        bundles[0]["external_flat_filename"],
                        Path(fixture["dist_bundle"]).name,
                    )
                    self.assertEqual(
                        ref.entry["evidence_commit"],
                        audit["upstream_commit"],
                    )
                    self.assertTrue((l10n_dir / fixture["dist_bundle"]).is_file())

    def test_lock_state_is_consistent_with_tsv_progress(self) -> None:
        unfinished_states = {"PENDING", "DRAFT", "BLOCKED"}

        for key, l10n_dir, refs, _fixture_path, _fixture in self.iter_cases():
            rows = load_tsv(l10n_dir / "strings.tsv")
            has_unfinished_rows = any(
                row["state"] in unfinished_states for row in rows
            )

            for ref in refs:
                entry = ref.entry
                with self.subTest(
                    component=key[0],
                    revision=key[1],
                    qupath_version=ref.qupath_version,
                ):
                    self.assertEqual(entry["localization_revision"], key[1])
                    self.assertNotEqual(
                        entry["translation_status"],
                        "NOT_STARTED",
                    )
                    self.assertNotEqual(
                        entry["validation_status"],
                        "NOT_APPLICABLE",
                    )

                    if entry["translation_status"] == "IN_PROGRESS":
                        self.assertEqual(
                            entry["validation_status"],
                            "NOT_VALIDATED",
                        )

                    if has_unfinished_rows:
                        self.assertEqual(
                            entry["translation_status"],
                            "IN_PROGRESS",
                        )
                        self.assertEqual(
                            entry["validation_status"],
                            "NOT_VALIDATED",
                        )


if __name__ == "__main__":
    unittest.main()
