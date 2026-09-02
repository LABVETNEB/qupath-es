from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

if __package__:
    from .properties_audit import (
        MESSAGE_FORMAT_RE,
        PropertiesParseError,
        parse_properties,
    )
else:
    from properties_audit import (
        MESSAGE_FORMAT_RE,
        PropertiesParseError,
        parse_properties,
    )


# ---------------------------------------------------------------------------
# Placeholder tokenisers
# ---------------------------------------------------------------------------

# Strict java.util.Formatter specifier.
#
# Deliberately excludes the ' ' (space) flag.  The space flag is legal Java but
# never appears in QuPath UI resources, whereas a literal percent sign followed
# by a space is common ("400% (downsample = 0.25)", "100% is 'normal'").  Keeping
# the space flag makes the tokeniser read "% (d" out of "400% (downsample" and
# then report a spurious mismatch as soon as the following word is translated.
#
# Conversions follow java.util.Formatter: general/character/integral/floating
# point, the 't'/'T' date-time prefix, the '%' literal and the 'n' newline.
JAVA_FORMAT_RE = re.compile(
    r"%"
    r"(?:(?P<index>\d+)\$)?"
    r"(?P<flags>[-#+0,(]*)"
    r"(?P<width>\d+)?"
    r"(?:\.(?P<precision>\d+))?"
    r"(?:(?P<conv>[bBhHsScCdoxXeEfgGaA%n])|[tT](?P<dt>[a-zA-Z]))"
)

# Characters that must never appear literally in a bundle value.
DISALLOWED_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")

SUSPECT_TOKENS = ("TODO", "FIXME", "XXX", "???")

REPLACEMENT_CHARACTER = "�"


def message_format_tokens(value: str) -> list[str]:
    """Raw ``{n}`` / ``{n,type}`` tokens, ignoring MessageFormat quoting."""
    return [match.group(0) for match in MESSAGE_FORMAT_RE.finditer(value)]


def message_format_effective_tokens(value: str) -> list[str]:
    """
    Tokens that MessageFormat would actually treat as arguments.

    MessageFormat quoting rules: ``''`` is a literal apostrophe; a lone ``'``
    opens a quoted run that ends at the next lone ``'`` or at end of string.
    Anything inside a quoted run - including ``{0}`` - is literal text.

    This is what makes an un-doubled apostrophe dangerous in Spanish: it can
    silently neutralise a placeholder that worked in English.
    """
    literal_parts: list[str] = []
    i = 0
    length = len(value)
    quoted = False

    while i < length:
        ch = value[i]

        if ch == "'":
            if i + 1 < length and value[i + 1] == "'":
                # Escaped apostrophe - literal, does not toggle quoting.
                i += 2
                continue

            quoted = not quoted
            i += 1
            continue

        if not quoted:
            literal_parts.append(ch)

        i += 1

    return message_format_tokens("".join(literal_parts))


def printf_tokens(value: str) -> list[str]:
    return [match.group(0) for match in JAVA_FORMAT_RE.finditer(value)]


def format_tokens_are_positional(tokens: list[str]) -> bool:
    """True when every argument-consuming specifier carries an ``n$`` index."""
    if not tokens:
        return False

    consuming = 0

    for token in tokens:
        match = JAVA_FORMAT_RE.fullmatch(token)

        if match is None:
            return False

        if match.group("conv") in {"%", "n"}:
            # Neither consumes an argument, so neither blocks reordering.
            continue

        consuming += 1

        if match.group("index") is None:
            return False

    return consuming > 0


def unescaped_apostrophes(value: str) -> int:
    """Count apostrophes that MessageFormat would treat as quoting."""
    count = 0
    i = 0
    length = len(value)

    while i < length:
        if value[i] == "'":
            if i + 1 < length and value[i + 1] == "'":
                i += 2
                continue

            count += 1

        i += 1

    return count


def brace_balance(value: str) -> tuple[int, int]:
    return value.count("{"), value.count("}")


