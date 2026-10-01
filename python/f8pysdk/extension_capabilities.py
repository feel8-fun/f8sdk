"""Static validation of tool, skill, and resource declarations."""
from __future__ import annotations

import re

from .extension_spec import ExtensionManifest
from .service_paths import ServicePaths


def validate_capabilities(manifest: ExtensionManifest, paths: ServicePaths) -> None:
    if not (manifest.service_classes or manifest.tools or manifest.skills or manifest.resources):
        raise ValueError(f'Extension has no capabilities: {manifest.extension_id}')
    for identifiers in (tuple(tool.tool_id for tool in manifest.tools),
                        tuple(skill.skill_id for skill in manifest.skills),
                        tuple(resource.resource_id for resource in manifest.resources)):
        if len(set(identifiers)) != len(identifiers) or any(
            not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value) for value in identifiers
        ):
            raise ValueError(f'Invalid or duplicate capability ID in {manifest.extension_id}')
    for asset in (*manifest.skills, *manifest.resources):
        path = paths.package_path(asset.path, relative_to=paths.package_root)
        if not path.is_file():
            raise ValueError(f'Missing capability asset: {asset.path}')
    for tool in manifest.tools:
        if not tool.command or not 1 <= tool.timeout_seconds <= 3600:
            raise ValueError(f'Invalid tool launcher: {tool.tool_id}')
        cwd = paths.package_path(tool.workdir, relative_to=paths.package_root)
        if manifest.runtime.kind == 'native':
            paths.package_path(tool.command, relative_to=cwd)
        elif tool.command != 'python':
            raise ValueError('Managed tool entrypoints must declare python')
        if manifest.runtime.kind == 'shared' and (len(tool.args) != 2 or tool.args[0] != '-m'):
            raise ValueError('Shared tools must launch python -m module')
        names = [field.name for field in tool.fields]
        if len(set(names)) != len(names) or any(not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', name) for name in names):
            raise ValueError(f'Invalid tool fields: {tool.tool_id}')
        if any(field.choices and field.kind != 'string' for field in tool.fields):
            raise ValueError('Tool choices require string fields')
