"""Build an extension ZIP from an independent service source tree and wheel/runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

import msgspec
import yaml
from packaging.utils import parse_wheel_filename
from packaging.tags import sys_tags

from .release_spec import PublishedArtifact
from .runtime_package import validate_runtime_package

from .codec import copy_model, validate_as
from .extension_spec import ExtensionCatalog
from .extension_capabilities import validate_capabilities
from .monitoring import validate_describe_monitor_contract
from .service_runtime_tools.inventory.index import ServiceIndex, index_paths, indexed_entry, read_service_index
from .service_runtime_tools.inventory.entry import absolutize_entry_paths
from .specs import F8ServiceDescribe, F8ServiceEntry


def validate_package(source: Path) -> ExtensionCatalog:
    catalog_path = source / 'extension.json'
    if not catalog_path.is_file():
        catalog_path = source / 'config/extensions.json'
    catalog = msgspec.json.decode(catalog_path.read_bytes(), type=ExtensionCatalog)
    if len(catalog.extensions) != 1:
        raise ValueError('An extension package must own exactly one extension')
    index_path = source / 'config/service-index.json'
    index = (read_service_index(index_path) if index_path.is_file() else
             ServiceIndex(schemaVersion='f8serviceIndex/1', services=(), modelRoot='${F8_MODEL_ROOT}'))
    paths = index_paths(index_path, index)
    owners = [service for extension in catalog.extensions for service in extension.service_classes]
    if not catalog.extensions or len(owners) != len(set(owners)) or set(owners) != {item.serviceClass for item in index.services}:
        raise ValueError('Extension ownership must match the service index exactly')
    for extension in catalog.extensions:
        validate_capabilities(extension, paths)
    ids = [extension.extension_id for extension in catalog.extensions]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate extension ID')
    for item in index.services:
        for relative in item.manifests.values():
            path = paths.package_path(relative, relative_to=index_path.parent)
            if not path.is_relative_to(source.resolve()) or not path.is_file():
                raise ValueError(f'Missing or unsafe service metadata: {relative}')
        for platform, relative in item.manifests.items():
            manifest = paths.package_path(relative, relative_to=index_path.parent)
            entry = validate_as(F8ServiceEntry, yaml.safe_load(manifest.read_text()))
            if entry.serviceClass != item.serviceClass:
                raise ValueError(f'Service manifest disagrees with index: {relative}')
            if entry.launch.command in {'pixi', 'pixi.exe'}:
                raise ValueError(f'Extension must declare its own module/executable, not a superbuild task: {relative}')
            absolutize_entry_paths(entry, service_dir=manifest.parent,
                                    paths=index_paths(index_path, index, item, platform=platform))
        describe_path = paths.package_path(item.describe, relative_to=index_path.parent)
        if not describe_path.is_relative_to(source.resolve()):
            raise ValueError(f'Unsafe service description path: {item.describe}')
        if describe_path.is_file():
            payload = json.loads(describe_path.read_bytes())
            describe = validate_as(F8ServiceDescribe, payload)
            if describe.service.serviceClass != item.serviceClass:
                raise ValueError(f'Service description disagrees with index: {item.serviceClass}')
            validate_describe_monitor_contract(payload)
    return catalog


def _extract_wheel(wheel: Path, destination: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            path = destination / info.filename
            if not path.resolve().is_relative_to(destination.resolve()) or '\\' in info.filename:
                raise ValueError(f'Unsafe wheel path: {info.filename}')
            if '.data' in Path(info.filename).parts[0]:
                raise ValueError(f'Extension wheel must contain importable modules only: {info.filename}')
        archive.extractall(destination)


def build_extension(source: Path, output: Path, *, wheel: Path | None = None, runtime_root: Path | None = None,
                    web_assets: Path | None = None) -> Path:
    source = source.resolve()
    catalog = validate_package(source)
    if catalog.extensions[0].application is not None:
        from .application_packaging import build_application
        if wheel is None:
            raise ValueError('Application extensions require their backend wheel')
        platform = 'windows-x86_64' if sys.platform == 'win32' else 'linux-x86_64'
        return build_application(source, wheel, output, runtime_root=runtime_root, web_assets=web_assets, platform=platform)
    if web_assets is not None:
        raise ValueError('Frontend assets require an application extension')
    kinds = {extension.runtime.kind for extension in catalog.extensions}
    if kinds <= {'workspace', 'shared', 'pixi'}:
        python_package = True
    elif kinds == {'native'}:
        python_package = False
    else:
        raise ValueError('This builder accepts native services or managed Python services')
    if python_package != (wheel is not None):
        raise ValueError('Python extensions require --wheel; native extensions must not supply one')
    if python_package and any(extension.runtime.environment is None for extension in catalog.extensions):
        raise ValueError('Python extensions must declare their runtime environment')
    if kinds == {'workspace'} and runtime_root is None:
        from .extension_runtime_build import build_source_runtime

        assert wheel is not None
        with tempfile.TemporaryDirectory(prefix='f8-extension-runtime-') as temporary:
            runtime = build_source_runtime(source, Path(temporary).resolve(), wheel.resolve(), catalog.extensions[0])
            return build_extension(source, output, wheel=wheel, runtime_root=runtime)
    private_runtime = kinds == {'pixi'} or (kinds == {'workspace'} and runtime_root is not None)
    with tempfile.TemporaryDirectory(prefix='f8-extension-') as temporary:
        # Windows temp directories may use an 8.3 alias or a junction. Resolve
        # the root just as indexed_entry resolves every service workdir.
        stage = Path(temporary).resolve()
        shutil.copytree(source / 'config', stage / 'config')
        if (source / 'resources').is_dir():
            shutil.copytree(source / 'resources', stage / 'resources')
        published = copy_model(catalog, update={
            'preinstalled': (),
            'extensions': tuple(copy_model(extension, update={
                'runtime': copy_model(extension.runtime, update={'kind': 'pixi' if private_runtime else 'shared'})
            }) if extension.runtime.kind == 'workspace' else extension for extension in catalog.extensions),
        })
        (stage / 'config/extensions.json').write_bytes(msgspec.json.encode(published))
        tags = tuple(sorted(str(tag) for tag in parse_wheel_filename(wheel.name)[3])) if wheel is not None else ()
        if wheel is not None and not set(tags).intersection(str(tag) for tag in sys_tags()):
            raise ValueError('Extension wheel is incompatible with the publisher interpreter')
        if len(published.extensions) == 1:
            extension = published.extensions[0]
            platform = ('any' if wheel is not None and not private_runtime and all(tag.endswith('-any') for tag in tags)
                        else 'windows-x86_64' if sys.platform == 'win32' else 'linux-x86_64')
            if platform != 'any' and sys.platform not in {'linux', 'win32'}:
                raise ValueError(f'Unsupported extension release platform: {sys.platform}')
            (stage / 'config/artifact.json').write_bytes(msgspec.json.encode(PublishedArtifact(
                schema_version='f8artifact/1', artifact_id=extension.extension_id, version=extension.version,
                kind='extension', platform=platform, wheel_tags=tags,
            )))
        if wheel is not None:
            _extract_wheel(wheel, stage / 'python')
            if private_runtime:
                if kinds not in ({'pixi'}, {'workspace'}) or runtime_root is None:
                    raise ValueError('Independent Pixi extensions require a single runtime kind and --runtime-root')
                runtime_root = runtime_root.resolve()
                runtimes = validate_runtime_package(runtime_root)
                declared = {extension.runtime.environment for extension in catalog.extensions}
                if not declared <= {item.runtime_id for item in runtimes.runtimes}:
                    raise ValueError('Extension default environment must be declared in its published runtime workspace')
                locked_wheels: list[Path] = []
                for definition in runtimes.runtimes:
                    workspace = runtime_root / definition.manifest.removeprefix('${F8_PACKAGE_ROOT}/')
                    lock = yaml.safe_load(workspace.with_name('pixi.lock').read_text(encoding='utf-8'))
                    locked_wheels.extend(workspace.parent / entry['pypi'] for entry in lock['packages']
                                         if isinstance(entry.get('pypi'), str) and '://' not in entry['pypi'])
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
                if not any(path.name == wheel.name and hashlib.sha256(path.read_bytes()).hexdigest() == digest
                           for path in locked_wheels):
                    raise ValueError('Extension wheel must be part of its published runtime lock')
                shutil.copytree(runtime_root, stage / 'runtime-definition',
                    ignore=shutil.ignore_patterns('.git', '.pixi', '__pycache__'))
                relocated = copy_model(runtimes, update={'runtimes': tuple(copy_model(item, update={
                    'manifest': '${F8_PACKAGE_ROOT}/runtime-definition/' + item.manifest.removeprefix('${F8_PACKAGE_ROOT}/'),
                }) for item in runtimes.runtimes)})
                (stage / 'config/runtime-environments.json').write_bytes(msgspec.json.encode(relocated))
                for item in relocated.runtimes:
                    subprocess.run(['pixi', 'lock', '--manifest-path', str(stage / item.manifest.removeprefix('${F8_PACKAGE_ROOT}/')),
                                    '--check'], check=True)
            elif runtime_root is not None:
                raise ValueError('Shared Python extensions must not embed a private runtime')
        else:
            if runtime_root is None:
                raise ValueError('Native extensions require --runtime-root with deployed runtime dependencies')
            index_path = stage / 'config/service-index.json'
            index = read_service_index(index_path)
            if any(sys.platform not in item.manifests and 'any' not in item.manifests for item in index.services):
                raise ValueError(f'Native service package does not support {sys.platform}')
            index = copy_model(index, update={'services': tuple(copy_model(item, update={
                'bundleRoots': {platform: reference for platform, reference in item.bundleRoots.items()
                                if platform in {sys.platform, 'any'}},
                'manifests': {platform: relative for platform, relative in item.manifests.items()
                              if platform in {sys.platform, 'any'}},
            }) for item in index.services)})
            index_path.write_bytes(msgspec.json.encode(index))
            copied: set[Path] = set()
            for item in index.services:
                entry = indexed_entry(stage / 'config/service-index.json', index, item)
                if entry is None:
                    continue
                if not isinstance(entry.launch.workdir, str):
                    raise ValueError(f'Missing native service workdir: {item.serviceClass}')
                directory = Path(entry.launch.workdir).resolve()
                if not directory.is_relative_to(stage / 'runtime/bundles'):
                    raise ValueError(f'Native service workdir must be inside runtime/bundles: {item.serviceClass}')
                relative = directory.relative_to(stage / 'runtime/bundles')
                original = runtime_root.resolve() / relative
                if not original.resolve().is_relative_to(runtime_root.resolve()):
                    raise ValueError(f'Unsafe native runtime path: {original}')
                if directory not in copied:
                    shutil.copytree(original, directory)
                    copied.add(directory)
        if any(extension.service_classes for extension in catalog.extensions):
            _refresh_describes(stage, python_package=python_package)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_archive = output.with_suffix('.zip.tmp')
        with zipfile.ZipFile(temporary_archive, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.write(path, path.relative_to(stage).as_posix())
        temporary_archive.replace(output)
    with output.open('rb') as archive_file:
        digest = hashlib.file_digest(archive_file, 'sha256').hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n')
    return output


def _refresh_describes(stage: Path, *, python_package: bool) -> None:
    index_path = stage / 'config/service-index.json'
    index = read_service_index(index_path)
    for item in index.services:
        entry = indexed_entry(index_path, index, item)
        if entry is None:
            continue
        if not isinstance(entry.launch.workdir, str):
            raise ValueError(f'Missing service workdir: {item.serviceClass}')
        if python_package:
            args = entry.launch.args or []
            if entry.launch.command != 'python' or len(args) != 2 or args[0] != '-m':
                raise ValueError(f'Python service must launch python -m module: {item.serviceClass}')
            command = [sys.executable, '-I', '-c',
                       'import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); '
                       'runpy.run_module(sys.argv.pop(1), run_name="__main__")',
                       str(stage / 'python'), args[1], '--describe']
        else:
            command = [entry.launch.command, *(entry.launch.args or []), '--describe']
        process = subprocess.run(command, cwd=entry.launch.workdir, env={**os.environ, **(entry.launch.env or {})},
                                 capture_output=True, text=True, timeout=120)
        if process.returncode:
            raise RuntimeError(f'{item.serviceClass} --describe failed ({process.returncode}):\n{process.stderr}')
        payload = json.loads(process.stdout)
        describe = validate_as(F8ServiceDescribe, payload)
        if describe.service.serviceClass != item.serviceClass:
            raise ValueError(f'Built service class mismatch: {item.serviceClass}')
        validate_describe_monitor_contract(payload)
        describe_path = index_paths(index_path, index, item).package_path(item.describe, relative_to=index_path.parent)
        describe_path.parent.mkdir(parents=True, exist_ok=True)
        describe_path.write_bytes(msgspec.json.encode(describe))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    parser.add_argument('--wheel', type=Path)
    parser.add_argument('--wheel-dir', type=Path)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--web-assets', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.wheel_dir is not None:
        wheels = tuple(args.wheel_dir.glob('*.whl'))
        if args.wheel is not None or len(wheels) != 1:
            parser.error('--wheel-dir must contain exactly one extension wheel')
        args.wheel = wheels[0]
    if args.check:
        validate_package(args.source)
    elif args.output is not None:
        print(build_extension(args.source, args.output, wheel=args.wheel, runtime_root=args.runtime_root, web_assets=args.web_assets))
    else:
        parser.error('--output or --check is required')


if __name__ == '__main__':
    main()
