from __future__ import annotations

import csv
import fnmatch
import json
import sys
import unittest
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = ROOT / "components"
VERSIONS_DIR = ROOT / "versions"
TOOLS_DIR = ROOT / "tools"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import protected_identifiers  # noqa: E402
import translation_generator  # noqa: E402


REQUIRED_TSV_FIELDS = {"key", "en", "es"}
INVENTORY_DIR_NAME = "protected-identifiers"


def load_json(path: Path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    return json.loads(raw.decode("utf-8", errors="strict"))


def load_tsv(path: Path) -> list[dict[str, str]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    if b"\r" in raw:
        raise ValueError(f"{path} must use LF line endings")

    text = raw.decode("utf-8", errors="strict")
    reader = csv.DictReader(StringIO(text, newline=""), delimiter="\t")

    if reader.fieldnames is None or not REQUIRED_TSV_FIELDS <= set(
        reader.fieldnames
    ):
        raise ValueError(f"{path}: missing required TSV fields")

    return list(reader)


def discover_localization_revisions() -> dict[tuple[str, str], Path]:
    result: dict[tuple[str, str], Path] = {}

    for l10n_root in sorted(COMPONENTS_DIR.glob("*/l10n")):
        if not l10n_root.is_dir():
            continue
        component_id = l10n_root.parent.name
        for revision_dir in sorted(
            path for path in l10n_root.iterdir() if path.is_dir()
        ):
            result[(component_id, revision_dir.name)] = revision_dir

    return result


def discover_inventories():
    result: dict[tuple[str, str], tuple[Path, dict]] = {}

    for inventory_root in sorted(
        COMPONENTS_DIR.glob(f"*/{INVENTORY_DIR_NAME}")
    ):
        if not inventory_root.is_dir():
            continue

        for inventory_path in sorted(inventory_root.glob("*.json")):
            inventory = protected_identifiers.load_inventory(inventory_path)
            key = (
                inventory["component_id"],
                inventory["localization_revision"],
            )
            if key in result:
                raise ValueError(
                    f"duplicate protected-identifier inventory for {key}"
                )
            result[key] = (inventory_path, inventory)

    return result


def discover_lock_refs() -> dict[tuple[str, str], list[dict]]:
    result: dict[tuple[str, str], list[dict]] = {}

    for lock_path in sorted(VERSIONS_DIR.glob("*/components.lock.json")):
        lock = load_json(lock_path)
        for entry in lock["components"]:
            revision = entry["localization_revision"]
            if revision is None:
                continue
            result.setdefault(
                (entry["component_id"], revision), []
            ).append(entry)

    return result


class ProtectedIdentifierContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.localizations = discover_localization_revisions()
        cls.inventories = discover_inventories()
        cls.lock_refs = discover_lock_refs()

    def test_every_materialized_localization_has_exactly_one_inventory(self):
        self.assertTrue(self.localizations)
        self.assertEqual(
            set(self.localizations),
            set(self.inventories),
        )

    def test_inventory_matches_lock_evidence_and_component_policy(self):
        self.assertEqual(set(self.localizations), set(self.lock_refs))

        for key in sorted(self.inventories):
            component_id, revision = key
            inventory_path, inventory = self.inventories[key]
            manifest_path = COMPONENTS_DIR / component_id / "component.json"
            manifest = load_json(manifest_path)
            policy = manifest["audit_policy"]
            declared_categories = set(
                policy["protected_identifier_categories"]
            )

            with self.subTest(component=component_id, revision=revision):
                self.assertTrue(inventory_path.is_file())
                self.assertEqual(inventory["component_id"], component_id)
                self.assertEqual(
                    inventory["localization_revision"],
                    revision,
                )
                self.assertTrue(
                    {
                        rule["category"]
                        for rule in inventory["rules"]
                    }
                    <= declared_categories
                )

            pinned_evidence = protected_identifiers.evidence_commits(
                inventory
            )
            for ref in self.lock_refs[key]:
                with self.subTest(
                    component=component_id,
                    revision=revision,
                    evidence_commit=ref["evidence_commit"],
                ):
                    self.assertIn(
                        ref["evidence_commit"],
                        pinned_evidence,
                    )
                    self.assertTrue(
                        (
                            COMPONENTS_DIR
                            / component_id
                            / "audits"
                            / f"{ref['evidence_commit']}.json"
                        ).is_file()
                    )

            relevant_paths = policy["relevant_paths"]
            for evidence_path in protected_identifiers.evidence_paths(
                inventory
            ):
                with self.subTest(
                    component=component_id,
                    evidence_path=evidence_path,
                ):
                    self.assertTrue(
                        any(
                            fnmatch.fnmatch(
                                evidence_path,
                                pattern,
                            )
                            for pattern in relevant_paths
                        ),
                        msg=(
                            f"{evidence_path!r} is not covered by "
                            f"{relevant_paths!r}"
                        ),
                    )

    def test_current_localized_values_preserve_protected_identifiers(self):
        for key in sorted(self.inventories):
            component_id, revision = key
            _inventory_path, inventory = self.inventories[key]
            rows = load_tsv(
                self.localizations[key] / "strings.tsv"
            )
            applied = 0

            for row in rows:
                source_value = translation_generator.decode_work_text(
                    row["en"]
                )
                target_value = translation_generator.decode_work_text(
                    row["es"]
                )

                row_errors = protected_identifiers.preservation_errors(
                    source_value,
                    target_value,
                    inventory["rules"],
                )

                applied += sum(
                    protected_identifiers.rule_match_count(
                        source_value,
                        rule,
                    )
                    > 0
                    for rule in inventory["rules"]
                )

                with self.subTest(
                    component=component_id,
                    revision=revision,
                    key=row["key"],
                ):
                    self.assertEqual([], row_errors)

            with self.subTest(component=component_id, revision=revision):
                self.assertGreater(
                    applied,
                    0,
                    "inventory must actively protect at least one source value",
                )


class ProtectedIdentifierMatcherTests(unittest.TestCase):
    def test_measurement_name_prefix_change_fails(self):
        rules = [
            {
                "category": "MEASUREMENT_NAME",
                "value": "Logit: ",
                "match": "PREFIX",
                "evidence_paths": ["src/main/java/Example.java"],
            }
        ]

        errors = protected_identifiers.preservation_errors(
            "Logit: Tumor",
            "Logito: Tumor",
            rules,
        )

        self.assertEqual(1, len(errors))
        self.assertEqual("MEASUREMENT_NAME", errors[0]["category"])

    def test_measurement_name_prefix_preserved_passes(self):
        rules = [
            {
                "category": "MEASUREMENT_NAME",
                "value": "Embedding ",
                "match": "PREFIX",
                "evidence_paths": ["src/main/java/Example.java"],
            }
        ]

        self.assertEqual(
            [],
            protected_identifiers.preservation_errors(
                "Embedding 3",
                "Embedding 3",
                rules,
            ),
        )

    def test_contains_rule_preserves_exact_occurrence_count(self):
        rules = [
            {
                "category": "MODEL_IDENTIFIER",
                "value": "InstanSeg",
                "match": "CONTAINS",
                "evidence_paths": ["src/main/resources/strings.properties"],
            }
        ]

        self.assertEqual(
            [],
            protected_identifiers.preservation_errors(
                "Run InstanSeg with InstanSeg defaults",
                "Ejecutar InstanSeg con valores de InstanSeg",
                rules,
            ),
        )
        self.assertEqual(
            1,
            len(
                protected_identifiers.preservation_errors(
                    "Run InstanSeg with InstanSeg defaults",
                    "Ejecutar InstanSeg con valores predeterminados",
                    rules,
                )
            ),
        )

    def test_unknown_match_mode_is_rejected_fail_closed(self):
        inventory = {
            "schema_version": 1,
            "component_id": "example",
            "localization_revision": "v1",
            "evidence": [
                {
                    "commit": "a" * 40,
                    "files": {
                        "src/main/java/Example.java": "b" * 40
                    },
                }
            ],
            "inventory_status": "PARTIAL",
            "rules": [
                {
                    "category": "MEASUREMENT_NAME",
                    "value": "Area",
                    "match": "REGEX",
                    "evidence_paths": ["src/main/java/Example.java"],
                }
            ],
        }

        with self.assertRaises(
            protected_identifiers.ProtectedIdentifierInventoryError
        ):
            protected_identifiers.validate_inventory(inventory)


if __name__ == "__main__":
    unittest.main()
