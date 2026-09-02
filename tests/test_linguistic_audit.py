from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.linguistic_audit import (
    audit,
    deaccent,
    detect_qupath_version,
    has_mojibake,
)
from tools.translation_generator import TSV_FIELDS


TSV_HEADER = "\t".join(TSV_FIELDS) + "\n"


def tsv_row(key, en, es, state="REVIEWED"):
    return "\t".join(
        [key, en, es, state, "TEST", "tester", "2026-01-01", "0.7.0", "", ""]
    ) + "\n"


class AuditHelpersTests(unittest.TestCase):

    def test_deaccent_folds_spanish_diacritics(self):
        self.assertEqual(deaccent("Elíptica"), "eliptica")
        self.assertEqual(deaccent("NÚCLEO"), "nucleo")
        self.assertEqual(deaccent("anotación"), "anotacion")

    def test_mojibake_detection(self):
        self.assertTrue(has_mojibake("SecciÃ³n"))
        self.assertTrue(has_mojibake("Secci�n"))
        self.assertFalse(has_mojibake("Sección"))


class AuditTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "base.properties"
        self.tsv = self.tmp / "work.tsv"
        self.target = self.tmp / "target.properties"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, entries):
        """entries: list of (key, en, es, state)."""
        self.base.write_text(
            "".join(f"{k} = {en}\n" for k, en, _, _ in entries),
            encoding="utf-8",
            newline="\n",
        )
        self.target.write_text(
            "".join(f"{k} = {es}\n" for k, _, es, _ in entries),
            encoding="utf-8",
            newline="\n",
        )
        self.tsv.write_text(
            TSV_HEADER
            + "".join(tsv_row(k, en, es, state) for k, en, es, state in entries),
            encoding="utf-8",
            newline="",
        )

    def test_clean_translation_is_safe_to_install(self):
        self._write([
            ("a", "Annotations", "Anotaciones", "REVIEWED"),
            ("b", "TMA", "TMA", "KEEP_EN"),
        ])

        report = audit(self.base, self.tsv, self.target)

        self.assertEqual(report["error_count"], 0, report["errors"])
        self.assertEqual(report["warning_count"], 0, report["warnings"])
        self.assertEqual(report["verdict"], "SAFE TO INSTALL")

    def test_dropped_acronym_is_an_error(self):
        self._write([
            ("a", "Show TMA grid", "Mostrar cuadricula", "REVIEWED"),
        ])

        report = audit(self.base, self.tsv, self.target)

        self.assertEqual(report["verdict"], "DO NOT INSTALL")
        self.assertTrue(
            any(
                e["check"] == "acronym" and e["acronym"] == "TMA"
                for e in report["errors"]
            )
        )

    def test_untranslated_state_is_an_error(self):
        self._write([
            ("a", "Annotations", "Anotaciones", "PENDING"),
        ])

        report = audit(self.base, self.tsv, self.target)

        self.assertTrue(
            any(e["type"] == "not_reviewed" for e in report["errors"])
        )

    def test_identical_without_keep_en_is_an_error(self):
        self._write([
            ("a", "Hello", "Hello", "REVIEWED"),
        ])

        report = audit(self.base, self.tsv, self.target)

        self.assertTrue(
            any(
                e["type"] == "identical_to_english_without_keep_en"
                for e in report["errors"]
            )
        )

    def test_keep_en_that_was_translated_is_an_error(self):
        self._write([
            ("a", "TMA", "MTA", "KEEP_EN"),
        ])

        report = audit(self.base, self.tsv, self.target)

        self.assertTrue(
            any(e["type"] == "keep_en_but_translated" for e in report["errors"])
        )


class FalsePositiveRegressionTests(unittest.TestCase):
    """Each case here previously produced a spurious finding."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = self.tmp / "base.properties"
        self.tsv = self.tmp / "work.tsv"
        self.target = self.tmp / "target.properties"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _audit(self, key, en, es, state="REVIEWED"):
        self.base.write_text(f"{key} = {en}\n", encoding="utf-8", newline="\n")
        self.target.write_text(f"{key} = {es}\n", encoding="utf-8", newline="\n")
        self.tsv.write_text(
            TSV_HEADER + tsv_row(key, en, es, state),
            encoding="utf-8",
            newline="",
        )
        return audit(self.base, self.tsv, self.target)

    def test_accented_inflection_satisfies_glossary(self):
        # 'ellipse' -> 'elíptica': the accent must not defeat the stem match.
        report = self._audit(
            "a",
            "Create a rectangle or ellipse annotation",
            "Crear una anotación rectangular o elíptica",
        )
        self.assertEqual(report["warning_count"], 0, report["warnings"])

    def test_projection_satisfies_project_glossary(self):
        # 'Z-project' -> 'proyección Z' shares the stem 'proyec', not 'proyect'.
        report = self._audit("a", "Show Z-project overlay",
                             "Mostrar superposición de proyección Z")
        self.assertEqual(report["warning_count"], 0, report["warnings"])

    def test_english_trailing_preposition_is_not_truncation(self):
        # 'Sort by' -> 'Ordenar por' is complete, not truncated.
        report = self._audit("a", "Sort by", "Ordenar por")
        self.assertEqual(report["warning_count"], 0, report["warnings"])

    def test_literal_percent_is_not_a_placeholder(self):
        report = self._audit(
            "a",
            "Set the zoom factor to 400% (downsample = 0.25)",
            "Establecer el factor de zoom en 400% (submuestreo = 0.25)",
        )
        self.assertEqual(report["error_count"], 0, report["errors"])

    def test_real_placeholder_change_is_still_caught(self):
        report = self._audit("a", "Could not parse %s", "No se pudo analizar")

        self.assertTrue(
            any(e["check"] == "placeholder" for e in report["errors"])
        )

class VersionDetectionTests(unittest.TestCase):
    """The audit must report the version it actually audited.

    Regression guard: the report used to hardcode "0.7.0", so auditing a
    migrated 0.8.x workspace would have claimed to be a 0.7.0 audit.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _audit_with_version(self, qupath_ver):
        base = self.tmp / "base.properties"
        target = self.tmp / "target.properties"
        tsv = self.tmp / "versions" / qupath_ver / "work" / "translation.tsv"
        tsv.parent.mkdir(parents=True, exist_ok=True)

        base.write_text("a = Hello\n", encoding="utf-8", newline="\n")
        target.write_text("a = Hola\n", encoding="utf-8", newline="\n")
        tsv.write_text(
            TSV_HEADER + "\t".join(
                ["a", "Hello", "Hola", "REVIEWED", "B", "r",
                 "2026-01-01", qupath_ver, "", ""]
            ) + "\n",
            encoding="utf-8", newline="",
        )
        return audit(base, tsv, target)

    def test_version_comes_from_the_tsv(self):
        self.assertEqual(
            self._audit_with_version("0.8.0")["qupath_version"], "0.8.0"
        )
        self.assertEqual(
            self._audit_with_version("0.7.0")["qupath_version"], "0.7.0"
        )

    def test_mixed_versions_are_flagged_not_silently_picked(self):
        rows = [
            {"qupath_ver": "0.7.0"},
            {"qupath_ver": "0.8.0"},
        ]
        result = detect_qupath_version(rows, Path("x/versions/0.8.0/work/t.tsv"))
        self.assertTrue(result.startswith("MIXED:"))

    def test_directory_name_is_the_fallback(self):
        result = detect_qupath_version(
            [{"qupath_ver": ""}],
            Path("repo/versions/1.2.3/work/translation.tsv"),
        )
        self.assertEqual(result, "1.2.3")


if __name__ == "__main__":
    unittest.main()
