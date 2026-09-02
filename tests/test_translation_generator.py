from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.properties_audit import parse_properties
from tools.translation_generator import (
    TSV_FIELDS,
    decode_work_text,
    encode_work_text,
    escape_property_value,
    export_identity_tsv,
    generate_bundle,
)


ROOT = Path(__file__).resolve().parents[1]

BASE = (
    ROOT
    / "versions"
    / "0.7.0"
    / "base"
    / "qupath-gui-strings.properties"
)

EXPECTED_SHA256 = (
    "796EFC44FC23369E4D7BDFDE69C0FA2A702051BF2F9D71399157B505E8D45D2D"
)


class TranslationGeneratorUnitTests(unittest.TestCase):

    def test_work_text_roundtrip(self):
        value = "Uno\\dos\nTres\tCuatro"

        encoded = encode_work_text(value)
        decoded = decode_work_text(encoded)

        self.assertEqual(decoded, value)

    def test_property_value_escape(self):
        value = "Línea 1\nLínea 2\\final"

        self.assertEqual(
            escape_property_value(value),
            "Línea 1\\nLínea 2\\\\final",
        )

    def test_identity_generation_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            tsv = tmp / "translation.tsv"
            output = tmp / "output.properties"

            export_identity_tsv(
                BASE,
                tsv,
                "0.7.0",
            )

            report = generate_bundle(
                BASE,
                tsv,
                output,
            )

            self.assertTrue(report["identity_mode"])
            self.assertEqual(report["changed_entries"], 0)
            self.assertEqual(
                output.read_bytes(),
                BASE.read_bytes(),
            )

            digest = hashlib.sha256(
                output.read_bytes()
            ).hexdigest().upper()

            self.assertEqual(
                digest,
                EXPECTED_SHA256,
            )

    def test_one_translation_changes_only_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            base = tmp / "base.properties"
            tsv = tmp / "translation.tsv"
            output = tmp / "output.properties"

            base.write_text(
                "# Header\n"
                "one = Hello\n"
                "two = Open %s\n",
                encoding="utf-8",
                newline="\n",
            )

            export_identity_tsv(
                base,
                tsv,
                "test",
            )

            with tsv.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                rows = list(
                    csv.DictReader(
                        handle,
                        delimiter="\t",
                    )
                )

            rows[0]["es"] = "Hola"

            with tsv.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=TSV_FIELDS,
                    delimiter="\t",
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)

            report = generate_bundle(
                base,
                tsv,
                output,
            )

            self.assertFalse(report["identity_mode"])
            self.assertEqual(
                report["changed_entries"],
                1,
            )

            text = output.read_text(
                encoding="utf-8"
            )

            self.assertIn("# Header\n", text)
            self.assertIn("one = Hola\n", text)
            self.assertIn("two = Open %s\n", text)

            entries = parse_properties(text)

            self.assertEqual(entries[0].value, "Hola")
            self.assertEqual(entries[1].value, "Open %s")

    def test_source_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            base = tmp / "base.properties"
            tsv = tmp / "translation.tsv"
            output = tmp / "output.properties"

            base.write_text(
                "one = Hello\n",
                encoding="utf-8",
                newline="\n",
            )

            export_identity_tsv(
                base,
                tsv,
                "test",
            )

            text = tsv.read_text(encoding="utf-8")
            text = text.replace("Hello", "Changed")
            tsv.write_text(
                text,
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaises(ValueError):
                generate_bundle(
                    base,
                    tsv,
                    output,
                )

    def test_key_reordering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            base = tmp / "base.properties"
            tsv = tmp / "translation.tsv"
            output = tmp / "output.properties"

            base.write_text(
                "one = One\n"
                "two = Two\n",
                encoding="utf-8",
                newline="\n",
            )

            export_identity_tsv(
                base,
                tsv,
                "test",
            )

            with tsv.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                rows = list(
                    csv.DictReader(
                        handle,
                        delimiter="\t",
                    )
                )

            rows.reverse()

            with tsv.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=TSV_FIELDS,
                    delimiter="\t",
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaises(ValueError):
                generate_bundle(
                    base,
                    tsv,
                    output,
                )


if __name__ == "__main__":
    unittest.main()
