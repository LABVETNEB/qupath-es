from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if __package__:
    from .properties_audit import (
        MESSAGE_FORMAT_RE,
        PRINTF_RE,
        PropertiesParseError,
        parse_properties,
    )
else:
    from properties_audit import (
        MESSAGE_FORMAT_RE,
        PRINTF_RE,
        PropertiesParseError,
        parse_properties,
    )


def message_format_tokens(value: str) -> list[str]:
    return [match.group(0) for match in MESSAGE_FORMAT_RE.finditer(value)]


def printf_tokens(value: str) -> list[str]:
    return [match.group(0) for match in PRINTF_RE.finditer(value)]


def duplicate_keys(entries) -> list[str]:
    counts = Counter(entry.key for entry in entries)
    return sorted(key for key, count in counts.items() if count > 1)


def validate_translation(base_text: str, target_text: str) -> dict:
    base_entries = parse_properties(base_text)
    target_entries = parse_properties(target_text)

    base_keys = [entry.key for entry in base_entries]
    target_keys = [entry.key for entry in target_entries]

    base_duplicates = duplicate_keys(base_entries)
    target_duplicates = duplicate_keys(target_entries)

    base_set = set(base_keys)
    target_set = set(target_keys)

    missing_keys = sorted(base_set - target_set)
    extra_keys = sorted(target_set - base_set)

    errors: list[dict] = []

    for key in base_duplicates:
        errors.append(
            {
                "type": "duplicate_base_key",
                "key": key,
            }
        )

    for key in target_duplicates:
        errors.append(
            {
                "type": "duplicate_target_key",
                "key": key,
            }
        )

    for key in missing_keys:
        errors.append(
            {
                "type": "missing_key",
                "key": key,
            }
        )

    for key in extra_keys:
        errors.append(
            {
                "type": "extra_key",
                "key": key,
            }
        )

    order_identical = base_keys == target_keys

    if (
        not order_identical
        and not missing_keys
        and not extra_keys
        and not base_duplicates
        and not target_duplicates
    ):
        errors.append(
            {
                "type": "key_order_mismatch",
            }
        )

    base_by_key = {entry.key: entry for entry in base_entries}
    target_by_key = {entry.key: entry for entry in target_entries}

    common_keys = [
        key
        for key in base_keys
        if key in target_by_key
    ]

    placeholder_errors = 0
    empty_value_errors = 0

    for key in common_keys:
        base_value = base_by_key[key].value
        target_value = target_by_key[key].value

        if base_value and not target_value:
            errors.append(
                {
                    "type": "empty_target_value",
                    "key": key,
                }
            )
            empty_value_errors += 1

        base_message = message_format_tokens(base_value)
        target_message = message_format_tokens(target_value)

        if Counter(base_message) != Counter(target_message):
            errors.append(
                {
                    "type": "message_format_mismatch",
                    "key": key,
                    "base": base_message,
                    "target": target_message,
                }
            )
            placeholder_errors += 1

        base_printf = printf_tokens(base_value)
        target_printf = printf_tokens(target_value)

        if base_printf != target_printf:
            errors.append(
                {
                    "type": "printf_mismatch",
                    "key": key,
                    "base": base_printf,
                    "target": target_printf,
                }
            )
            placeholder_errors += 1

    return {
        "ok": len(errors) == 0,
        "base_entries": len(base_entries),
        "target_entries": len(target_entries),
        "base_unique_keys": len(base_set),
        "target_unique_keys": len(target_set),
        "missing_keys": missing_keys,
        "extra_keys": extra_keys,
        "base_duplicate_keys": base_duplicates,
        "target_duplicate_keys": target_duplicates,
        "key_order_identical": order_identical,
        "placeholder_errors": placeholder_errors,
        "empty_value_errors": empty_value_errors,
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a translated QuPath Java .properties bundle"
    )

    parser.add_argument("base", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)

    args = parser.parse_args()

    try:
        base_raw = args.base.read_bytes()
        target_raw = args.target.read_bytes()

        base_text = base_raw.decode("utf-8", errors="strict")
        target_text = target_raw.decode("utf-8", errors="strict")

        report = validate_translation(base_text, target_text)

    except (UnicodeDecodeError, PropertiesParseError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("Translation validation")
    print("----------------------")
    print(f"Base entries:            {report['base_entries']}")
    print(f"Target entries:          {report['target_entries']}")
    print(f"Base unique keys:        {report['base_unique_keys']}")
    print(f"Target unique keys:      {report['target_unique_keys']}")
    print(f"Missing keys:            {len(report['missing_keys'])}")
    print(f"Extra keys:              {len(report['extra_keys'])}")
    print(f"Base duplicate keys:     {len(report['base_duplicate_keys'])}")
    print(f"Target duplicate keys:   {len(report['target_duplicate_keys'])}")
    print(f"Key order identical:     {report['key_order_identical']}")
    print(f"Placeholder errors:      {report['placeholder_errors']}")
    print(f"Empty target values:     {report['empty_value_errors']}")
    print(f"Total errors:            {report['error_count']}")
    print(f"Result:                  {'PASS' if report['ok'] else 'FAIL'}")

    if report["errors"]:
        print("\nErrors:")
        for error in report["errors"][:50]:
            print(" ", json.dumps(error, ensure_ascii=False))

        if len(report["errors"]) > 50:
            print(
                f"  ... {len(report['errors']) - 50} additional errors omitted"
            )

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)

        args.json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        print(f"\nReport written: {args.json_path}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

