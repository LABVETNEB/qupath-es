from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

if __package__:
    from .properties_audit import parse_properties
    from .translation_validator import validate_translation
else:
    from properties_audit import parse_properties
    from translation_validator import validate_translation


TSV_FIELDS = [
    "key",
    "en",
    "es",
    "state",
    "batch",
    "reviewer",
    "rev_date",
    "qupath_ver",
    "issues",
    "notes",
]


def encode_work_text(value: str) -> str:
    """
    Encode a semantic Java Properties value into a TSV-friendly
    human-editable representation.
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\f", "\\f")
    )


def decode_work_text(value: str) -> str:
    """
    Decode the project TSV representation back to a semantic value.
    """
    out = []
    i = 0

    while i < len(value):
        ch = value[i]

        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1

        if i >= len(value):
            raise ValueError("Dangling backslash in TSV value")

        esc = value[i]

        if esc == "n":
            out.append("\n")
        elif esc == "r":
            out.append("\r")
        elif esc == "t":
            out.append("\t")
        elif esc == "f":
            out.append("\f")
        elif esc == "\\":
            out.append("\\")
        else:
            raise ValueError(
                f"Unsupported TSV escape sequence: \\{esc}"
            )

        i += 1

    return "".join(out)


def escape_property_value(value: str) -> str:
    """
    Encode a semantic value for a UTF-8 Java .properties file.

    Unicode characters are written directly as UTF-8.
    Control characters and backslashes are escaped.
    """
    out = []

    for i, ch in enumerate(value):
        if ch == "\\":
            out.append("\\\\")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\f":
            out.append("\\f")
        elif ch == " " and i == 0:
            out.append("\\ ")
        else:
            out.append(ch)

    return "".join(out)


def value_start_index(line: str) -> int:
    """
    Locate the start of the raw value in the first physical line of
    a Java .properties entry while respecting escaped separators.
    """
    length = len(line)
    i = 0

    while i < length and line[i] in " \t\f":
        i += 1

    escaped = False

    while i < length:
        ch = line[i]

        if ch == "\\":
            escaped = not escaped
            i += 1
            continue

        if not escaped:
            if ch in "=:":
                i += 1

                while i < length and line[i] in " \t\f":
                    i += 1

                return i

            if ch in " \t\f":
                while i < length and line[i] in " \t\f":
                    i += 1

                if i < length and line[i] in "=:":
                    i += 1

                while i < length and line[i] in " \t\f":
                    i += 1

                return i

        escaped = False
        i += 1

    return length


def detect_newline(raw: bytes) -> str:
    if b"\r\n" in raw:
        return "\r\n"
    return "\n"


def export_identity_tsv(
    base_path: Path,
    tsv_path: Path,
    qupath_version: str,
) -> None:
    raw = base_path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    entries = parse_properties(text)

    tsv_path.parent.mkdir(parents=True, exist_ok=True)

    with tsv_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=TSV_FIELDS,
            delimiter="\t",
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )

        writer.writeheader()

        for entry in entries:
            encoded = encode_work_text(entry.value)

            writer.writerow(
                {
                    "key": entry.key,
                    "en": encoded,
                    "es": encoded,
                    "state": "PENDING",
                    "batch": "",
                    "reviewer": "",
                    "rev_date": "",
                    "qupath_ver": qupath_version,
                    "issues": "",
                    "notes": "",
                }
            )


def load_tsv(tsv_path: Path):
    with tsv_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        if reader.fieldnames != TSV_FIELDS:
            raise ValueError(
                "Unexpected TSV header.\n"
                f"Expected: {TSV_FIELDS}\n"
                f"Found:    {reader.fieldnames}"
            )

        rows = list(reader)

    keys = [row["key"] for row in rows]

    if len(keys) != len(set(keys)):
        seen = set()
        duplicates = []

        for key in keys:
            if key in seen and key not in duplicates:
                duplicates.append(key)
            seen.add(key)

        raise ValueError(
            "Duplicate keys in TSV: "
            + ", ".join(duplicates)
        )

    return rows


def generate_bundle(
    base_path: Path,
    tsv_path: Path,
    output_path: Path,
) -> dict:
    base_raw = base_path.read_bytes()
    base_text = base_raw.decode("utf-8", errors="strict")
    newline = detect_newline(base_raw)

    entries = parse_properties(base_text)
    rows = load_tsv(tsv_path)

    if len(rows) != len(entries):
        raise ValueError(
            f"TSV row count {len(rows)} does not match "
            f"base entry count {len(entries)}"
        )

    base_keys = [entry.key for entry in entries]
    tsv_keys = [row["key"] for row in rows]

    if tsv_keys != base_keys:
        raise ValueError(
            "TSV key order does not exactly match the canonical bundle"
        )

    translations = {}

    for entry, row in zip(entries, rows):
        en_value = decode_work_text(row["en"])
        es_value = decode_work_text(row["es"])

        if en_value != entry.value:
            raise ValueError(
                f"English source drift for key {entry.key!r}"
            )

        translations[entry.key] = es_value

    # Critical identity fast-path:
    # if every target value equals the canonical English semantic value,
    # write the original bytes without decoding/re-encoding.
    if all(
        translations[entry.key] == entry.value
        for entry in entries
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base_raw)

        return {
            "identity_mode": True,
            "changed_entries": 0,
            "bytes": len(base_raw),
            "sha256": hashlib.sha256(base_raw).hexdigest().upper(),
        }

    physical = base_text.splitlines(keepends=True)

    replacements = []

    for entry in entries:
        target_value = translations[entry.key]

        if target_value == entry.value:
            continue

        start = entry.start_line - 1
        end = entry.end_line

        first_line = physical[start]

        first_content = first_line.rstrip("\r\n")
        prefix_end = value_start_index(first_content)
        prefix = first_content[:prefix_end]

        rendered = (
            prefix
            + escape_property_value(target_value)
            + newline
        )

        replacements.append(
            (start, end, rendered, entry.key)
        )

    # Replace from the end backwards so physical indexes stay stable.
    for start, end, rendered, _key in reversed(replacements):
        physical[start:end] = [rendered]

    generated_text = "".join(physical)
    generated_raw = generated_text.encode("utf-8")

    # Semantic validation is mandatory before writing the result.
    report = validate_translation(
        base_text,
        generated_text,
    )

    if not report["ok"]:
        raise ValueError(
            "Generated bundle failed semantic validation: "
            f"{report['errors'][:10]}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(generated_raw)

    return {
        "identity_mode": False,
        "changed_entries": len(replacements),
        "bytes": len(generated_raw),
        "sha256": hashlib.sha256(
            generated_raw
        ).hexdigest().upper(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a validated QuPath localization bundle"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    export = sub.add_parser(
        "export-tsv",
        help="Create an identity translation TSV from the canonical bundle",
    )
    export.add_argument("base", type=Path)
    export.add_argument("tsv", type=Path)
    export.add_argument(
        "--qupath-version",
        required=True,
        help="QuPath version stamped into every row. There is deliberately no "
             "default: a wrong version number would silently mislabel the "
             "whole workspace.",
    )

    generate = sub.add_parser(
        "generate",
        help="Generate a localization bundle from a translation TSV",
    )
    generate.add_argument("base", type=Path)
    generate.add_argument("tsv", type=Path)
    generate.add_argument("output", type=Path)

    args = parser.parse_args()

    try:
        if args.command == "export-tsv":
            export_identity_tsv(
                args.base,
                args.tsv,
                args.qupath_version,
            )

            print(f"TSV written: {args.tsv}")
            return 0

        if args.command == "generate":
            report = generate_bundle(
                args.base,
                args.tsv,
                args.output,
            )

            print("Bundle generation")
            print("-----------------")
            print(
                f"Identity mode:     "
                f"{report['identity_mode']}"
            )
            print(
                f"Changed entries:   "
                f"{report['changed_entries']}"
            )
            print(
                f"Bytes:             "
                f"{report['bytes']}"
            )
            print(
                f"SHA-256:           "
                f"{report['sha256']}"
            )
            print(
                f"Output:            "
                f"{args.output}"
            )

            return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
