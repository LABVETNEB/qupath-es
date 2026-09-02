from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PropertyEntry:
    key: str
    value: str
    logical_line: str
    start_line: int
    end_line: int


class PropertiesParseError(ValueError):
    pass


def has_odd_trailing_backslashes(text: str) -> bool:
    count = 0
    for ch in reversed(text):
        if ch != "\\":
            break
        count += 1
    return count % 2 == 1


def logical_lines(text: str):
    physical = text.splitlines()

    i = 0
    while i < len(physical):
        start = i + 1
        current = physical[i]

        while has_odd_trailing_backslashes(current):
            current = current[:-1]
            i += 1

            if i >= len(physical):
                raise PropertiesParseError(
                    f"Continuation at EOF beginning on physical line {start}"
                )

            continuation = physical[i].lstrip(" \t\f")
            current += continuation

        yield start, i + 1, current
        i += 1


def java_unescape(text: str, line_number: int) -> str:
    out = []
    i = 0

    while i < len(text):
        ch = text[i]

        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        i += 1

        if i >= len(text):
            raise PropertiesParseError(
                f"Dangling backslash on logical entry beginning line {line_number}"
            )

        esc = text[i]

        if esc == "t":
            out.append("\t")
        elif esc == "n":
            out.append("\n")
        elif esc == "r":
            out.append("\r")
        elif esc == "f":
            out.append("\f")
        elif esc == "u":
            if i + 4 >= len(text):
                raise PropertiesParseError(
                    f"Incomplete Unicode escape on line {line_number}"
                )

            hexpart = text[i + 1:i + 5]

            if not re.fullmatch(r"[0-9A-Fa-f]{4}", hexpart):
                raise PropertiesParseError(
                    f"Invalid Unicode escape \\u{hexpart} on line {line_number}"
                )

            out.append(chr(int(hexpart, 16)))
            i += 4
        else:
            # Java Properties removes the escape slash for other escaped chars.
            out.append(esc)

        i += 1

    return "".join(out)


def split_key_value(line: str, line_number: int):
    length = len(line)
    i = 0

    while i < length and line[i] in " \t\f":
        i += 1

    if i >= length:
        return None

    if line[i] in "#!":
        return None

    key_start = i
    escaped = False
    separator_index = None
    separator_kind = None

    while i < length:
        ch = line[i]

        if ch == "\\":
            escaped = not escaped
            i += 1
            continue

        if not escaped:
            if ch in "=:":
                separator_index = i
                separator_kind = ch
                break

            if ch in " \t\f":
                separator_index = i
                separator_kind = "whitespace"
                break

        escaped = False
        i += 1

    if separator_index is None:
        raw_key = line[key_start:]
        raw_value = ""
    else:
        raw_key = line[key_start:separator_index]
        i = separator_index

        if separator_kind == "whitespace":
            while i < length and line[i] in " \t\f":
                i += 1

            if i < length and line[i] in "=:":
                i += 1
        else:
            i += 1

        while i < length and line[i] in " \t\f":
            i += 1

        raw_value = line[i:]

    key = java_unescape(raw_key, line_number)
    value = java_unescape(raw_value, line_number)

    return key, value


def parse_properties(text: str):
    entries = []

    for start, end, logical in logical_lines(text):
        parsed = split_key_value(logical, start)

        if parsed is None:
            continue

        key, value = parsed

        entries.append(
            PropertyEntry(
                key=key,
                value=value,
                logical_line=logical,
                start_line=start,
                end_line=end,
            )
        )

    return entries


MESSAGE_FORMAT_RE = re.compile(r"(?<!\{)\{(\d+)(?:,[^{}]+)?\}(?!\})")

PRINTF_RE = re.compile(
    r"%(?:\d+\$)?[-#+ 0,(<]*\d*(?:\.\d+)?[tT]?[a-zA-Z%]"
)


def main():
    parser = argparse.ArgumentParser(
        description="Audit a Java .properties localization bundle"
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)

    args = parser.parse_args()

    try:
        raw = args.file.read_bytes()
        text = raw.decode("utf-8", errors="strict")
        entries = parse_properties(text)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    keys = [entry.key for entry in entries]
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)

    continuation_entries = sum(
        1 for entry in entries if entry.end_line > entry.start_line
    )

    message_format_entries = [
        entry.key
        for entry in entries
        if MESSAGE_FORMAT_RE.search(entry.value)
    ]

    printf_entries = [
        entry.key
        for entry in entries
        if PRINTF_RE.search(entry.value)
        and "%%" not in entry.value
    ]

    report = {
        "file": str(args.file),
        "bytes": len(raw),
        "physical_lines": len(text.splitlines()),
        "entries": len(entries),
        "unique_keys": len(set(keys)),
        "duplicate_keys": duplicates,
        "duplicate_key_count": len(duplicates),
        "entries_with_physical_continuation": continuation_entries,
        "message_format_entries": len(message_format_entries),
        "printf_candidate_entries": len(printf_entries),
    }

    print("Java .properties audit")
    print("----------------------")
    print(f"File:                         {report['file']}")
    print(f"Bytes:                        {report['bytes']}")
    print(f"Physical lines:               {report['physical_lines']}")
    print(f"Parsed entries:               {report['entries']}")
    print(f"Unique keys:                  {report['unique_keys']}")
    print(f"Duplicate keys:               {report['duplicate_key_count']}")
    print(
        "Entries with continuation:   "
        f"{report['entries_with_physical_continuation']}"
    )
    print(
        "MessageFormat candidates:    "
        f"{report['message_format_entries']}"
    )
    print(
        "printf candidates:           "
        f"{report['printf_candidate_entries']}"
    )

    if duplicates:
        print("\nDUPLICATES:")
        for key in duplicates:
            print(f"  {key}")

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\nReport written: {args.json_path}")

    return 1 if duplicates else 0


if __name__ == "__main__":
    raise SystemExit(main())
