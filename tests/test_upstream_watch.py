"""Tests for the read-only upstream drift detector."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "upstream_watch.py"

SPEC = importlib.util.spec_from_file_location("upstream_watch", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
upstream_watch = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = upstream_watch
SPEC.loader.exec_module(upstream_watch)


class FakeApi:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get_json(self, path: str) -> Any:
        self.calls.append(path)
        if path not in self.responses:
            raise AssertionError(f"unexpected API request: {path}")
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return value


class UpstreamWatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifests = upstream_watch.load_extension_manifests()
        cls.by_id = {
            manifest["component_id"]: manifest
            for manifest in cls.manifests
        }

    def manifest(self, component_id: str = "instanseg") -> dict[str, Any]:
        return self.by_id[component_id]

    def routes_for(
        self,
        manifest: dict[str, Any],
        *,
        head: str,
        compare: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        repository = manifest["repository"]
        baseline = manifest["initial_audit"]["upstream_commit"]
        routes: dict[str, Any] = {
            f"repos/{repository}": {"default_branch": "main"},
            f"repos/{repository}/commits/main": {"sha": head},
        }
        if head != baseline:
            routes[
                f"repos/{repository}/compare/{baseline}...{head}"
            ] = compare
        return routes

    def test_discovers_exactly_12_extension_manifests(self) -> None:
        self.assertEqual(len(self.manifests), 12)
        self.assertNotIn("qupath-core", self.by_id)

        registry = upstream_watch.load_json(upstream_watch.REGISTRY_PATH)
        expected = [
            entry["id"]
            for entry in registry["components"]
            if entry["type"] == "QUPATH_EXTENSION"
        ]
        self.assertEqual(
            [item["component_id"] for item in self.manifests],
            expected,
        )

    def test_core_directory_remains_forbidden(self) -> None:
        self.assertFalse(
            (upstream_watch.COMPONENTS_DIR / "qupath-core").exists()
        )

    def test_select_manifests_preserves_requested_order_and_deduplicates(self) -> None:
        selected = upstream_watch.select_manifests(
            self.manifests,
            ["sam", "instanseg", "sam"],
        )
        self.assertEqual(
            [item["component_id"] for item in selected],
            ["sam", "instanseg"],
        )

    def test_select_manifests_rejects_core(self) -> None:
        with self.assertRaisesRegex(ValueError, "qupath-core"):
            upstream_watch.select_manifests(
                self.manifests,
                ["qupath-core"],
            )

    def test_relevant_path_globs_match_source_and_resources(self) -> None:
        patterns = self.manifest()["audit_policy"]["relevant_paths"]
        self.assertTrue(
            upstream_watch.is_relevant_path(
                "src/main/java/qupath/ext/Test.java",
                patterns,
            )
        )
        self.assertTrue(
            upstream_watch.is_relevant_path(
                "src/main/resources/qupath/ext/ui/strings.properties",
                patterns,
            )
        )
        self.assertFalse(
            upstream_watch.is_relevant_path("README.md", patterns)
        )

    def test_path_classification_prioritizes_resource_bundles(self) -> None:
        manifest = self.manifest()
        bundle = manifest["audit_policy"]["bundle_paths"][0]
        self.assertEqual(
            upstream_watch.classify_path(
                bundle,
                manifest["audit_policy"]["bundle_paths"],
            ),
            "RESOURCE_BUNDLE",
        )
        self.assertEqual(
            upstream_watch.classify_path(
                "settings.gradle.kts",
                [],
            ),
            "BUILD_METADATA",
        )
        self.assertEqual(
            upstream_watch.classify_path(
                "src/main/java/qupath/ext/Test.java",
                [],
            ),
            "JAVA_SOURCE",
        )

    def test_current_when_default_branch_head_equals_snapshot(self) -> None:
        manifest = self.manifest()
        baseline = manifest["initial_audit"]["upstream_commit"]
        api = FakeApi(
            self.routes_for(
                manifest,
                head=baseline,
            )
        )

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_CURRENT)
        self.assertFalse(result["relevant_drift"])
        self.assertTrue(result["analysis_complete"])
        self.assertEqual(result["changed_files_reported"], 0)
        self.assertEqual(result["action"], "NONE")
        self.assertEqual(len(api.calls), 2)

    def test_relevant_drift_is_reported_and_classified(self) -> None:
        manifest = self.manifest()
        head = "a" * 40
        bundle = manifest["audit_policy"]["bundle_paths"][0]
        compare = {
            "status": "ahead",
            "ahead_by": 3,
            "behind_by": 0,
            "files": [
                {
                    "filename": bundle,
                    "status": "modified",
                    "additions": 2,
                    "deletions": 1,
                    "changes": 3,
                },
                {
                    "filename": "README.md",
                    "status": "modified",
                    "additions": 1,
                    "deletions": 0,
                    "changes": 1,
                },
            ],
        }
        api = FakeApi(self.routes_for(manifest, head=head, compare=compare))

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_DRIFT)
        self.assertTrue(result["relevant_drift"])
        self.assertEqual(result["action"], "REVIEW_REQUIRED")
        self.assertEqual(result["changed_files_reported"], 2)
        self.assertEqual(len(result["relevant_changed_files"]), 1)
        self.assertEqual(
            result["relevant_changed_files"][0]["classification"],
            "RESOURCE_BUNDLE",
        )

    def test_irrelevant_only_drift_does_not_require_review(self) -> None:
        manifest = self.manifest()
        head = "b" * 40
        compare = {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "files": [
                {
                    "filename": "README.md",
                    "status": "modified",
                    "additions": 5,
                    "deletions": 1,
                    "changes": 6,
                }
            ],
        }
        api = FakeApi(self.routes_for(manifest, head=head, compare=compare))

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_DRIFT)
        self.assertFalse(result["relevant_drift"])
        self.assertEqual(result["action"], "NO_RELEVANT_CHANGE")
        self.assertEqual(result["relevant_changed_files"], [])

    def test_rename_checks_previous_path_for_relevance(self) -> None:
        manifest = self.manifest()
        head = "c" * 40
        compare = {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
            "files": [
                {
                    "filename": "docs/old-ui.txt",
                    "previous_filename": (
                        "src/main/resources/qupath/ext/"
                        "instanseg/ui/legacy.txt"
                    ),
                    "status": "renamed",
                    "additions": 0,
                    "deletions": 0,
                    "changes": 0,
                }
            ],
        }
        api = FakeApi(self.routes_for(manifest, head=head, compare=compare))

        result = upstream_watch.watch_component(manifest, api)

        self.assertTrue(result["relevant_drift"])
        self.assertEqual(len(result["relevant_changed_files"]), 1)

    def test_diverged_history_is_unknown_not_silently_drift(self) -> None:
        manifest = self.manifest()
        head = "d" * 40
        compare = {
            "status": "diverged",
            "ahead_by": 2,
            "behind_by": 2,
            "files": [],
        }
        api = FakeApi(self.routes_for(manifest, head=head, compare=compare))

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_UNKNOWN)
        self.assertIsNone(result["relevant_drift"])
        self.assertEqual(result["action"], "INVESTIGATE")
        self.assertIn("not a simple ancestor", result["error"])

    def test_missing_compare_file_list_is_unknown(self) -> None:
        manifest = self.manifest()
        head = "e" * 40
        compare = {
            "status": "ahead",
            "ahead_by": 1,
            "behind_by": 0,
        }
        api = FakeApi(self.routes_for(manifest, head=head, compare=compare))

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_UNKNOWN)
        self.assertIn("file list", result["error"])

    def test_api_failure_is_error_and_does_not_raise_from_component(self) -> None:
        manifest = self.manifest()
        repository = manifest["repository"]
        api = FakeApi(
            {
                f"repos/{repository}": upstream_watch.UpstreamWatchError(
                    "simulated network failure"
                )
            }
        )

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_ERROR)
        self.assertIn("simulated network failure", result["error"])

    def test_compare_file_cap_is_reported_as_partial_analysis(self) -> None:
        manifest = self.manifest()
        head = "f" * 40
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
            "ahead_by": 301,
            "behind_by": 0,
            "files": files,
        }
        api = FakeApi(self.routes_for(manifest, head=head, compare=compare))

        result = upstream_watch.watch_component(manifest, api)

        self.assertEqual(result["status"], upstream_watch.STATUS_UNKNOWN)
        self.assertIsNone(result["relevant_drift"])
        self.assertEqual(result["action"], "INVESTIGATE")
        self.assertFalse(result["analysis_complete"])
        self.assertTrue(result["warnings"])
        self.assertIn("truncated", result["error"])

    def test_summary_counts_status_and_relevant_drift_independently(self) -> None:
        results = [
            {"status": "CURRENT", "relevant_drift": False},
            {"status": "DRIFT", "relevant_drift": True},
            {"status": "DRIFT", "relevant_drift": False},
            {"status": "UNKNOWN", "relevant_drift": None},
            {"status": "ERROR", "relevant_drift": None},
        ]

        summary = upstream_watch.summarize(results)

        self.assertEqual(
            summary,
            {
                "total": 5,
                "current": 1,
                "drift": 2,
                "relevant_drift": 1,
                "unknown": 1,
                "error": 1,
            },
        )

    def test_exit_code_is_zero_without_errors_when_drift_is_informational(self) -> None:
        report = {
            "summary": {
                "error": 0,
                "unknown": 0,
                "relevant_drift": 1,
            }
        }
        self.assertEqual(
            upstream_watch.exit_code(report, fail_on_drift=False),
            0,
        )
        self.assertEqual(
            upstream_watch.exit_code(report, fail_on_drift=True),
            1,
        )

    def test_exit_code_two_for_unknown_or_error(self) -> None:
        for summary in (
            {"error": 1, "unknown": 0, "relevant_drift": 0},
            {"error": 0, "unknown": 1, "relevant_drift": 0},
        ):
            with self.subTest(summary=summary):
                self.assertEqual(
                    upstream_watch.exit_code(
                        {"summary": summary},
                        fail_on_drift=False,
                    ),
                    2,
                )

    def test_report_is_read_only_and_has_stable_top_level_contract(self) -> None:
        manifest = self.manifest()
        baseline = manifest["initial_audit"]["upstream_commit"]
        api = FakeApi(self.routes_for(manifest, head=baseline))

        report = upstream_watch.build_report([manifest], api)

        self.assertEqual(
            set(report),
            {
                "schema_version",
                "watch_type",
                "generated_at",
                "read_only",
                "components",
                "summary",
            },
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["watch_type"], "UPSTREAM_DRIFT_WATCH")
        self.assertTrue(report["read_only"])
        self.assertEqual(report["summary"]["current"], 1)

    def test_tool_source_contains_no_repository_write_api(self) -> None:
        source = TOOL_PATH.read_text(encoding="utf-8")
        self.assertNotIn("urllib.request.Request(url, data=", source)
        self.assertNotIn('method="POST"', source)
        self.assertNotIn('method="PATCH"', source)
        self.assertNotIn('method="PUT"', source)
        self.assertNotIn('method="DELETE"', source)
        self.assertNotIn(".write_text(", source)
        self.assertNotIn(".write_bytes(", source)


if __name__ == "__main__":
    unittest.main()
