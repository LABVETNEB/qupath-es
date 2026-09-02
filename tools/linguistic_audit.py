"""
Linguistic and structural audit of the Spanish translation.

This runs *on top of* translation_validator.py.  The validator protects the
runtime contract (keys, placeholders, escapes); this tool looks for problems a
machine can spot in the Spanish text itself: dropped acronyms, glossary drift,
leftover English, broken Spanish punctuation, truncation, mojibake.

Errors block a release.  Warnings need human review but do not block.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .properties_audit import parse_properties
    from .translation_generator import decode_work_text, load_tsv
    from .translation_validator import (
        message_format_tokens,
        printf_tokens,
        validate_translation,
    )
else:
    from properties_audit import parse_properties
    from translation_generator import decode_work_text, load_tsv
    from translation_validator import (
        message_format_tokens,
        printf_tokens,
        validate_translation,
    )


# Acronyms and product names that must survive translation.
ACRONYMS = [
    "TMA", "RGB", "ROI", "DAB", "H&E", "H-DAB", "JSON", "GeoJSON",
    "URI", "URL", "SVG", "OME-TIFF", "OME-Zarr", "ImageJ", "Bio-Formats",
    "QuPath", "SLIC", "DoG", "Groovy", "GitHub", "OMERO", "Java",
    "ReadTheDocs", "YouTube", "Delaunay", "html", "markdown",
]

# EN term -> acceptable Spanish stems.  Checked only when the English value
# contains the term as a whole word.
GLOSSARY = {
    "annotation": ["anotaci"],
    "annotations": ["anotacion"],
    "detection": ["detecci"],
    "detections": ["deteccion"],
    "cell": ["célul", "celul"],
    "cells": ["célul", "celul"],
    "nucleus": ["núcle", "nucle"],
    "nuclei": ["núcle", "nucle"],
    "measurement": ["medici"],
    "measurements": ["medicion"],
    "classification": ["clasificaci"],
    "viewer": ["visor"],
    # 'proyecto' / 'proyeccion' - the shared stem is 'proyec'.
    "project": ["proyec"],
    "hierarchy": ["jerarqu"],
    "workflow": ["flujo de trabajo"],
    "overlay": ["superposici"],
    "opacity": ["opacidad"],
    "magnification": ["magnificaci"],
    "downsample": ["submuestre"],
    "scalebar": ["barra de escala"],
    "tile": ["tesela"],
    "tiles": ["tesela"],
    "brush": ["pincel"],
    "polygon": ["polígon", "poligon"],
    "polyline": ["polilíne", "poliline"],
    "rectangle": ["rectángul", "rectangul"],
    # 'elipse' / 'elíptica' - match the shared stem, not one inflection.
    "ellipse": ["elip"],
    "threshold": ["umbral"],
    "stain": ["tinci", "tinción"],
    "clipboard": ["portapapeles"],
    "thumbnail": ["miniatur"],
    "centroid": ["centroid"],
    "superpixel": ["superpíxel", "superpixel"],
    "preferences": ["preferencias"],
}

# English function words that should not survive in Spanish prose.
ENGLISH_LEAKS = [
    "the", "and", "with", "from", "this", "that", "which", "when",
    "your", "you", "will", "should", "cannot", "instead", "however",
]

TRUNCATION_TAILS = (
    " de", " del", " el", " la", " los", " las", " un", " una",
    " y", " o", " a", " en", " con", " que", " para", " por", ",",
)

# An English label may legitimately end in a preposition ("Sort by",
# "Switch to"), in which case the Spanish equivalent does too and is not
# truncated.
ENGLISH_TAILS = (
    " by", " to", " of", " for", " with", " from", " in", " on", " as", ",",
)

SUSPECT_LITERALS = ("TODO", "FIXME", "XXX", "null", "undefined")


def words(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z']+", text.lower()))


def deaccent(text: str) -> str:
    """Lowercase and strip diacritics, so glossary stems match inflections.

    Without this, the stem 'elip' fails to match 'eliptica' written with its
    accent ('elíptica'), producing permanent false positives.
    """
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def has_mojibake(text: str) -> bool:
    """Detect the classic UTF-8-read-as-Latin-1 signatures."""
    if "�" in text:
        return True

    for marker in ("Ã¡", "Ã©", "Ã­", "Ã³", "Ãº", "Ã±", "Â¿", "Â¡", "Âº", "Î¼"):
        if marker in text:
            return True

    return False


def audit(base_path: Path, tsv_path: Path, target_path: Path) -> dict:
    base_text = base_path.read_bytes().decode("utf-8", errors="strict")
    target_raw = target_path.read_bytes()
    target_text = target_raw.decode("utf-8", errors="strict")

    base_entries = parse_properties(base_text)
    rows = load_tsv(tsv_path)
    row_by_key = {row["key"]: row for row in rows}

    structural = validate_translation(base_text, target_text)

    errors: list[dict] = []
    warnings: list[dict] = []

    states = Counter(row["state"] for row in rows)

    # Structural findings are promoted verbatim.
    for error in structural["errors"]:
        errors.append({"check": "structural", **error})

    for warning in structural["warnings"]:
        warnings.append({"check": "structural", **warning})

    if target_raw.startswith(b"\xef\xbb\xbf"):
        errors.append({"check": "encoding", "type": "bom_present"})

    identical_without_keep_en = []

    for entry in base_entries:
        key = entry.key
        row = row_by_key.get(key)

        if row is None:
            errors.append({"check": "tsv", "type": "missing_tsv_row", "key": key})
            continue

        en = decode_work_text(row["en"])
        es = decode_work_text(row["es"])
        state = row["state"]

        # -- state hygiene ---------------------------------------------------
        if state in {"PENDING", "DRAFT"}:
            errors.append(
                {"check": "state", "type": "not_reviewed", "key": key,
                 "state": state}
            )

        if state == "BLOCKED":
            warnings.append(
                {"check": "state", "type": "blocked", "key": key,
                 "issues": row["issues"]}
            )

        if not es.strip():
            errors.append({"check": "value", "type": "empty", "key": key})
            continue

        if es == en and state != "KEEP_EN":
            identical_without_keep_en.append(key)
            errors.append(
                {"check": "value", "type": "identical_to_english_without_keep_en",
                 "key": key}
            )

        if state == "KEEP_EN" and es != en:
            errors.append(
                {"check": "state", "type": "keep_en_but_translated", "key": key}
            )

        # -- encoding --------------------------------------------------------
        if has_mojibake(es):
            errors.append({"check": "encoding", "type": "mojibake", "key": key})

        for ch in es:
            if unicodedata.category(ch) == "Cc" and ch not in "\t\n\r\f":
                errors.append(
                    {"check": "encoding", "type": "control_character",
                     "key": key, "codepoint": f"U+{ord(ch):04X}"}
                )
                break

        # -- placeholders (belt and braces on top of the validator) ----------
        if Counter(message_format_tokens(en)) != Counter(
            message_format_tokens(es)
        ):
            errors.append(
                {"check": "placeholder", "type": "message_format", "key": key}
            )

        if printf_tokens(en) != printf_tokens(es):
            errors.append(
                {"check": "placeholder", "type": "printf", "key": key}
            )

        if en.count("\\n") != es.count("\\n"):
            errors.append(
                {"check": "structure", "type": "escaped_newline_literal",
                 "key": key}
            )

        # -- acronyms --------------------------------------------------------
        for acronym in ACRONYMS:
            if acronym in en and acronym not in es:
                errors.append(
                    {"check": "acronym", "type": "dropped", "key": key,
                     "acronym": acronym}
                )

        # -- glossary --------------------------------------------------------
        en_words = words(en)
        es_folded = deaccent(es)

        for term, stems in GLOSSARY.items():
            if term in en_words and not any(
                deaccent(stem) in es_folded for stem in stems
            ):
                warnings.append(
                    {"check": "glossary", "type": "term_not_found", "key": key,
                     "term": term, "expected_any_of": stems}
                )

        # -- leftover English -------------------------------------------------
        if "http" not in es:
            leaks = sorted(words(es) & set(ENGLISH_LEAKS))

            if leaks:
                warnings.append(
                    {"check": "language", "type": "possible_english_leftover",
                     "key": key, "words": leaks}
                )

        # -- whitespace / punctuation ------------------------------------------
        if "  " in es and "  " not in en:
            warnings.append(
                {"check": "whitespace", "type": "double_space", "key": key}
            )

        if es != es.strip() and en == en.strip():
            warnings.append(
                {"check": "whitespace", "type": "edge_whitespace", "key": key}
            )

        stripped = es.rstrip()

        if stripped.endswith("?") and "¿" not in es:
            warnings.append(
                {"check": "punctuation", "type": "missing_opening_question",
                 "key": key}
            )

        if stripped.endswith("!") and "¡" not in es:
            warnings.append(
                {"check": "punctuation", "type": "missing_opening_exclamation",
                 "key": key}
            )

        if en.rstrip().endswith(".") and not stripped.endswith((".", "?", "!", "\"")):
            warnings.append(
                {"check": "punctuation", "type": "lost_final_period", "key": key}
            )

        # -- truncation ------------------------------------------------------
        en_stripped = en.rstrip()

        if (
            stripped.endswith(TRUNCATION_TAILS)
            and not en_stripped.endswith(TRUNCATION_TAILS)
            and not en_stripped.endswith(ENGLISH_TAILS)
        ):
            warnings.append(
                {"check": "quality", "type": "possible_truncation", "key": key}
            )

        for literal in SUSPECT_LITERALS:
            if literal in es and literal not in en:
                errors.append(
                    {"check": "quality", "type": "suspect_literal", "key": key,
                     "literal": literal}
                )

    keys = [entry.key for entry in base_entries]

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "qupath_version": "0.7.0",
        "base": str(base_path),
        "tsv": str(tsv_path),
        "target": str(target_path),
        "totals": {
            "total_keys": len(keys),
            "unique_keys": len(set(keys)),
            "duplicate_keys": len(keys) - len(set(keys)),
            "translated": states.get("REVIEWED", 0) + states.get("VERIFIED_UI", 0),
            "reviewed": states.get("REVIEWED", 0),
            "verified_ui": states.get("VERIFIED_UI", 0),
            "keep_en": states.get("KEEP_EN", 0),
            "blocked": states.get("BLOCKED", 0),
            "pending": states.get("PENDING", 0),
            "draft": states.get("DRAFT", 0),
        },
        "structural_checks": {
            "key_order_identical": structural["key_order_identical"],
            "missing_keys": len(structural["missing_keys"]),
            "extra_keys": len(structural["extra_keys"]),
            "placeholder_errors": structural["placeholder_errors"],
            "structural_errors": structural["structural_errors"],
            "empty_values": structural["empty_value_errors"],
        },
        "placeholder_checks": {
            "message_format_keys": sum(
                1 for e in base_entries if message_format_tokens(e.value)
            ),
            "printf_keys": sum(
                1 for e in base_entries if printf_tokens(e.value)
            ),
        },
        "identical_to_english": {
            "count": structural["identical_values"],
            "keep_en": states.get("KEEP_EN", 0),
            "without_keep_en": identical_without_keep_en,
        },
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "verdict": "SAFE TO INSTALL" if not errors else "DO NOT INSTALL",
    }

    return report


def write_markdown(report: dict, path: Path) -> None:
    t = report["totals"]
    s = report["structural_checks"]
    p = report["placeholder_checks"]

    warning_counts = Counter(
        f"{w['check']}/{w['type']}" for w in report["warnings"]
    )
    error_counts = Counter(
        f"{e['check']}/{e['type']}" for e in report["errors"]
    )

    lines = [
        "# QuPath ES - global translation audit",
        "",
        f"- Generated: `{report['generated']}`",
        f"- QuPath version: `{report['qupath_version']}`",
        f"- Base bundle: `{report['base']}`",
        f"- Target bundle: `{report['target']}`",
        "",
        "## Totals",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Total keys | {t['total_keys']} |",
        f"| Unique keys | {t['unique_keys']} |",
        f"| Duplicate keys | {t['duplicate_keys']} |",
        f"| REVIEWED | {t['reviewed']} |",
        f"| VERIFIED_UI | {t['verified_ui']} |",
        f"| KEEP_EN | {t['keep_en']} |",
        f"| BLOCKED | {t['blocked']} |",
        f"| PENDING | {t['pending']} |",
        f"| DRAFT | {t['draft']} |",
        "",
        "## Structural checks",
        "",
        "| Check | Value |",
        "| --- | --- |",
        f"| Key order identical | {s['key_order_identical']} |",
        f"| Missing keys | {s['missing_keys']} |",
        f"| Extra keys | {s['extra_keys']} |",
        f"| Placeholder errors | {s['placeholder_errors']} |",
        f"| Structural errors | {s['structural_errors']} |",
        f"| Empty values | {s['empty_values']} |",
        "",
        "## Placeholder checks",
        "",
        f"- Keys using MessageFormat `{{n}}`: {p['message_format_keys']}",
        f"- Keys using java.util.Formatter `%s`/`%d`: {p['printf_keys']}",
        "",
        "## Identical to English",
        "",
        f"- Total identical: {report['identical_to_english']['count']}",
        f"- Marked KEEP_EN: {report['identical_to_english']['keep_en']}",
        f"- Identical **without** KEEP_EN: "
        f"{len(report['identical_to_english']['without_keep_en'])}",
        "",
        "## Result",
        "",
        f"- Errors: **{report['error_count']}**",
        f"- Warnings: **{report['warning_count']}**",
        f"- Verdict: **{report['verdict']}**",
        "",
    ]

    if error_counts:
        lines += ["### Errors by type", "", "| Type | Count |", "| --- | --- |"]
        lines += [f"| `{k}` | {v} |" for k, v in error_counts.most_common()]
        lines.append("")

    if warning_counts:
        lines += [
            "### Warnings by type",
            "",
            "Warnings need human review but do not block a release.",
            "",
            "| Type | Count |",
            "| --- | --- |",
        ]
        lines += [f"| `{k}` | {v} |" for k, v in warning_counts.most_common()]
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Linguistic audit of the Spanish QuPath bundle"
    )
    parser.add_argument("base", type=Path)
    parser.add_argument("tsv", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--markdown", dest="md_path", type=Path, required=True)
    parser.add_argument(
        "--show",
        type=int,
        default=25,
        help="How many individual findings to print",
    )

    args = parser.parse_args()

    try:
        report = audit(args.base, args.tsv, args.target)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(report, args.md_path)

    t = report["totals"]

    print("Global translation audit")
    print("------------------------")
    print(f"Total keys:              {t['total_keys']}")
    print(f"REVIEWED:                {t['reviewed']}")
    print(f"KEEP_EN:                 {t['keep_en']}")
    print(f"BLOCKED:                 {t['blocked']}")
    print(f"PENDING:                 {t['pending']}")
    print(f"DRAFT:                   {t['draft']}")
    print(f"Errors:                  {report['error_count']}")
    print(f"Warnings:                {report['warning_count']}")
    print(f"Verdict:                 {report['verdict']}")

    if report["errors"]:
        print("\nErrors:")
        for error in report["errors"][: args.show]:
            print(" ", json.dumps(error, ensure_ascii=False))

    if report["warnings"]:
        print("\nWarning summary:")
        counts = Counter(
            f"{w['check']}/{w['type']}" for w in report["warnings"]
        )
        for name, count in counts.most_common():
            print(f"  {name:<45} {count}")

    print(f"\nJSON:     {args.json_path}")
    print(f"Markdown: {args.md_path}")

    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
