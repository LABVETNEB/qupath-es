"""
Repository-level integrity guards.

These protect invariants that live in the repository rather than in a single
module, and that a fresh clone must also satisfy.

The fingerprint check in particular is a regression guard: the canonical
bundle was once committed LF-normalised, so a clone produced a file whose
SHA-256 did not match the recorded fingerprint even though the working copy
on the original machine was fine.  `.gitattributes` now marks both the base
and dist bundles `-text`; this test fails loudly if that ever regresses.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from tools.properties_audit import parse_properties

REPO = Path(__file__).resolve().parents[1]
VERSION_DIR = REPO / "versions" / "0.7.0"
FINGERPRINT = VERSION_DIR / "fingerprint.json"
BASE = VERSION_DIR / "base" / "qupath-gui-strings.properties"
DIST = VERSION_DIR / "dist" / "qupath-gui-strings_es.properties"


def sha256_upper(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class FingerprintConsistencyTests(unittest.TestCase):
    """The recorded fingerprint must describe the files actually on disk."""

    def setUp(self):
        self.fingerprint = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
        self.artifacts = self.fingerprint["artifacts"]

    def test_base_bundle_matches_recorded_sha256(self):
        recorded = self.artifacts["root_bundle"]["sha256"]

        self.assertEqual(
            sha256_upper(BASE),
            recorded,
            "Canonical bundle bytes differ from the recorded fingerprint. "
            "The usual cause is Git line-ending normalisation; "
            "versions/*/base/* must stay '-text' in .gitattributes.",
        )

    def test_base_bundle_matches_recorded_size(self):
        self.assertEqual(
            BASE.stat().st_size,
            self.artifacts["root_bundle"]["bytes"],
        )

    def test_every_recorded_artifact_exists_and_matches(self):
        for name, artifact in self.artifacts.items():
            path = VERSION_DIR / artifact["path"]

            with self.subTest(artifact=name):
                self.assertTrue(path.is_file(), f"missing artifact: {path}")
                self.assertEqual(sha256_upper(path), artifact["sha256"])
                self.assertEqual(path.stat().st_size, artifact["bytes"])


class ComponentBundleAttributeTests(unittest.TestCase):
    """Generated extension bundles must retain their committed bytes on checkout."""

    def test_component_dist_bundles_are_marked_binary_in_git_attributes(self):
        bundles = sorted(REPO.glob("components/*/l10n/*/dist/*.properties"))
        self.assertTrue(bundles, "expected at least one component dist bundle")

        for path in bundles:
            relative = path.relative_to(REPO).as_posix()
            with self.subTest(path=relative):
                result = subprocess.run(
                    ["git", "check-attr", "text", "--", relative],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertTrue(
                    result.stdout.rstrip().endswith(": text: unset"),
                    f"{relative} must be '-text' in .gitattributes; "
                    f"git reported {result.stdout.strip()!r}",
                )


class DistributedBundleTests(unittest.TestCase):
    """The generated bundle is what gets installed; guard its shape."""

    def setUp(self):
        if not DIST.is_file():
            self.skipTest("dist bundle not generated yet")

        self.base_raw = BASE.read_bytes()
        self.dist_raw = DIST.read_bytes()

    def test_no_byte_order_mark(self):
        self.assertFalse(self.dist_raw.startswith(b"\xef\xbb\xbf"))

    def test_strict_utf8(self):
        self.dist_raw.decode("utf-8", errors="strict")

    def test_line_endings_match_canonical_bundle(self):
        base_crlf = self.base_raw.count(b"\r\n")
        dist_crlf = self.dist_raw.count(b"\r\n")

        if base_crlf:
            self.assertEqual(
                dist_crlf,
                self.dist_raw.count(b"\n"),
                "canonical bundle uses CRLF, so the generated bundle must too",
            )
        else:
            self.assertEqual(dist_crlf, 0)

    def test_keys_and_order_match_canonical_bundle(self):
        base_keys = [
            e.key for e in parse_properties(self.base_raw.decode("utf-8"))
        ]
        dist_keys = [
            e.key for e in parse_properties(self.dist_raw.decode("utf-8"))
        ]

        self.assertEqual(dist_keys, base_keys)

    def test_no_empty_values(self):
        empty = [
            e.key
            for e in parse_properties(self.dist_raw.decode("utf-8"))
            if not e.value.strip()
        ]

        self.assertEqual(empty, [])


class TranslationTableTests(unittest.TestCase):
    """The translation table must stay aligned with the canonical bundle."""

    def test_translation_table_covers_every_key_exactly(self):
        from tools.es_translations import KEEP_EN, TRANSLATIONS

        base_keys = [
            e.key for e in parse_properties(BASE.read_text(encoding="utf-8"))
        ]

        self.assertEqual(
            sorted(TRANSLATIONS), sorted(base_keys),
            "es_translations.TRANSLATIONS must contain exactly the bundle keys",
        )
        self.assertTrue(
            set(KEEP_EN).issubset(set(base_keys)),
            "KEEP_EN references keys that are not in the bundle",
        )

    def test_keep_en_entries_are_identical_to_english(self):
        from tools.es_translations import KEEP_EN, TRANSLATIONS

        entries = {
            e.key: e.value
            for e in parse_properties(BASE.read_text(encoding="utf-8"))
        }

        for key in sorted(KEEP_EN):
            with self.subTest(key=key):
                spanish = TRANSLATIONS[key].replace("\\n", "\n")
                self.assertEqual(spanish, entries[key])


if __name__ == "__main__":
    unittest.main()
