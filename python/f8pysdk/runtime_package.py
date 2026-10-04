"""Portable, locked runtime validation shared by independent publishers and Studio."""
from __future__ import annotations

from pathlib import Path
import re
import tomllib
from typing import cast
from urllib.parse import urlsplit

import msgspec
from packaging.version import Version
import yaml

from .release_spec import RuntimeCatalog
from .specs import F8JsonValue

JsonObject = dict[str, F8JsonValue]


def validate_runtime_package(root: Path) -> RuntimeCatalog:
    catalog = msgspec.json.decode((root / 'config/runtime-environments.json').read_bytes(), type=RuntimeCatalog)
    names: set[str] = set()
    for definition in catalog.runtimes:
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', definition.runtime_id) or definition.runtime_id in names:
            raise ValueError('Published runtime IDs must be safe and unique')
        names.add(definition.runtime_id)
        if (definition.provider_id is None or definition.version is None
                or definition.development_environment is not None):
            raise ValueError('Published runtimes require providerId/version and no developmentEnvironment')
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]*', definition.provider_id):
            raise ValueError('Invalid runtime provider identity')
        Version(definition.version)
        if definition.abi is not None and not definition.abi.strip():
            raise ValueError('Runtime ABI must not be empty')
        prefix = '${F8_PACKAGE_ROOT}/'
        if not definition.manifest.startswith(prefix):
            raise ValueError('Runtime manifest requires an explicit package root reference')
        manifest_path = (root / definition.manifest.removeprefix(prefix)).resolve()
        if not manifest_path.is_relative_to(root.resolve()) or manifest_path.name != 'pixi.toml':
            raise ValueError('Unsafe runtime manifest reference')
        workspace = manifest_path.parent
        if workspace == root.resolve():
            raise ValueError('Runtime catalog must reference a separate workspace directory')
        manifest = cast(JsonObject, tomllib.loads(manifest_path.read_text(encoding='utf-8')))
        environments = manifest.get('environments')
        if not isinstance(environments, dict) or definition.runtime_id not in environments:
            raise ValueError('Runtime workspace must contain its declared environment')

        def check(value: F8JsonValue, workspace: Path = workspace) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == 'editable' and item is True:
                        raise ValueError('Published runtime cannot reference editable packages')
                    if key == 'path':
                        if not isinstance(item, str):
                            raise ValueError('Runtime package path must be a string')
                        wheel = (workspace / item).resolve()
                        if not wheel.is_relative_to(root.resolve()) or wheel.suffix != '.whl' or not wheel.is_file():
                            raise ValueError('Published runtime paths must reference contained wheels')
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)

        check(manifest)
        lock = cast(F8JsonValue, yaml.safe_load((workspace / 'pixi.lock').read_text(encoding='utf-8')))
        if not isinstance(lock, dict):
            raise ValueError('Published runtime requires a structured lock')
        entries = cast(JsonObject, lock).get('packages', [])
        if not isinstance(entries, list):
            raise ValueError('Runtime lock packages must be a list')
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Invalid runtime lock package')
            for key in ('pypi', 'conda'):
                reference = cast(JsonObject, entry).get(key)
                if not isinstance(reference, str):
                    continue
                if '://' in reference:
                    remote = urlsplit(reference)
                    if remote.scheme != 'https' or not remote.hostname or remote.username or remote.password:
                        raise ValueError('Locked runtime downloads must use HTTPS without credentials')
                    if key == 'pypi' and not remote.path.endswith('.whl'):
                        raise ValueError('Locked Python runtime inputs must be wheels, not source distributions')
                else:
                    target = (workspace / reference).resolve()
                    if not target.is_relative_to(root.resolve()) or not target.is_file():
                        raise ValueError('Locked runtime input escapes package or is missing')
                    if key == 'pypi' and target.suffix != '.whl':
                        raise ValueError('Locked Python runtime inputs must be wheels')
    if not names:
        raise ValueError('A runtime package must publish at least one environment')
    return catalog
