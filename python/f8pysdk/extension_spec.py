"""Publisher-facing extension metadata, independent of the Studio server."""
from __future__ import annotations

from typing import Literal

import msgspec

from .specs import F8JsonValue

RuntimeKind = Literal['native', 'bundled', 'workspace', 'pixi', 'shared']


class ExtensionRuntime(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    kind: RuntimeKind = 'native'
    environment: str | None = None
    requires_python: str | None = None
    dependencies: tuple[str, ...] = ()


class ExtensionToolField(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    name: str
    label: str
    kind: Literal['string', 'integer', 'number', 'boolean'] = 'string'
    required: bool = False
    default: F8JsonValue = None
    choices: tuple[str, ...] = ()


class ExtensionTool(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    tool_id: str
    name: str
    description: str
    command: str
    args: tuple[str, ...] = ()
    workdir: str = '${F8_PACKAGE_ROOT}'
    fields: tuple[ExtensionToolField, ...] = ()
    platforms: tuple[Literal['linux', 'win32', 'darwin'], ...] = ()
    timeout_seconds: int = 300
    requires_confirmation: bool = True


class ExtensionSkill(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    skill_id: str
    path: str


class ExtensionResource(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    resource_id: str
    path: str
    description: str = ''


class ExtensionManifest(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    extension_id: str
    name: str
    version: str
    description: str
    service_classes: tuple[str, ...] = ()
    tools: tuple[ExtensionTool, ...] = ()
    skills: tuple[ExtensionSkill, ...] = ()
    resources: tuple[ExtensionResource, ...] = ()
    runtime: ExtensionRuntime = ExtensionRuntime()
    model_directories: tuple[str, ...] = ()


class ExtensionCatalog(msgspec.Struct, frozen=True, kw_only=True, rename='camel', forbid_unknown_fields=True):
    schema_version: Literal['f8extensionCatalog/1']
    extensions: tuple[ExtensionManifest, ...]
    preinstalled: tuple[str, ...] = ()
