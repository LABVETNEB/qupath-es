"""
Tests for the version-aware migration engine.

The migration policy is the safety-critical part of this repository: it decides
which Spanish translations may be carried into a new QuPath version without a
human looking at them.  Every case of that policy has a test here, built on
synthetic bundles so no QuPath installation is needed.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.qupath_version_migrator import (
    MigrationError,
    capture_bundle,
    classify_entry,
    detect_installations,
    inspect_installation,
    migrate,
    placeholder_signature,
    status,
    structural_signature,
)
from tools.translation_generator import TSV_FIELDS

REPO = Path(__file__).resolve().parents[1]


def write_bundle(path: Path, entries: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{k} = {v}\n" for k, v in entries)
    path.write_text(body, encoding="utf-8", newline="\n")


def write_tsv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=TSV_FIELDS, delimiter="\t",
            lineterminator="\n", quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)


def row(key, en, es, state="REVIEWED", issues="", notes=""):
    return {
        "key": key, "en": en, "es": es, "state": state, "batch": "TEST",
        "reviewer": "tester", "rev_date": "2026-01-01", "qupath_ver": "0.7.0",
        "issues": issues, "notes": notes,
    }


def read_tsv(path: Path) -> dict[str, dict]:
    text = path.read_text(encoding="utf-8")
    return {
        r["key"]: r
        for r in csv.DictReader(io.StringIO(text), delimiter="\t")
    }


class SignatureTests(unittest.TestCase):

    def test_messageformat_reordering_keeps_signature(self):
        self.assertEqual(
            placeholder_signature("A {0} B {1}"),
            placeholder_signature("B {1} A {0}"),
        )

    def test_messageformat_index_change_alters_signature(self):
        self.assertNotEqual(
            placeholder_signature("Value {0}"),
            placeholder_signature("Value {1}"),
        )

    def test_printf_order_is_part_of_signature(self):
        self.assertNotEqual(
            placeholder_signature("%s then %d"),
            placeholder_signature("%d then %s"),
        )

    def test_structural_signature_tracks_newlines_and_braces(self):
        self.assertNotEqual(
            structural_signature("one\ntwo"),
            structural_signature("one two"),
        )
        self.assertNotEqual(
            structural_signature("{{a}}"),
            structural_signature("{a}"),
        )


class ClassificationTests(unittest.TestCase):
    """Cases A-G of the migration policy."""

    def test_case_a_unchanged_english_is_reused(self):
        old = row("k", "Hello", "Hola")
        d = classify_entry(old, "Hello", "Hello", "k")

        self.assertEqual(d["case"], "A_REUSE")
        self.assertEqual(d["state"], "REVIEWED")
        self.assertEqual(d["es"], "Hola")

    def test_case_a_unfinished_stays_unfinished(self):
        old = row("k", "Hello", "Hola", state="DRAFT")
        d = classify_entry(old, "Hello", "Hello", "k")

        self.assertEqual(d["case"], "A_REUSE_UNFINISHED")
        self.assertEqual(d["state"], "DRAFT")

    def test_case_b_changed_english_is_never_auto_approved(self):
        old = row("k", "Open file", "Abrir archivo")
        d = classify_entry(old, "Open file", "Open image file", "k")

        self.assertEqual(d["case"], "B_SOURCE_CHANGED")
        self.assertEqual(d["state"], "DRAFT")
        self.assertIn("SOURCE_CHANGED", d["issues"])
        # Old translation is carried as a reference, not as an answer.
        self.assertEqual(d["es"], "Abrir archivo")

    def test_case_c_new_key_is_pending(self):
        d = classify_entry(None, None, "Brand new label", "k")

        self.assertEqual(d["case"], "C_NEW")
        self.assertEqual(d["state"], "PENDING")

    def test_case_c_known_hardcoded_string_gets_a_suggestion(self):
        d = classify_entry(None, None, "Image list", "Panes.ProjectBrowser.imageList")

        self.assertEqual(d["state"], "PENDING", "a suggestion is not an approval")
        self.assertEqual(d["suggestion"], "Lista de imágenes")
        self.assertIn("Suggestion", d["notes"])

    def test_case_e_keep_en_is_preserved_when_english_is_unchanged(self):
        old = row("k", "TMA", "TMA", state="KEEP_EN")
        d = classify_entry(old, "TMA", "TMA", "k")

        self.assertEqual(d["case"], "E_KEEP_EN")
        self.assertEqual(d["state"], "KEEP_EN")

    def test_case_e_keep_en_is_rechecked_when_english_changes(self):
        old = row("k", "TMA", "TMA", state="KEEP_EN")
        d = classify_entry(old, "TMA", "TMA grid", "k")

        self.assertEqual(d["case"], "E_KEEP_EN_SOURCE_CHANGED")
        self.assertNotEqual(d["state"], "KEEP_EN")
        self.assertIn("KEEP_EN_NEEDS_REVIEW", d["issues"])

    def test_case_f_placeholder_change_is_blocked(self):
        old = row("k", "Loaded {0}", "Cargado {0}")
        d = classify_entry(old, "Loaded {0}", "Loaded {0} of {1}", "k")

        self.assertEqual(d["case"], "F_PLACEHOLDER_CHANGED")
        self.assertEqual(d["state"], "BLOCKED")
        self.assertIn("PLACEHOLDER_SIGNATURE_CHANGED", d["issues"])

    def test_case_f_printf_change_is_blocked(self):
        old = row("k", "Parsed %s", "Analizado %s")
        d = classify_entry(old, "Parsed %s", "Parsed %d", "k")

        self.assertEqual(d["state"], "BLOCKED")

    def test_case_g_structure_change_is_blocked(self):
        old = row("k", "One\\nTwo", "Uno\\nDos")
        d = classify_entry(old, "One\nTwo", "One Two", "k")

        self.assertEqual(d["case"], "G_STRUCTURE_CHANGED")
        self.assertEqual(d["state"], "BLOCKED")


class MigrationWorkspaceTests(unittest.TestCase):
    """End-to-end migration over a synthetic pair of versions."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        old = self.tmp / "versions" / "1.0.0"
        new = self.tmp / "versions" / "2.0.0"

        write_bundle(old / "base" / "qupath-gui-strings.properties", [
            ("same", "Hello"),
            ("changed", "Open file"),
            ("removed", "Old thing"),
            ("keepen", "TMA"),
            ("ph", "Loaded {0}"),
        ])
        write_tsv(old / "work" / "translation.tsv", [
            row("same", "Hello", "Hola"),
            row("changed", "Open file", "Abrir archivo"),
            row("removed", "Old thing", "Cosa antigua"),
            row("keepen", "TMA", "TMA", state="KEEP_EN"),
            row("ph", "Loaded {0}", "Cargado {0}"),
        ])

        write_bundle(new / "base" / "qupath-gui-strings.properties", [
            ("same", "Hello"),
            ("changed", "Open image file"),
            ("keepen", "TMA"),
            ("ph", "Loaded {0} of {1}"),
            ("brandnew", "A brand new label"),
        ])

        self.old_dir, self.new_dir = old, new

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_migration_produces_expected_states(self):
        report = migrate(self.tmp, "1.0.0", "2.0.0")
        rows = read_tsv(self.new_dir / "work" / "translation.tsv")

        self.assertEqual(rows["same"]["state"], "REVIEWED")
        self.assertEqual(rows["changed"]["state"], "DRAFT")
        self.assertEqual(rows["keepen"]["state"], "KEEP_EN")
        self.assertEqual(rows["ph"]["state"], "BLOCKED")
        self.assertEqual(rows["brandnew"]["state"], "PENDING")

        self.assertEqual(report["counts"]["auto_reused"], 2)
        self.assertEqual(report["counts"]["new_keys"], 1)
        self.assertEqual(report["counts"]["removed_keys"], 1)
        self.assertEqual(report["counts"]["placeholder_changed"], 1)

    def test_key_order_follows_the_new_bundle(self):
        migrate(self.tmp, "1.0.0", "2.0.0")
        text = (self.new_dir / "work" / "translation.tsv").read_text(encoding="utf-8")
        keys = [r["key"] for r in csv.DictReader(io.StringIO(text), delimiter="\t")]

        self.assertEqual(keys, ["same", "changed", "keepen", "ph", "brandnew"])

    def test_removed_key_is_archived_not_carried_over(self):
        migrate(self.tmp, "1.0.0", "2.0.0")
        rows = read_tsv(self.new_dir / "work" / "translation.tsv")

        self.assertNotIn("removed", rows)

        retired = read_tsv(self.new_dir / "work" / "retired.tsv")
        self.assertIn("removed", retired)

    def test_reports_are_written(self):
        migrate(self.tmp, "1.0.0", "2.0.0")

        js = self.new_dir / "reports" / "migration-from-1.0.0.json"
        md = self.new_dir / "reports" / "migration-from-1.0.0.md"

        self.assertTrue(js.is_file())
        self.assertTrue(md.is_file())

        data = json.loads(js.read_text(encoding="utf-8"))
        self.assertEqual(data["old_version"], "1.0.0")
        self.assertEqual(data["new_version"], "2.0.0")
        self.assertIn("safe_migration_percent", data)

    def test_will_not_silently_overwrite_an_existing_workspace(self):
        migrate(self.tmp, "1.0.0", "2.0.0")

        with self.assertRaises(MigrationError):
            migrate(self.tmp, "1.0.0", "2.0.0")

        # ... unless explicitly forced.
        migrate(self.tmp, "1.0.0", "2.0.0", force=True)

    def test_missing_inputs_raise_rather_than_guess(self):
        with self.assertRaises(MigrationError):
            migrate(self.tmp, "9.9.9", "2.0.0")


class StatusTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.v = self.tmp / "versions" / "1.0.0"
        write_bundle(self.v / "base" / "qupath-gui-strings.properties", [
            ("a", "Hello"), ("b", "World"),
        ])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_not_releasable_without_a_workspace(self):
        result = status(self.tmp, "1.0.0")
        self.assertFalse(result["releasable"])
        self.assertIn("no translation workspace", result["blockers"])

    def test_not_releasable_with_pending_entries(self):
        write_tsv(self.v / "work" / "translation.tsv", [
            row("a", "Hello", "Hola"),
            row("b", "World", "World", state="PENDING"),
        ])
        write_bundle(self.v / "dist" / "qupath-gui-strings_es.properties", [
            ("a", "Hola"), ("b", "World"),
        ])

        result = status(self.tmp, "1.0.0")

        self.assertFalse(result["releasable"])
        self.assertTrue(any("PENDING" in b for b in result["blockers"]))

    def test_releasable_when_everything_is_reviewed_and_valid(self):
        write_tsv(self.v / "work" / "translation.tsv", [
            row("a", "Hello", "Hola"),
            row("b", "World", "Mundo"),
        ])
        write_bundle(self.v / "dist" / "qupath-gui-strings_es.properties", [
            ("a", "Hola"), ("b", "Mundo"),
        ])

        result = status(self.tmp, "1.0.0")

        self.assertTrue(result["releasable"], result["blockers"])
        self.assertTrue(result["validation"]["ok"])

    def test_not_releasable_when_the_bundle_fails_validation(self):
        write_tsv(self.v / "work" / "translation.tsv", [
            row("a", "Hello", "Hola"),
            row("b", "World", "Mundo"),
        ])
        # Missing key 'b' - the validator must catch it.
        write_bundle(self.v / "dist" / "qupath-gui-strings_es.properties", [
            ("a", "Hola"),
        ])

        result = status(self.tmp, "1.0.0")

        self.assertFalse(result["releasable"])
        self.assertFalse(result["validation"]["ok"])


class InstallationDetectionTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_install(self, dir_name, jar_version, manifest_version,
                      with_bundle=True):
        root = self.tmp / dir_name
        app = root / "app"
        app.mkdir(parents=True)

        jar = app / f"qupath-gui-fx-{jar_version}.jar"
        manifest = "Manifest-Version: 1.0\n"
        if manifest_version:
            manifest += f"Implementation-Version: {manifest_version}\n"
            manifest += "QuPath-build-time: 2026-01-01 00:00\n"

        with zipfile.ZipFile(jar, "w") as zf:
            zf.writestr("META-INF/MANIFEST.MF", manifest)
            if with_bundle:
                zf.writestr(
                    "qupath/lib/gui/localization/qupath-gui-strings.properties",
                    "a = Hello\nb = World\n",
                )
        return root

    def test_version_comes_from_the_manifest_not_the_folder_name(self):
        root = self._make_install("QuPath-9.9.9", "0.8.0", "0.8.0")
        info = inspect_installation(root)

        self.assertTrue(info["valid"])
        self.assertEqual(info["version"], "0.8.0")
        self.assertEqual(info["version_sources"]["directory_name"], "9.9.9")

    def test_disagreement_between_sources_is_reported(self):
        root = self._make_install("QuPath-0.8.0", "0.8.0", "0.8.1")
        info = inspect_installation(root)

        self.assertTrue(any("jar name says" in p for p in info["problems"]))

    def test_missing_bundle_makes_the_installation_unusable(self):
        root = self._make_install("QuPath-0.8.0", "0.8.0", "0.8.0",
                                  with_bundle=False)
        info = inspect_installation(root)

        self.assertFalse(info["valid"])

    def test_multiple_installations_are_all_returned(self):
        self._make_install("QuPath-0.7.0", "0.7.0", "0.7.0")
        self._make_install("QuPath-0.8.0", "0.8.0", "0.8.0")

        found = [i for i in detect_installations([self.tmp]) if i["valid"]]

        self.assertEqual(len(found), 2)
        self.assertEqual(
            sorted(i["version"] for i in found), ["0.7.0", "0.8.0"]
        )

    def test_capture_extracts_the_bundle_and_writes_a_fingerprint(self):
        root = self._make_install("QuPath-0.8.0", "0.8.0", "0.8.0")
        repo = self.tmp / "repo"
        info = inspect_installation(root)

        fingerprint = capture_bundle(info, repo)

        base = repo / "versions" / "0.8.0" / "base" / "qupath-gui-strings.properties"
        self.assertTrue(base.is_file())
        self.assertEqual(base.read_bytes(), b"a = Hello\nb = World\n")
        self.assertEqual(
            fingerprint["artifacts"]["root_bundle"]["parsed_entries"], 2
        )
        self.assertTrue(
            (repo / "versions" / "0.8.0" / "fingerprint.json").is_file()
        )

    def test_capture_refuses_to_overwrite_a_captured_bundle(self):
        root = self._make_install("QuPath-0.8.0", "0.8.0", "0.8.0")
        repo = self.tmp / "repo"
        info = inspect_installation(root)

        capture_bundle(info, repo)

        with self.assertRaises(MigrationError):
            capture_bundle(info, repo)

        capture_bundle(info, repo, force=True)

    def test_corrupt_jar_is_reported_not_crashed_on(self):
        root = self.tmp / "QuPath-broken"
        app = root / "app"
        app.mkdir(parents=True)
        (app / "qupath-gui-fx-0.8.0.jar").write_bytes(b"not a zip")

        info = inspect_installation(root)
        self.assertFalse(info["valid"])


