"""Explicit service installation index. Loading never scans or runs services."""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
import sys
from typing import Literal

import msgspec

from f8pysdk.codec import copy_model, validate_as
from f8pysdk.specs import F8ServiceDescribe, F8ServiceEntry
from f8pysdk._specs.builtin_fields import normalize_describe_payload_dict
from f8pysdk.monitoring import validate_describe_monitor_contract
from f8pysdk.service_paths import ServicePaths

from .catalog import ServiceCatalog
from .entry import absolutize_entry_paths, _read_yaml
from .policy import merge_disabled_service_classes


class IndexedService(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    serviceClass: str
    manifests: dict[str, str]
    describe: str
    bundleRoots: dict[str, str] = msgspec.field(default_factory=dict)


class ServiceIndex(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    schemaVersion: Literal["f8serviceIndex/1"]
    services: tuple[IndexedService, ...]
    modelRoot: str


def default_service_index() -> Path:
    configured = os.environ.get("F8_SERVICE_INDEX")
    if configured:
        return Path(configured).expanduser().resolve()
    # Checkout and unpacked distribution roots; no recursive service discovery.
    for root in Path(__file__).resolve().parents:
        candidate = root / "config" / "service-index.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No service index installed. Set F8_SERVICE_INDEX to config/service-index.json.")


def read_service_index(path: Path) -> ServiceIndex:
    index = msgspec.json.decode(path.read_bytes(), type=ServiceIndex)
    classes = [item.serviceClass for item in index.services]
    if len(set(classes)) != len(classes):
        raise ValueError(f"Duplicate serviceClass in {path}")
    for item in index.services:
        if not item.serviceClass or not item.manifests:
            raise ValueError(f"Invalid registration in {path}: {item.serviceClass!r}")
        if set(item.manifests) - {"linux", "win32", "darwin", "any"}:
            raise ValueError(f"Unknown platform for {item.serviceClass}")
        if set(item.bundleRoots) - set(item.manifests):
            raise ValueError(f"Bundle platform has no manifest for {item.serviceClass}")
    return index


def index_paths(
    index_path: Path, index: ServiceIndex, item: IndexedService | None = None, *, platform: str | None = None,
) -> ServicePaths:
    index_path = index_path.resolve()
    paths = ServicePaths.for_index(index_path)
    paths = replace(paths, model_root=paths.resolve(index.modelRoot, relative_to=index_path.parent))
    if item is not None:
        bundle = item.bundleRoots.get(sys.platform if platform is None else platform, item.bundleRoots.get("any"))
        if bundle is not None:
            paths = paths.with_bundle(paths.package_path(bundle, relative_to=index_path.parent))
    return paths


def indexed_entry(index_path: Path, index: ServiceIndex, item: IndexedService) -> F8ServiceEntry | None:
    relative = item.manifests.get(sys.platform, item.manifests.get("any"))
    if relative is None:
        return None
    paths = index_paths(index_path, index, item)
    manifest = paths.package_path(relative, relative_to=index_path.parent)
    entry = validate_as(F8ServiceEntry, _read_yaml(manifest))
    if entry.serviceClass != item.serviceClass:
        raise ValueError(f"Service class mismatch in {manifest}")
    entry = absolutize_entry_paths(entry, service_dir=manifest.parent, paths=paths)
    env = dict(entry.launch.env or {})
    # The installer owns resource resolution, independent of the service cwd.
    env["F8_MODEL_ROOT"] = str(paths.model_root)
    return copy_model(entry, update={"launch": copy_model(entry.launch, update={"env": env})})


def load_index_into_catalog(
    *, path: Path | None = None, catalog: ServiceCatalog,
    disabled_service_classes: Sequence[str] | None = None,
    force_dynamic_service_classes: Sequence[str] = (),
) -> list[str]:
    path = (default_service_index() if path is None else path).resolve()
    index = read_service_index(path)
    disabled = set(merge_disabled_service_classes(explicit_service_classes=disabled_service_classes))
    found: list[str] = []
    for item in index.services:
        if item.serviceClass in disabled:
            continue
        entry = indexed_entry(path, index, item)
        if entry is None:
            continue
        # Installed registrations may point to descriptions in another immutable payload.
        describe_path = index_paths(path, index, item).resolve(item.describe, relative_to=path.parent)
        if item.serviceClass in force_dynamic_service_classes:
            from .describe import describe_entry
            payload = describe_entry(describe_path.parent, entry, force_dynamic=True)
            if payload is None:
                raise ValueError(f"Explicit description refresh failed: {item.serviceClass}")
        elif not describe_path.is_file():
            raise FileNotFoundError(f"Missing installed description {describe_path}; run pixi run install_services")
        else:
            raw = msgspec.json.decode(describe_path.read_bytes(), type=dict[str, object])
            payload = normalize_describe_payload_dict(raw)
        validate_describe_monitor_contract(payload)
        describe = validate_as(F8ServiceDescribe, payload)
        if describe.service.serviceClass != item.serviceClass:
            raise ValueError(f"Service class mismatch in {describe_path}")
        catalog.register_service(describe.service, entry=entry)
        if not isinstance(describe.operators, msgspec.UnsetType):
            catalog.register_operators(describe.operators)
        found.append(item.serviceClass)
    return found


def service_index_sources(path: Path) -> list[tuple[Path, Path]]:
    """Explicit manifest/description pairs for offline build and documentation tools."""
    path = path.resolve()
    result: list[tuple[Path, Path]] = []
    index = read_service_index(path)
    for item in index.services:
        manifest = item.manifests.get(sys.platform, item.manifests.get("any"))
        if manifest is not None:
            paths = index_paths(path, index, item)
            result.append((paths.package_path(manifest, relative_to=path.parent), paths.resolve(item.describe, relative_to=path.parent)))
    return result
