"""Public extension tool execution and resource contracts."""
from typing import Literal
import msgspec
from .extension_spec import ExtensionToolField
from .specs import F8JsonValue


class ToolView(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    tool_id: str
    name: str
    description: str
    fields: tuple[ExtensionToolField, ...]
    requires_confirmation: bool
    allow_concurrent: bool = False


class ToolRunRequest(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    arguments: dict[str, F8JsonValue]
    confirm: bool = False


class ToolResult(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    schema_version: Literal['f8toolResult/1']
    success: bool
    message: str
    data: F8JsonValue = None


class ToolJob(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    job_id: str
    extension_id: str
    extension_version: str
    tool_id: str
    arguments: dict[str, F8JsonValue]
    status: Literal['queued', 'running', 'succeeded', 'failed', 'cancelled']
    created_at: str
    updated_at: str
    result: ToolResult | None = None
    error: str = ''
    log: str = ''


class CapabilityResource(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    resource_id: str
    description: str


class ResourceContent(msgspec.Struct, frozen=True, kw_only=True, rename='camel'):
    extension_id: str
    resource_id: str
    content: str
