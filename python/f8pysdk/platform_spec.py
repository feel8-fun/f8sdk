"""Public response contracts for launcher application management."""
from typing import Literal

import msgspec

from .application_spec import ApplicationEndpoint, ApplicationManifest


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


