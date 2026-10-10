"""Public contracts for queued platform maintenance operations."""
from __future__ import annotations

from typing import Literal

import msgspec

from .extension_status import ExtensionImportRequest

ManagementAction = Literal[
    'import-extension', 'install-extension', 'uninstall-extension',
    'enable-extension', 'disable-extension', 'prepare-environment',
    'remove-environment', 'clean-unused-environments', 'start-source', 'start-application',
    'restart-source', 'restart-application',
    'import-application', 'prepare-application', 'select-application', 'deselect-application',
    'update-application', 'uninstall-application',
]
ManagementState = Literal['queued', 'running', 'succeeded', 'failed', 'cancelled']


class ManagementJobRequest(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    action: ManagementAction
    extension_id: str | None = None
    environment_id: str | None = None
    package: ExtensionImportRequest | None = None
    location: str | None = None
    sha256: str | None = None


class ManagementJob(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    job_id: str
    request: ManagementJobRequest
    state: ManagementState
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    detail: str = ''
    cancel_requested: bool = False
    cancellable: bool = True


class ManagementJobLog(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    log: str


class ManagementJobsClearRequest(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    job_ids: tuple[str, ...]
