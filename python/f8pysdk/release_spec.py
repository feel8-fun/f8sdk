"""Versioned publisher contracts for immutable extension and runtime artifacts."""
from __future__ import annotations

from typing import Literal

import msgspec


class ReleaseArtifact(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    artifact_id: str
    version: str
    kind: Literal['runtime', 'extension']
    location: str
    sha256: str


class RuntimeDefinition(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    runtime_id: str
    manifest: str
    development_environment: str | None = None
    provider_id: str | None = None
    version: str | None = None
    abi: str | None = None


class RuntimeCatalog(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    schema_version: Literal['f8runtimeCatalog/1']
    runtimes: tuple[RuntimeDefinition, ...]


class PublishedArtifact(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    schema_version: Literal['f8artifact/1']
    artifact_id: str
    version: str
    kind: Literal['runtime', 'extension']
    platform: Literal['any', 'linux-x86_64', 'windows-x86_64']
    wheel_tags: tuple[str, ...] = ()


class BundledExtensionPackage(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    path: str
    sha256: str


class BundledExtensionCatalog(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    schema_version: Literal['f8extensionPackages/1']
    packages: tuple[BundledExtensionPackage, ...]


class PlatformReleaseLock(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    schema_version: Literal['f8platformRelease/1']
    platform: Literal['linux-x86_64', 'windows-x86_64']
    artifacts: tuple[ReleaseArtifact, ...]
    base_runtime: str = 'platform-runtime'
    startup: tuple[str, ...] = ('webstudio',)
