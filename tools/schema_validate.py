"""Minimal, dependency-free validator for the JSON Schema subset used here.

This module intentionally does not claim full JSON Schema Draft 2020-12
compliance. It implements the closed subset exercised by the repository's
schemas so those files are executable contracts rather than documentation.
Unsupported keywords fail closed when they can affect validation semantics.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


SUPPORTED_KEYWORDS = {
    "$schema",
    "$defs",
    "$ref",
    "title",
    "description",
    "type",
    "const",
    "enum",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "minItems",
    "minLength",
    "pattern",
    "anyOf",
    "allOf",
    "if",
    "then",
}


class SchemaValidationError(ValueError):
    """Raised when an instance violates the supported schema contract."""


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _resolve_local_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise SchemaValidationError(f"unsupported non-local $ref: {ref!r}")

    node: Any = root_schema
    for raw_token in ref[2:].split("/"):
        token = _decode_pointer_token(raw_token)
        if not isinstance(node, dict) or token not in node:
            raise SchemaValidationError(f"unresolvable local $ref: {ref!r}")
        node = node[token]

    if not isinstance(node, dict):
        raise SchemaValidationError(f"$ref does not resolve to a schema object: {ref!r}")
    return node


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise SchemaValidationError(f"unsupported JSON Schema type: {expected!r}")


def _check_supported_keywords(schema: dict[str, Any], path: str) -> None:
    unsupported = sorted(set(schema) - SUPPORTED_KEYWORDS)
    if unsupported:
        raise SchemaValidationError(
            f"{path}: unsupported schema keyword(s): {', '.join(unsupported)}"
        )


def validate(
    instance: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "$",
) -> None:
    """Validate *instance* against the repository-supported schema subset."""
    if root_schema is None:
        root_schema = schema

    _check_supported_keywords(schema, path)

    ref = schema.get("$ref")
    if ref is not None:
        validate(
            instance,
            _resolve_local_ref(root_schema, ref),
            root_schema=root_schema,
            path=path,
        )
        siblings = {key: value for key, value in schema.items() if key != "$ref"}
        if not siblings:
            return
        schema = siblings
        _check_supported_keywords(schema, path)

    if "anyOf" in schema:
        failures: list[str] = []
        for candidate in schema["anyOf"]:
            try:
                validate(instance, candidate, root_schema=root_schema, path=path)
                break
            except SchemaValidationError as exc:
                failures.append(str(exc))
        else:
            raise SchemaValidationError(
                f"{path}: value matches none of the anyOf alternatives: "
                + " | ".join(failures)
            )

    if "allOf" in schema:
        for candidate in schema["allOf"]:
            validate(instance, candidate, root_schema=root_schema, path=path)

    if "if" in schema:
        try:
            validate(instance, schema["if"], root_schema=root_schema, path=path)
        except SchemaValidationError:
            condition_matches = False
        else:
            condition_matches = True
        if condition_matches and "then" in schema:
            validate(instance, schema["then"], root_schema=root_schema, path=path)

    if "type" in schema:
        declared = schema["type"]
        expected_types = declared if isinstance(declared, list) else [declared]
        if not any(_matches_type(instance, expected) for expected in expected_types):
            raise SchemaValidationError(
                f"{path}: expected type {expected_types!r}, got {type(instance).__name__}"
            )

    if "const" in schema and instance != schema["const"]:
        raise SchemaValidationError(
            f"{path}: expected constant {schema['const']!r}, got {instance!r}"
        )

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(
            f"{path}: {instance!r} is not one of {schema['enum']!r}"
        )

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise SchemaValidationError(
                f"{path}: string length {len(instance)} < {schema['minLength']}"
            )
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise SchemaValidationError(
                f"{path}: {instance!r} does not match /{schema['pattern']}/"
            )

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise SchemaValidationError(
                f"{path}: item count {len(instance)} < {schema['minItems']}"
            )
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, value in enumerate(instance):
                validate(
                    value,
                    item_schema,
                    root_schema=root_schema,
                    path=f"{path}[{index}]",
                )

    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise SchemaValidationError(
                f"{path}: missing required property/properties: {', '.join(missing)}"
            )

        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                validate(
                    value,
                    properties[key],
                    root_schema=root_schema,
                    path=f"{path}.{key}",
                )
            elif schema.get("additionalProperties") is False:
                raise SchemaValidationError(
                    f"{path}: additional property {key!r} is not allowed"
                )


def validate_file(schema_path: Path, instance_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    validate(instance, schema)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: schema_validate.py SCHEMA.json INSTANCE.json", file=sys.stderr)
        return 2

    schema_path = Path(args[0])
    instance_path = Path(args[1])
    try:
        validate_file(schema_path, instance_path)
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        print(f"ERROR {instance_path}: {exc}", file=sys.stderr)
        return 1

    print(f"OK {instance_path} validates against {schema_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
