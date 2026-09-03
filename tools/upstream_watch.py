#!/usr/bin/env python3
"""Detect upstream drift for registered QuPath extension audit snapshots.

This tool is read-only. It compares each extension's immutable initial audit
commit with the current upstream default branch using the GitHub REST API.
It never clones repositories, edits manifests, updates lockfiles, or claims
runtime compatibility.

The tool uses only the Python standard library. CI tests mock the API so test
results do not depend on network access.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = ROOT / "components"
REGISTRY_PATH = COMPONENTS_DIR / "registry.json"
GITHUB_API = "https://api.github.com"
COMPARE_FILE_LIMIT = 300

STATUS_CURRENT = "CURRENT"
STATUS_DRIFT = "DRIFT"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_ERROR = "ERROR"


class UpstreamWatchError(RuntimeError):
    """Operational error while resolving upstream state."""


def load_json(path: Path) -> Any:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} has a UTF-8 BOM")
    return json.loads(data.decode("utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repository_slug(value: str) -> str:
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"invalid GitHub repository slug: {value!r}")
    return value


def load_extension_manifests() -> list[dict[str, Any]]:
    registry = load_json(REGISTRY_PATH)
    manifests: list[dict[str, Any]] = []

    for entry in registry["components"]:
        if entry["type"] != "QUPATH_EXTENSION":
            continue

        component_id = entry["id"]
        path = COMPONENTS_DIR / component_id / "component.json"
        if not path.is_file():
            raise ValueError(f"missing component manifest: {path}")

        manifest = load_json(path)
        if manifest.get("component_id") != component_id:
            raise ValueError(
                f"manifest id mismatch for {component_id}: "
                f"{manifest.get('component_id')!r}"
            )
        if manifest.get("repository") != entry["repository"]:
            raise ValueError(
                f"repository mismatch for {component_id}: "
                f"{manifest.get('repository')!r}"
            )

        _repository_slug(manifest["repository"])
        manifests.append(manifest)

    if (COMPONENTS_DIR / "qupath-core").exists():
        raise ValueError(
            "components/qupath-core must not exist; Core remains under versions/"
        )

    return manifests


def select_manifests(
    manifests: Sequence[dict[str, Any]],
    component_ids: Sequence[str] | None,
) -> list[dict[str, Any]]:
    if not component_ids:
        return list(manifests)

    by_id = {item["component_id"]: item for item in manifests}
    requested = list(dict.fromkeys(component_ids))

    invalid = [component_id for component_id in requested if component_id not in by_id]
    if invalid:
        if "qupath-core" in invalid:
            raise ValueError(
                "qupath-core is not watched through components/: "
                "Core remains under versions/<v>/"
            )
        raise ValueError(f"unknown extension component(s): {', '.join(invalid)}")

    return [by_id[component_id] for component_id in requested]


def path_matches(path: str, pattern: str) -> bool:
    """Match repository paths against manifest glob patterns."""
    path = path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    return fnmatch.fnmatchcase(path, pattern)


def is_relevant_path(path: str, patterns: Iterable[str]) -> bool:
    return any(path_matches(path, pattern) for pattern in patterns)


def classify_path(path: str, bundle_paths: Iterable[str]) -> str:
    normalized = path.replace("\\", "/")
    bundles = {item.replace("\\", "/") for item in bundle_paths}

    if normalized in bundles:
        return "RESOURCE_BUNDLE"
    if normalized in {
        "settings.gradle.kts",
        "build.gradle.kts",
        "gradle/libs.versions.toml",
    }:
        return "BUILD_METADATA"
    if normalized.endswith(".fxml"):
        return "FXML"
    if normalized.startswith("src/main/java/") and normalized.endswith(".java"):
        return "JAVA_SOURCE"
    if normalized.startswith("src/main/groovy/") or normalized.endswith(".groovy"):
        return "GROOVY_SCRIPT"
    if normalized.startswith("src/main/python/") or normalized.endswith(".py"):
        return "PYTHON_SOURCE"
    if normalized.startswith("src/main/scripts/"):
        return "SCRIPT"
    if normalized.startswith("src/main/resources/"):
        if normalized.endswith((".json", ".yaml", ".yml")):
            return "RESOURCE_METADATA"
        return "RESOURCE"
    return "OTHER_RELEVANT"


class GitHubApi:
    """Minimal GitHub REST client using urllib only."""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str = GITHUB_API,
        timeout: float = 20.0,
    ) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str) -> Any:
        url = f"{self.api_base}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "qupath-es-upstream-watch/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            message = exc.reason or f"HTTP {exc.code}"
            raise UpstreamWatchError(
                f"GitHub API HTTP {exc.code} for {url}: {message}"
            ) from exc
        except urllib.error.URLError as exc:
            raise UpstreamWatchError(
                f"GitHub API request failed for {url}: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise UpstreamWatchError(
                f"GitHub API request timed out for {url}"
            ) from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpstreamWatchError(
                f"GitHub API returned invalid JSON for {url}"
            ) from exc


def _quote_ref(ref: str) -> str:
    return urllib.parse.quote(ref, safe="")


def _normalized_changed_file(
    item: Mapping[str, Any],
    *,
    relevant_patterns: Sequence[str],
    bundle_paths: Sequence[str],
) -> dict[str, Any]:
    filename = str(item.get("filename", ""))
    previous_filename = item.get("previous_filename")
    destination_relevant = is_relevant_path(filename, relevant_patterns)
    previous_relevant = bool(previous_filename) and is_relevant_path(
        str(previous_filename), relevant_patterns
    )
    relevant = destination_relevant or previous_relevant

    classification_path = filename
    if not destination_relevant and previous_relevant:
        classification_path = str(previous_filename)

    classification = (
        classify_path(classification_path, bundle_paths)
        if relevant
        else "IRRELEVANT"
    )

    return {
        "path": filename,
        "previous_path": previous_filename,
        "change_status": item.get("status"),
        "additions": item.get("additions"),
        "deletions": item.get("deletions"),
        "changes": item.get("changes"),
        "relevant": relevant,
        "classification": classification,
    }


def watch_component(
    manifest: Mapping[str, Any],
    api: GitHubApi,
) -> dict[str, Any]:
    component_id = str(manifest["component_id"])
    repository = _repository_slug(str(manifest["repository"]))
    baseline = str(manifest["initial_audit"]["upstream_commit"])
    policy = manifest["audit_policy"]
    relevant_patterns = list(policy["relevant_paths"])
    bundle_paths = list(policy["bundle_paths"])

    base_result: dict[str, Any] = {
        "component_id": component_id,
        "repository": repository,
        "baseline_commit": baseline,
        "default_branch": None,
        "head_commit": None,
        "status": STATUS_ERROR,
        "relevant_drift": None,
        "compare_status": None,
        "ahead_by": None,
        "behind_by": None,
        "changed_files_reported": None,
        "relevant_changed_files": [],
        "analysis_complete": False,
        "action": "INVESTIGATE",
        "warnings": [],
        "error": None,
    }

    try:
        repo_data = api.get_json(f"repos/{repository}")
        default_branch = str(repo_data["default_branch"])
        base_result["default_branch"] = default_branch

        commit_data = api.get_json(
            f"repos/{repository}/commits/{_quote_ref(default_branch)}"
        )
        head = str(commit_data["sha"])
        base_result["head_commit"] = head

        if head == baseline:
            base_result.update(
                {
                    "status": STATUS_CURRENT,
                    "relevant_drift": False,
                    "compare_status": "identical",
                    "ahead_by": 0,
                    "behind_by": 0,
                    "changed_files_reported": 0,
                    "analysis_complete": True,
                    "action": "NONE",
                }
            )
            return base_result

        compare = api.get_json(
            f"repos/{repository}/compare/"
            f"{_quote_ref(baseline)}...{_quote_ref(head)}"
        )
        compare_status = str(compare.get("status", "unknown"))
        base_result["compare_status"] = compare_status
        base_result["ahead_by"] = compare.get("ahead_by")
        base_result["behind_by"] = compare.get("behind_by")

        files_raw = compare.get("files")
        if not isinstance(files_raw, list):
            base_result.update(
                {
                    "status": STATUS_UNKNOWN,
                    "relevant_drift": None,
                    "action": "INVESTIGATE",
                    "error": "GitHub compare response did not include a file list",
                }
            )
            return base_result

        normalized = [
            _normalized_changed_file(
                item,
                relevant_patterns=relevant_patterns,
                bundle_paths=bundle_paths,
            )
            for item in files_raw
        ]
        relevant_files = [item for item in normalized if item["relevant"]]
        base_result["changed_files_reported"] = len(normalized)
        base_result["relevant_changed_files"] = relevant_files

        analysis_complete = len(normalized) < COMPARE_FILE_LIMIT
        base_result["analysis_complete"] = analysis_complete
        if not analysis_complete:
            base_result["warnings"].append(
                "GitHub compare returned 300 files; the inventory may be truncated"
            )

        if compare_status == "identical":
            base_result.update(
                {
                    "status": STATUS_CURRENT,
                    "relevant_drift": False,
                    "action": "NONE",
                }
            )
            return base_result

        if compare_status == "ahead":
            if not analysis_complete and not relevant_files:
                base_result.update(
                    {
                        "status": STATUS_UNKNOWN,
                        "relevant_drift": None,
                        "action": "INVESTIGATE",
                        "error": (
                            "GitHub compare file inventory is truncated before "
                            "relevant drift can be ruled out"
                        ),
                    }
                )
                return base_result

            relevant_drift = bool(relevant_files)
            base_result.update(
                {
                    "status": STATUS_DRIFT,
                    "relevant_drift": relevant_drift,
                    "action": (
                        "REVIEW_REQUIRED"
                        if relevant_drift
                        else "NO_RELEVANT_CHANGE"
                    ),
                }
            )
            return base_result

        base_result.update(
            {
                "status": STATUS_UNKNOWN,
                "relevant_drift": None,
                "action": "INVESTIGATE",
                "error": (
                    "audited baseline is not a simple ancestor of upstream head "
                    f"(compare status: {compare_status})"
                ),
            }
        )
        return base_result

    except (KeyError, TypeError, ValueError, UpstreamWatchError) as exc:
        base_result["status"] = STATUS_ERROR
        base_result["relevant_drift"] = None
        base_result["action"] = "INVESTIGATE"
        base_result["error"] = str(exc)
        return base_result


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    summary = {
        "total": len(results),
        "current": 0,
        "drift": 0,
        "relevant_drift": 0,
        "unknown": 0,
        "error": 0,
    }
    for result in results:
        status = result["status"]
        if status == STATUS_CURRENT:
            summary["current"] += 1
        elif status == STATUS_DRIFT:
            summary["drift"] += 1
            if result.get("relevant_drift"):
                summary["relevant_drift"] += 1
        elif status == STATUS_UNKNOWN:
            summary["unknown"] += 1
        elif status == STATUS_ERROR:
            summary["error"] += 1
    return summary


def build_report(
    manifests: Sequence[dict[str, Any]],
    api: GitHubApi,
) -> dict[str, Any]:
    results = [watch_component(manifest, api) for manifest in manifests]
    return {
        "schema_version": 1,
        "watch_type": "UPSTREAM_DRIFT_WATCH",
        "generated_at": utc_now(),
        "read_only": True,
        "components": results,
        "summary": summarize(results),
    }


def exit_code(report: Mapping[str, Any], *, fail_on_drift: bool) -> int:
    summary = report["summary"]
    if summary["error"] or summary["unknown"]:
        return 2
    if fail_on_drift and summary["relevant_drift"]:
        return 1
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare immutable extension audit snapshots with current "
            "upstream default branches."
        )
    )
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        metavar="ID",
        help="watch only this extension id; repeat to select multiple",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="return exit code 1 when relevant upstream drift is detected",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="GitHub API timeout in seconds (default: 20)",
    )
    parser.add_argument(
        "--api-base",
        default=GITHUB_API,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        manifests = load_extension_manifests()
        selected = select_manifests(manifests, args.component)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"upstream-watch: {exc}", file=sys.stderr)
        return 2

    token = os.environ.get("GITHUB_TOKEN")
    api = GitHubApi(
        token=token,
        api_base=args.api_base,
        timeout=args.timeout,
    )
    report = build_report(selected, api)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return exit_code(report, fail_on_drift=args.fail_on_drift)


if __name__ == "__main__":
    raise SystemExit(main())
