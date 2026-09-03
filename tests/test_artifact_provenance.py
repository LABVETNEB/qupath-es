"""Tests for artifact provenance semantics and the opt-in verifier."""
from __future__ import annotations

import copy
import io
import json
import unittest
from pathlib import Path

from tools.schema_validate import SchemaValidationError, validate
from tools.verify_artifacts import (
    ArtifactVerificationError,
    _validate_release_url,
    sha256_response,
)


REPO = Path(__file__).resolve().parents[1]
LOCK = REPO / "versions" / "0.7.0" / "components.lock.json"
SCHEMA = REPO / "schemas" / "components-lock.schema.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class ArtifactProvenanceSchemaTests(unittest.TestCase):
    def setUp(self):
        self.lock = load(LOCK)
        self.schema = load(SCHEMA)

    def test_release_pin_cannot_drop_sha256(self):
        broken = copy.deepcopy(self.lock)
        entry = next(
            item for item in broken["components"]
            if item["pin_basis"] == "UPSTREAM_RELEASE"
        )
        entry["artifact_sha256"] = None
        with self.assertRaises(SchemaValidationError):
            validate(broken, self.schema)

    def test_release_pin_cannot_drop_asset_url(self):
        broken = copy.deepcopy(self.lock)
        entry = next(
            item for item in broken["components"]
            if item["pin_basis"] == "UPSTREAM_RELEASE"
        )
        entry["artifact_url"] = None
        with self.assertRaises(SchemaValidationError):
            validate(broken, self.schema)

    def test_commit_only_pin_may_have_no_artifact(self):
        validate(self.lock, self.schema)
        tiatoolbox = next(
            item for item in self.lock["components"]
            if item["component_id"] == "tiatoolbox"
        )
        self.assertEqual(tiatoolbox["pin_basis"], "AUDITED_COMMIT")
        self.assertIsNone(tiatoolbox["artifact_url"])
        self.assertIsNone(tiatoolbox["artifact_sha256"])


class ArtifactVerifierUnitTests(unittest.TestCase):
    def test_sha256_response_is_uppercase_and_streamed(self):
        self.assertEqual(
            sha256_response(io.BytesIO(b"abc")),
            "BA7816BF8F01CFEA414140DE5DAE2223B00361A396177A9CB410FF61F20015AD",
        )

    def test_release_url_must_be_github_https_and_end_with_asset_name(self):
        _validate_release_url(
            "https://github.com/example/project/releases/download/v1/a.jar",
            "a.jar",
        )
        for url in (
            "http://github.com/example/project/releases/download/v1/a.jar",
            "https://example.com/example/project/releases/download/v1/a.jar",
            "https://github.com/example/project/archive/v1.zip",
            "https://github.com/example/project/releases/download/v1/other.jar",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ArtifactVerificationError):
                    _validate_release_url(url, "a.jar")


if __name__ == "__main__":
    unittest.main()
