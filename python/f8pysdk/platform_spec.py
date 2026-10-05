"""Public response contracts for launcher application management."""
from typing import Literal

import msgspec

from .application_spec import ApplicationEndpoint, ApplicationManifest
from .specs import F8ServiceDescribe


class ApplicationRecord(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    version: str
    sha256: str


class ApplicationStatus(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    manifest: ApplicationManifest
    sha256: str
    selected: bool
    prepared: bool
    state: Literal['stopped', 'running', 'failed']
    log_path: str
    endpoints: tuple[ApplicationEndpoint, ...]


class PlatformInventory(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    describes: tuple[F8ServiceDescribe, ...]
    skills: dict[str, str]
    service_classes: tuple[str, ...]


class ServiceStartRequest(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    service_class: str
    bus_backend: Literal['zenoh', 'mem'] = 'zenoh'
    zenoh_config_path: str | None = None
    zenoh_connect: tuple[str, ...] = ()
    zenoh_listen: tuple[str, ...] = ()
    zenoh_shm_pool_bytes: int = 256 * 1024 * 1024


class ServiceProcessStatus(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    service_id: str
    service_class: str
    running: bool


class ProcessLog(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    sequence: int
    service_id: str
    line: str


class DevelopmentApplication(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    manifest: ApplicationManifest
    runtime_manifest: str
    workdir: str
    arguments: tuple[str, ...]
    environment: dict[str, str] = msgspec.field(default_factory=dict)


class DevelopmentCatalog(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    applications: tuple[DevelopmentApplication, ...]


class SourceApplicationStatus(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    version: str
    state: Literal['stopped', 'running', 'failed']
    endpoints: tuple[ApplicationEndpoint, ...]
    log_path: str
    managed: bool = True


class SourceApplicationRegistration(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    extension_id: str
    version: str
    instance: str
    url: str


class ApplicationOperation(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    action: Literal['stop']
    state: Literal['running', 'succeeded', 'failed']
    detail: str = ''
