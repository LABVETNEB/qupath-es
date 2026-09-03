from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
SPEC_PATH = "versions/0.7.0/release-es.json"
SPEC = ROOT / SPEC_PATH
SPEC_SCHEMA = ROOT / "schemas" / "release-spec.schema.json"
MANIFEST_SCHEMA = ROOT / "schemas" / "release-manifest.schema.json"
LOCALIZATION_LOCK = ROOT / "versions" / "0.7.0" / "localizations.lock.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import build_release  # noqa: E402
import schema_validate  # noqa: E402


FIXED_TAG = "test-release-0.7.0-es"

REQUIRED_OPERATIONAL_PAYLOAD = {
    "runtime/update-qupath-es.ps1",
    "runtime/probe-locale-capability.groovy",
    "tools/properties_audit.py",
    "tools/qupath_version_migrator.py",
    "tools/translation_generator.py",
    "tools/translation_validator.py",
    "versions/supported-versions.json",
    "versions/0.7.0/base/MANIFEST.MF",
    "versions/0.7.0/base/qupath-gui-strings.properties",
    "versions/0.7.0/base/qupath-gui-strings_en.properties",
    "versions/0.7.0/dist/qupath-gui-strings_es.properties",
    "versions/0.7.0/fingerprint.json",
    "versions/0.7.0/target-version.json",
    "versions/0.7.0/work/translation.tsv",
    "versions/0.7.0/runtime/qupath-es-startup.groovy",
    "versions/0.7.0/runtime/setup-es-preferences.groovy",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_upper(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="strict").strip()


class ReleaseEngineeringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = load_json(SPEC)
        cls.spec_schema = load_json(SPEC_SCHEMA)
        cls.manifest_schema = load_json(MANIFEST_SCHEMA)
        cls.localization_lock = load_json(LOCALIZATION_LOCK)
        cls.head = git_text("rev-parse", "HEAD")
        cls.source = build_release.GitSource(ROOT, cls.head)

    def test_release_contract_json_is_strict_utf8_without_bom_and_uses_lf(self):
        for path in (SPEC, SPEC_SCHEMA, MANIFEST_SCHEMA):
            with self.subTest(path=path):
                raw = path.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                raw.decode("utf-8", errors="strict")
                self.assertNotIn(b"\r", raw)

    def test_release_spec_schema_is_executable(self):
        schema_validate.validate(self.spec, self.spec_schema)
        self.assertFalse(self.spec_schema["additionalProperties"])
        entry = self.spec_schema["$defs"]["payloadEntry"]
        self.assertFalse(entry["additionalProperties"])

    def test_release_manifest_schema_is_closed(self):
        self.assertFalse(self.manifest_schema["additionalProperties"])
        self.assertFalse(
            self.manifest_schema["$defs"]["payloadFile"]["additionalProperties"]
        )
        self.assertFalse(
            self.manifest_schema["$defs"]["outputFile"]["additionalProperties"]
        )

    def test_release_payload_paths_are_unique_safe_and_versioned(self):
        paths = [entry["path"] for entry in self.spec["payload"]]
        self.assertEqual(len(paths), len(set(paths)))

        for text in paths:
            with self.subTest(path=text):
                path = PurePosixPath(text)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertNotIn("\\", text)
                self.assertEqual(str(path), text)
                raw = self.source.read_bytes(text)
                self.assertIsInstance(raw, bytes)

    def test_release_payload_supports_the_current_updater(self):
        paths = {entry["path"] for entry in self.spec["payload"]}
        self.assertTrue(REQUIRED_OPERATIONAL_PAYLOAD <= paths)

    def test_release_spec_covers_exactly_distributed_localizations(self):
        distributed = {
            entry["component_id"]: entry
            for entry in self.localization_lock["localizations"]
            if (
                entry["locale"] == self.spec["locale"]
                and entry["distribution_status"] == "DISTRIBUTED"
            )
        }
        bundle_entries = {
            entry["component_id"]: entry
            for entry in self.spec["payload"]
            if entry["role"] == "LOCALIZATION_BUNDLE"
        }

        self.assertEqual(set(bundle_entries), set(distributed))
        self.assertTrue(distributed)

        for component_id, state in distributed.items():
            with self.subTest(component=component_id):
                item = bundle_entries[component_id]
                self.assertEqual(state["translation_status"], "TRANSLATED")
                self.assertEqual(state["validation_status"], "VALIDATED")
                self.assertEqual(item["path"], state["dist_bundle"])
                raw = self.source.read_bytes(item["path"])
                self.assertEqual(sha256_upper(raw), state["dist_sha256"])

    def test_build_is_byte_reproducible_and_self_verifying(self):
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = build_release.build_release(
                ROOT,
                SPEC_PATH,
                Path(first_dir),
                release_tag=FIXED_TAG,
                source_commit=self.head,
            )
            second = build_release.build_release(
                ROOT,
                SPEC_PATH,
                Path(second_dir),
                release_tag=FIXED_TAG,
                source_commit=self.head,
            )

            self.assertEqual(set(first), {"artifact", "manifest", "sbom", "checksums"})
            self.assertEqual(set(first), set(second))

            for name in first:
                with self.subTest(output=name):
                    self.assertEqual(
                        first[name].read_bytes(),
                        second[name].read_bytes(),
                    )

            manifest = load_json(first["manifest"])
            schema_validate.validate(manifest, self.manifest_schema)
            self.assertEqual(manifest["source_commit"], self.head)
            self.assertEqual(
                manifest["source_date_epoch"],
                self.source.commit_epoch(),
            )
            self.assertEqual(manifest["release_tag"], FIXED_TAG)
            self.assertEqual(manifest["qupath_version"], self.spec["qupath_version"])
            self.assertEqual(manifest["locale"], self.spec["locale"])

            artifact_raw = first["artifact"].read_bytes()
            sbom_raw = first["sbom"].read_bytes()
            self.assertEqual(
                manifest["artifact"]["sha256"],
                sha256_upper(artifact_raw),
            )
            self.assertEqual(
                manifest["artifact"]["bytes"],
                len(artifact_raw),
            )
            self.assertEqual(
                manifest["sbom"]["sha256"],
                sha256_upper(sbom_raw),
            )
            self.assertEqual(
                manifest["sbom"]["bytes"],
                len(sbom_raw),
            )

            payload_by_archive_path = {
                entry["archive_path"]: entry
                for entry in manifest["payload"]
            }
            expected_archive_paths = sorted(payload_by_archive_path)

            with zipfile.ZipFile(first["artifact"], "r") as archive:
                self.assertEqual(archive.namelist(), expected_archive_paths)
                for info in archive.infolist():
                    with self.subTest(archive_path=info.filename):
                        self.assertEqual(
                            info.date_time,
                            build_release.FIXED_ZIP_TIMESTAMP,
                        )
                        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                        self.assertEqual(info.create_system, 3)
                        self.assertEqual((info.external_attr >> 16) & 0o777, 0o644)

                        record = payload_by_archive_path[info.filename]
                        source_raw = self.source.read_bytes(record["source_path"])
                        self.assertEqual(archive.read(info.filename), source_raw)
                        self.assertEqual(record["sha256"], sha256_upper(source_raw))
                        self.assertEqual(record["bytes"], len(source_raw))

            sbom = json.loads(sbom_raw.decode("utf-8"))
            self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
            self.assertEqual(sbom["dataLicense"], "CC0-1.0")
            self.assertEqual(len(sbom["packages"]), 1)
            self.assertEqual(
                sbom["packages"][0]["checksums"][0]["checksumValue"],
                manifest["artifact"]["sha256"],
            )
            self.assertEqual(len(sbom["files"]), len(manifest["payload"]))

            sbom_checksums = {
                file_entry["fileName"][2:]: file_entry["checksums"][0]["checksumValue"]
                for file_entry in sbom["files"]
            }
            self.assertEqual(
                sbom_checksums,
                {
                    entry["archive_path"]: entry["sha256"]
                    for entry in manifest["payload"]
                },
            )

            checksum_lines = first["checksums"].read_text(
                encoding="ascii"
            ).splitlines()
            checksum_map = {
                filename: digest
                for digest, filename in (
                    line.split("  ", 1)
                    for line in checksum_lines
                )
            }
            self.assertEqual(
                checksum_map[first["artifact"].name],
                sha256_upper(first["artifact"].read_bytes()),
            )
            self.assertEqual(
                checksum_map[first["manifest"].name],
                sha256_upper(first["manifest"].read_bytes()),
            )
            self.assertEqual(
                checksum_map[first["sbom"].name],
                sha256_upper(first["sbom"].read_bytes()),
            )

    def test_builder_rejects_path_traversal(self):
        bad = copy.deepcopy(self.spec)
        bad["payload"][0]["path"] = "../README.md"

        with self.assertRaises(build_release.ReleaseError):
            build_release.validate_release_spec(self.source, bad)

    def test_builder_rejects_unsupported_localization_in_release(self):
        bad = copy.deepcopy(self.spec)
        bad["payload"].append(
            {
                "path": (
                    "components/instanseg/l10n/v0.1.7/"
                    "dist/strings_es.properties"
                ),
                "role": "LOCALIZATION_BUNDLE",
                "component_id": "instanseg",
            }
        )

        with self.assertRaises(build_release.ReleaseError):
            build_release.validate_release_spec(self.source, bad)


if __name__ == "__main__":
    unittest.main()
