"""Publish a application and its locked runtime without Studio build code."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile
from typing import Literal

import msgspec
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from .application_package import read_application, read_application_extension, validate_application
from .extension_runtime_build import build_source_runtime
from .extension_spec import ExtensionCatalog
from .release_spec import PublishedArtifact
from .runtime_package import validate_runtime_package


def build_application(source: Path, wheel: Path, output: Path, *, runtime_root: Path | None = None,
                    web_assets: Path | None = None, platform: Literal['linux-x86_64', 'windows-x86_64']) -> Path:
    extension = read_application_extension(source)
    manifest = read_application(source)
    _name, wheel_version, _build, _tags = parse_wheel_filename(wheel.name)
    if canonicalize_name(_name) != canonicalize_name(manifest.launch.distribution):
        raise ValueError('Application wheel must match its declared launch distribution')
    if wheel_version != Version(manifest.version):
        raise ValueError('Backend wheel and application release versions must match')
    if platform not in {'linux-x86_64', 'windows-x86_64'}:
        raise ValueError('Application requires a supported target platform')
    if manifest.release_role == 'webstudio' and web_assets is None:
        raise ValueError('WebStudio publishing requires built frontend assets')
    if web_assets is not None and manifest.web_assets is None:
        raise ValueError('Application does not declare frontend assets')
    with tempfile.TemporaryDirectory(prefix='f8-application-publish-') as temporary:
        root = Path(temporary)
        if runtime_root is None:
            build_source_runtime(source, root, wheel, extension)
        else:
            validate_runtime_package(runtime_root)
            shutil.copytree(runtime_root, root, dirs_exist_ok=True)
        published = msgspec.structs.replace(extension, runtime=msgspec.structs.replace(extension.runtime, kind='pixi'))
        catalog = ExtensionCatalog(schema_version='f8extensionCatalog/1', extensions=(published,))
        (root / 'extension.json').write_bytes(msgspec.json.encode(catalog))
        config = root / 'config'
        config.mkdir(exist_ok=True)
        (config / 'extensions.json').write_bytes(msgspec.json.encode(catalog))
        (config / 'service-index.json').write_text('{"schemaVersion":"f8serviceIndex/1","services":[],"modelRoot":"${F8_MODEL_ROOT}"}\n')
        if web_assets is not None:
            assert manifest.web_assets is not None
            prefix = '${F8_PACKAGE_ROOT}/'
            if not manifest.web_assets.startswith(prefix):
                raise ValueError('Frontend path requires package root')
            destination = (root / manifest.web_assets.removeprefix(prefix)).resolve()
            if not destination.is_relative_to(root.resolve()):
                raise ValueError('Uncontained frontend destination')
            shutil.copytree(web_assets, destination)
        (root / 'config/artifact.json').write_bytes(msgspec.json.encode(PublishedArtifact(
            schema_version='f8artifact/1', artifact_id=manifest.extension_id,
            version=manifest.version, kind='extension', platform=platform,
        )))
        validate_application(root)
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.with_suffix(output.suffix + '.tmp')
        try:
            with zipfile.ZipFile(staging, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(root.rglob('*')):
                    if path.is_symlink():
                        raise ValueError(f'Application contains a symlink: {path}')
                    if path.is_file():
                        archive.write(path, path.relative_to(root).as_posix())
            staging.replace(output)
        finally:
            staging.unlink(missing_ok=True)
    return output


class PublishArguments(argparse.Namespace):
    source: Path
    wheel: Path
    output: Path
    runtime_root: Path | None
    web_assets: Path | None
    platform: Literal['linux-x86_64', 'windows-x86_64']


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--web-assets', type=Path)
    parser.add_argument('--platform', required=True, choices=('linux-x86_64', 'windows-x86_64'))
    args = PublishArguments()
    parser.parse_args(namespace=args)
    build_application(args.source.resolve(), args.wheel.resolve(), args.output.resolve(),
                    runtime_root=args.runtime_root, web_assets=args.web_assets, platform=args.platform)


if __name__ == '__main__':
    main()
