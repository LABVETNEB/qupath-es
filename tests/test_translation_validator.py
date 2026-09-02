from __future__ import annotations

import unittest

from tools.translation_validator import validate_translation


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


if __name__ == "__main__":
    unittest.main()
