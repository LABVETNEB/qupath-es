"""
Fail-closed guard for tag-gated qupath-es releases.

Two commands are intentionally separate:

preflight
    Proves that a manual workflow dispatch is running from an existing tag,
    that the checked-out/tagged commit is already contained in main, and that
    the tagged release specification, localization state and canonical
    fingerprints are internally consistent.

verify-outputs
    Independently verifies the four files emitted by build_release.py before
    they are attested or published.

The guard performs no network writes and never creates tags or releases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

if __package__:
    from . import build_release, schema_validate
else:
    import build_release
    import schema_validate


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
TAG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class ReleaseGuardError(RuntimeError):
    """Raised when a release precondition cannot be proven."""


def _sha256_upper(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _git(
    root: Path,
    *args: str,
    allow_ancestor_false: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ReleaseGuardError(f"cannot run Git: {exc}") from exc

    allowed = {0, 1} if allow_ancestor_false else {0}
    if result.returncode not in allowed:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseGuardError(
            f"Git command failed ({' '.join(args)}): {detail or result.returncode}"
        )
    return result


def _git_text(root: Path, *args: str) -> str:
    return _git(root, *args).stdout.decode("utf-8", errors="strict").strip()


def _resolve_commit(root: Path, ref: str) -> str:
    resolved = _git_text(root, "rev-parse", f"{ref}^{{commit}}")
    if not SHA40_RE.fullmatch(resolved):
        raise ReleaseGuardError(f"{ref!r} did not resolve to a full commit SHA")
    return resolved


def _validate_tag_ref(tag_ref: str) -> str:
    prefix = "refs/tags/"
    if not tag_ref.startswith(prefix):
        raise ReleaseGuardError(
            f"release must be dispatched from a tag ref, got {tag_ref!r}"
        )

    tag = tag_ref[len(prefix) :]
    if not TAG_NAME_RE.fullmatch(tag):
        raise ReleaseGuardError(f"unsafe release tag name: {tag!r}")
    if ".." in tag or "//" in tag or tag.endswith("/"):
        raise ReleaseGuardError(f"unsafe release tag name: {tag!r}")
    return tag


def verify_tag_checkout(
    root: Path,
    *,
    tag_ref: str,
    checkout_commit: str,
    main_ref: str,
) -> dict:
    root = root.resolve()
    tag = _validate_tag_ref(tag_ref)

    if not SHA40_RE.fullmatch(checkout_commit):
        raise ReleaseGuardError(
            "checkout_commit must be a 40-character lowercase Git SHA"
        )

    head_commit = _resolve_commit(root, "HEAD")
    tag_commit = _resolve_commit(root, tag_ref)
    main_commit = _resolve_commit(root, main_ref)

    if head_commit != checkout_commit:
        raise ReleaseGuardError(
            f"HEAD {head_commit} != workflow checkout {checkout_commit}"
        )
    if tag_commit != checkout_commit:
        raise ReleaseGuardError(
            f"tag {tag_ref} resolves to {tag_commit}, not {checkout_commit}"
        )

    ancestor = _git(
        root,
        "merge-base",
        "--is-ancestor",
        checkout_commit,
        main_ref,
        allow_ancestor_false=True,
    )
    if ancestor.returncode == 1:
        raise ReleaseGuardError(
            f"tagged commit {checkout_commit} is not contained in {main_ref}"
        )

    return {
        "tag": tag,
        "tag_ref": tag_ref,
        "source_commit": checkout_commit,
        "main_ref": main_ref,
        "main_commit": main_commit,
    }


def _safe_version_artifact_path(version: str, relative_path: str) -> str:
    path = PurePosixPath(relative_path)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ReleaseGuardError(
            f"unsafe canonical fingerprint path: {relative_path!r}"
        )
    if "\\" in relative_path or str(path) != relative_path:
        raise ReleaseGuardError(
            f"non-canonical fingerprint path: {relative_path!r}"
        )
    return f"versions/{version}/{relative_path}"


def _verify_canonical_fingerprint(
    source: build_release.GitSource,
    spec: dict,
) -> dict:
    version = spec["qupath_version"]
    fingerprint = source.read_json(f"versions/{version}/fingerprint.json")

    if fingerprint.get("qupath", {}).get("version") != version:
        raise ReleaseGuardError(
            "fingerprint.json and release spec target different QuPath versions"
        )

    artifacts = fingerprint.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ReleaseGuardError("fingerprint.json declares no canonical artifacts")

    verified: dict[str, dict] = {}
    for name, record in sorted(artifacts.items()):
        if not isinstance(record, dict):
            raise ReleaseGuardError(f"invalid fingerprint record for {name!r}")

        relative_path = record.get("path")
        expected_sha = record.get("sha256")
        expected_bytes = record.get("bytes")

        if not isinstance(relative_path, str):
            raise ReleaseGuardError(f"{name}: fingerprint path is missing")
        if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
            raise ReleaseGuardError(f"{name}: invalid recorded SHA-256")
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise ReleaseGuardError(f"{name}: invalid recorded byte count")

        repo_path = _safe_version_artifact_path(version, relative_path)
        raw = source.read_bytes(repo_path)
        actual_sha = _sha256_upper(raw)

        if actual_sha != expected_sha:
            raise ReleaseGuardError(
                f"{repo_path}: sha256 {actual_sha} != recorded {expected_sha}"
            )
        if len(raw) != expected_bytes:
            raise ReleaseGuardError(
                f"{repo_path}: {len(raw)} bytes != recorded {expected_bytes}"
            )

        verified[name] = {
            "path": repo_path,
            "sha256": actual_sha,
            "bytes": len(raw),
        }

    return verified


def _verify_supported_version(
    source: build_release.GitSource,
    spec: dict,
    canonical: dict,
) -> dict:
    version = spec["qupath_version"]
    supported = source.read_json("versions/supported-versions.json")
    versions = supported.get("versions", {})
    declared = versions.get(version)

    if not isinstance(declared, dict):
        raise ReleaseGuardError(
            f"QuPath {version} is absent from versions/supported-versions.json"
        )
    if declared.get("status") != "stable":
        raise ReleaseGuardError(
            f"QuPath {version} is not declared stable; refusing public release"
        )

    root_bundle = canonical.get("root_bundle")
    if not root_bundle:
        raise ReleaseGuardError("canonical root_bundle fingerprint is missing")
    if declared.get("base_bundle_sha256") != root_bundle["sha256"]:
        raise ReleaseGuardError(
            "supported-versions base_bundle_sha256 disagrees with fingerprint.json"
        )

    lock = source.read_json(f"versions/{version}/localizations.lock.json")
    core_matches = [
        entry
        for entry in lock.get("localizations", [])
        if (
            entry.get("component_id") == "qupath-core"
            and entry.get("locale") == spec["locale"]
        )
    ]
    if len(core_matches) != 1:
        raise ReleaseGuardError(
            "expected exactly one qupath-core localization for release locale"
        )

    core = core_matches[0]
    if core.get("distribution_status") != "DISTRIBUTED":
        raise ReleaseGuardError(
            "qupath-core localization is not DISTRIBUTED for this locale"
        )

    if spec["locale"] == "es":
        recorded = declared.get("spanish_bundle_sha256")
        if recorded != core.get("dist_sha256"):
            raise ReleaseGuardError(
                "supported-versions spanish_bundle_sha256 disagrees with "
                "localizations.lock.json"
            )

    return declared


def verify_release_state(
    root: Path,
    *,
    source_commit: str,
    spec_path: str,
) -> dict:
    root = root.resolve()
    source = build_release.GitSource(root, source_commit)
    spec = source.read_json(spec_path)

    payload = build_release.validate_release_spec(source, spec)
    canonical = _verify_canonical_fingerprint(source, spec)
    supported = _verify_supported_version(source, spec, canonical)

    distributed_components = sorted(
        {
            entry["component_id"]
            for entry in payload
            if entry["role"] == build_release.LOCALIZATION_BUNDLE_ROLE
        }
    )

    return {
        "source_commit": source_commit,
        "spec": spec_path,
        "qupath_version": spec["qupath_version"],
        "locale": spec["locale"],
        "artifact_basename": spec["artifact_basename"],
        "payload_files": len(payload),
        "distributed_components": distributed_components,
        "supported_status": supported["status"],
        "canonical_artifacts": canonical,
    }


def preflight(
    root: Path,
    *,
    tag_ref: str,
    checkout_commit: str,
    main_ref: str,
    spec_path: str,
) -> dict:
    git_state = verify_tag_checkout(
        root,
        tag_ref=tag_ref,
        checkout_commit=checkout_commit,
        main_ref=main_ref,
    )
    release_state = verify_release_state(
        root,
        source_commit=checkout_commit,
        spec_path=spec_path,
    )
    return {**git_state, **release_state}


def _parse_checksum_file(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise ReleaseGuardError("SHA256SUMS must be ASCII") from exc

    if "\r" in text:
        raise ReleaseGuardError("SHA256SUMS must use LF line endings")
    if not text.endswith("\n"):
        raise ReleaseGuardError("SHA256SUMS must end with LF")

    records: dict[str, str] = {}
    lines = text.splitlines()
    for line in lines:
        match = re.fullmatch(r"([0-9A-F]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if not match:
            raise ReleaseGuardError(f"invalid SHA256SUMS record: {line!r}")
        digest, filename = match.groups()
        if filename in records:
            raise ReleaseGuardError(
                f"duplicate SHA256SUMS filename: {filename}"
            )
        records[filename] = digest

    if [name for name in records] != sorted(records):
        raise ReleaseGuardError("SHA256SUMS records must be filename-sorted")
    return records


def verify_output_set(root: Path, output_dir: Path) -> dict:
    root = root.resolve()
    output_dir = output_dir.resolve()

    if not output_dir.is_dir():
        raise ReleaseGuardError(f"release output directory not found: {output_dir}")

    entries = list(output_dir.iterdir())
    if any(not path.is_file() for path in entries):
        raise ReleaseGuardError("release output directory may contain files only")
    if len(entries) != 4:
        raise ReleaseGuardError(
            f"release output must contain exactly 4 files, found {len(entries)}"
        )

    manifest_candidates = [
        path for path in entries if path.name.endswith(".manifest.json")
    ]
    if len(manifest_candidates) != 1:
        raise ReleaseGuardError("expected exactly one *.manifest.json output")

    manifest_path = manifest_candidates[0]
    basename = manifest_path.name[: -len(".manifest.json")]

    expected_names = {
        f"{basename}.zip",
        f"{basename}.manifest.json",
        f"{basename}.spdx.json",
        f"{basename}.SHA256SUMS",
    }
    actual_names = {path.name for path in entries}
    if actual_names != expected_names:
        raise ReleaseGuardError(
            f"unexpected release output set: {sorted(actual_names)}"
        )

    artifact_path = output_dir / f"{basename}.zip"
    sbom_path = output_dir / f"{basename}.spdx.json"
    checksums_path = output_dir / f"{basename}.SHA256SUMS"

    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8", errors="strict")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseGuardError(f"invalid release manifest: {exc}") from exc

    manifest_schema = json.loads(
        (root / "schemas" / "release-manifest.schema.json").read_text(
            encoding="utf-8"
        )
    )
    schema_validate.validate(manifest, manifest_schema)

    artifact_raw = artifact_path.read_bytes()
    manifest_raw = manifest_path.read_bytes()
    sbom_raw = sbom_path.read_bytes()
    checksums_raw = checksums_path.read_bytes()

    artifact_sha = _sha256_upper(artifact_raw)
    manifest_sha = _sha256_upper(manifest_raw)
    sbom_sha = _sha256_upper(sbom_raw)

    if manifest["artifact"]["filename"] != artifact_path.name:
        raise ReleaseGuardError("manifest artifact filename mismatch")
    if manifest["artifact"]["sha256"] != artifact_sha:
        raise ReleaseGuardError("manifest artifact SHA-256 mismatch")
    if manifest["artifact"]["bytes"] != len(artifact_raw):
        raise ReleaseGuardError("manifest artifact byte count mismatch")

    if manifest["sbom"]["filename"] != sbom_path.name:
        raise ReleaseGuardError("manifest SBOM filename mismatch")
    if manifest["sbom"]["sha256"] != sbom_sha:
        raise ReleaseGuardError("manifest SBOM SHA-256 mismatch")
    if manifest["sbom"]["bytes"] != len(sbom_raw):
        raise ReleaseGuardError("manifest SBOM byte count mismatch")

    if manifest["checksums_filename"] != checksums_path.name:
        raise ReleaseGuardError("manifest checksums filename mismatch")

    checksum_records = _parse_checksum_file(checksums_raw)
    expected_checksums = {
        artifact_path.name: artifact_sha,
        manifest_path.name: manifest_sha,
        sbom_path.name: sbom_sha,
    }
    if checksum_records != expected_checksums:
        raise ReleaseGuardError(
            "SHA256SUMS does not exactly describe artifact, manifest and SBOM"
        )

    try:
        sbom = json.loads(sbom_raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseGuardError(f"invalid SPDX JSON: {exc}") from exc

    if sbom.get("spdxVersion") != "SPDX-2.3":
        raise ReleaseGuardError("SBOM is not SPDX-2.3")
    packages = sbom.get("packages")
    if not isinstance(packages, list) or len(packages) != 1:
        raise ReleaseGuardError("SBOM must describe exactly one release package")

    package_checksums = packages[0].get("checksums")
    if not isinstance(package_checksums, list):
        raise ReleaseGuardError("SBOM package checksum is missing")

    sha256_values = [
        item.get("checksumValue")
        for item in package_checksums
        if isinstance(item, dict) and item.get("algorithm") == "SHA256"
    ]
    if sha256_values != [artifact_sha]:
        raise ReleaseGuardError("SBOM package checksum does not match release ZIP")

    files = sbom.get("files")
    if not isinstance(files, list) or len(files) != len(manifest["payload"]):
        raise ReleaseGuardError("SBOM file set does not match manifest payload")

    sbom_file_hashes: dict[str, str] = {}
    for file_entry in files:
        if not isinstance(file_entry, dict):
            raise ReleaseGuardError("invalid SBOM file entry")
        file_name = file_entry.get("fileName")
        if not isinstance(file_name, str) or not file_name.startswith("./"):
            raise ReleaseGuardError("SBOM fileName must start with './'")

        checksums = file_entry.get("checksums")
        if not isinstance(checksums, list):
            raise ReleaseGuardError("SBOM file checksum is missing")

        values = [
            item.get("checksumValue")
            for item in checksums
            if isinstance(item, dict) and item.get("algorithm") == "SHA256"
        ]
        if len(values) != 1 or not isinstance(values[0], str):
            raise ReleaseGuardError("SBOM file must have exactly one SHA256")
        sbom_file_hashes[file_name[2:]] = values[0]

    manifest_file_hashes = {
        entry["archive_path"]: entry["sha256"]
        for entry in manifest["payload"]
    }
    if sbom_file_hashes != manifest_file_hashes:
        raise ReleaseGuardError("SBOM file hashes do not match manifest payload")

    return {
        "artifact_basename": basename,
        "artifact": {
            "filename": artifact_path.name,
            "sha256": artifact_sha,
            "bytes": len(artifact_raw),
        },
        "manifest": {
            "filename": manifest_path.name,
            "sha256": manifest_sha,
            "bytes": len(manifest_raw),
        },
        "sbom": {
            "filename": sbom_path.name,
            "sha256": sbom_sha,
            "bytes": len(sbom_raw),
        },
        "checksums": {
            "filename": checksums_path.name,
            "bytes": len(checksums_raw),
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed guard for qupath-es releases."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="Verify tag, main ancestry and release source state.",
    )
    preflight_parser.add_argument("--repo", type=Path, required=True)
    preflight_parser.add_argument("--tag-ref", required=True)
    preflight_parser.add_argument("--checkout-commit", required=True)
    preflight_parser.add_argument(
        "--main-ref",
        default="refs/remotes/origin/main",
    )
    preflight_parser.add_argument("--spec", required=True)

    outputs_parser = subparsers.add_parser(
        "verify-outputs",
        help="Verify ZIP, manifest, SBOM and SHA256SUMS before publication.",
    )
    outputs_parser.add_argument("--repo", type=Path, required=True)
    outputs_parser.add_argument("--output-dir", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            result = preflight(
                args.repo,
                tag_ref=args.tag_ref,
                checkout_commit=args.checkout_commit,
                main_ref=args.main_ref,
                spec_path=args.spec,
            )
        elif args.command == "verify-outputs":
            result = verify_output_set(args.repo, args.output_dir)
        else:  # pragma: no cover - argparse owns this branch
            raise ReleaseGuardError(f"unsupported command: {args.command}")
    except (
        ReleaseGuardError,
        build_release.ReleaseError,
        schema_validate.SchemaValidationError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        print(f"release guard failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
