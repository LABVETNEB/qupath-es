"""Verify pinned upstream release assets against lockfile SHA-256 values.

This command is intentionally opt-in and networked; CI does not download third-
party release assets. The lockfile itself is validated offline by the test
suite. Use this tool when refreshing provenance or before relying on an asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = REPO / "versions" / "0.7.0" / "components.lock.json"
CHUNK_SIZE = 1024 * 1024


class ArtifactVerificationError(RuntimeError):
    pass


def _validate_release_url(url: str, artifact_name: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ArtifactVerificationError(
            f"artifact URL must be an https://github.com release asset: {url}"
        )
    if "/releases/download/" not in parsed.path:
        raise ArtifactVerificationError(f"not a GitHub release download URL: {url}")
    if not parsed.path.endswith("/" + artifact_name):
        raise ArtifactVerificationError(
            f"artifact URL does not end with artifact_name {artifact_name!r}: {url}"
        )


def sha256_response(response) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = response.read(CHUNK_SIZE)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest().upper()


def verify_entry(entry: dict, *, timeout: float = 60.0) -> str:
    component_id = entry["component_id"]
    artifact_name = entry.get("artifact_name")
    url = entry.get("artifact_url")
    expected = entry.get("artifact_sha256")

    if not artifact_name or not url or not expected:
        raise ArtifactVerificationError(
            f"{component_id}: artifact provenance is incomplete"
        )

    _validate_release_url(url, artifact_name)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "qupath-es-artifact-verifier/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            actual = sha256_response(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ArtifactVerificationError(
            f"{component_id}: could not download {url}: {exc}"
        ) from exc

    if actual != expected:
        raise ArtifactVerificationError(
            f"{component_id}: SHA-256 mismatch: {actual} != {expected}"
        )
    return actual


def _load_entries(lock_path: Path) -> list[dict]:
    data = json.loads(lock_path.read_text(encoding="utf-8"))
    return data["components"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify upstream release assets pinned in components.lock.json."
    )
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument(
        "--component",
        action="append",
        default=[],
        help="component id to verify; repeat to select more than one",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args(argv)

    entries = _load_entries(args.lock)
    selected = set(args.component)
    if selected:
        entries = [entry for entry in entries if entry["component_id"] in selected]
        missing = selected - {entry["component_id"] for entry in entries}
        if missing:
            print(f"Unknown component(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    else:
        entries = [entry for entry in entries if entry["pin_basis"] == "UPSTREAM_RELEASE"]

    failures = 0
    for entry in entries:
        component_id = entry["component_id"]
        try:
            digest = verify_entry(entry, timeout=args.timeout)
        except ArtifactVerificationError as exc:
            failures += 1
            print(f"FAIL {exc}", file=sys.stderr)
        else:
            print(f"OK {component_id} {digest}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
