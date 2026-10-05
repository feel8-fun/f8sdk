from __future__ import annotations

from typing import Literal

import msgspec

from .extension_spec import (
    ExtensionCatalog as ExtensionCatalog,
    ExtensionManifest as ExtensionManifest,
    ExtensionRuntime as ExtensionRuntime,
    ExtensionTool,
    RuntimeKind as RuntimeKind,
)

from .specs import F8ServiceDescribe
from .application_spec import ApplicationManifest
from .platform_spec import ApplicationOperation


class ExtensionServiceDetail(msgspec.Struct, frozen=True, kw_only=True, rename="camel"):
    service_class: str
    describe: F8ServiceDescribe | None


class ExtensionSkillDetail(msgspec.Struct, frozen=True, kw_only=True, rename="camel"):
    skill_id: str
    content: str


class ExtensionDetail(msgspec.Struct, frozen=True, kw_only=True, rename="camel"):
    extension_id: str
    services: tuple[ExtensionServiceDetail, ...]
    tools: tuple[ExtensionTool, ...]
    skills: tuple[ExtensionSkillDetail, ...]
    application: ApplicationManifest | None = None


class ExtensionRecord(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    version: str
    installed: bool
    enabled: bool
    environment_id: str | None = None


class ExtensionStatus(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    name: str
    version: str
    description: str
    state: Literal['unavailable', 'available', 'installing', 'installed', 'disabled', 'failed']
    detail: str
    service_classes: tuple[str, ...]
    runtime_kind: RuntimeKind
    environment_id: str | None
    preinstalled: bool
    tool_ids: tuple[str, ...] = ()
    skill_ids: tuple[str, ...] = ()
    resource_ids: tuple[str, ...] = ()
    runtime_environment: str | None = None
    application: bool = False
    source_checkout: bool = False
    source_path: str | None = None
    running: bool = False
    managed: bool = False
    release_sha256: str | None = None
    application_operation: ApplicationOperation | None = None
    running_source: bool = False


class ExtensionToggleRequest(msgspec.Struct, frozen=True, kw_only=True):
    enabled: bool


class ExtensionImportRequest(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    url: str
    sha256: str


class ExtensionInstallPlan(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    environment_id: str | None
    runtime_kind: RuntimeKind
    action: Literal['none', 'reuse', 'create', 'bundled', 'workspace', 'shared']
    requires_network: bool


class EnvironmentStatus(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    environment_id: str
    runtime_kind: RuntimeKind
    extension_ids: tuple[str, ...]
    ready: bool
    name: str = ''
    source: Literal['official', 'package'] = 'package'
    revision: str = ''
    state: Literal['declared', 'preparing', 'ready', 'changed', 'missing', 'failed'] = 'declared'
    detail: str = ''
    service_classes: tuple[str, ...] = ()
    tool_ids: tuple[str, ...] = ()
    can_remove: bool = False


class EnvironmentUsage(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    logical_bytes: int = 0
    unique_file_bytes: int = 0
    shared_link_bytes: int = 0
    exclusive_file_bytes: int = 0
    allocated_bytes: int | None = None
    exclusive_allocated_bytes: int | None = None


class EnvironmentPackage(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    name: str
    version: str
    manager: Literal['conda', 'pypi']
    build: str = ''
    platform: str = ''


class EnvironmentDetail(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    environment_id: str
    name: str
    revision: str
    manifest: str
    storage_path: str
    cache_path: str
    usage: EnvironmentUsage
    packages: tuple[EnvironmentPackage, ...] = ()
    package_inventory: Literal['installed', 'locked'] = 'locked'
    definition_path: str = ''
    source_environment: str = ''
    provider_id: str | None = None
    provider_version: str | None = None
    abi: str | None = None


class RuntimeStorageRequest(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    path: str


class UnusedEnvironment(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    environment_id: str
    path: str
    usage: EnvironmentUsage


class RuntimeStorageStatus(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    path: str
    cache_path: str
    can_change: bool
    environment_usage: EnvironmentUsage = msgspec.field(default_factory=EnvironmentUsage)
    cache_usage: EnvironmentUsage = msgspec.field(default_factory=EnvironmentUsage)
    total_usage: EnvironmentUsage = msgspec.field(default_factory=EnvironmentUsage)
    unused_environments: tuple[UnusedEnvironment, ...] = ()
    usage_updated_at: float | None = None
