"""Publisher-side conversion of a source workspace to locked wheel inputs."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
from typing import cast

import msgspec
from packaging.utils import canonicalize_name, parse_wheel_filename

from .extension_spec import ExtensionManifest
from .release_spec import RuntimeCatalog, RuntimeDefinition
from .runtime_package import validate_runtime_package
from .specs import F8JsonValue

JsonObject = dict[str, F8JsonValue]


def _key(value: str) -> str:
    return value if re.fullmatch(r'[A-Za-z0-9_-]+', value) else json.dumps(value)


def _value(value: F8JsonValue) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(_value(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(f'{_key(key)} = {_value(item)}' for key, item in value.items()) + '}'
    raise ValueError('Null is not valid in a Pixi manifest')


def build_source_runtime(source: Path, root: Path, wheel: Path, extension: ExtensionManifest) -> Path:
    """Build local dependency wheels and resolve only at explicit publication time."""
    manifest = cast(JsonObject, tomllib.loads((source / 'pixi.toml').read_text(encoding='utf-8')))
    if not (source / 'pixi.lock').is_file():
        raise ValueError('Publishing a source extension requires its own pixi.lock')
    wheels = root / 'wheels'
    wheels.mkdir(parents=True)
    shutil.copy2(wheel, wheels / wheel.name)
    supplied_name = canonicalize_name(parse_wheel_filename(wheel.name)[0])

    def replace_paths(table: JsonObject) -> None:
        table.pop('tasks', None)
        for key, value in table.items():
            if key == 'pypi-dependencies' and isinstance(value, dict):
                for name, specification in value.items():
                    if not isinstance(specification, dict):
                        continue
                    dependency_spec = cast(JsonObject, specification)
                    local = dependency_spec.get('path')
                    if not isinstance(local, str):
                        continue
                    normalized = canonicalize_name(name)
                    if normalized != supplied_name:
                        dependency = (source / local).resolve()
                        if dependency.is_file() and dependency.suffix == '.whl':
                            shutil.copy2(dependency, wheels / dependency.name)
                        elif dependency.is_dir():
                            subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
                                            '--no-build-isolation', '-w', str(wheels), str(dependency)], check=True)
                        else:
                            raise ValueError(f'Missing local publisher dependency: {dependency}')
                    candidates = [path for path in wheels.glob('*.whl')
                                  if canonicalize_name(parse_wheel_filename(path.name)[0]) == normalized]
                    if len(candidates) != 1:
                        raise ValueError(f'Expected one published wheel for {name}')
                    dependency_spec['path'] = '../wheels/' + candidates[0].name
                    dependency_spec.pop('editable', None)
            elif isinstance(value, dict):
                replace_paths(value)

    replace_paths(manifest)
    environments = manifest.get('environments')
    if environments is None:
        empty_features: list[F8JsonValue] = []
        environments = {'default': empty_features}
        manifest['environments'] = environments
    if not isinstance(environments, dict) or extension.runtime.environment not in environments:
        raise ValueError('Extension default environment must be declared in its source workspace')
    workspace = root / 'workspace'
    workspace.mkdir()
    lines: list[str] = []
    for name, value in manifest.items():
        if not isinstance(value, dict):
            raise ValueError(f'Invalid Pixi table: {name}')
        lines.append(f'[{_key(name)}]')
        lines.extend(f'{_key(key)} = {_value(item)}' for key, item in value.items())
        lines.append('')
    (workspace / 'pixi.toml').write_text('\n'.join(lines), encoding='utf-8')
    shutil.copy2(source / 'pixi.lock', workspace / 'pixi.lock')
    subprocess.run(['pixi', 'lock', '--manifest-path', str(workspace / 'pixi.toml')], check=True)
    config = root / 'config'
    config.mkdir()
    definitions = tuple(RuntimeDefinition(runtime_id=name, provider_id=extension.extension_id,
                        version=extension.version, manifest='${F8_PACKAGE_ROOT}/workspace/pixi.toml')
                        for name in environments)
    (config / 'runtime-environments.json').write_bytes(msgspec.json.encode(RuntimeCatalog(
        schema_version='f8runtimeCatalog/1', runtimes=definitions,
    )))
    validate_runtime_package(root)
    return root
