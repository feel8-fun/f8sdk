"""Publish an independently built bootstrap/provider wheel and its runtime."""
from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Literal
import zipfile

import msgspec
from packaging.utils import parse_wheel_filename
from packaging.version import Version

from .extension_runtime_build import build_source_runtime
from .extension_spec import ExtensionManifest, ExtensionRuntime
from .release_spec import PublishedArtifact


def build_runtime(source: Path, wheel: Path, output: Path, *, runtime_id: str, provider_id: str,
                  version: str, platform: Literal['linux-x86_64', 'windows-x86_64']) -> Path:
    if parse_wheel_filename(wheel.name)[1] != Version(version):
        raise ValueError('Runtime wheel and provider version must match')
    with tempfile.TemporaryDirectory(prefix='f8-runtime-provider-') as temporary:
        root = Path(temporary)
        request = ExtensionManifest(extension_id=provider_id, name=provider_id, version=version,
                                    description='Independent runtime provider',
                                    runtime=ExtensionRuntime(kind='workspace', environment=runtime_id))
        build_source_runtime(source, root, wheel, request)
        (root / 'config/artifact.json').write_bytes(msgspec.json.encode(PublishedArtifact(
            schema_version='f8artifact/1', artifact_id=runtime_id, version=version, kind='runtime', platform=platform)))
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.with_suffix('.zip.tmp')
        try:
            with zipfile.ZipFile(staging, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(root.rglob('*')):
                    if path.is_symlink():
                        raise ValueError(f'Runtime package contains a symlink: {path}')
                    if path.is_file():
                        archive.write(path, path.relative_to(root).as_posix())
            staging.replace(output)
        finally:
            staging.unlink(missing_ok=True)
    return output
