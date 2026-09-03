from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
COMPONENT_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TOP_LEVEL_FIELDS = {
    "schema_version",
    "component_id",
    "localization_revision",
    "evidence",
    "inventory_status",
    "rules",
}

EVIDENCE_FIELDS = {"commit", "files"}

RULE_FIELDS = {
    "category",
    "value",
    "match",
    "evidence_paths",
}

ALLOWED_INVENTORY_STATUS = {"PARTIAL", "COMPLETE"}
ALLOWED_MATCH_MODES = {"EXACT", "PREFIX", "CONTAINS"}


class ProtectedIdentifierInventoryError(ValueError):
    """Raised when a protected-identifier inventory violates its contract."""


def _require_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    context: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ProtectedIdentifierInventoryError(
            f"{context}: field mismatch; missing={missing}; extra={extra}"
        )


def _validate_relative_path(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProtectedIdentifierInventoryError(
            f"{context} must be a non-empty string"
        )

    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ProtectedIdentifierInventoryError(
            f"{context}: unsafe relative path {value!r}"
        )

    return value


def validate_inventory(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProtectedIdentifierInventoryError("inventory root must be an object")

    _require_exact_fields(data, TOP_LEVEL_FIELDS, "inventory")

    if data["schema_version"] != 1:
        raise ProtectedIdentifierInventoryError(
            "inventory.schema_version must be 1"
        )

    component_id = data["component_id"]
    if not isinstance(component_id, str) or not COMPONENT_ID_RE.fullmatch(
        component_id
    ):
        raise ProtectedIdentifierInventoryError(
            "inventory.component_id must be kebab-case"
        )

    revision = data["localization_revision"]
    if (
        not isinstance(revision, str)
        or not revision
        or "/" in revision
        or "\\" in revision
        or revision in {".", ".."}
    ):
        raise ProtectedIdentifierInventoryError(
            "inventory.localization_revision must be a simple non-empty name"
        )

    if data["inventory_status"] not in ALLOWED_INVENTORY_STATUS:
        raise ProtectedIdentifierInventoryError(
            "inventory.inventory_status must be PARTIAL or COMPLETE"
        )

    evidence = data["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise ProtectedIdentifierInventoryError(
            "inventory.evidence must be a non-empty array"
        )

    evidence_commits_seen: set[str] = set()
    evidenced_paths: set[str] = set()

    for index, entry in enumerate(evidence):
        context = f"inventory.evidence[{index}]"
        if not isinstance(entry, dict):
            raise ProtectedIdentifierInventoryError(
                f"{context} must be an object"
            )
        _require_exact_fields(entry, EVIDENCE_FIELDS, context)

        commit = entry["commit"]
        if not isinstance(commit, str) or not SHA1_RE.fullmatch(commit):
            raise ProtectedIdentifierInventoryError(
                f"{context}.commit must be a 40-hex commit SHA"
            )
        if commit in evidence_commits_seen:
            raise ProtectedIdentifierInventoryError(
                f"{context}: duplicate evidence commit {commit}"
            )
        evidence_commits_seen.add(commit)

        files = entry["files"]
        if not isinstance(files, dict) or not files:
            raise ProtectedIdentifierInventoryError(
                f"{context}.files must be a non-empty object"
            )

        for path_value, blob_sha in files.items():
            path_value = _validate_relative_path(
                path_value,
                f"{context}.files path",
            )
            if not isinstance(blob_sha, str) or not SHA1_RE.fullmatch(blob_sha):
                raise ProtectedIdentifierInventoryError(
                    f"{context}.files[{path_value!r}] must be a 40-hex blob SHA"
                )
            evidenced_paths.add(path_value)

    rules = data["rules"]
    if not isinstance(rules, list) or not rules:
        raise ProtectedIdentifierInventoryError(
            "inventory.rules must be a non-empty array"
        )

    seen: set[tuple[str, str, str]] = set()

    for index, rule in enumerate(rules):
        context = f"inventory.rules[{index}]"
        if not isinstance(rule, dict):
            raise ProtectedIdentifierInventoryError(
                f"{context} must be an object"
            )

        _require_exact_fields(rule, RULE_FIELDS, context)

        category = rule["category"]
        if (
            not isinstance(category, str)
            or not category
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*", category)
        ):
            raise ProtectedIdentifierInventoryError(
                f"{context}.category must be UPPER_SNAKE_CASE"
            )

        value = rule["value"]
        if not isinstance(value, str) or value == "":
            raise ProtectedIdentifierInventoryError(
                f"{context}.value must be a non-empty string"
            )

        match = rule["match"]
        if match not in ALLOWED_MATCH_MODES:
            raise ProtectedIdentifierInventoryError(
                f"{context}.match must be one of "
                f"{sorted(ALLOWED_MATCH_MODES)}"
            )

        evidence_paths = rule["evidence_paths"]
        if (
            not isinstance(evidence_paths, list)
            or not evidence_paths
            or len(evidence_paths) != len(set(evidence_paths))
        ):
            raise ProtectedIdentifierInventoryError(
                f"{context}.evidence_paths must be a non-empty unique array"
            )

        for evidence_path in evidence_paths:
            evidence_path = _validate_relative_path(
                evidence_path,
                f"{context}.evidence_paths",
            )
            if evidence_path not in evidenced_paths:
                raise ProtectedIdentifierInventoryError(
                    f"{context}: evidence path {evidence_path!r} has no "
                    "pinned blob in inventory.evidence"
                )

        identity = (category, value, match)
        if identity in seen:
            raise ProtectedIdentifierInventoryError(
                f"{context}: duplicate rule {identity!r}"
            )
        seen.add(identity)

    return data


def load_inventory(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ProtectedIdentifierInventoryError(f"{path} has a UTF-8 BOM")
    if b"\r" in raw:
        raise ProtectedIdentifierInventoryError(
            f"{path} must use LF line endings"
        )
    try:
        text = raw.decode("utf-8", errors="strict")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtectedIdentifierInventoryError(
            f"{path}: invalid UTF-8 JSON: {exc}"
        ) from exc
    return validate_inventory(data)


def evidence_commits(inventory: dict[str, Any]) -> set[str]:
    return {entry["commit"] for entry in inventory["evidence"]}


def evidence_paths(inventory: dict[str, Any]) -> set[str]:
    return {
        path
        for entry in inventory["evidence"]
        for path in entry["files"]
    }


def rule_match_count(text: str, rule: dict[str, Any]) -> int:
    value = rule["value"]
    mode = rule["match"]

    if mode == "EXACT":
        return int(text == value)
    if mode == "PREFIX":
        return int(text.startswith(value))
    if mode == "CONTAINS":
        return text.count(value)

    raise ProtectedIdentifierInventoryError(
        f"unsupported match mode: {mode!r}"
    )


def preservation_errors(
    source_value: str,
    target_value: str,
    rules: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    for rule in rules:
        source_count = rule_match_count(source_value, rule)
        if source_count == 0:
            continue

        target_count = rule_match_count(target_value, rule)
        if target_count != source_count:
            errors.append(
                {
                    "type": "protected_identifier_mismatch",
                    "category": rule["category"],
                    "value": rule["value"],
                    "match": rule["match"],
                    "source_count": source_count,
                    "target_count": target_count,
                }
            )

    return errors
