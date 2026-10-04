"""Versioned contracts for independently published platform applications."""
from __future__ import annotations

from typing import Literal

import msgspec


class ApplicationProtocol(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    protocol_id: str
    version: str


class ApplicationDependency(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    extension_id: str
    protocol_id: str
    versions: str


class ApplicationEndpoint(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    name: str
    url: str


class ApplicationHealth(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    endpoint: str
    path: str
    service: str
    protocol_version: str
    timeout_seconds: float = 30.0
    bootstrap_path: str | None = None


class ApplicationLaunch(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    environment: str
    module: str
    distribution: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = msgspec.field(default_factory=dict)


class ApplicationSpec(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    launch: ApplicationLaunch
    provides: tuple[ApplicationProtocol, ...]
    endpoints: tuple[ApplicationEndpoint, ...]
    health: ApplicationHealth
    requires: tuple[ApplicationDependency, ...] = ()
    web_assets: str | None = None
    release_role: Literal['application', 'webstudio'] = 'application'


class ApplicationManifest(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    """Resolved lifecycle view derived from an extension manifest."""
    extension_id: str
    version: str
    title: str
    launch: ApplicationLaunch
    provides: tuple[ApplicationProtocol, ...]
    endpoints: tuple[ApplicationEndpoint, ...]
    health: ApplicationHealth
    requires: tuple[ApplicationDependency, ...] = ()
    web_assets: str | None = None
    release_role: Literal['application', 'webstudio'] = 'application'


