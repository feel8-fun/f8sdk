"""Typed local platform client. Applications do not own installation state."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TypeVar
from urllib.parse import quote, urlsplit

import httpx
import msgspec

from .platform_errors import ConflictError, InvalidRequestError, NotFoundError, ServiceUnavailableError
from .platform_spec import PlatformInventory, ProcessLog, ServiceProcessStatus, ServiceStartRequest
from .application_spec import ApplicationEndpoint
from .tool_spec import CapabilityResource, ResourceContent, ToolJob, ToolRunRequest, ToolView
from .management_job import ManagementJob, ManagementJobRequest, ManagementJobLog, ManagementJobsClearRequest

T = TypeVar('T')


class PlatformConnection(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    url: str
    token_file: str


def segment(value: str) -> str:
    if not value or value in {'.', '..'} or '/' in value or '\\' in value:
        raise InvalidRequestError('Invalid platform resource identity')
    return quote(value, safe='')


class PlatformClient:
    def __init__(self, connection: PlatformConnection, *, transport: httpx.BaseTransport | None = None) -> None:
        address = urlsplit(connection.url)
        if address.scheme != 'http' or address.hostname not in {'127.0.0.1', 'localhost', '::1', 'testserver'}:
            raise InvalidRequestError('Platform connection must use loopback HTTP')
        self.connection = connection
        self.http = httpx.Client(base_url=connection.url,
            headers={'Authorization': f'Bearer {Path(connection.token_file).read_text().strip()}'},
            timeout=300, trust_env=False, transport=transport)
        self.tools = PlatformTools(self)
        self.jobs = PlatformJobs(self)

    @classmethod
    def from_environment(cls) -> PlatformClient:
        root = Path(os.environ.get('F8_PLATFORM_DATA_ROOT', str(Path.home() / '.feel8')))
        path = Path(os.environ.get('F8_PLATFORM_CONNECTION_FILE', str(root / 'platform.json')))
        if not path.is_file():
            raise ServiceUnavailableError('Platform is not running. Start the Launcher (pixi run platform_dev in a development workspace).')
        return cls(msgspec.json.decode(path.read_bytes(), type=PlatformConnection))

    def request(self, method: str, path: str, *, content: bytes | None = None, params: str = '') -> httpx.Response:
        if not path.startswith('/api/') or '?' in path or any(part in {'.', '..'} for part in path.split('/')) or '\\' in path:
            raise InvalidRequestError('Invalid platform API path')
        try:
            return self.http.request(method, path, content=content, params=params,
                                     headers={'Content-Type': 'application/json'} if content is not None else None)
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError(f'Cannot reach platform at {self.connection.url}: {exc}') from exc

    def read(self, method: str, path: str, model: type[T], *, payload: object = None, params: str = '') -> T:
        response = self.request(method, path, content=msgspec.json.encode(payload) if payload is not None else None, params=params)
        if response.is_error:
            error = msgspec.json.decode(response.content, type=dict[str, object])
            message = str(error.get('message', error.get('detail', response.text)))
            if response.status_code == 404:
                raise NotFoundError(message)
            if response.status_code == 409:
                raise ConflictError(message)
            if response.status_code in {400, 422}:
                raise InvalidRequestError(message)
            raise ServiceUnavailableError(message)
        return msgspec.json.decode(response.content, type=model)

    def inventory(self) -> PlatformInventory:
        return self.read('GET', '/api/inventory', PlatformInventory)

    def application_dependencies(self, identifier: str, *, start: bool = False) -> tuple[ApplicationEndpoint, ...]:
        return self.read('POST' if start else 'GET', f'/api/application-dependencies/{segment(identifier)}', tuple[ApplicationEndpoint, ...])

    def services(self) -> tuple[ServiceProcessStatus, ...]:
        return self.read('GET', '/api/service-processes', tuple[ServiceProcessStatus, ...])

    async def start_service(self, identifier: str, request: ServiceStartRequest) -> ServiceProcessStatus:
        return await asyncio.to_thread(self.read, 'POST', f'/api/service-processes/{segment(identifier)}/start',
                                       ServiceProcessStatus, payload=request)

    async def stop_service(self, identifier: str) -> ServiceProcessStatus:
        return await asyncio.to_thread(self.read, 'POST', f'/api/service-processes/{segment(identifier)}/stop', ServiceProcessStatus)

    def logs(self, after: int) -> tuple[ProcessLog, ...]:
        return self.read('GET', '/api/service-processes/logs', tuple[ProcessLog, ...], params=f'after={after}')

    def close(self) -> None:
        self.http.close()


class PlatformJobs:
    def __init__(self, client: PlatformClient) -> None:
        self.client = client

    def list(self) -> tuple[ManagementJob, ...]:
        return self.client.read('GET', '/api/management-jobs', tuple[ManagementJob, ...])

    def clear_completed(self, identifiers: tuple[str, ...]) -> tuple[ManagementJob, ...]:
        return self.client.read('POST', '/api/management-jobs/clear-completed', tuple[ManagementJob, ...],
                                payload=ManagementJobsClearRequest(job_ids=identifiers))

    def submit(self, request: ManagementJobRequest) -> ManagementJob:
        return self.client.read('POST', '/api/management-jobs', ManagementJob, payload=request)

    def get(self, identifier: str) -> ManagementJob:
        return self.client.read('GET', f'/api/management-jobs/{segment(identifier)}', ManagementJob)

    def cancel(self, identifier: str) -> ManagementJob:
        return self.client.read('POST', f'/api/management-jobs/{segment(identifier)}/cancel', ManagementJob)

    def logs(self, identifier: str) -> ManagementJobLog:
        return self.client.read('GET', f'/api/management-jobs/{segment(identifier)}/logs', ManagementJobLog)


class PlatformTools:
    def __init__(self, client: PlatformClient) -> None:
        self.client = client

    def list(self) -> tuple[ToolView, ...]:
        return self.client.read('GET', '/api/extension-tools', tuple[ToolView, ...])

    def submit(self, extension_id: str, tool_id: str, request: ToolRunRequest) -> ToolJob:
        return self.client.read('POST', f'/api/extension-tools/{segment(extension_id)}/{segment(tool_id)}/run', ToolJob, payload=request)

    def jobs(self) -> tuple[ToolJob, ...]:
        return self.client.read('GET', '/api/tool-jobs', tuple[ToolJob, ...])

    def get(self, job_id: str) -> ToolJob:
        return self.client.read('GET', f'/api/tool-jobs/{segment(job_id)}', ToolJob)

    async def cancel(self, job_id: str) -> ToolJob:
        return await asyncio.to_thread(self.client.read, 'POST', f'/api/tool-jobs/{segment(job_id)}/cancel', ToolJob)

    def resources(self) -> tuple[CapabilityResource, ...]:
        return self.client.read('GET', '/api/extension-resources', tuple[CapabilityResource, ...])

    def read_resource(self, extension_id: str, resource_id: str) -> ResourceContent:
        return self.client.read('GET', f'/api/extension-resources/{segment(extension_id)}/{segment(resource_id)}', ResourceContent)
