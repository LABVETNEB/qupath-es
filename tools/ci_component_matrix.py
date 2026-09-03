#!/usr/bin/env python3
"""Detect extension components affected by a Git diff.

The output is intended for GitHub Actions dynamic matrices, but the detector is
standard-library only and can be tested locally. QuPath Core is intentionally
not part of the component matrix because it has no components/qupath-core/
directory; Core remains protected by the always-on global jobs.

Detection is conservative:
- direct components/<id>/... changes select that extension;
- registry/lock/localization-lock changes are compared structurally so only
  changed extension entries are selected;
- shared component contracts select every extension;
- malformed or unresolvable Git/JSON state fails the detector instead of
  silently returning an empty matrix.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

REGISTRY_PATH = "components/registry.json"
COMPONENT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCK_RE = re.compile(
    r"^versions/[^/]+/(?P<kind>components|localizations)\.lock\.json$"
)

SHARED_COMPONENT_PATHS = frozenset(
    {
        ".github/workflows/ci.yml",
        "schemas/component-registry.schema.json",
        "schemas/components-lock.schema.json",
        "schemas/localizations-lock.schema.json",
        "tools/component_audit.py",
        "tools/protected_identifiers.py",
        "tools/ci_component_matrix.py",
        "tools/component_ci.py",
        "tests/test_component_audit.py",
        "tests/test_component_registry.py",
        "tests/test_components_lock.py",
        "tests/test_extension_translation.py",
        "tests/test_language_axis.py",
        "tests/test_protected_identifiers.py",
        "tests/test_ci_component_matrix.py",
        "tests/test_component_ci.py",
    }
)

class ComponentMatrixError(RuntimeError):
    """Fail-closed component-matrix detection error."""

def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ComponentMatrixError(f"cannot run Git: {exc}") from exc
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ComponentMatrixError(
            f"git {' '.join(args)} failed: {detail or 'unknown error'}"
        )
    return result

def resolve_commit(root: Path, ref: str) -> str:
    raw = _git(root, "rev-parse", f"{ref}^{{commit}}").stdout
    try:
        commit = raw.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise ComponentMatrixError(f"Git returned a non-ASCII commit for {ref}") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ComponentMatrixError(f"{ref!r} did not resolve to a full commit SHA")
    return commit

def git_blob(root: Path, ref: str, repo_path: str) -> bytes:
    if repo_path.startswith("/") or "\\" in repo_path or ".." in Path(repo_path).parts:
        raise ComponentMatrixError(f"unsafe repository path: {repo_path!r}")
    result = _git(root, "show", f"{ref}:{repo_path}", check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ComponentMatrixError(
            f"cannot read {repo_path} at {ref}: {detail or 'missing path'}"
        )
    return result.stdout

def json_at(root: Path, ref: str, repo_path: str) -> Any:
    raw = git_blob(root, ref, repo_path)
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ComponentMatrixError(f"{repo_path} at {ref} has a UTF-8 BOM")
    try:
        return json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComponentMatrixError(
            f"{repo_path} at {ref} is not strict UTF-8 JSON: {exc}"
        ) from exc

def _registry_entries(root: Path, ref: str) -> list[dict[str, Any]]:
    data = json_at(root, ref, REGISTRY_PATH)
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        raise ComponentMatrixError("component registry lacks components[]")
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(data["components"]):
        if not isinstance(entry, dict):
            raise ComponentMatrixError(f"registry component #{index} is not an object")
        component_id = entry.get("id")
        component_type = entry.get("type")
        if not isinstance(component_id, str) or not COMPONENT_ID_RE.fullmatch(component_id):
            raise ComponentMatrixError(
                f"registry component #{index} has invalid id {component_id!r}"
            )
        if component_id in seen:
            raise ComponentMatrixError(f"duplicate registry id: {component_id}")
        seen.add(component_id)
        if not isinstance(component_type, str):
            raise ComponentMatrixError(
                f"registry component {component_id} lacks a string type"
            )
        entries.append(entry)
    return entries

def extension_ids(root: Path, ref: str) -> list[str]:
    ids = [
        entry["id"]
        for entry in _registry_entries(root, ref)
        if entry["type"] == "QUPATH_EXTENSION"
    ]
    if "qupath-core" in ids:
        raise ComponentMatrixError("qupath-core cannot be an extension matrix target")
    if not ids:
        raise ComponentMatrixError("registry contains no extension components")
    return ids

def changed_paths(root: Path, base: str, head: str) -> list[str]:
    base_commit = resolve_commit(root, base)
    head_commit = resolve_commit(root, head)
    raw = _git(
        root,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        base_commit,
        head_commit,
    ).stdout
    paths: list[str] = []
    for token in raw.split(b"\0"):
        if not token:
            continue
        try:
            path = token.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ComponentMatrixError("Git diff contains a non-UTF-8 path") from exc
        if path.startswith("/") or "\\" in path or ".." in Path(path).parts:
            raise ComponentMatrixError(f"unsafe changed path: {path!r}")
        paths.append(path)
    return paths

def _index_entries(
    data: Any,
    *,
    list_field: str,
    key_fields: tuple[str, ...],
    context: str,
) -> dict[tuple[str, ...], dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get(list_field), list):
        raise ComponentMatrixError(f"{context} lacks {list_field}[]")
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    for index, entry in enumerate(data[list_field]):
        if not isinstance(entry, dict):
            raise ComponentMatrixError(f"{context} {list_field}[{index}] is not object")
        key_values: list[str] = []
        for field in key_fields:
            value = entry.get(field)
            if not isinstance(value, str) or not value:
                raise ComponentMatrixError(
                    f"{context} {list_field}[{index}] lacks {field}"
                )
            key_values.append(value)
        key = tuple(key_values)
        if key in result:
            raise ComponentMatrixError(f"{context} duplicate key {key!r}")
        result[key] = entry
    return result

def _changed_registry_ids(root: Path, base: str, head: str) -> set[str]:
    old = {entry["id"]: entry for entry in _registry_entries(root, base)}
    new = {entry["id"]: entry for entry in _registry_entries(root, head)}
    changed = {
        component_id
        for component_id in set(old) | set(new)
        if old.get(component_id) != new.get(component_id)
    }
    removed_extensions = {
        component_id
        for component_id in changed
        if old.get(component_id, {}).get("type") == "QUPATH_EXTENSION"
        and component_id not in new
    }
    if removed_extensions:
        raise ComponentMatrixError(
            "extension ids are stable; registry removed "
            + ", ".join(sorted(removed_extensions))
        )
    return {
        component_id
        for component_id in changed
        if new.get(component_id, {}).get("type") == "QUPATH_EXTENSION"
    }

def _changed_lock_ids(
    root: Path,
    base: str,
    head: str,
    repo_path: str,
    kind: str,
) -> set[str]:
    old_data = json_at(root, base, repo_path)
    new_data = json_at(root, head, repo_path)
    if kind == "components":
        old = _index_entries(
            old_data,
            list_field="components",
            key_fields=("component_id",),
            context=f"{repo_path}@{base}",
        )
        new = _index_entries(
            new_data,
            list_field="components",
            key_fields=("component_id",),
            context=f"{repo_path}@{head}",
        )
    elif kind == "localizations":
        old = _index_entries(
            old_data,
            list_field="localizations",
            key_fields=("component_id", "locale"),
            context=f"{repo_path}@{base}",
        )
        new = _index_entries(
            new_data,
            list_field="localizations",
            key_fields=("component_id", "locale"),
            context=f"{repo_path}@{head}",
        )
    else:
        raise ComponentMatrixError(f"unsupported lock kind: {kind}")
    changed_keys = {
        key for key in set(old) | set(new) if old.get(key) != new.get(key)
    }
    return {key[0] for key in changed_keys}

def detect_components(root: Path, base: str, head: str) -> dict[str, Any]:
    root = root.resolve()
    base_commit = resolve_commit(root, base)
    head_commit = resolve_commit(root, head)
    ordered_extensions = extension_ids(root, head_commit)
    extension_set = set(ordered_extensions)
    paths = changed_paths(root, base_commit, head_commit)
    selected: set[str] = set()

    for repo_path in paths:
        if repo_path in SHARED_COMPONENT_PATHS:
            selected.update(extension_set)
            continue
        if repo_path == REGISTRY_PATH:
            selected.update(_changed_registry_ids(root, base_commit, head_commit))
            continue
        lock_match = LOCK_RE.fullmatch(repo_path)
        if lock_match:
            changed = _changed_lock_ids(
                root,
                base_commit,
                head_commit,
                repo_path,
                lock_match.group("kind"),
            )
            unknown = changed - extension_set - {"qupath-core"}
            if unknown:
                raise ComponentMatrixError(
                    f"{repo_path} references unknown changed components: "
                    + ", ".join(sorted(unknown))
                )
            selected.update(changed & extension_set)
            continue
        if repo_path.startswith("components/"):
            parts = repo_path.split("/")
            if len(parts) < 3:
                continue
            component_id = parts[1]
            if component_id == "qupath-core":
                raise ComponentMatrixError(
                    "components/qupath-core/ is forbidden by repository architecture"
                )
            if component_id not in extension_set:
                raise ComponentMatrixError(
                    f"changed component path is not registered: {component_id}"
                )
            selected.add(component_id)

    ordered_selected = [
        component_id
        for component_id in ordered_extensions
        if component_id in selected
    ]
    return {
        "base": base_commit,
        "head": head_commit,
        "changed_paths": paths,
        "components": ordered_selected,
    }

def all_components(root: Path, head: str) -> dict[str, Any]:
    root = root.resolve()
    head_commit = resolve_commit(root, head)
    return {
        "base": None,
        "head": head_commit,
        "changed_paths": [],
        "components": extension_ids(root, head_commit),
    }

def write_github_output(path: Path, components: Iterable[str]) -> None:
    component_list = list(components)
    payload = json.dumps(component_list, separators=(",", ":"))
    has_components = "true" if component_list else "false"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"components={payload}\n")
        handle.write(f"has_components={has_components}\n")

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect extension components affected by a Git diff."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--all",
        action="store_true",
        help="select every registered extension component",
    )
    mode.add_argument(
        "--base",
        help="base commit/ref; requires --head",
    )
    parser.add_argument("--head", help="head commit/ref")
    parser.add_argument(
        "--github-output",
        type=Path,
        help="append components/has_components outputs for GitHub Actions",
    )
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.all:
        if not args.head:
            print("ERROR: --all requires --head", file=sys.stderr)
            return 2
    elif not args.head:
        print("ERROR: --base requires --head", file=sys.stderr)
        return 2
    try:
        if args.all:
            result = all_components(args.repo, args.head)
        else:
            result = detect_components(args.repo, args.base, args.head)
        if args.github_output is not None:
            write_github_output(args.github_output, result["components"])
    except (ComponentMatrixError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
