"""Regression tests for late review findings on upstream_watch."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "upstream_watch.py"

SPEC = importlib.util.spec_from_file_location("upstream_watch_regression", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
upstream_watch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = upstream_watch
SPEC.loader.exec_module(upstream_watch)


class FakeApi:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses

    def get_json(self, path: str) -> Any:
        if path not in self.responses:
            raise AssertionError(f"unexpected API request: {path}")
        return self.responses[path]


class UpstreamWatchRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = next(
            item
            for item in upstream_watch.load_extension_manifests()
            if item["component_id"] == "instanseg"
        )

    def routes(self, *, head: str, compare: dict[str, Any]) -> dict[str, Any]:
        repository = self.manifest["repository"]
        baseline = self.manifest["initial_audit"]["upstream_commit"]
        return {
            f"repos/{repository}": {"default_branch": "main"},
            f"repos/{repository}/commits/main": {"sha": head},
            f"repos/{repository}/compare/{baseline}...{head}": compare,
        }

    def test_outbound_rename_keeps_source_classification(self) -> None:
        bundle = self.manifest["audit_policy"]["bundle_paths"][0]
        head = "1" * 40
        compare = {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "files": [
                {
                    "filename": "docs/archived-strings.properties",
                    "previous_filename": bundle,
                    "status": "renamed",
                    "additions": 0,
                    "deletions": 0,
                    "changes": 0,
                }
            ],
        }

        result = upstream_watch.watch_component(
            self.manifest,
            FakeApi(self.routes(head=head, compare=compare)),
        )

        self.assertEqual(result["status"], upstream_watch.STATUS_DRIFT)
        self.assertTrue(result["relevant_drift"])
        self.assertEqual(result["action"], "REVIEW_REQUIRED")
        self.assertEqual(
            result["relevant_changed_files"][0]["classification"],
            "RESOURCE_BUNDLE",
        )

    def test_truncated_negative_compare_is_unknown(self) -> None:
        head = "2" * 40
        files = [
            {
                "filename": f"docs/change-{index}.md",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
            }
            for index in range(upstream_watch.COMPARE_FILE_LIMIT)
        ]
        compare = {
            "status": "ahead",
            "ahead_by": upstream_watch.COMPARE_FILE_LIMIT + 1,
            "behind_by": 0,
            "files": files,
        }

        result = upstream_watch.watch_component(
            self.manifest,
            FakeApi(self.routes(head=head, compare=compare)),
        )

        self.assertEqual(result["status"], upstream_watch.STATUS_UNKNOWN)
        self.assertIsNone(result["relevant_drift"])
        self.assertFalse(result["analysis_complete"])
        self.assertEqual(result["action"], "INVESTIGATE")
        self.assertIn("truncated", result["error"])
        self.assertEqual(
            upstream_watch.exit_code(
                {"summary": upstream_watch.summarize([result])},
                fail_on_drift=False,
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
