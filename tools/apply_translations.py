"""
Apply the reviewed Spanish translations to versions/<v>/work/translation.tsv.

The TSV is the project's source of truth: keys, order and the English column
are never modified here.  Only 'es' and the review metadata are written.

Leading/trailing whitespace is copied from the English source so that a
translator never has to think about it, and so the validator's
edge_whitespace_changed warning stays clean.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import sys
from pathlib import Path

if __package__:
    from .es_translations import KEEP_EN, TRANSLATIONS
    from .translation_generator import TSV_FIELDS, load_tsv
else:
    from es_translations import KEEP_EN, TRANSLATIONS
    from translation_generator import TSV_FIELDS, load_tsv

BATCH = "GLOBAL-ES-0.7.0"
REVIEWER = "Claude"
QUPATH_VERSION = "0.7.0"

WHITESPACE = " \t\f"


def leading_whitespace(value: str) -> str:
    i = 0
    while i < len(value) and value[i] in WHITESPACE:
        i += 1
    return value[:i]


def trailing_whitespace(value: str) -> str:
    i = len(value)
    while i > 0 and value[i - 1] in WHITESPACE:
        i -= 1
    return value[i:]


def align_whitespace(english: str, spanish: str) -> str:
    """Give the Spanish value the same edge whitespace as the English one."""
    core = spanish.strip(WHITESPACE)

    if not core:
        return spanish

    return leading_whitespace(english) + core + trailing_whitespace(english)


def apply(tsv_path: Path, rev_date: str) -> dict:
    rows = load_tsv(tsv_path)

    missing = [row["key"] for row in rows if row["key"] not in TRANSLATIONS]
    unknown = sorted(set(TRANSLATIONS) - {row["key"] for row in rows})

    if missing or unknown:
        raise ValueError(
            f"Translation table does not match the bundle: "
            f"{len(missing)} missing, {len(unknown)} unknown"
        )

    stats = {
        "rows": len(rows),
        "reviewed": 0,
        "keep_en": 0,
        "blocked": 0,
        "unchanged_from_english": 0,
    }

    for row in rows:
        key = row["key"]
        english = row["en"]
        spanish = align_whitespace(english, TRANSLATIONS[key])

        row["es"] = spanish
        row["batch"] = BATCH
        row["reviewer"] = REVIEWER
        row["rev_date"] = rev_date
        row["qupath_ver"] = QUPATH_VERSION
        row["issues"] = ""

        if key in KEEP_EN:
            row["state"] = "KEEP_EN"
            row["notes"] = "Deliberately identical to English"
            stats["keep_en"] += 1
        else:
            row["state"] = "REVIEWED"
            row["notes"] = ""
            stats["reviewed"] += 1

        if spanish == english:
            stats["unchanged_from_english"] += 1

    with tsv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=TSV_FIELDS,
            delimiter="\t",
            lineterminator="\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply Spanish translations to the working TSV"
    )
    parser.add_argument("tsv", type=Path)
    parser.add_argument(
        "--date",
        default=_dt.date.today().isoformat(),
        help="ISO review date (default: today)",
    )

    args = parser.parse_args()

    try:
        stats = apply(args.tsv, args.date)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("Applied Spanish translations")
    print("----------------------------")
    for name, value in stats.items():
        print(f"{name:<28} {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
