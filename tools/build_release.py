"""
Build deterministic qupath-es release artifacts from immutable Git blobs.

This tool does not publish anything. It consumes a versioned release
specification at one exact source commit and produces four local files:

- <artifact_basename>.zip
- <artifact_basename>.manifest.json
- <artifact_basename>.spdx.json
- <artifact_basename>.SHA256SUMS

The ZIP is byte-reproducible for the same Git commit and release spec:
entries are sorted, uncompressed, use a fixed DOS timestamp and permissions,
and source bytes come from `git show <commit>:<path>` rather than the checkout.
That prevents core.autocrlf or host filesystem metadata from changing a release.

Publication, tag verification and provenance attestation belong to the release
workflow, not to this builder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

if __package__:
    from . import schema_validate
else:
    import schema_validate


SOURCE_REPOSITORY = "https://github.com/LABVETNEB/qupath-es"
SPEC_SCHEMA_PATH = "schemas/release-spec.schema.json"
MANIFEST_SCHEMA_PATH = "schemas/release-manifest.schema.json"
LOCALIZATION_BUNDLE_ROLE = "LOCALIZATION_BUNDLE"

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FIXED_FILE_MODE = stat.S_IFREG | 0o644


class ReleaseError(RuntimeError):
    """Fail-closed release contract violation."""


def canonical_json_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _safe_repo_path(text: str) -> PurePosixPath:
    if "\\" in text:
        raise ReleaseError(f"repository path must use '/': {text!r}")

    path = PurePosixPath(text)
    if path.is_absolute():
        raise ReleaseError(f"absolute repository path is forbidden: {text!r}")
    if not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ReleaseError(f"unsafe repository path: {text!r}")
    if str(path) != text:
        raise ReleaseError(f"non-canonical repository path: {text!r}")
    return path


def _validate_tag(tag: str) -> None:
    if not TAG_RE.fullmatch(tag):
        raise ReleaseError(
            "release tag must start with an alphanumeric character and contain "
            "only alphanumerics, '.', '_', '-' or '/'"
        )
    if ".." in tag or "//" in tag or tag.endswith("/"):
        raise ReleaseError(f"unsafe release tag: {tag!r}")


class GitSource:
    """Read exact bytes and metadata from one immutable commit."""

    def __init__(self, root: Path, commit: str):
        self.root = root.resolve()
        if not COMMIT_RE.fullmatch(commit):
            raise ReleaseError(
                "source_commit must be a 40-character lowercase Git SHA"
            )

        resolved = self._run_text(
            ["rev-parse", f"{commit}^{{commit}}"],
            description=f"resolve commit {commit}",
        ).strip()
        if resolved != commit:
            raise ReleaseError(
                f"source commit resolved to unexpected SHA {resolved!r}"
            )
        self.commit = commit

    def _run(
        self,
        args: list[str],
        *,
        description: str,
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise ReleaseError(f"cannot run Git to {description}: {exc}") from exc

        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise ReleaseError(
                f"Git failed to {description}: {detail or 'unknown error'}"
            )
        return result

    def _run_text(self, args: list[str], *, description: str) -> str:
        raw = self._run(args, description=description).stdout
        return raw.decode("utf-8", errors="strict")

    def read_bytes(self, repo_path: str) -> bytes:
        _safe_repo_path(repo_path)
        return self._run(
            ["show", f"{self.commit}:{repo_path}"],
            description=f"read {repo_path} from {self.commit}",
        ).stdout

    def read_json(self, repo_path: str):
        try:
            return json.loads(
                self.read_bytes(repo_path).decode("utf-8", errors="strict")
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReleaseError(
                f"invalid UTF-8 JSON at {repo_path}: {exc}"
            ) from exc

    def commit_epoch(self) -> int:
        text = self._run_text(
            ["show", "-s", "--format=%ct", self.commit],
            description=f"read commit timestamp for {self.commit}",
        ).strip()
        try:
            value = int(text)
        except ValueError as exc:
            raise ReleaseError(
                f"Git returned an invalid commit timestamp: {text!r}"
            ) from exc
        if value < 0:
            raise ReleaseError("commit timestamp must be non-negative")
        return value


def _read_payload(source: GitSource, spec: dict) -> list[dict]:
    seen_paths: set[str] = set()
    payload: list[dict] = []

    for item in spec["payload"]:
        source_text = item["path"]
        _safe_repo_path(source_text)

        if source_text in seen_paths:
            raise ReleaseError(f"duplicate payload path: {source_text}")
        seen_paths.add(source_text)

        raw = source.read_bytes(source_text)
        payload.append(
            {
                "source_path": source_text,
                "archive_path": (
                    f"{spec['artifact_basename']}/{source_text}"
                ),
                "role": item["role"],
                "component_id": item["component_id"],
                "sha256": sha256_upper(raw),
                "bytes": len(raw),
                "_raw": raw,
            }
        )

    return payload


def _validate_distributed_localizations(
    source: GitSource,
    spec: dict,
    payload: list[dict],
) -> None:
    lock_path = (
        f"versions/{spec['qupath_version']}/localizations.lock.json"
    )
    lock = source.read_json(lock_path)

    if lock["qupath_version"] != spec["qupath_version"]:
        raise ReleaseError(
            "release spec and localization lock target different QuPath versions"
        )

    distributed = {
        entry["component_id"]: entry
        for entry in lock["localizations"]
        if (
            entry["locale"] == spec["locale"]
            and entry["distribution_status"] == "DISTRIBUTED"
        )
    }

    declared_bundles = {
        entry["component_id"]: entry
        for entry in payload
        if entry["role"] == LOCALIZATION_BUNDLE_ROLE
    }

    if None in declared_bundles:
        raise ReleaseError(
            "LOCALIZATION_BUNDLE payload entries require component_id"
        )

    if set(declared_bundles) != set(distributed):
        missing = sorted(set(distributed) - set(declared_bundles))
        extra = sorted(set(declared_bundles) - set(distributed))
        raise ReleaseError(
            "release payload must cover exactly the DISTRIBUTED localizations "
            f"for locale {spec['locale']}; missing={missing}, extra={extra}"
        )

    for component_id, state in distributed.items():
        bundle = declared_bundles[component_id]

        if state["translation_status"] != "TRANSLATED":
            raise ReleaseError(
                f"{component_id}/{spec['locale']} is distributed but not TRANSLATED"
            )
        if state["validation_status"] != "VALIDATED":
            raise ReleaseError(
                f"{component_id}/{spec['locale']} is distributed but not VALIDATED"
            )
        if not state["dist_bundle"] or not state["dist_sha256"]:
            raise ReleaseError(
                f"{component_id}/{spec['locale']} lacks dist bundle fingerprint"
            )
        if bundle["source_path"] != state["dist_bundle"]:
            raise ReleaseError(
                f"{component_id}/{spec['locale']} payload path "
                f"{bundle['source_path']!r} != lock path {state['dist_bundle']!r}"
            )
        if bundle["sha256"] != state["dist_sha256"]:
            raise ReleaseError(
                f"{component_id}/{spec['locale']} payload sha256 "
                f"{bundle['sha256']} != lock sha256 {state['dist_sha256']}"
            )


def validate_release_spec(source: GitSource, spec: dict) -> list[dict]:
    schema = source.read_json(SPEC_SCHEMA_PATH)
    schema_validate.validate(spec, schema)

    artifact_basename = spec["artifact_basename"]
    if "/" in artifact_basename or "\\" in artifact_basename:
        raise ReleaseError(
            "artifact_basename must be a filename stem, not a path"
        )

    for item in spec["payload"]:
        if (
            item["role"] != LOCALIZATION_BUNDLE_ROLE
            and item["component_id"] is not None
        ):
            raise ReleaseError(
                "component_id is reserved for LOCALIZATION_BUNDLE payload entries"
            )

    payload = _read_payload(source, spec)
    _validate_distributed_localizations(source, spec, payload)
    return payload


def _write_deterministic_zip(
    path: Path,
    payload: list[dict],
) -> tuple[str, int]:
    with zipfile.ZipFile(
        path,
        mode="w",
        compression=zipfile.ZIP_STORED,
        strict_timestamps=True,
    ) as archive:
        for item in sorted(payload, key=lambda entry: entry["archive_path"]):
            info = zipfile.ZipInfo(
                filename=item["archive_path"],
                date_time=FIXED_ZIP_TIMESTAMP,
            )
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = FIXED_FILE_MODE << 16
            archive.writestr(info, item["_raw"])

    raw = path.read_bytes()
    return sha256_upper(raw), len(raw)


def _spdx_document(
    spec: dict,
    payload: list[dict],
    release_tag: str,
    source_commit: str,
    source_date_epoch: int,
    artifact_sha256: str,
) -> dict:
    created = datetime.fromtimestamp(
        source_date_epoch,
        tz=timezone.utc,
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    namespace_tag = quote(release_tag, safe="")
    document_namespace = (
        f"{SOURCE_REPOSITORY}/releases/tag/{namespace_tag}/"
        f"sbom/{source_commit}"
    )

    sorted_payload = sorted(payload, key=lambda entry: entry["archive_path"])
    files = []
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package",
        }
    ]

    for index, item in enumerate(sorted_payload, start=1):
        spdx_id = f"SPDXRef-File-{index:03d}"
        files.append(
            {
                "SPDXID": spdx_id,
                "fileName": f"./{item['archive_path']}",
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": item["sha256"],
                    }
                ],
                "licenseConcluded": "NOASSERTION",
                "licenseInfoInFiles": ["NOASSERTION"],
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": spdx_id,
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{spec['artifact_basename']} release SBOM",
        "documentNamespace": document_namespace,
        "creationInfo": {
            "created": created,
            "creators": ["Tool: qupath-es/tools/build_release.py"],
        },
        "packages": [
            {
                "name": spec["artifact_basename"],
                "SPDXID": "SPDXRef-Package",
                "versionInfo": release_tag,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "checksums": [
                    {
                        "algorithm": "SHA256",
                        "checksumValue": artifact_sha256,
                    }
                ],
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        ],
        "files": files,
        "relationships": relationships,
    }


def build_release(
    root: Path,
    spec_path: str,
    output_dir: Path,
    *,
    release_tag: str,
    source_commit: str,
) -> dict:
    root = root.resolve()
    _validate_tag(release_tag)
    _safe_repo_path(spec_path)

    source = GitSource(root, source_commit)
    spec = source.read_json(spec_path)
    payload = validate_release_spec(source, spec)
    source_date_epoch = source.commit_epoch()

    output_dir.mkdir(parents=True, exist_ok=True)

    basename = spec["artifact_basename"]
    artifact_name = f"{basename}.zip"
    manifest_name = f"{basename}.manifest.json"
    sbom_name = f"{basename}.spdx.json"
    checksums_name = f"{basename}.SHA256SUMS"

    artifact_path = output_dir / artifact_name
    manifest_path = output_dir / manifest_name
    sbom_path = output_dir / sbom_name
    checksums_path = output_dir / checksums_name

    artifact_sha256, artifact_bytes = _write_deterministic_zip(
        artifact_path,
        payload,
    )

    sbom = _spdx_document(
        spec,
        payload,
        release_tag,
        source_commit,
        source_date_epoch,
        artifact_sha256,
    )
    sbom_raw = canonical_json_bytes(sbom)
    sbom_path.write_bytes(sbom_raw)
    sbom_sha256 = sha256_upper(sbom_raw)

    manifest_payload = [
        {
            key: item[key]
            for key in (
                "source_path",
                "archive_path",
                "role",
                "component_id",
                "sha256",
                "bytes",
            )
        }
        for item in sorted(payload, key=lambda entry: entry["archive_path"])
    ]

    manifest = {
        "schema_version": 1,
        "release_tag": release_tag,
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": source_commit,
        "source_date_epoch": source_date_epoch,
        "qupath_version": spec["qupath_version"],
        "locale": spec["locale"],
        "artifact": {
            "filename": artifact_name,
            "sha256": artifact_sha256,
            "bytes": artifact_bytes,
        },
        "sbom": {
            "filename": sbom_name,
            "format": "SPDX-2.3-json",
            "sha256": sbom_sha256,
            "bytes": len(sbom_raw),
        },
        "checksums_filename": checksums_name,
        "payload": manifest_payload,
    }

    manifest_schema = source.read_json(MANIFEST_SCHEMA_PATH)
    schema_validate.validate(manifest, manifest_schema)

    manifest_raw = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_raw)
    manifest_sha256 = sha256_upper(manifest_raw)

    checksum_records = {
        artifact_name: artifact_sha256,
        manifest_name: manifest_sha256,
        sbom_name: sbom_sha256,
    }
    checksum_text = "".join(
        f"{checksum_records[name]}  {name}\n"
        for name in sorted(checksum_records)
    )
    checksums_path.write_text(
        checksum_text,
        encoding="ascii",
        newline="\n",
    )

    return {
        "artifact": artifact_path,
        "manifest": manifest_path,
        "sbom": sbom_path,
        "checksums": checksums_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build reproducible qupath-es release artifacts."
    )
    parser.add_argument(
        "--spec",
        required=True,
        help="Repository-relative release spec JSON.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where release artifacts are written.",
    )
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the checkout containing this tool).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        outputs = build_release(
            args.repo,
            args.spec,
            args.output_dir,
            release_tag=args.release_tag,
            source_commit=args.source_commit,
        )
    except (
        ReleaseError,
        OSError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"release build failed: {exc}", file=sys.stderr)
        return 2

    summary = {
        name: path.name
        for name, path in outputs.items()
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