def duplicate_keys(entries) -> list[str]:
    counts = Counter(entry.key for entry in entries)
    return sorted(key for key, count in counts.items() if count > 1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

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
    warnings: list[dict] = []

    for key in base_duplicates:
        errors.append({"type": "duplicate_base_key", "key": key})

    for key in target_duplicates:
        errors.append({"type": "duplicate_target_key", "key": key})

    for key in missing_keys:
        errors.append({"type": "missing_key", "key": key})

    for key in extra_keys:
        errors.append({"type": "extra_key", "key": key})

    order_identical = base_keys == target_keys

    if (
        not order_identical
        and not missing_keys
        and not extra_keys
        and not base_duplicates
        and not target_duplicates
    ):
        errors.append({"type": "key_order_mismatch"})

    base_by_key = {entry.key: entry for entry in base_entries}
    target_by_key = {entry.key: entry for entry in target_entries}

    common_keys = [key for key in base_keys if key in target_by_key]

    placeholder_errors = 0
    empty_value_errors = 0
    structural_errors = 0
    identical_values = 0

    for key in common_keys:
        base_value = base_by_key[key].value
        target_value = target_by_key[key].value

        # -- empty values ----------------------------------------------------
        if base_value and not target_value:
            errors.append({"type": "empty_target_value", "key": key})
            empty_value_errors += 1

        elif base_value.strip() and not target_value.strip():
            errors.append({"type": "blank_target_value", "key": key})
            empty_value_errors += 1

        # -- MessageFormat ---------------------------------------------------
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

        # Placeholders neutralised by an un-doubled apostrophe.
        base_effective = Counter(message_format_effective_tokens(base_value))
        target_effective = Counter(message_format_effective_tokens(target_value))

        lost = base_effective - target_effective

        if lost:
            errors.append(
                {
                    "type": "message_format_quote_loss",
                    "key": key,
                    "lost": sorted(lost.elements()),
                }
            )
            placeholder_errors += 1

        gained = target_effective - base_effective

        if gained:
            warnings.append(
                {
                    "type": "message_format_quote_gain",
                    "key": key,
                    "gained": sorted(gained.elements()),
                }
            )

        if target_message and unescaped_apostrophes(target_value):
            warnings.append(
                {"type": "unescaped_apostrophe_with_placeholder", "key": key}
            )

        # -- java.util.Formatter ---------------------------------------------
        base_printf = printf_tokens(base_value)
        target_printf = printf_tokens(target_value)

        if base_printf != target_printf:
            # Reordering is only safe when every specifier is positional.
            reorder_safe = (
                format_tokens_are_positional(base_printf)
                and Counter(base_printf) == Counter(target_printf)
            )

            if not reorder_safe:
                errors.append(
                    {
                        "type": "printf_mismatch",
                        "key": key,
                        "base": base_printf,
                        "target": target_printf,
                    }
                )
                placeholder_errors += 1

        # -- structural integrity ---------------------------------------------
        if brace_balance(base_value) != brace_balance(target_value):
            errors.append(
                {
                    "type": "brace_balance_mismatch",
                    "key": key,
                    "base": list(brace_balance(base_value)),
                    "target": list(brace_balance(target_value)),
                }
            )
            structural_errors += 1

        if base_value.count("\n") != target_value.count("\n"):
            errors.append(
                {
                    "type": "newline_count_mismatch",
                    "key": key,
                    "base": base_value.count("\n"),
                    "target": target_value.count("\n"),
                }
            )
            structural_errors += 1

        if base_value.count("\t") != target_value.count("\t"):
            errors.append(
                {
                    "type": "tab_count_mismatch",
                    "key": key,
                    "base": base_value.count("\t"),
                    "target": target_value.count("\t"),
                }
            )
            structural_errors += 1

        if REPLACEMENT_CHARACTER in target_value:
            errors.append({"type": "replacement_character", "key": key})
            structural_errors += 1

        control = DISALLOWED_CONTROL_RE.search(target_value)

        if control and not DISALLOWED_CONTROL_RE.search(base_value):
            errors.append(
                {
                    "type": "control_character",
                    "key": key,
                    "codepoint": f"U+{ord(control.group(0)):04X}",
                }
            )
            structural_errors += 1

        # -- cosmetic / linguistic warnings ------------------------------------
        if base_value == target_value and base_value.strip():
            identical_values += 1

        base_edges = (
            len(base_value) - len(base_value.lstrip()),
            len(base_value) - len(base_value.rstrip()),
        )
        target_edges = (
            len(target_value) - len(target_value.lstrip()),
            len(target_value) - len(target_value.rstrip()),
        )

        if base_edges != target_edges:
            warnings.append(
                {
                    "type": "edge_whitespace_changed",
                    "key": key,
                    "base": list(base_edges),
                    "target": list(target_edges),
                }
            )

        if "  " in target_value and "  " not in base_value:
            warnings.append({"type": "double_space_introduced", "key": key})

        for token in SUSPECT_TOKENS:
            if token in target_value and token not in base_value:
                warnings.append(
                    {"type": "suspect_marker", "key": key, "marker": token}
                )

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
        "structural_errors": structural_errors,
        "identical_values": identical_values,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a translated QuPath Java .properties bundle"
    )

    parser.add_argument("base", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument(
        "--show-warnings",
        action="store_true",
        help="List warnings in the console output",
    )

    args = parser.parse_args()

    try:
        base_raw = args.base.read_bytes()
        target_raw = args.target.read_bytes()

        if target_raw.startswith(b"\xef\xbb\xbf"):
            print(
                "ERROR: target bundle starts with a UTF-8 BOM",
                file=sys.stderr,
            )
            return 2

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
    print(f"Structural errors:       {report['structural_errors']}")
    print(f"Empty target values:     {report['empty_value_errors']}")
    print(f"Values identical to EN:  {report['identical_values']}")
    print(f"Total errors:            {report['error_count']}")
    print(f"Total warnings:          {report['warning_count']}")
    print(f"Result:                  {'PASS' if report['ok'] else 'FAIL'}")

    if report["errors"]:
        print("\nErrors:")
        for error in report["errors"][:50]:
            print(" ", json.dumps(error, ensure_ascii=False))

        if len(report["errors"]) > 50:
            print(
                f"  ... {len(report['errors']) - 50} additional errors omitted"
            )

    if args.show_warnings and report["warnings"]:
        print("\nWarnings:")
        for warning in report["warnings"][:50]:
            print(" ", json.dumps(warning, ensure_ascii=False))

        if len(report["warnings"]) > 50:
            print(
                f"  ... {len(report['warnings']) - 50} additional warnings "
                "omitted"
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