class UpdaterScriptTests(unittest.TestCase):
    """Static guards on the PowerShell entry point."""

    @classmethod
    def setUpClass(cls):
        cls.script = (REPO / "runtime" / "update-qupath-es.ps1").read_text(
            encoding="utf-8")

    def test_script_exists(self):
        self.assertTrue((REPO / "runtime" / "update-qupath-es.ps1").is_file())

    def test_dry_run_is_the_default(self):
        self.assertIn("[switch]$Apply", self.script)
        self.assertIn("No files were installed.", self.script)

    def test_refuses_to_write_while_qupath_is_running(self):
        self.assertIn("Test-QuPathRunning", self.script)
        self.assertIn("Close QuPath manually", self.script)

    def test_never_kills_processes_or_restarts_the_machine(self):
        for forbidden in ("Stop-Process", "taskkill", "Restart-Computer",
                          "Stop-Computer", "shutdown"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, self.script)

    def test_backs_up_before_replacing(self):
        self.assertIn("New-Backup", self.script)
        self.assertIn("Hash mismatch after copy", self.script)

    def test_apply_requires_a_releasable_version(self):
        self.assertIn("Refusing to install an unvalidated translation",
                      self.script)

    def test_locale_mode_is_measured_not_assumed(self):
        self.assertIn("Invoke-CapabilityProbe", self.script)
        self.assertIn("LOCALE_MODE_NATIVE", self.script)
        self.assertIn("LOCALE_MODE_STARTUP_FALLBACK", self.script)

    def test_capability_probe_exists_and_is_read_only(self):
        probe = REPO / "runtime" / "probe-locale-capability.groovy"
        self.assertTrue(probe.is_file())

        text = probe.read_text(encoding="utf-8")
        self.assertNotIn("Property().set(", text)
        self.assertNotIn(".put(", text)

    def test_no_powershell_7_only_syntax(self):
        """The script must run on Windows PowerShell 5.1, which most machines
        have out of the box - not just on PowerShell 7."""
        for token in ("??", "?.", "-Parallel", "&&", "||"):
            with self.subTest(token=token):
                self.assertNotIn(token, self.script)

    def test_collections_are_wrapped_before_counting(self):
        """Regression: under StrictMode in Windows PowerShell 5.1 a pipeline
        that yields a single object is a scalar, and a scalar has no .Count.
        Every .Count must therefore be taken from an @()-wrapped value."""
        import re

        for match in re.finditer(r"(\$[A-Za-z_][\w.]*)\.Count", self.script):
            expression = match.group(1)
            # For "$result.problems" it is the member that must be an array,
            # so accept an assignment to the whole expression or to its last
            # component (which covers hashtable literals).
            member = expression.rsplit(".", 1)[-1]

            patterns = [
                re.escape(expression) + r"\s*=\s*@[({]",
                r"\b" + re.escape(member) + r"\s*=\s*@[({]",
            ]

            with self.subTest(expression=expression):
                self.assertTrue(
                    any(re.search(p, self.script) for p in patterns),
                    f"{expression}.Count is read but neither {expression} nor "
                    f"'{member}' is assigned from @(...) or @{{...}}",
                )

    def test_shortcut_targets_the_graphical_launcher_only(self):
        """A desktop shortcut must never open the console launcher: that opens
        a terminal window and exists only for diagnostics."""
        self.assertIn("Get-GuiLauncher", self.script)
        self.assertIn("notmatch '(?i)console'", self.script)

    def test_shortcut_refuses_when_spanish_is_not_installed(self):
        """A shortcut called 'QuPath Español' that opens an English QuPath
        would be worse than no shortcut at all."""
        self.assertIn("Test-SpanishInstalled", self.script)
        self.assertIn(
            "Refusing to create a shortcut that would open QuPath in English",
            self.script,
        )

    def test_shortcut_can_be_removed(self):
        self.assertIn("Remove-SpanishShortcut", self.script)
        self.assertIn("[switch]$RemoveShortcut", self.script)

    def test_shortcut_does_not_overwrite_without_force(self):
        self.assertIn("Already exists (use -Force to replace)", self.script)

    def test_script_is_pure_ascii(self):
        """Windows PowerShell 5.1 reads a BOM-less script using the system ANSI
        code page, while PowerShell 7 reads it as UTF-8.  An accented literal
        therefore produces different strings in the two shells - which once
        made them create two differently named desktop shortcuts, neither able
        to find the other's."""
        raw = (REPO / "runtime" / "update-qupath-es.ps1").read_bytes()
        offenders = [(i, b) for i, b in enumerate(raw) if b > 0x7F]

        self.assertEqual(
            offenders, [],
            "non-ASCII bytes in the script; build accented text from code "
            "points instead, e.g. [char]0x00F1",
        )

    def test_accented_shortcut_name_is_built_from_a_code_point(self):
        self.assertIn("[char]0x00F1", self.script)

    def test_native_probe_call_tolerates_stderr(self):
        """QuPath's launcher writes warnings to stderr; with
        $ErrorActionPreference = 'Stop' those become terminating errors in
        Windows PowerShell and the probe silently never runs."""
        self.assertIn("$ErrorActionPreference = 'Continue'", self.script)
        self.assertIn("finally", self.script)


class SupportedVersionsTests(unittest.TestCase):

    def test_registry_is_valid_and_matches_reality(self):
        path = REPO / "versions" / "supported-versions.json"
        self.assertTrue(path.is_file())

        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data["versions"]["0.7.0"]

        real = status(REPO, "0.7.0")

        self.assertEqual(entry["base_bundle_sha256"], real["base_sha256"])
        self.assertEqual(entry["spanish_bundle_sha256"], real["dist_sha256"])
        self.assertEqual(entry["translation_keys"], real["base_keys"])


if __name__ == "__main__":
    unittest.main()
