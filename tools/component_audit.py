#!/usr/bin/env python3
"""Materialize and verify immutable per-extension audit snapshots.

The component axis is for QuPath extensions. QuPath Core remains versioned
under versions/<v>/ and therefore intentionally has no components/qupath-core/
directory. The source architecture audit still contains all 13 corpus members,
so Core remains part of cross-layer integrity checks without being projected
into a component directory.

This tool is offline and standard-library only. It does not fetch upstream
repositories and it does not claim new runtime validation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "components" / "registry.json"
SOURCE_REPORT_PATH = (
    ROOT
    / "versions"
    / "0.7.0"
    / "reports"
    / "ecosystem-repository-architecture-audit.json"
)

PROTECTED_IDENTIFIER_CATEGORIES = [
    "JAVA_CLASS",
    "JAVA_PACKAGE",
    "METHOD",
    "VARIABLE",
    "INTERNAL_ENUM",
    "FILE_NAME",
    "PATH",
    "SERIALIZED_KEY",
    "CONFIGURATION_KEY",
    "CLI_ARGUMENT",
    "CLI_FLAG",
    "MODEL_IDENTIFIER",
    "CHECKPOINT",
    "ENGINE",
    "MODEL_ARCHITECTURE",
    "MEASUREMENT_NAME",
    "PATHCLASS",
    "PARAMETER_KEY",
    "FUNCTION_NAME",
    "SCRIPT_COMMAND",
    "IMPORT",
    "URL",
    "HASH",
    "UUID",
    "ARTIFACT_NAME",
    "FILE_EXTENSION",
    "TENSOR_NAME",
    "MODEL_IO_NODE",
    "MODEL_WEIGHT",
]

EXTENSION_RELEVANT_PATHS = [
    "settings.gradle.kts",
    "build.gradle.kts",
    "gradle/libs.versions.toml",
    "src/main/java/**",
    "src/main/resources/**",
    "src/main/groovy/**",
    "src/main/python/**",
    "src/main/scripts/**",
]


def load_json(path: Path) -> Any:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    return json.loads(data.decode("utf-8"))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def index_by_id(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        component_id = item["id"]
        if component_id in result:
            raise ValueError(f"duplicate component id: {component_id}")
        result[component_id] = item
    return result


def build_manifest(
    registry_entry: dict[str, Any],
    audit_entry: dict[str, Any],
) -> dict[str, Any]:
    if registry_entry["type"] != "QUPATH_EXTENSION":
        raise ValueError(
            f"{registry_entry['id']} is not an extension component"
        )

    bundle_paths = [
        bundle["path"]
        for bundle in audit_entry["resource_bundle_status"]["bundles"]
    ]

    return {
        "schema_version": 1,
        "component_id": registry_entry["id"],
        "repository": registry_entry["repository"],
        "manifest_role": "COMPONENT_MANIFEST",
        "audit_policy": {
            "relevant_paths": EXTENSION_RELEVANT_PATHS,
            "bundle_paths": bundle_paths,
            "protected_identifier_categories": PROTECTED_IDENTIFIER_CATEGORIES,
            "explicit_protected_identifiers": [],
            "explicit_identifier_inventory_status": (
                "NOT_ENUMERATED_IN_INITIAL_AUDIT"
            ),
        },
        "fork_policy": {
            "strategy": "SATELLITE_ONLY_IF_REQUIRED",
            "repository": registry_entry["satellite_fork"],
            "patches_live_in_qupath_es": True,
            "source_code_vendored_here": False,
        },
        "initial_audit": {
            "upstream_commit": audit_entry["audited_commit"],
            "snapshot": f"audits/{audit_entry['audited_commit']}.json",
        },
    }


def build_snapshot(
    registry_entry: dict[str, Any],
    audit_entry: dict[str, Any],
    source_report: dict[str, Any],
) -> dict[str, Any]:
    if registry_entry["type"] != "QUPATH_EXTENSION":
        raise ValueError(
            f"{registry_entry['id']} is not an extension component"
        )

    compatibility = audit_entry["qupath_compatibility"]
    translation = audit_entry["translation_mechanism"]

    return {
        "schema_version": 1,
        "snapshot_type": "UPSTREAM_COMPONENT_AUDIT",
        "component_id": registry_entry["id"],
        "repository": registry_entry["repository"],
        "default_branch": audit_entry["default_branch"],
        "upstream_commit": audit_entry["audited_commit"],
        "upstream_commit_date": audit_entry["audited_commit_date"],
        "audited_at": audit_entry["audited_at"],
        "latest_release_or_tag": audit_entry["latest_release_or_tag"],
        "qupath_compatibility": {
            "declared_api_version": compatibility["declared_api_version"],
            "verified_against_0_7_0_at_runtime": compatibility[
                "verified_against_0_7_0_at_runtime"
            ],
            "bundled_in_qupath_0_7_0_install": compatibility[
                "bundled_in_qupath_0_7_0_install"
            ],
        },
        "resource_bundle_status": audit_entry["resource_bundle_status"],
        "parameterlist_status": audit_entry["parameterlist_status"],
        "pathclass_status": audit_entry["pathclass_status"],
        "hardcoded_ui_status": audit_entry["hardcoded_ui_status"],
        "translation_mechanism": {
            "resolution": translation["resolution"],
            "reachable_by_external_localization_directory": translation[
                "reachable_by_external_localization_directory"
            ],
            "display_category_aware": translation["display_category_aware"],
        },
        "localization_strategy_class": audit_entry[
            "localization_strategy_class"
        ],
        "fork_required": audit_entry["fork_required"],
        "patch_required": audit_entry["patch_required"],
        "audit_status": audit_entry["audit_status"],
        "translation_status": audit_entry["translation_status"],
        "validation_status": audit_entry["validation_status"],
        "distribution_status": audit_entry["distribution_status"],
        "unknowns": audit_entry["unknowns"],
        "source_report": {
            "path": str(SOURCE_REPORT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "repository_head": source_report["repository_head"],
            "audit_generated_at": source_report["generated_at"],
        },
    }


def expected_files(
    component_ids: set[str] | None = None,
) -> dict[Path, dict[str, Any]]:
    registry = load_json(REGISTRY_PATH)
    source_report = load_json(SOURCE_REPORT_PATH)

    registry_index = index_by_id(registry["components"])
    audit_index = index_by_id(source_report["components"])

    if set(registry_index) != set(audit_index):
        missing_from_audit = sorted(set(registry_index) - set(audit_index))
        missing_from_registry = sorted(set(audit_index) - set(registry_index))
        raise ValueError(
            "registry/audit component mismatch: "
            f"missing_from_audit={missing_from_audit}; "
            f"missing_from_registry={missing_from_registry}"
        )

    extension_ids = [
        entry["id"]
        for entry in registry["components"]
        if entry["type"] == "QUPATH_EXTENSION"
    ]

    if component_ids is None:
        selected_ids = extension_ids
    else:
        unknown = sorted(component_ids - set(registry_index))
        if unknown:
            raise ValueError(f"unknown component ids: {unknown}")
        non_extensions = sorted(
            component_id
            for component_id in component_ids
            if registry_index[component_id]["type"] != "QUPATH_EXTENSION"
        )
        if non_extensions:
            raise ValueError(
                "component directories are extension-only; "
                f"not projectable: {non_extensions}"
            )
        selected_ids = [
            component_id
            for component_id in extension_ids
            if component_id in component_ids
        ]

    result: dict[Path, dict[str, Any]] = {}
    for component_id in selected_ids:
        registry_entry = registry_index[component_id]
        audit_entry = audit_index[component_id]
        component_dir = ROOT / "components" / component_id
        commit = audit_entry["audited_commit"]

        result[component_dir / "component.json"] = build_manifest(
            registry_entry, audit_entry
        )
        result[component_dir / "audits" / f"{commit}.json"] = build_snapshot(
            registry_entry, audit_entry, source_report
        )

    return result


def check_files(expected: dict[Path, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for path, value in expected.items():
        relative = path.relative_to(ROOT)
        if not path.is_file():
            errors.append(f"missing: {relative}")
            continue
        try:
            actual = load_json(path)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid {relative}: {exc}")
            continue
        if actual != value:
            errors.append(f"content mismatch: {relative}")
    return errors


def write_files(expected: dict[Path, dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for path, value in expected.items():
        relative = path.relative_to(ROOT)
        desired = json_text(value).encode("utf-8")
        if path.exists():
            current = load_json(path)
            if current != value:
                raise ValueError(
                    f"refusing to overwrite existing different file: {relative}"
                )
            actions.append(f"unchanged {relative}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(desired)
        actions.append(f"created {relative}")
    return actions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify or bootstrap extension manifests and immutable audit "
            "snapshots from the versioned ecosystem architecture audit."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify files (default)")
    mode.add_argument(
        "--write",
        action="store_true",
        help="create missing files, refusing to overwrite different files",
    )
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        help="limit operation to an extension component id; may be repeated",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    selected = set(args.component) if args.component else None
    try:
        expected = expected_files(selected)
        if args.write:
            for action in write_files(expected):
                print(action)
            return 0
        errors = check_files(expected)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {len(expected) // 2} extension audit snapshots verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
