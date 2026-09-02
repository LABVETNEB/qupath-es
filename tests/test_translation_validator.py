from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.translation_validator import (
    message_format_effective_tokens,
    printf_tokens,
    unescaped_apostrophes,
    validate_translation,
)


class TranslationValidatorTests(unittest.TestCase):

    def test_valid_translation_passes(self):
        base = (
            "one = Hello\n"
            "two = Open %s\n"
            "three = Value {0}\n"
        )

        target = (
            "one = Hola\n"
            "two = Abrir %s\n"
            "three = Valor {0}\n"
        )

        report = validate_translation(base, target)

        self.assertTrue(report["ok"])
        self.assertEqual(report["error_count"], 0)

    def test_missing_key_fails(self):
        base = (
            "one = One\n"
            "two = Two\n"
        )

        target = "one = Uno\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertIn("two", report["missing_keys"])

    def test_extra_key_fails(self):
        base = "one = One\n"

        target = (
            "one = Uno\n"
            "two = Dos\n"
        )

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertIn("two", report["extra_keys"])

    def test_reordered_keys_fail(self):
        base = (
            "one = One\n"
            "two = Two\n"
        )

        target = (
            "two = Dos\n"
            "one = Uno\n"
        )

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertFalse(report["key_order_identical"])

    def test_duplicate_target_key_fails(self):
        base = (
            "one = One\n"
            "two = Two\n"
        )

        target = (
            "one = Uno\n"
            "two = Dos\n"
            "two = Otro\n"
        )

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertIn("two", report["target_duplicate_keys"])

    def test_printf_placeholder_change_fails(self):
        base = "message = Open %s\n"
        target = "message = Abrir %d\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["placeholder_errors"], 0)

    def test_message_format_change_fails(self):
        base = "message = Value {0}\n"
        target = "message = Valor {1}\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["placeholder_errors"], 0)

    def test_accidental_empty_value_fails(self):
        base = "message = Hello\n"
        target = "message =\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertEqual(report["empty_value_errors"], 1)


class FormatterTokeniserTests(unittest.TestCase):
    """A literal percent sign must not be mistaken for a format specifier."""

    def test_literal_percent_is_not_a_specifier(self):
        for text in (
            "Set the zoom factor to 400% (downsample = 0.25)",
            "must be >10% and <90%",
            "Set % bright and % dark pixels",
            "100% is 'normal', while lower values are slower",
        ):
            with self.subTest(text=text):
                self.assertEqual(printf_tokens(text), [])

    def test_real_specifiers_are_detected(self):
        cases = {
            "Open %s": ["%s"],
            "%d classes selected": ["%d"],
            "%1$s and %2$d": ["%1$s", "%2$d"],
            "line%n": ["%n"],
            "100%% done": ["%%"],
            "%.2f and %,d and %-10s": ["%.2f", "%,d", "%-10s"],
            "%tY": ["%tY"],
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(printf_tokens(text), expected)

    def test_translating_words_after_literal_percent_passes(self):
        base = "zoom = Set the zoom factor to 400% (downsample = 0.25)\n"
        target = (
            "zoom = Establecer el factor de zoom a 400% "
            "(submuestreo = 0.25)\n"
        )

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["placeholder_errors"], 0)


class PositionalFormatTests(unittest.TestCase):

    def test_non_positional_reorder_fails(self):
        base = "m = %s wrote %d lines\n"
        target = "m = %d lineas escritas por %s\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["placeholder_errors"], 0)

    def test_positional_reorder_passes(self):
        base = "m = %1$s wrote %2$d lines\n"
        target = "m = %2$d lineas escritas por %1$s\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])

    def test_dropped_specifier_fails(self):
        base = "m = Could not parse %s\n"
        target = "m = No se pudo analizar\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["placeholder_errors"], 0)

    def test_duplicated_specifier_fails(self):
        base = "m = Value {0}\n"
        target = "m = Valor {0} de {0}\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["placeholder_errors"], 0)


class MessageFormatQuotingTests(unittest.TestCase):

    def test_effective_tokens_ignore_quoted_runs(self):
        self.assertEqual(
            message_format_effective_tokens("Value {0}"), ["{0}"]
        )
        # A lone apostrophe quotes the rest of the string.
        self.assertEqual(
            message_format_effective_tokens("Can't show {0}"), []
        )
        # Doubled apostrophes are literal and do not quote.
        self.assertEqual(
            message_format_effective_tokens("Can''t show {0}"), ["{0}"]
        )

    def test_unescaped_apostrophe_neutralising_placeholder_fails(self):
        # A single (odd) apostrophe opens a quoted run that swallows {0}.
        base = "m = Unable to load {0}\n"
        target = "m = No se ha podido cargar l'archivo {0}\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(
                error["type"] == "message_format_quote_loss"
                for error in report["errors"]
            )
        )

    def test_doubled_apostrophe_keeps_placeholder_valid(self):
        base = "m = Unable to load {0}\n"
        target = "m = No se ha podido cargar l''archivo {0}\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])

    def test_balanced_pair_of_apostrophes_keeps_placeholder_valid(self):
        # Two apostrophes close the quoted run before the placeholder, so the
        # argument still resolves - this must not be reported as an error.
        base = "m = Unable to load {0}\n"
        target = "m = No se ha podido cargar el 'plugin' {0}\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(
            any(
                warning["type"] == "unescaped_apostrophe_with_placeholder"
                for warning in report["warnings"]
            )
        )

    def test_apostrophe_without_placeholder_is_fine(self):
        base = "m = Auto brightness\n"
        target = "m = Brillo 'automatico'\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])

    def test_counting_unescaped_apostrophes(self):
        self.assertEqual(unescaped_apostrophes("plain"), 0)
        self.assertEqual(unescaped_apostrophes("it's"), 1)
        self.assertEqual(unescaped_apostrophes("it''s"), 0)
        self.assertEqual(unescaped_apostrophes("'a' and 'b'"), 4)


