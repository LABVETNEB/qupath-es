#!/usr/bin/env python3
"""Project supported qupath-es extension distributions into a QuPath catalog.

The catalog is generated from repository authorities; it is never hand-curated.
Only extension localizations that are translated, validated, distributed, runtime
compatible with the target QuPath version, and backed by a pinned GitHub release
asset can be emitted.

This tool is intentionally offline and standard-library only. It validates URL
shape but never performs network requests. Publication of the catalog URL is a
separate governance decision.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

if __package__:
    from . import schema_validate
else:
    import schema_validate


DEFAULT_QUPATH_VERSION = "0.7.0"
DEFAULT_LOCALE = "es"
CATALOG_PATH = Path("catalog/catalog.json")
CATALOG_SCHEMA_PATH = Path("schemas/extension-catalog.schema.json")
REGISTRY_PATH = Path("components/registry.json")
MODEL_REPOSITORY = "qupath/extension-catalog-model"
MODEL_COMMIT = "89dd551c81db0b16455fc172a05ada694ac013ae"
VERSION_RE = re.compile(r"^v[0-9]+(?:\.[0-9]+)?(?:\.[0-9]+)?(?:-rc[0-9]+)?$")
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")


class CatalogProjectionError(RuntimeError):
    """Fail-closed catalog projection error."""


@dataclass(frozen=True)
class ProjectionResult:
    catalog: dict[str, Any]
    excluded: dict[str, tuple[str, ...]]


def _load_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CatalogProjectionError(f"cannot read {path}: {exc}") from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        raise CatalogProjectionError(f"{path} has a UTF-8 BOM")
    if b"\r" in raw:
        raise CatalogProjectionError(f"{path} must use LF line endings")
    try:
        return json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CatalogProjectionError(f"invalid UTF-8 JSON at {path}: {exc}") from exc


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _index(items: Any, key: str, context: str) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        raise CatalogProjectionError(f"{context} must be an array")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CatalogProjectionError(f"{context}[{index}] must be an object")
        identity = item.get(key)
        if not isinstance(identity, str) or not identity:
            raise CatalogProjectionError(f"{context}[{index}].{key} must be a non-empty string")
        if identity in result:
            raise CatalogProjectionError(f"duplicate {key} {identity!r} in {context}")
        result[identity] = item
    return result


def _localization_index(items: Any, context: str) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(items, list):
        raise CatalogProjectionError(f"{context} must be an array")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CatalogProjectionError(f"{context}[{index}] must be an object")
        component_id = item.get("component_id")
        locale = item.get("locale")
        if not isinstance(component_id, str) or not component_id:
            raise CatalogProjectionError(f"{context}[{index}].component_id is invalid")
        if not isinstance(locale, str) or not locale:
            raise CatalogProjectionError(f"{context}[{index}].locale is invalid")
        identity = (component_id, locale)
        if identity in result:
            raise CatalogProjectionError(f"duplicate localization {identity!r}")
        result[identity] = item
    return result


def _validate_release_url(url: str, repository: str) -> None:
    if not isinstance(url, str) or not url.startswith("https://"):
        raise CatalogProjectionError("catalog release URL must use https")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise CatalogProjectionError(f"catalog release URL must be hosted on github.com: {url}")
    expected_prefix = f"/{repository}/releases/download/"
    if not parsed.path.startswith(expected_prefix):
        raise CatalogProjectionError(
            f"catalog release URL {url!r} does not belong to {repository!r}"
        )


def _catalog_name(qupath_version: str, locale: str) -> str:
    return f"qupath-es {locale} — QuPath {qupath_version}"


def _catalog_description(qupath_version: str, locale: str) -> str:
    return (
        f"Extensiones con localización {locale} validada, runtime compatible y "
        f"distribución soportada por qupath-es para QuPath {qupath_version}."
    )


def project_catalog(
    registry: dict[str, Any],
    components_lock: dict[str, Any],
    localizations_lock: dict[str, Any],
    *,
    qupath_version: str,
    locale: str,
) -> ProjectionResult:
    if components_lock.get("qupath_version") != qupath_version:
        raise CatalogProjectionError("components lock targets a different QuPath version")
    if localizations_lock.get("qupath_version") != qupath_version:
        raise CatalogProjectionError("localizations lock targets a different QuPath version")

    registry_index = _index(registry.get("components"), "id", "registry.components")
    pin_index = _index(components_lock.get("components"), "component_id", "components_lock.components")
    localization_index = _localization_index(
        localizations_lock.get("localizations"),
        "localizations_lock.localizations",
    )

    extensions: list[dict[str, Any]] = []
    excluded: dict[str, tuple[str, ...]] = {}

    for component in registry.get("components", []):
        component_id = component["id"]
        if component.get("type") != "QUPATH_EXTENSION":
            continue

        pin = pin_index.get(component_id)
        localization = localization_index.get((component_id, locale))
        if pin is None:
            raise CatalogProjectionError(f"missing component pin for {component_id}")
        if localization is None:
            raise CatalogProjectionError(f"missing {locale} localization state for {component_id}")

        reasons: list[str] = []
        if localization.get("translation_status") != "TRANSLATED":
            reasons.append("translation_not_translated")
        if localization.get("validation_status") != "VALIDATED":
            reasons.append("localization_not_validated")
        if localization.get("distribution_status") != "DISTRIBUTED":
            reasons.append("localization_not_distributed")
        if pin.get("runtime_compatibility") == "NOT_VERIFIED":
            reasons.append("runtime_not_verified")

        if reasons:
            excluded[component_id] = tuple(reasons)
            continue

        # A satellite fork needs its own artifact provenance contract. The current
        # components lock records upstream release assets, so silently projecting
        # one as a localized fork would be unsafe.
        if pin.get("fork_repo") is not None or pin.get("fork_tag") is not None:
            raise CatalogProjectionError(
                f"{component_id}: satellite fork distribution requires explicit "
                "fork artifact provenance before catalog projection"
            )

        release_name = pin.get("upstream_tag")
        artifact_name = pin.get("artifact_name")
        artifact_url = pin.get("artifact_url")
        artifact_sha256 = pin.get("artifact_sha256")

        if not isinstance(release_name, str) or not VERSION_RE.fullmatch(release_name):
            raise CatalogProjectionError(
                f"{component_id}: catalog candidate lacks a semantic upstream tag"
            )
        if not isinstance(artifact_name, str) or not artifact_name:
            raise CatalogProjectionError(f"{component_id}: catalog candidate lacks artifact_name")
        if not isinstance(artifact_url, str) or not artifact_url:
            raise CatalogProjectionError(f"{component_id}: catalog candidate lacks artifact_url")
        if not isinstance(artifact_sha256, str) or not SHA256_RE.fullmatch(artifact_sha256):
            raise CatalogProjectionError(
                f"{component_id}: catalog candidate lacks pinned artifact SHA-256"
            )

        repository = component.get("repository")
        owner = component.get("owner")
        canonical_name = component.get("canonical_name")
        description = component.get("role")
        if not all(isinstance(value, str) and value for value in (
            repository,
            owner,
            canonical_name,
            description,
        )):
            raise CatalogProjectionError(f"{component_id}: registry metadata is incomplete")

        _validate_release_url(artifact_url, repository)
        version = f"v{qupath_version}"

        extensions.append(
            {
                "name": canonical_name,
                "description": description,
                "author": owner,
                "homepage": f"https://github.com/{repository}",
                "starred": False,
                "releases": [
                    {
                        "name": release_name,
                        "main_url": artifact_url,
                        "version_range": {
                            "min": version,
                            "max": version,
                        },
                    }
                ],
            }
        )

    unknown_pins = sorted(set(pin_index) - set(registry_index))
    if unknown_pins:
        raise CatalogProjectionError(f"component pins reference unknown ids: {unknown_pins}")

    catalog = {
        "name": _catalog_name(qupath_version, locale),
        "description": _catalog_description(qupath_version, locale),
        "extensions": extensions,
    }
    return ProjectionResult(catalog=catalog, excluded=excluded)


def build_projection(root: Path, *, qupath_version: str, locale: str) -> ProjectionResult:
    root = root.resolve()
    registry = _load_json(root / REGISTRY_PATH)
    components_lock = _load_json(root / "versions" / qupath_version / "components.lock.json")
    localizations_lock = _load_json(
        root / "versions" / qupath_version / "localizations.lock.json"
    )
    result = project_catalog(
        registry,
        components_lock,
        localizations_lock,
        qupath_version=qupath_version,
        locale=locale,
    )
    schema = _load_json(root / CATALOG_SCHEMA_PATH)
    schema_validate.validate(result.catalog, schema)
    return result


def check_catalog(
    root: Path,
    output_path: Path,
    *,
    qupath_version: str,
    locale: str,
) -> ProjectionResult:
    result = build_projection(root, qupath_version=qupath_version, locale=locale)
    expected = canonical_json_bytes(result.catalog)
    absolute = root / output_path
    try:
        actual = absolute.read_bytes()
    except OSError as exc:
        raise CatalogProjectionError(f"cannot read generated catalog {absolute}: {exc}") from exc
    if actual != expected:
        raise CatalogProjectionError(
            f"{output_path} is stale; regenerate it with tools/catalog_projection.py --write"
        )
    return result


def write_catalog(
    root: Path,
    output_path: Path,
    *,
    qupath_version: str,
    locale: str,
) -> ProjectionResult:
    result = build_projection(root, qupath_version=qupath_version, locale=locale)
    absolute = root / output_path
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_bytes(canonical_json_bytes(result.catalog))
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or verify the QuPath Extension Manager catalog projection."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify catalog (default)")
    mode.add_argument("--write", action="store_true", help="regenerate catalog")
    parser.add_argument("--qupath-version", default=DEFAULT_QUPATH_VERSION)
    parser.add_argument("--locale", default=DEFAULT_LOCALE)
    parser.add_argument("--output", type=Path, default=CATALOG_PATH)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write:
            result = write_catalog(
                args.repo,
                args.output,
                qupath_version=args.qupath_version,
                locale=args.locale,
            )
            action = "written"
        else:
            result = check_catalog(
                args.repo,
                args.output,
                qupath_version=args.qupath_version,
                locale=args.locale,
            )
            action = "verified"
    except (CatalogProjectionError, KeyError, TypeError, ValueError) as exc:
        print(f"catalog projection failed: {exc}", file=sys.stderr)
        return 2

    print(
        f"OK: catalog {action}: {len(result.catalog['extensions'])} extension(s); "
        f"{len(result.excluded)} excluded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
