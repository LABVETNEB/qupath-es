"""
Locale timing audit for an installed QuPath distribution.

Question it answers: when the display locale changes *after* the GUI has been
built, which bundle keys update and which stay frozen in the language they
were resolved in at construction time?

Method (read-only, bytecode constant pools):

  For every class in the QuPath jars, look for
    - a reference to QuPathResources.getString      -> static lookup
    - a reference to registerProperty/createProperty/
      LocalizedResourceManager, or an @ActionConfig/@ActionMenu/@Pref
      annotation                                    -> locale-bound property

  Then, for each key of the canonical bundle, find the classes whose constant
  pool contains that key literal and classify the key:

    DYNAMIC_LOCALE_BOUND   every referencing class binds properties
    STATIC_AT_CONSTRUCTION every referencing class only does a static lookup
    MIXED                  referenced from both kinds of class
    UNKNOWN                no class references the literal (key is built at
                           runtime by concatenation, or resolved from FXML)

STATIC_AT_CONSTRUCTION is the category a late locale switch cannot fix.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .coverage_audit import class_strings
    from .properties_audit import parse_properties
else:
    from coverage_audit import class_strings
    from properties_audit import parse_properties


STATIC_MARKERS = {"getString"}
STATIC_OWNER = "qupath/lib/gui/localization/QuPathResources"

DYNAMIC_MARKERS = {
    "registerProperty",
    "createProperty",
    "qupath/fx/localization/LocalizedResourceManager",
    "Lqupath/lib/gui/actions/annotations/ActionConfig;",
    "Lqupath/lib/gui/actions/annotations/ActionMenu;",
    "Lqupath/fx/prefs/annotations/Pref;",
    "Lqupath/fx/prefs/annotations/BooleanPref;",
    "Lqupath/fx/prefs/annotations/IntegerPref;",
    "Lqupath/fx/prefs/annotations/DoublePref;",
    "Lqupath/fx/prefs/annotations/StringPref;",
    "Lqupath/fx/prefs/annotations/ColorPref;",
    "Lqupath/fx/prefs/annotations/LocalePref;",
    "Lqupath/fx/prefs/annotations/DirectoryPref;",
    "Lqupath/fx/prefs/annotations/PrefCategory;",
}


def classify_class(strings: set[str]) -> str:
    static = STATIC_OWNER in strings and bool(STATIC_MARKERS & strings)
    dynamic = bool(DYNAMIC_MARKERS & strings)

    if dynamic and static:
        return "MIXED"
    if dynamic:
        return "DYNAMIC_LOCALE_BOUND"
    if static:
        return "STATIC_AT_CONSTRUCTION"
    return "NONE"


def audit(app_dir: Path, base_bundle: Path) -> dict:
    keys = [e.key for e in parse_properties(
        base_bundle.read_text(encoding="utf-8"))]
    key_set = set(keys)

    class_kind: dict[str, str] = {}
    key_classes: dict[str, set[str]] = defaultdict(set)

    for jar in sorted(app_dir.glob("qupath*.jar")):
        with zipfile.ZipFile(jar) as zf:
            for name in zf.namelist():
                if not name.endswith(".class"):
                    continue

                strings = set(class_strings(zf.read(name)))
                kind = classify_class(strings)
                label = f"{jar.name}::{name}"

                if kind != "NONE":
                    class_kind[label] = kind

                for literal in strings & key_set:
                    key_classes[literal].add(label)

    key_kind: dict[str, str] = {}

    for key in keys:
        refs = key_classes.get(key, set())
        kinds = {class_kind.get(ref, "NONE") for ref in refs}
        kinds.discard("NONE")

        if not kinds:
            key_kind[key] = "UNKNOWN"
        elif kinds == {"DYNAMIC_LOCALE_BOUND"}:
            key_kind[key] = "DYNAMIC_LOCALE_BOUND"
        elif kinds == {"STATIC_AT_CONSTRUCTION"}:
            key_kind[key] = "STATIC_AT_CONSTRUCTION"
        else:
            key_kind[key] = "MIXED"

    counts = Counter(key_kind.values())
    class_counts = Counter(class_kind.values())

    static_keys = sorted(k for k, v in key_kind.items()
                         if v == "STATIC_AT_CONSTRUCTION")
    mixed_keys = sorted(k for k, v in key_kind.items() if v == "MIXED")

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_dir": str(app_dir),
        "base_bundle": str(base_bundle),
        "total_keys": len(keys),
        "key_classification": dict(counts),
        "class_classification": dict(class_counts),
        "static_at_construction_keys": static_keys,
        "mixed_keys": mixed_keys,
        "classes_static_only": sorted(
            label for label, kind in class_kind.items()
            if kind == "STATIC_AT_CONSTRUCTION"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit which bundle keys are frozen at GUI construction"
    )
    parser.add_argument("app_dir", type=Path)
    parser.add_argument("base_bundle", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)

    args = parser.parse_args()

    try:
        report = audit(args.app_dir, args.base_bundle)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("Locale timing audit")
    print("-------------------")
    print(f"Total keys: {report['total_keys']}")
    print()
    print("Keys by classification:")
    for kind, count in sorted(report["key_classification"].items(),
                              key=lambda kv: -kv[1]):
        print(f"  {kind:<24} {count}")
    print()
    print("Classes by classification:")
    for kind, count in sorted(report["class_classification"].items(),
                              key=lambda kv: -kv[1]):
        print(f"  {kind:<24} {count}")
    print()
    print(f"STATIC_AT_CONSTRUCTION keys: "
          f"{len(report['static_at_construction_keys'])}")
    for key in report["static_at_construction_keys"][:40]:
        print(f"  {key}")
    print(f"\nJSON: {args.json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