class StructuralIntegrityTests(unittest.TestCase):

    def test_brace_imbalance_fails(self):
        base = "m = Press {{Click here}} to continue\n"
        target = "m = Pulse {{Haga clic aqui} para continuar\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["structural_errors"], 0)

    def test_matched_double_braces_pass(self):
        base = "m = Press {{Click here}} to continue\n"
        target = "m = Pulse {{Haga clic aqui}} para continuar\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])

    def test_lost_escaped_newline_fails(self):
        base = "m = First line\\nSecond line\n"
        target = "m = Primera linea Segunda linea\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(
                error["type"] == "newline_count_mismatch"
                for error in report["errors"]
            )
        )

    def test_preserved_escaped_newline_passes(self):
        base = "m = First line\\nSecond line\n"
        target = "m = Primera linea\\nSegunda linea\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])

    def test_replacement_character_fails(self):
        base = "m = Section\n"
        target = "m = Secci�n\n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertTrue(
            any(
                error["type"] == "replacement_character"
                for error in report["errors"]
            )
        )

    def test_whitespace_only_target_fails(self):
        base = "m = Hello\n"
        target = "m = \\ \n"

        report = validate_translation(base, target)

        self.assertFalse(report["ok"])
        self.assertGreater(report["empty_value_errors"], 0)

    def test_continuation_lines_are_supported(self):
        base = (
            "m = First part \\\n"
            "    second part\n"
        )
        target = (
            "m = Primera parte \\\n"
            "    segunda parte\n"
        )

        report = validate_translation(base, target)

        self.assertTrue(report["ok"], report["errors"])

    def test_identical_values_are_counted_not_failed(self):
        base = "m = TMA\n"
        target = "m = TMA\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"])
        self.assertEqual(report["identical_values"], 1)


class WarningTests(unittest.TestCase):

    def test_suspect_marker_warns_without_failing(self):
        base = "m = Hello\n"
        target = "m = Hola TODO\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"])
        self.assertTrue(
            any(
                warning["type"] == "suspect_marker"
                for warning in report["warnings"]
            )
        )

    def test_double_space_warns_without_failing(self):
        base = "m = Hello world\n"
        target = "m = Hola  mundo\n"

        report = validate_translation(base, target)

        self.assertTrue(report["ok"])
        self.assertTrue(
            any(
                warning["type"] == "double_space_introduced"
                for warning in report["warnings"]
            )
        )


class ExitCodeTests(unittest.TestCase):
    """PASS = 0, validation failure = 1, parse/IO/encoding = 2."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.base = Path(self.tmp) / "base.properties"
        self.target = Path(self.tmp) / "target.properties"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, module_form: bool):
        repo_root = Path(__file__).resolve().parents[1]

        if module_form:
            cmd = [sys.executable, "-m", "tools.translation_validator"]
        else:
            cmd = [
                sys.executable,
                str(repo_root / "tools" / "translation_validator.py"),
            ]

        return subprocess.run(
            cmd + [str(self.base), str(self.target)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

    def test_pass_returns_zero_for_both_invocations(self):
        self.base.write_bytes("m = Hello\n".encode("utf-8"))
        self.target.write_bytes("m = Hola\n".encode("utf-8"))

        for module_form in (False, True):
            with self.subTest(module_form=module_form):
                self.assertEqual(self._run(module_form).returncode, 0)

    def test_validation_failure_returns_one(self):
        self.base.write_bytes("m = Hello\nn = Bye\n".encode("utf-8"))
        self.target.write_bytes("m = Hola\n".encode("utf-8"))

        self.assertEqual(self._run(False).returncode, 1)

    def test_invalid_encoding_returns_two(self):
        self.base.write_bytes("m = Hello\n".encode("utf-8"))
        self.target.write_bytes(b"m = Secci\xf3n\n")

        self.assertEqual(self._run(False).returncode, 2)

    def test_utf8_bom_returns_two(self):
        self.base.write_bytes("m = Hello\n".encode("utf-8"))
        self.target.write_bytes(b"\xef\xbb\xbfm = Hola\n")

        self.assertEqual(self._run(False).returncode, 2)

    def test_missing_file_returns_two(self):
        self.base.write_bytes("m = Hello\n".encode("utf-8"))

        self.assertEqual(self._run(False).returncode, 2)


if __name__ == "__main__":
    unittest.main()
