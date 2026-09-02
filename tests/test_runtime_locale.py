"""
Guards for the runtime locale strategy.

The Spanish display locale is applied by a startup script rather than by JVM
options, because the bundled runtime makes every earlier mechanism impossible
(see versions/0.7.0/reports/pre-gui-locale-solution.md).  These tests pin the
properties that decision depends on, so a future edit cannot quietly break
number formatting or start touching global state.
"""
from __future__ import annotations

import json
import hashlib
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERSION_DIR = REPO / "versions" / "0.7.0"
RUNTIME_DIR = VERSION_DIR / "runtime"
STARTUP = RUNTIME_DIR / "qupath-es-startup.groovy"
FINGERPRINT = VERSION_DIR / "fingerprint.json"
DIST = VERSION_DIR / "dist" / "qupath-gui-strings_es.properties"

EXPECTED_DIST_SHA256 = (
    "E4A966C90D1CE1368DE9EA21DECC7D9DBB0180087B60D3724690AAD4C128FC19"
)


def sha256_upper(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def strip_comments(groovy: str) -> str:
    """Remove /* */ and // comments so assertions test code, not prose.

    The scripts document the very API calls they must never make, so a naive
    substring check would fail on the explanation rather than on the code.
    """
    without_block = re.sub(r"/\*.*?\*/", "", groovy, flags=re.S)
    return re.sub(r"//[^\n]*", "", without_block)


class StartupScriptTests(unittest.TestCase):
    """The startup script must change DISPLAY only, and be idempotent."""

    @classmethod
    def setUpClass(cls):
        cls.raw = STARTUP.read_text(encoding="utf-8")
        cls.text = strip_comments(cls.raw)

    def test_script_exists(self):
        self.assertTrue(STARTUP.is_file())

    def test_sets_display_locale(self):
        self.assertIn("defaultLocaleDisplayProperty", self.text)

    def test_never_assigns_the_default_locale(self):
        """`Locale.setDefault` or assigning defaultLocaleProperty would move
        the FORMAT category too, changing the decimal separator."""
        self.assertNotIn("Locale.setDefault", self.text)

        assignments = re.findall(
            r"defaultLocaleProperty\(\)\s*\.\s*set\s*\(", self.text
        )
        self.assertEqual(assignments, [], "must not assign the default locale")

    def test_never_assigns_the_format_locale(self):
        assignments = re.findall(
            r"defaultLocaleFormatProperty\(\)\s*\.\s*set\s*\(", self.text
        )
        self.assertEqual(assignments, [], "must not assign the FORMAT locale")

    def test_is_idempotent(self):
        """It must detect an already-Spanish display locale and do nothing."""
        self.assertIn("alreadySpanish", self.text)
        self.assertIn("if (!alreadySpanish)", self.text)

    def test_records_format_evidence(self):
        """Every launch must leave proof that formatting was not disturbed."""
        self.assertIn("formatSample", self.text)
        self.assertIn("formatUsesDot", self.text)

    def test_documents_why_it_exists(self):
        """The runtime defect is non-obvious; the file must explain itself."""
        self.assertIn("jdk.localedata", self.raw)

    def test_uses_language_tag_not_available_locales(self):
        """forLanguageTag works on a runtime without jdk.localedata;
        looking the locale up in getAvailableLocales() would not."""
        self.assertIn("Locale.forLanguageTag", self.text)
        self.assertNotIn("getAvailableLocales", self.text)


class NoGlobalStateTests(unittest.TestCase):
    """Nothing in the repository may configure machine-wide Java behaviour."""

    FORBIDDEN = (
        "setx",
        "[Environment]::SetEnvironmentVariable",
        "_JAVA_OPTIONS",
        "HKLM",
        "Set-ItemProperty",
    )

    KILL_COMMANDS = (
        "Stop-Process",
        "taskkill",
        "Restart-Computer",
        "Stop-Computer",
        "shutdown /",
    )

    def _executable_files(self):
        """Files that could actually run something.

        Reports and this test file legitimately name these tokens as prose or
        as test data, so they are excluded: the point is to catch a script that
        *does* it, not a document that *mentions* it.
        """
        for path in REPO.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "reports" in path.parts or "tests" in path.parts:
                continue
            if path.suffix.lower() not in {
                ".py", ".groovy", ".ps1", ".cmd", ".bat"
            }:
                continue
            yield path

    def _scan(self, tokens):
        offenders = []

        for path in self._executable_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            if path.suffix.lower() == ".groovy":
                text = strip_comments(text)

            for token in tokens:
                if token in text:
                    offenders.append(f"{path.relative_to(REPO)}: {token}")

        return offenders

    def test_no_persistent_environment_configuration(self):
        self.assertEqual(
            self._scan(self.FORBIDDEN), [], "global state configuration found"
        )

    def test_no_process_killing_commands(self):
        self.assertEqual(self._scan(self.KILL_COMMANDS), [])


class InstalledDistributionTests(unittest.TestCase):
    """The installation itself must remain untouched."""

    def setUp(self):
        self.fingerprint = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
        self.jar = Path(self.fingerprint["source"]["jar"])

        if not self.jar.is_file():
            self.skipTest("QuPath installation not present on this machine")

    def test_qupath_jar_matches_recorded_hash(self):
        self.assertEqual(
            sha256_upper(self.jar),
            self.fingerprint["source"]["jar_sha256"].upper(),
            "qupath-gui-fx jar has been modified",
        )


class DistBundleTests(unittest.TestCase):

    def test_dist_bundle_hash_is_pinned(self):
        self.assertTrue(DIST.is_file())
        self.assertEqual(sha256_upper(DIST), EXPECTED_DIST_SHA256)


class ProbeScriptTests(unittest.TestCase):
    """The diagnostic probes must stay read-only."""

    PROBES = [
        "diagnose-locale.groovy",
        "probe-locale-converter.groovy",
        "probe-prefs-node.groovy",
    ]

    def test_probes_exist(self):
        for name in self.PROBES:
            with self.subTest(probe=name):
                self.assertTrue((RUNTIME_DIR / name).is_file())

    def test_read_only_probes_do_not_write_preferences(self):
        for name in self.PROBES:
            text = (RUNTIME_DIR / name).read_text(encoding="utf-8")
            with self.subTest(probe=name):
                self.assertNotIn(".put(", text)
                self.assertNotIn("removeNode", text)
                self.assertNotIn("Property().set(", text)


if __name__ == "__main__":
    unittest.main()
