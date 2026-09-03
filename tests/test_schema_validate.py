"""Executable-contract tests for the repository JSON schemas."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.schema_validate import SchemaValidationError, validate


REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "components" / "registry.json"
REGISTRY_SCHEMA = REPO / "schemas" / "component-registry.schema.json"
LOCK = REPO / "versions" / "0.7.0" / "components.lock.json"
LOCK_SCHEMA = REPO / "schemas" / "components-lock.schema.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class RepositorySchemaContractTests(unittest.TestCase):
    def test_component_registry_validates_against_its_schema(self):
        validate(load(REGISTRY), load(REGISTRY_SCHEMA))

    def test_components_lock_validates_against_its_schema(self):
        validate(load(LOCK), load(LOCK_SCHEMA))


class ValidatorBehaviorTests(unittest.TestCase):
    def test_rejects_invalid_enum(self):
        with self.assertRaisesRegex(SchemaValidationError, "not one of"):
            validate("P9", {"enum": ["P0", "P1"]})

    def test_rejects_missing_required_property(self):
        schema = {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
            "additionalProperties": False,
        }
        with self.assertRaisesRegex(SchemaValidationError, "missing required"):
            validate({}, schema)

    def test_rejects_additional_property_in_closed_object(self):
        schema = {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "additionalProperties": False,
        }
        with self.assertRaisesRegex(SchemaValidationError, "additional property"):
            validate({"id": "ok", "extra": True}, schema)

    def test_local_ref_and_pattern_are_enforced(self):
        schema = {
            "type": "object",
            "required": ["sha"],
            "properties": {"sha": {"$ref": "#/$defs/sha"}},
            "additionalProperties": False,
            "$defs": {
                "sha": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{4}$",
                }
            },
        }
        validate({"sha": "0a1f"}, schema)
        with self.assertRaisesRegex(SchemaValidationError, "does not match"):
            validate({"sha": "XYZ"}, schema)

    def test_anyof_accepts_null_or_matching_string(self):
        schema = {
            "anyOf": [
                {"type": "null"},
                {"type": "string", "pattern": "^v\\d+$"},
            ]
        }
        validate(None, schema)
        validate("v7", schema)
        with self.assertRaisesRegex(SchemaValidationError, "anyOf"):
            validate("release", schema)

    def test_unsupported_semantic_keyword_fails_closed(self):
        with self.assertRaisesRegex(SchemaValidationError, "unsupported schema keyword"):
            validate("x", {"type": "string", "format": "email"})


if __name__ == "__main__":
    unittest.main()
