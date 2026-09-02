from __future__ import annotations

import hashlib
import unittest
from collections import Counter
from pathlib import Path

from tools.properties_audit import (
    PropertiesParseError,
    parse_properties,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = (
    ROOT
    / "versions"
    / "0.7.0"
    / "base"
    / "qupath-gui-strings.properties"
)

EXPECTED_BASE_SHA256 = (
    "796EFC44FC23369E4D7BDFDE69C0FA2A702051BF2F9D71399157B505E8D45D2D"
)


class PropertiesParserTests(unittest.TestCase):

    def test_basic_separators(self):
        text = (
            "# comment\n"
            "\n"
            "alpha=value1\n"
            "beta:value2\n"
            "gamma value3\n"
        )

        entries = parse_properties(text)

        self.assertEqual(
            [(e.key, e.value) for e in entries],
            [
                ("alpha", "value1"),
                ("beta", "value2"),
                ("gamma", "value3"),
            ],
        )

    def test_escaped_separator_in_key(self):
        entries = parse_properties(r"alpha\=beta = value")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "alpha=beta")
        self.assertEqual(entries[0].value, "value")

    def test_single_continuation(self):
        text = "message=first\\\n    second\n"

        entries = parse_properties(text)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "message")
        self.assertEqual(entries[0].value, "firstsecond")
        self.assertEqual(entries[0].start_line, 1)
        self.assertEqual(entries[0].end_line, 2)

    def test_multiple_continuations_same_property(self):
        text = "message=one\\\n  two\\\n  three\n"

        entries = parse_properties(text)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].value, "onetwothree")
        self.assertEqual(entries[0].start_line, 1)
        self.assertEqual(entries[0].end_line, 3)

    def test_even_backslashes_do_not_continue(self):
        text = "first=abc\\\\\nsecond=value\n"

        entries = parse_properties(text)

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].key, "first")
        self.assertEqual(entries[0].value, "abc\\")
        self.assertEqual(entries[1].key, "second")
        self.assertEqual(entries[1].value, "value")

    def test_unicode_escape(self):
        entries = parse_properties(r"name=Espa\u00f1a")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].value, "España")

    def test_control_escape(self):
        entries = parse_properties(r"message=primera\nsegunda")

        self.assertEqual(entries[0].value, "primera\nsegunda")

    def test_empty_value(self):
        entries = parse_properties("empty=\n")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "empty")
        self.assertEqual(entries[0].value, "")

    def test_key_without_explicit_separator(self):
        entries = parse_properties("lonelyKey\n")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "lonelyKey")
        self.assertEqual(entries[0].value, "")

    def test_invalid_unicode_escape_is_rejected(self):
        with self.assertRaises(PropertiesParseError):
            parse_properties(r"bad=\u12ZZ")

    def test_continuation_at_eof_is_rejected(self):
        with self.assertRaises(PropertiesParseError):
            parse_properties("bad=value\\")

    def test_duplicate_keys_are_observable(self):
        entries = parse_properties(
            "duplicate=one\n"
            "duplicate=two\n"
        )

        counts = Counter(e.key for e in entries)

        self.assertEqual(counts["duplicate"], 2)


class QuPath070IntegrationTests(unittest.TestCase):

    def test_canonical_bundle_hash(self):
        raw = BASE.read_bytes()

        self.assertEqual(
            hashlib.sha256(raw).hexdigest().upper(),
            EXPECTED_BASE_SHA256,
        )

    def test_canonical_bundle_utf8(self):
        BASE.read_bytes().decode("utf-8", errors="strict")

    def test_canonical_bundle_entry_count(self):
        text = BASE.read_text(encoding="utf-8")
        entries = parse_properties(text)

        self.assertEqual(len(entries), 894)

    def test_canonical_bundle_has_unique_keys(self):
        text = BASE.read_text(encoding="utf-8")
        entries = parse_properties(text)

        keys = [entry.key for entry in entries]

        self.assertEqual(len(keys), 894)
        self.assertEqual(len(set(keys)), 894)

    def test_canonical_bundle_continuation_entry_count(self):
        text = BASE.read_text(encoding="utf-8")
        entries = parse_properties(text)

        continuation_entries = [
            entry
            for entry in entries
            if entry.end_line > entry.start_line
        ]

        self.assertEqual(len(continuation_entries), 20)


if __name__ == "__main__":
    unittest.main()
