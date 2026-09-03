#!/usr/bin/env python3
"""Run offline checks for one registered QuPath extension component.

This is the per-component CI entry point used by the dynamic matrix. It does
not replace the always-on repository test suite; it adds a narrow, explicit
check that can scale with the number of extensions.

QuPath Core is intentionally excluded because Core has no components/qupath-core/
directory and remains protected by the global/version-level checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


COMPONENT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ComponentCheckError(RuntimeError):
    """A component-specific invariant failed."""


def load_json(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ComponentCheckError(f"{path} has a UTF-8 BOM")
    if b"\r" in raw:
        raise ComponentCheckError(f"{path} must use LF line endings")
    try:
        return json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComponentCheckError(f"{path}: invalid UTF-8 JSON: {exc}") from exc


def sha256_upper(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _registry_entry(root: Path, component_id: str) -> dict[str, Any]:
    registry = load_json(root / "components" / "registry.json")
    entries = registry.get("components")
    if not isinstance(entries, list):
        raise ComponentCheckError("components/registry.json lacks components[]")

    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("id") == component_id
    ]
    if len(matches) != 1:
        raise ComponentCheckError(
            f"registry must contain exactly one {component_id!r} entry"
        )
    entry = matches[0]
    if entry.get("type") != "QUPATH_EXTENSION":
        raise ComponentCheckError(
            f"{component_id} is not a QUPATH_EXTENSION matrix target"
        )
    return entry


def _run_component_audit(root: Path, component_id: str) -> str:
    tool = root / "tools" / "component_audit.py"
    if not tool.is_file():
        raise ComponentCheckError("tools/component_audit.py is missing")

    result = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--check",
            "--component",
            component_id,
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or f"exit {result.returncode}"
        raise ComponentCheckError(
            f"component audit failed for {component_id}: {detail}"
        )
    return result.stdout.decode("utf-8", errors="strict").strip()


def _unique_component_lock_entry(
    path: Path,
    component_id: str,
) -> dict[str, Any]:
    data = load_json(path)
    entries = data.get("components")
    if not isinstance(entries, list):
        raise ComponentCheckError(f"{path} lacks components[]")
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("component_id") == component_id
    ]
    if len(matches) != 1:
        raise ComponentCheckError(
            f"{path}: expected exactly one {component_id} lock entry"
        )
    return matches[0]


def _localization_entries(
    path: Path,
    component_id: str,
) -> list[dict[str, Any]]:
    data = load_json(path)
    entries = data.get("localizations")
    if not isinstance(entries, list):
        raise ComponentCheckError(f"{path} lacks localizations[]")
    matches = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("component_id") == component_id
    ]
    if not matches:
        raise ComponentCheckError(
            f"{path}: no localization projection for {component_id}"
        )

    locales: set[str] = set()
    for entry in matches:
        locale = entry.get("locale")
        if not isinstance(locale, str) or not locale:
            raise ComponentCheckError(
                f"{path}: {component_id} localization lacks locale"
            )
        if locale in locales:
            raise ComponentCheckError(
                f"{path}: duplicate {component_id}/{locale} localization"
            )
        locales.add(locale)
    return matches


def _verify_localization_materialization(
    root: Path,
    path: Path,
    entry: dict[str, Any],
) -> dict[str, Any]:
    component_id = entry["component_id"]
    locale = entry["locale"]
    source = entry.get("source_of_truth")
    dist = entry.get("dist_bundle")
    dist_sha256 = entry.get("dist_sha256")

    if source is not None:
        if not isinstance(source, str) or not source:
            raise ComponentCheckError(
                f"{path}: {component_id}/{locale} source_of_truth must be null/string"
            )
        source_path = root / source
        if not source_path.is_file():
            raise ComponentCheckError(
                f"{path}: missing source_of_truth {source}"
            )

    if dist is None:
        if dist_sha256 is not None:
            raise ComponentCheckError(
                f"{path}: {component_id}/{locale} has hash without dist bundle"
            )
        return {
            "locale": locale,
            "materialized": False,
            "dist_sha256": None,
        }

    if not isinstance(dist, str) or not dist:
        raise ComponentCheckError(
            f"{path}: {component_id}/{locale} dist_bundle must be null/string"
        )
    if (
        not isinstance(dist_sha256, str)
        or not re.fullmatch(r"[0-9A-F]{64}", dist_sha256)
    ):
        raise ComponentCheckError(
            f"{path}: {component_id}/{locale} lacks canonical dist_sha256"
        )

    dist_path = root / dist
    if not dist_path.is_file():
        raise ComponentCheckError(f"{path}: missing dist bundle {dist}")
    actual = sha256_upper(dist_path)
    if actual != dist_sha256:
        raise ComponentCheckError(
            f"{path}: {component_id}/{locale} dist SHA {actual} "
            f"!= recorded {dist_sha256}"
        )

    return {
        "locale": locale,
        "materialized": True,
        "dist_sha256": actual,
    }


def _verify_protected_inventories(
    root: Path,
    component_id: str,
) -> list[str]:
    inventory_dir = root / "components" / component_id / "protected-identifiers"
    if not inventory_dir.exists():
        return []
    if not inventory_dir.is_dir():
        raise ComponentCheckError(
            f"{inventory_dir.relative_to(root)} must be a directory"
        )

    revisions: list[str] = []
    for path in sorted(inventory_dir.glob("*.json")):
        data = load_json(path)
        if data.get("component_id") != component_id:
            raise ComponentCheckError(
                f"{path}: inventory component_id != {component_id}"
            )
        revision = data.get("localization_revision")
        if not isinstance(revision, str) or not revision:
            raise ComponentCheckError(
                f"{path}: inventory lacks localization_revision"
            )
        if revision in revisions:
            raise ComponentCheckError(
                f"{path}: duplicate protected inventory revision {revision}"
            )
        revisions.append(revision)
    return revisions


def check_component(root: Path, component_id: str) -> dict[str, Any]:
    root = root.resolve()
    if not COMPONENT_ID_RE.fullmatch(component_id):
        raise ComponentCheckError(
            f"component id must be kebab-case: {component_id!r}"
        )
    if component_id == "qupath-core":
        raise ComponentCheckError(
            "qupath-core belongs to version/global CI, not the extension matrix"
        )

    registry_entry = _registry_entry(root, component_id)
    component_dir = root / "components" / component_id
    if not component_dir.is_dir():
        raise ComponentCheckError(
            f"missing component directory: components/{component_id}"
        )

    audit_output = _run_component_audit(root, component_id)

    versions: list[dict[str, Any]] = []
    lock_paths = sorted((root / "versions").glob("*/components.lock.json"))
    if not lock_paths:
        raise ComponentCheckError("no versions/*/components.lock.json found")

    for lock_path in lock_paths:
        version_dir = lock_path.parent
        lock_entry = _unique_component_lock_entry(lock_path, component_id)
        localization_lock = version_dir / "localizations.lock.json"
        localization_results: list[dict[str, Any]] = []

        if localization_lock.is_file():
            for entry in _localization_entries(
                localization_lock,
                component_id,
            ):
                localization_results.append(
                    _verify_localization_materialization(
                        root,
                        localization_lock,
                        entry,
                    )
                )

        versions.append(
            {
                "qupath_version": version_dir.name,
                "pin_basis": lock_entry.get("pin_basis"),
                "audit_status": lock_entry.get("audit_status"),
                "runtime_compatibility": lock_entry.get(
                    "runtime_compatibility"
                ),
                "localizations": localization_results,
            }
        )

    inventories = _verify_protected_inventories(root, component_id)

    return {
        "component_id": component_id,
        "repository": registry_entry.get("repository"),
        "audit": audit_output,
        "versions": versions,
        "protected_inventory_revisions": inventories,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline CI checks for one extension component."
    )
    parser.add_argument("--component", required=True)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = check_component(args.repo, args.component)
    except (ComponentCheckError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
