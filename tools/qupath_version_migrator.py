"""
Version-aware migration engine for the QuPath Spanish localization.

This is the deterministic half of the updater: it detects installations,
captures canonical bundles, and migrates a translation from one QuPath version
to the next.  It never edits a QuPath installation - `runtime/update-qupath-es.ps1`
owns every write outside this repository.

Nothing here guesses at Spanish.  A translation is reused only when the English
source, the placeholder signature and the structural signature are all
identical; anything else is handed to a human with a reason attached.

Subcommands
    detect    find QuPath installations and identify their versions
    capture   extract a version's canonical bundle into versions/<v>/base/
    migrate   build versions/<new>/work/translation.tsv from an older version
    status    report whether a version is releasable
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .properties_audit import parse_properties
    from .translation_generator import (
        TSV_FIELDS,
        decode_work_text,
        encode_work_text,
        load_tsv,
    )
    from .translation_validator import (
        message_format_tokens,
        printf_tokens,
        validate_translation,
    )
else:
    from properties_audit import parse_properties
    from translation_generator import (
        TSV_FIELDS,
        decode_work_text,
        encode_work_text,
        load_tsv,
    )
    from translation_validator import (
        message_format_tokens,
        printf_tokens,
        validate_translation,
    )


BUNDLE_IN_JAR = "qupath/lib/gui/localization/qupath-gui-strings.properties"
ENGLISH_STUB_IN_JAR = (
    "qupath/lib/gui/localization/qupath-gui-strings_en.properties"
)
GUI_JAR_GLOB = "qupath-gui-fx-*.jar"

SCHEMA_VERSION = 2

# Strings that were hardcoded in QuPath 0.7.0 and externalised later.  When a
# new version introduces a key carrying one of these English values we can
# offer the Spanish wording we already know - as a *suggestion* only.  The
# entry still lands as PENDING; a human decides.
KNOWN_HARDCODED_SUGGESTIONS = {
    "Image list": "Lista de imágenes",
    "Search entry in project": "Buscar entrada en el proyecto",
    "Drag & drop an image file or project folder":
        "Arrastre y suelte un archivo de imagen o una carpeta de proyecto",
}


class MigrationError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def placeholder_signature(value: str) -> tuple:
    """What the runtime will substitute into this string.

    MessageFormat arguments may be reordered by a translator, so they are
    compared as a multiset; java.util.Formatter specifiers are positional
    unless explicitly indexed, so their order is part of the signature.
    """
    return (
        tuple(sorted(Counter(message_format_tokens(value)).items())),
        tuple(printf_tokens(value)),
    )


def structural_signature(value: str) -> tuple:
    """Layout-bearing features a translation must preserve."""
    return (
        value.count("\n"),
        value.count("\t"),
        value.count("{"),
        value.count("}"),
    )


def read_bundle_entries(text: str) -> dict[str, str]:
    return {e.key: e.value for e in parse_properties(text)}


def bundle_key_order(text: str) -> list[str]:
    return [e.key for e in parse_properties(text)]


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------

def read_manifest(jar: Path) -> dict[str, str]:
    try:
        with zipfile.ZipFile(jar) as zf:
            raw = zf.read("META-INF/MANIFEST.MF")
    except (KeyError, zipfile.BadZipFile, OSError):
        return {}

    attrs: dict[str, str] = {}

    for line in raw.decode("utf-8", errors="replace").splitlines():
        if ":" in line and not line.startswith(" "):
            name, _, value = line.partition(":")
            attrs[name.strip()] = value.strip()

    return attrs


def inspect_installation(root: Path) -> dict:
    """Identify a QuPath installation without trusting its directory name."""
    info = {
        "path": str(root),
        "directory_name": root.name,
        "valid": False,
        "version": None,
        "version_sources": {},
        "gui_jar": None,
        "gui_jar_sha256": None,
        "build_time": None,
        "latest_commit": None,
        "bundle_present": False,
        "problems": [],
    }

    app = root / "app"

    if not app.is_dir():
        info["problems"].append("no app/ directory")
        return info

    jars = sorted(app.glob(GUI_JAR_GLOB))

    if not jars:
        info["problems"].append(f"no {GUI_JAR_GLOB} in app/")
        return info

    if len(jars) > 1:
        info["problems"].append(
            "multiple gui jars: " + ", ".join(j.name for j in jars)
        )
        return info

    jar = jars[0]
    info["gui_jar"] = str(jar)
    info["gui_jar_sha256"] = sha256_upper(jar.read_bytes())

    # Source 1: the jar file name.
    match = re.match(r"qupath-gui-fx-(.+)\.jar$", jar.name)
    if match:
        info["version_sources"]["jar_name"] = match.group(1)

    # Source 2: the jar manifest - authoritative.
    attrs = read_manifest(jar)
    if attrs.get("Implementation-Version"):
        info["version_sources"]["manifest"] = attrs["Implementation-Version"]
    info["build_time"] = attrs.get("QuPath-build-time")
    info["latest_commit"] = attrs.get("QuPath-latest-commit")

    # Source 3: the directory name, used only for cross-checking.
    dir_match = re.match(r"QuPath[-_ ]v?(.+)$", root.name)
    if dir_match:
        info["version_sources"]["directory_name"] = dir_match.group(1)

    try:
        with zipfile.ZipFile(jar) as zf:
            info["bundle_present"] = BUNDLE_IN_JAR in zf.namelist()
    except (zipfile.BadZipFile, OSError) as exc:
        # A truncated download or a partially written jar must be reported,
        # not raised: the updater has to keep going and describe the problem.
        info["problems"].append(f"gui jar is not readable as a zip: {exc}")
        return info

    if not info["bundle_present"]:
        info["problems"].append(f"{BUNDLE_IN_JAR} not found in gui jar")

    manifest_version = info["version_sources"].get("manifest")
    jar_version = info["version_sources"].get("jar_name")

    if manifest_version:
        info["version"] = manifest_version
    elif jar_version:
        info["version"] = jar_version
        info["problems"].append("manifest has no Implementation-Version")
    else:
        info["problems"].append("version could not be determined")
        return info

    if jar_version and manifest_version and jar_version != manifest_version:
        info["problems"].append(
            f"jar name says {jar_version}, manifest says {manifest_version}"
        )

    info["valid"] = info["bundle_present"] and bool(info["version"])
    return info


def detect_installations(search_roots: list[Path]) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    for root in search_roots:
        if not root.is_dir():
            continue

        candidates = []

        if (root / "app").is_dir():
            candidates.append(root)
        else:
            candidates.extend(sorted(p for p in root.glob("QuPath*") if p.is_dir()))

        for candidate in candidates:
            resolved = str(candidate.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(inspect_installation(candidate))

    return found


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def capture_bundle(install: dict, repo: Path, force: bool = False) -> dict:
    if not install.get("valid"):
        raise MigrationError(
            f"installation is not usable: {install.get('problems')}"
        )

    version = install["version"]
    version_dir = repo / "versions" / version
    base_dir = version_dir / "base"
    fingerprint_path = version_dir / "fingerprint.json"

    existing = base_dir / "qupath-gui-strings.properties"

    if existing.is_file() and not force:
        raise MigrationError(
            f"versions/{version}/base already exists; captured bundles are "
            f"immutable. Re-run with --force only if you know it is wrong."
        )

    jar = Path(install["gui_jar"])

    with zipfile.ZipFile(jar) as zf:
        bundle_bytes = zf.read(BUNDLE_IN_JAR)
        manifest_bytes = zf.read("META-INF/MANIFEST.MF")
        try:
            stub_bytes = zf.read(ENGLISH_STUB_IN_JAR)
        except KeyError:
            stub_bytes = None

    text = bundle_bytes.decode("utf-8", errors="strict")
    entries = parse_properties(text)
    keys = [e.key for e in entries]
    duplicates = sorted(k for k, c in Counter(keys).items() if c > 1)

    base_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("work", "dist", "reports", "runtime"):
        (version_dir / sub).mkdir(parents=True, exist_ok=True)

    existing.write_bytes(bundle_bytes)
    (base_dir / "MANIFEST.MF").write_bytes(manifest_bytes)
    if stub_bytes is not None:
        (base_dir / "qupath-gui-strings_en.properties").write_bytes(stub_bytes)

    fingerprint = {
        "schema_version": SCHEMA_VERSION,
        "captured": now_iso(),
        "qupath": {
            "version": version,
            "implementation_version":
                install["version_sources"].get("manifest"),
            "build_time": install.get("build_time"),
            "latest_commit": install.get("latest_commit"),
        },
        "source": {
            "installation_root": install["path"],
            "jar": install["gui_jar"],
            "jar_sha256": install["gui_jar_sha256"],
            "bundle_path_in_jar": BUNDLE_IN_JAR,
        },
        "artifacts": {
            "root_bundle": {
                "path": "base/qupath-gui-strings.properties",
                "bytes": len(bundle_bytes),
                "sha256": sha256_upper(bundle_bytes),
                "encoding": "UTF-8",
                "physical_lines": len(text.replace("\r\n", "\n").split("\n")),
                "parsed_entries": len(entries),
                "unique_keys": len(set(keys)),
                "duplicate_keys": len(duplicates),
            },
            "manifest": {
                "path": "base/MANIFEST.MF",
                "bytes": len(manifest_bytes),
                "sha256": sha256_upper(manifest_bytes),
            },
        },
        "base_files_policy": "IMMUTABLE",
    }

    if stub_bytes is not None:
        fingerprint["artifacts"]["english_stub"] = {
            "path": "base/qupath-gui-strings_en.properties",
            "bytes": len(stub_bytes),
            "sha256": sha256_upper(stub_bytes),
        }

    fingerprint_path.write_text(
        json.dumps(fingerprint, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if duplicates:
        fingerprint["duplicate_key_names"] = duplicates

    return fingerprint


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

def classify_entry(old_row: dict | None, old_en: str | None,
                   new_en: str, key: str) -> dict:
    """Decide what happens to one key of the new bundle."""
    if old_row is None:
        suggestion = KNOWN_HARDCODED_SUGGESTIONS.get(new_en.strip())

        return {
            "case": "C_NEW",
            "state": "PENDING",
            "es": new_en,
            "issues": "NEW_KEY",
            "notes": (
                f"Suggestion from 0.7.0 hardcoded string: {suggestion}"
                if suggestion else ""
            ),
            "suggestion": suggestion,
        }

    old_es = decode_work_text(old_row["es"])
    old_state = old_row["state"]

    placeholder_changed = (
        placeholder_signature(old_en) != placeholder_signature(new_en)
    )
    structure_changed = (
        structural_signature(old_en) != structural_signature(new_en)
    )
    source_changed = old_en != new_en

    if not source_changed:
        # Case A / E: English is byte-identical, so the translation still fits.
        if old_state == "KEEP_EN":
            return {
                "case": "E_KEEP_EN",
                "state": "KEEP_EN",
                "es": old_es,
                "issues": "",
                "notes": "Migrated unchanged; deliberately identical to English",
            }

        if old_state in {"REVIEWED", "VERIFIED_UI"}:
            return {
                "case": "A_REUSE",
                "state": "REVIEWED",
                "es": old_es,
                "issues": "",
                "notes": "Migrated unchanged from previous version",
            }

        # It was not finished before; it is still not finished.
        return {
            "case": "A_REUSE_UNFINISHED",
            "state": old_state if old_state in {"PENDING", "DRAFT", "BLOCKED"}
            else "DRAFT",
            "es": old_es,
            "issues": old_row.get("issues", ""),
            "notes": "Migrated unchanged, but was not reviewed before",
        }

    # From here the English source changed.
    issues = ["SOURCE_CHANGED"]
    case = "B_SOURCE_CHANGED"
    state = "DRAFT"

    if placeholder_changed:
        issues.append("PLACEHOLDER_SIGNATURE_CHANGED")
        case = "F_PLACEHOLDER_CHANGED"
        state = "BLOCKED"

    if structure_changed:
        issues.append("STRUCTURE_CHANGED")
        if case != "F_PLACEHOLDER_CHANGED":
            case = "G_STRUCTURE_CHANGED"
        state = "BLOCKED"

    if old_state == "KEEP_EN":
        # The reason for keeping English may no longer hold.
        issues.append("KEEP_EN_NEEDS_REVIEW")
        case = "E_KEEP_EN_SOURCE_CHANGED"
        state = "DRAFT" if state == "DRAFT" else state

    return {
        "case": case,
        "state": state,
        "es": old_es,
        "issues": ";".join(issues),
        "notes": "Previous translation kept as a reference only - re-review",
    }


def migrate(repo: Path, old_version: str, new_version: str,
            reviewer: str = "migrator", force: bool = False) -> dict:
    old_dir = repo / "versions" / old_version
    new_dir = repo / "versions" / new_version

    old_base = old_dir / "base" / "qupath-gui-strings.properties"
    old_tsv = old_dir / "work" / "translation.tsv"
    new_base = new_dir / "base" / "qupath-gui-strings.properties"
    new_tsv = new_dir / "work" / "translation.tsv"

    for path in (old_base, old_tsv, new_base):
        if not path.is_file():
            raise MigrationError(f"required file missing: {path}")

    if new_tsv.is_file() and not force:
        raise MigrationError(
            f"{new_tsv} already exists; refusing to overwrite a translation "
            f"in progress. Re-run with --force to rebuild it."
        )

    old_text = old_base.read_bytes().decode("utf-8", errors="strict")
    new_bytes = new_base.read_bytes()
    new_text = new_bytes.decode("utf-8", errors="strict")

    old_entries = read_bundle_entries(old_text)
    new_entries_list = parse_properties(new_text)
    new_keys = [e.key for e in new_entries_list]
    new_entries = {e.key: e.value for e in new_entries_list}

    old_rows = {row["key"]: row for row in load_tsv(old_tsv)}

    today = datetime.now().date().isoformat()

    rows: list[dict] = []
    detail: list[dict] = []
    case_counts: Counter = Counter()

    for key in new_keys:
        new_en = new_entries[key]
        old_row = old_rows.get(key)
        old_en = old_entries.get(key)

        # A key can exist in the old TSV but not in the old bundle only if the
        # workspace drifted; treat it as new.
        if old_row is not None and old_en is None:
            old_row = None

        decision = classify_entry(old_row, old_en, new_en, key)
        case_counts[decision["case"]] += 1

        rows.append({
            "key": key,
            "en": encode_work_text(new_en),
            "es": encode_work_text(decision["es"]),
            "state": decision["state"],
            "batch": f"MIGRATED-{old_version}-TO-{new_version}",
            "reviewer": reviewer if decision["state"] in
            {"REVIEWED", "KEEP_EN"} else "",
            "rev_date": today if decision["state"] in
            {"REVIEWED", "KEEP_EN"} else "",
            "qupath_ver": new_version,
            "issues": decision["issues"],
            "notes": decision["notes"],
        })

        if decision["case"] not in {"A_REUSE", "E_KEEP_EN"}:
            record = {
                "key": key,
                "case": decision["case"],
                "state": decision["state"],
                "issues": decision["issues"],
                "new_en": new_en,
            }
            if old_en is not None:
                record["old_en"] = old_en
            if decision.get("suggestion"):
                record["suggestion"] = decision["suggestion"]
            detail.append(record)

    removed = sorted(set(old_rows) - set(new_keys))

    # Write the new working TSV.
    new_tsv.parent.mkdir(parents=True, exist_ok=True)
    with new_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=TSV_FIELDS, delimiter="\t",
            lineterminator="\n", quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        writer.writerows(rows)

    # Archive removed keys so a later version that reinstates one can reuse it.
    if removed:
        retired = new_dir / "work" / "retired.tsv"
        with retired.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=TSV_FIELDS, delimiter="\t",
                lineterminator="\n", quoting=csv.QUOTE_MINIMAL,
            )
            writer.writeheader()
            for key in removed:
                writer.writerow(old_rows[key])

    reusable = case_counts["A_REUSE"] + case_counts["E_KEEP_EN"]
    total = len(new_keys)

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated": now_iso(),
        "old_version": old_version,
        "new_version": new_version,
        "old_bundle_sha256": sha256_upper(old_base.read_bytes()),
        "new_bundle_sha256": sha256_upper(new_bytes),
        "old_keys": len(old_entries),
        "new_keys": total,
        "cases": dict(case_counts),
        "counts": {
            "auto_reused": reusable,
            "keep_en_migrated": case_counts["E_KEEP_EN"],
            "source_changed": case_counts["B_SOURCE_CHANGED"]
            + case_counts["E_KEEP_EN_SOURCE_CHANGED"],
            "placeholder_changed": case_counts["F_PLACEHOLDER_CHANGED"],
            "structure_changed": case_counts["G_STRUCTURE_CHANGED"],
            "new_keys": case_counts["C_NEW"],
            "removed_keys": len(removed),
            "requires_review": total - reusable,
            "blocked": case_counts["F_PLACEHOLDER_CHANGED"]
            + case_counts["G_STRUCTURE_CHANGED"],
        },
        "safe_migration_percent": round(100.0 * reusable / total, 1)
        if total else 0.0,
        "removed_key_names": removed,
        "entries_requiring_attention": detail,
        "outputs": {
            "translation_tsv": str(new_tsv),
            "retired_tsv": str(new_dir / "work" / "retired.tsv")
            if removed else None,
        },
    }

    reports_dir = new_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / f"migration-from-{old_version}.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    md_path = reports_dir / f"migration-from-{old_version}.md"
    md_path.write_text(render_migration_markdown(report), encoding="utf-8",
                       newline="\n")

    report["outputs"]["report_json"] = str(json_path)
    report["outputs"]["report_markdown"] = str(md_path)

    return report


def render_migration_markdown(report: dict) -> str:
    c = report["counts"]
    lines = [
        f"# Migration {report['old_version']} -> {report['new_version']}",
        "",
        f"- Generated: `{report['generated']}`",
        f"- Old bundle SHA-256: `{report['old_bundle_sha256']}`",
        f"- New bundle SHA-256: `{report['new_bundle_sha256']}`",
        "",
        "## Key counts",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Keys in {report['old_version']} | {report['old_keys']} |",
        f"| Keys in {report['new_version']} | {report['new_keys']} |",
        f"| Automatically reusable | {c['auto_reused']} |",
        f"| KEEP_EN migrated | {c['keep_en_migrated']} |",
        f"| English source changed | {c['source_changed']} |",
        f"| Placeholder signature changed | {c['placeholder_changed']} |",
        f"| Structure changed | {c['structure_changed']} |",
        f"| New keys | {c['new_keys']} |",
        f"| Removed keys | {c['removed_keys']} |",
        f"| Blocked | {c['blocked']} |",
        f"| Requiring review | {c['requires_review']} |",
        "",
        f"**Safe automatic migration: {report['safe_migration_percent']}%**",
        "",
        "A translation is reused only when the English source, the placeholder",
        "signature and the structural signature are all unchanged. Everything",
        "else is carried over as a reference and marked for review.",
        "",
        "## Cases",
        "",
        "| Case | Count | Meaning |",
        "| --- | --- | --- |",
    ]

    meanings = {
        "A_REUSE": "English unchanged, previous translation reused",
        "A_REUSE_UNFINISHED": "English unchanged, but was not reviewed before",
        "B_SOURCE_CHANGED": "English text changed - re-review",
        "C_NEW": "New key - not translated",
        "E_KEEP_EN": "Deliberately English, carried over",
        "E_KEEP_EN_SOURCE_CHANGED": "Was KEEP_EN, English changed - re-check",
        "F_PLACEHOLDER_CHANGED": "Placeholder signature changed - blocked",
        "G_STRUCTURE_CHANGED": "Escapes/structure changed - blocked",
    }

    for case, count in sorted(report["cases"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{case}` | {count} | {meanings.get(case, '')} |")

    if report["removed_key_names"]:
        lines += [
            "",
            "## Removed keys",
            "",
            "Archived in `work/retired.tsv`; not added to the new bundle.",
            "",
            "```",
        ]
        lines += report["removed_key_names"]
        lines.append("```")

    attention = report["entries_requiring_attention"]

    if attention:
        lines += [
            "",
            f"## Entries requiring attention ({len(attention)})",
            "",
            "| Key | Case | Issues |",
            "| --- | --- | --- |",
        ]
        for item in attention[:200]:
            lines.append(
                f"| `{item['key']}` | `{item['case']}` | {item['issues']} |"
            )
        if len(attention) > 200:
            lines.append(f"| ... | {len(attention) - 200} more | |")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def status(repo: Path, version: str) -> dict:
    version_dir = repo / "versions" / version
    base = version_dir / "base" / "qupath-gui-strings.properties"
    tsv = version_dir / "work" / "translation.tsv"
    dist = version_dir / "dist" / "qupath-gui-strings_es.properties"

    result = {
        "version": version,
        "version_dir": str(version_dir),
        "base_present": base.is_file(),
        "tsv_present": tsv.is_file(),
        "dist_present": dist.is_file(),
        "states": {},
        "releasable": False,
        "blockers": [],
    }

    if not result["base_present"]:
        result["blockers"].append("canonical bundle not captured")
        return result

    result["base_sha256"] = sha256_upper(base.read_bytes())
    result["base_keys"] = len(parse_properties(
        base.read_bytes().decode("utf-8")))

    if not result["tsv_present"]:
        result["blockers"].append("no translation workspace")
        return result

    rows = load_tsv(tsv)
    states = Counter(row["state"] for row in rows)
    result["states"] = dict(states)
    result["rows"] = len(rows)

    for blocking_state in ("PENDING", "DRAFT", "BLOCKED"):
        if states.get(blocking_state):
            result["blockers"].append(
                f"{states[blocking_state]} entries are {blocking_state}"
            )

    if not result["dist_present"]:
        result["blockers"].append("Spanish bundle not generated")
        return result

    result["dist_sha256"] = sha256_upper(dist.read_bytes())

    validation = validate_translation(
        base.read_bytes().decode("utf-8"),
        dist.read_bytes().decode("utf-8"),
    )
    result["validation"] = {
        "ok": validation["ok"],
        "error_count": validation["error_count"],
        "warning_count": validation["warning_count"],
        "missing_keys": len(validation["missing_keys"]),
        "extra_keys": len(validation["extra_keys"]),
        "key_order_identical": validation["key_order_identical"],
        "placeholder_errors": validation["placeholder_errors"],
        "structural_errors": validation["structural_errors"],
        "empty_value_errors": validation["empty_value_errors"],
    }

    if not validation["ok"]:
        result["blockers"].append(
            f"validator reports {validation['error_count']} errors"
        )

    result["releasable"] = not result["blockers"]
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def emit(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Version-aware migration engine for QuPath ES"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="find QuPath installations")
    p_detect.add_argument("--search-root", type=Path, action="append",
                          default=None)
    p_detect.add_argument("--qupath-path", type=Path, default=None)

    p_capture = sub.add_parser("capture", help="capture a canonical bundle")
    p_capture.add_argument("--qupath-path", type=Path, required=True)
    p_capture.add_argument("--repo", type=Path, required=True)
    p_capture.add_argument("--force", action="store_true")

    p_migrate = sub.add_parser("migrate", help="migrate a translation")
    p_migrate.add_argument("--repo", type=Path, required=True)
    p_migrate.add_argument("--old", required=True)
    p_migrate.add_argument("--new", required=True)
    p_migrate.add_argument("--reviewer", default="migrator")
    p_migrate.add_argument("--force", action="store_true")

    p_status = sub.add_parser("status", help="report release readiness")
    p_status.add_argument("--repo", type=Path, required=True)
    p_status.add_argument("--version", required=True)

    args = parser.parse_args(argv)

    try:
        if args.command == "detect":
            if args.qupath_path:
                emit([inspect_installation(args.qupath_path)])
            else:
                roots = args.search_root or [
                    Path.home() / "AppData" / "Local"
                ]
                emit(detect_installations(roots))

        elif args.command == "capture":
            install = inspect_installation(args.qupath_path)
            emit(capture_bundle(install, args.repo, force=args.force))

        elif args.command == "migrate":
            emit(migrate(args.repo, args.old, args.new, args.reviewer,
                         force=args.force))

        elif args.command == "status":
            emit(status(args.repo, args.version))

    except (MigrationError, ValueError, OSError, UnicodeDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
