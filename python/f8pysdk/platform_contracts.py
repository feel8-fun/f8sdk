"""Declarative public management routes shared by platform and UI clients."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .extension_status import (
    EnvironmentDetail, RuntimeStorageRequest, RuntimeStorageStatus,
    ExtensionDetail, EnvironmentStatus, ExtensionImportRequest,
    ExtensionInstallPlan, ExtensionStatus, ExtensionToggleRequest,
)
from .platform_spec import ApplicationStatus, SourceApplicationStatus, ApplicationOperation
from .platform_api import ImportApplication, ApplicationVersion
from .management_job import ManagementJob, ManagementJobRequest, ManagementJobLog, ManagementJobsClearRequest
from .tool_spec import ToolView, ToolRunRequest, ToolJob, CapabilityResource, ResourceContent


@dataclass(frozen=True)
class RouteContract:
    method: str
    path: str
    request: Any
    response: Any
    status: int = 200
    response_media_type: str = 'application/json'


MANAGEMENT_ROUTES = (
    RouteContract('get', '/api/management-jobs', None, tuple[ManagementJob, ...]),
    RouteContract('post', '/api/management-jobs', ManagementJobRequest, ManagementJob, 202),
    RouteContract('post', '/api/management-jobs/clear-completed', ManagementJobsClearRequest, tuple[ManagementJob, ...]),
    RouteContract('get', '/api/management-jobs/{job_id}', None, ManagementJob),
    RouteContract('get', '/api/management-jobs/{job_id}/logs', None, ManagementJobLog),
    RouteContract('post', '/api/management-jobs/{job_id}/cancel', None, ManagementJob, 202),
    RouteContract('get', '/api/applications', None, tuple[ApplicationStatus, ...]),
    RouteContract('post', '/api/applications/import', ImportApplication, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/prepare', ApplicationVersion, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/select', ApplicationVersion, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/deselect', None, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/update', ApplicationVersion, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/uninstall', ApplicationVersion, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/start', None, ManagementJob, 202),
    RouteContract('post', '/api/applications/{extension_id}/stop', None, ApplicationOperation, 202),
    RouteContract('post', '/api/applications/{extension_id}/restart', None, ManagementJob, 202),
    RouteContract('get', '/api/source-applications', None, tuple[SourceApplicationStatus, ...]),
    RouteContract('post', '/api/source-applications/{extension_id}/start', None, ManagementJob, 202),
    RouteContract('post', '/api/source-applications/{extension_id}/stop', None, ApplicationOperation, 202),
    RouteContract('post', '/api/source-applications/{extension_id}/restart', None, ManagementJob, 202),
    RouteContract('get', '/api/extension-tools', None, tuple[ToolView, ...]),
    RouteContract('post', '/api/extension-tools/{extension_id}/{tool_id}/run', ToolRunRequest, ToolJob, 202),
    RouteContract('get', '/api/tool-jobs', None, tuple[ToolJob, ...]),
    RouteContract('get', '/api/tool-jobs/{job_id}', None, ToolJob),
    RouteContract('post', '/api/tool-jobs/{job_id}/cancel', None, ToolJob),
    RouteContract('get', '/api/extension-resources/{extension_id}/{resource_id}/file', None, None, 200, 'application/octet-stream'),
    RouteContract('get', '/api/extension-resources', None, tuple[CapabilityResource, ...]),
    RouteContract('get', '/api/extension-resources/{extension_id}/{resource_id}', None, ResourceContent),
    RouteContract("get", "/api/extensions", None, tuple[ExtensionStatus, ...], 200),
    RouteContract("post", "/api/extensions/import", ExtensionImportRequest, ManagementJob, 202),
    RouteContract("get", "/api/extensions/{extension_id}/detail", None, ExtensionDetail, 200),
    RouteContract("get", "/api/extensions/{extension_id}/plan", None, ExtensionInstallPlan, 200),
    RouteContract("get", "/api/environments", None, tuple[EnvironmentStatus, ...], 200),
    RouteContract("get", "/api/environments/storage", None, RuntimeStorageStatus, 200),
    RouteContract("put", "/api/environments/storage", RuntimeStorageRequest, RuntimeStorageStatus, 200),
    RouteContract("post", "/api/environments/unused/clean", None, ManagementJob, 202),
    RouteContract("get", "/api/environments/{environment_id}/detail", None, EnvironmentDetail, 200),
    RouteContract("post", "/api/environments/{environment_id}/prepare", None, ManagementJob, 202),
    RouteContract("post", "/api/environments/{environment_id}/cancel", None, ManagementJob, 202),
    RouteContract("delete", "/api/environments/{environment_id}", None, ManagementJob, 202),
    RouteContract("post", "/api/extensions/{extension_id}/install", None, ManagementJob, 202),
    RouteContract("post", "/api/extensions/{extension_id}/cancel", None, ManagementJob, 202),
    RouteContract("put", "/api/extensions/{extension_id}/enabled", ExtensionToggleRequest, ManagementJob, 202),
    RouteContract("delete", "/api/extensions/{extension_id}", None, ManagementJob, 202),
)
