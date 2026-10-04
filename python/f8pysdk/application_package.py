"""Validate portable application releases without importing application implementations."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import msgspec
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .application_spec import ApplicationManifest
from .extension_spec import ExtensionCatalog, ExtensionManifest
from .runtime_package import validate_runtime_package


TOKEN = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._-]*')


def read_application_extension(root: Path) -> ExtensionManifest:
    path = root / 'extension.json'
    if not path.is_file():
        path = root / 'config/extensions.json'
    catalog = msgspec.json.decode(path.read_bytes(), type=ExtensionCatalog)
    if len(catalog.extensions) != 1 or catalog.extensions[0].application is None:
        raise ValueError('Application package must own one extension with an application entry')
    return catalog.extensions[0]


def read_application(root: Path) -> ApplicationManifest:
    extension = read_application_extension(root)
    application = extension.application
    assert application is not None
    if extension.runtime.environment != application.launch.environment:
        raise ValueError('Application launch must use its declared extension environment')
    return ApplicationManifest(extension_id=extension.extension_id, version=extension.version,
                               title=extension.name, launch=application.launch, provides=application.provides,
                               endpoints=application.endpoints, health=application.health,
                               requires=application.requires, web_assets=application.web_assets,
                               release_role=application.release_role)


def validate_application(root: Path) -> ApplicationManifest:
    manifest = read_application(root)
    if not TOKEN.fullmatch(manifest.extension_id):
        raise ValueError('Invalid application identity')
    Version(manifest.version)
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*', manifest.launch.module):
        raise ValueError('Invalid Python launch module')
    runtimes = validate_runtime_package(root)
    if manifest.launch.environment not in {entry.runtime_id for entry in runtimes.runtimes}:
        raise ValueError('Application launch environment is missing')
    endpoint_names: set[str] = set()
    for endpoint in manifest.endpoints:
        if not TOKEN.fullmatch(endpoint.name) or endpoint.name in endpoint_names:
            raise ValueError('Application endpoints require unique safe names')
        endpoint_names.add(endpoint.name)
        url = urlsplit(endpoint.url)
        if (url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or not url.port or url.username or url.password or url.query or url.fragment
                or url.path not in {'', '/'}):
            raise ValueError('Application endpoints require explicit loopback HTTP ports')
    if manifest.health.endpoint not in endpoint_names:
        raise ValueError('Health probe references an undeclared endpoint')
    if (not manifest.health.path.startswith('/') or manifest.health.path.startswith('//')
            or not 0 < manifest.health.timeout_seconds <= 300):
        raise ValueError('Invalid application health probe')
    if manifest.health.bootstrap_path is not None and (
            not manifest.health.bootstrap_path.startswith('/') or manifest.health.bootstrap_path.startswith('//')):
        raise ValueError('Invalid health session bootstrap path')
    protocol_ids: set[str] = set()
    for protocol in manifest.provides:
        if not TOKEN.fullmatch(protocol.protocol_id) or protocol.protocol_id in protocol_ids:
            raise ValueError('Provided protocol identities must be safe and unique')
        protocol_ids.add(protocol.protocol_id)
        Version(protocol.version)
    dependencies: set[str] = set()
    for dependency in manifest.requires:
        if (not TOKEN.fullmatch(dependency.extension_id) or not TOKEN.fullmatch(dependency.protocol_id)
                or dependency.extension_id == manifest.extension_id or dependency.extension_id in dependencies):
            raise ValueError('Invalid or repeated application dependency')
        dependencies.add(dependency.extension_id)
        if not dependency.versions:
            raise ValueError('Application dependency requires a protocol version range')
        SpecifierSet(dependency.versions)
    if manifest.release_role == 'webstudio':
        if manifest.web_assets is None:
            raise ValueError('WebStudio requires its frontend in the same release')
    if manifest.web_assets is not None:
        prefix = '${F8_PACKAGE_ROOT}/'
        if not manifest.web_assets.startswith(prefix):
            raise ValueError('Frontend assets require an explicit package root')
        assets = (root / manifest.web_assets.removeprefix(prefix)).resolve()
        if not assets.is_relative_to(root.resolve()) or not (assets / 'index.html').is_file():
            raise ValueError('Application frontend must be contained and include index.html')
        marker = msgspec.json.decode((assets / 'f8-release.json').read_bytes(), type=dict[str, str])
        if marker != {'extensionId': manifest.extension_id, 'version': manifest.version}:
            raise ValueError('Frontend and backend must belong to the same application release')
    return manifest
