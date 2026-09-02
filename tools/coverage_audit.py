"""
Read-only localization coverage audit of an installed QuPath distribution.

Answers the question the main-bundle numbers cannot: once every key of
qupath-gui-strings.properties is translated, how much of the *application*
is actually in Spanish?

Evidence comes from the installed JARs themselves (a JAR is a ZIP), never
from the QuPath source tree, so the numbers describe the exact binary that
runs on this machine.

Categories
    MAIN_BUNDLE    qupath-gui-strings.properties - covered by this project
    OTHER_BUNDLE   another ResourceBundle - needs its own _es file
    EXTENSION      shipped extension jar
    FXML           FXML views ('%key' is localised, literal text is not)
    HARDCODED      prose string constants compiled into .class files
    PARAMETERLIST  hardcoded strings in analysis parameter dialogs
    UNSUPPORTED    third-party UI text outside QuPath's control
"""
from __future__ import annotations

import argparse
import io
import json
import re
import struct
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MAIN_BUNDLE = "qupath/lib/gui/localization/qupath-gui-strings.properties"

PARAMETER_MARKERS = (
    "addDoubleParameter", "addIntParameter", "addBooleanParameter",
    "addChoiceParameter", "addStringParameter", "addTitleParameter",
    "addEmptyParameter",
)

CONSTANT_UTF8 = 1
CONSTANT_SIZES = {
    3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
    15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2,
}


def class_strings(data: bytes) -> list[str]:
    """Extract the UTF-8 constant pool of a .class file."""
    if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
        return []

    count = struct.unpack(">H", data[8:10])[0]
    out: list[str] = []
    i = 10
    index = 1

    while index < count:
        if i >= len(data):
            break

        tag = data[i]
        i += 1

        if tag == CONSTANT_UTF8:
            if i + 2 > len(data):
                break
            length = struct.unpack(">H", data[i:i + 2])[0]
            i += 2
            raw = data[i:i + length]
            i += length
            try:
                out.append(raw.decode("utf-8", errors="replace"))
            except Exception:
                pass
        else:
            size = CONSTANT_SIZES.get(tag)
            if size is None:
                break
            i += size
            if tag in (5, 6):        # long / double take two pool slots
                index += 1

        index += 1

    return out


PROSE_RE = re.compile(r"^[A-Z][A-Za-z0-9'&/,.:()\-]*(?: [A-Za-z0-9'&/,.:()\-]+)+")


def is_prose(text: str) -> bool:
    """Conservative: a capitalised multi-word phrase that is not an identifier."""
    t = text.strip()

    if len(t) < 8 or len(t) > 400:
        return False
    if "\n" in t or "\t" in t:
        return False
    if t.startswith(("-fx-", "http", "/", ".", "#", "(", "[", "<")):
        return False
    if "/" in t and " " not in t:
        return False
    if re.search(r"[();{}]\s*$", t) and " " not in t:
        return False
    if re.fullmatch(r"[A-Za-z0-9_$./;()\[\]<>]+", t):     # descriptor or FQN
        return False
    if "()" in t or "$" in t or "::" in t:
        return False
    if t.count(" ") < 1:
        return False
    return bool(PROSE_RE.match(t))


def audit_jar(path: Path) -> dict:
    info = {
        "jar": path.name,
        "bundles": [],
        "fxml": [],
        "classes": 0,
        "prose_strings": 0,
        "parameterlist_classes": 0,
        "parameterlist_prose": 0,
    }

    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.endswith(".properties") and "/localization/" not in name:
                if "META-INF" in name:
                    continue
                info["bundles"].append(name)
            elif name.endswith(".properties"):
                info["bundles"].append(name)
            elif name.endswith(".fxml"):
                text = zf.read(name).decode("utf-8", errors="replace")
                keys = len(re.findall(r'"%[A-Za-z][\w.]*"', text))
                literals = len(
                    re.findall(r'(?:text|promptText)="(?!%)[^"]{2,}"', text)
                )
                info["fxml"].append(
                    {"path": name, "localized_refs": keys,
                     "literal_texts": literals}
                )
            elif name.endswith(".class"):
                info["classes"] += 1
                strings = class_strings(zf.read(name))
                prose = [s for s in strings if is_prose(s)]
                info["prose_strings"] += len(prose)

                if any(m in strings for m in PARAMETER_MARKERS):
                    info["parameterlist_classes"] += 1
                    info["parameterlist_prose"] += len(prose)

    return info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit localization coverage of an installed QuPath"
    )
    parser.add_argument("app_dir", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--main-bundle-keys", type=int, required=True)

    args = parser.parse_args()

    jars = sorted(args.app_dir.glob("qupath*.jar"))

    if not jars:
        print(f"ERROR: no qupath*.jar under {args.app_dir}", file=sys.stderr)
        return 2

    results = [audit_jar(jar) for jar in jars]

    main_bundle_jar = None
    other_bundles = []

    for jar, result in zip(jars, results):
        for bundle in result["bundles"]:
            if bundle == MAIN_BUNDLE:
                main_bundle_jar = jar.name
            elif bundle.endswith("_en.properties"):
                other_bundles.append(
                    {"jar": jar.name, "path": bundle, "role": "english_marker"}
                )
            else:
                other_bundles.append(
                    {"jar": jar.name, "path": bundle, "role": "resource_bundle"}
                )

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_dir": str(args.app_dir),
        "jars_scanned": len(jars),
        "main_bundle": {
            "path": MAIN_BUNDLE,
            "jar": main_bundle_jar,
            "keys": args.main_bundle_keys,
            "translated": args.main_bundle_keys,
        },
        "other_bundles": other_bundles,
        "fxml": [
            {"jar": r["jar"], **f} for r in results for f in r["fxml"]
        ],
        "per_jar": results,
        "totals": {
            "classes": sum(r["classes"] for r in results),
            "prose_strings": sum(r["prose_strings"] for r in results),
            "parameterlist_classes": sum(
                r["parameterlist_classes"] for r in results
            ),
            "parameterlist_prose": sum(
                r["parameterlist_prose"] for r in results
            ),
        },
    }

    args.json_path.parent.mkdir(parents=True, exist_ok=True)
    args.json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("Localization coverage audit")
    print("---------------------------")
    print(f"JARs scanned:              {report['jars_scanned']}")
    print(f"Main bundle jar:           {main_bundle_jar}")
    print(f"Main bundle keys:          {args.main_bundle_keys}")
    print(f"Other resource bundles:    {len(other_bundles)}")
    print(f"FXML views:                {len(report['fxml'])}")
    print(f"Classes scanned:           {report['totals']['classes']}")
    print(f"Prose string constants:    {report['totals']['prose_strings']}")
    print(
        f"ParameterList classes:     "
        f"{report['totals']['parameterlist_classes']}"
    )
    print(
        f"  prose in those classes:  "
        f"{report['totals']['parameterlist_prose']}"
    )
    print()
    print("Other bundles:")
    for bundle in other_bundles:
        print(f"  {bundle['jar']:<40} {bundle['path']}")
    print()
    print("FXML:")
    for f in report["fxml"]:
        print(
            f"  {f['jar']:<40} {f['path']}  "
            f"%keys={f['localized_refs']} literal={f['literal_texts']}"
        )
    print(f"\nJSON: {args.json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
