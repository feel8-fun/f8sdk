from pathlib import Path

import msgspec
import zipfile
import pytest

from f8pysdk.extension_capabilities import validate_capabilities
from f8pysdk.extension_packaging import build_extension, validate_package
from f8pysdk.extension_spec import ExtensionCatalog, ExtensionManifest, ExtensionRuntime, ExtensionSkill, ExtensionTool, ExtensionToolField
from f8pysdk.service_paths import ServicePaths


def test_skill_package_validates_without_services_or_index(tmp_path: Path) -> None:
    (tmp_path / 'config').mkdir()
    (tmp_path / 'SKILL.md').write_text('Workflow')
    manifest = ExtensionManifest(extension_id='knowledge', name='Knowledge', version='1.0', description='Skills',
                                 skills=(ExtensionSkill(skill_id='workflow', path='${F8_PACKAGE_ROOT}/SKILL.md'),))
    catalog = ExtensionCatalog(schema_version='f8extensionCatalog/1', extensions=(manifest,))
    (tmp_path / 'extension.json').write_bytes(msgspec.json.encode(catalog))
    assert validate_package(tmp_path) == catalog


def test_invalid_tool_fields_are_rejected_before_installation(tmp_path: Path) -> None:
    manifest = ExtensionManifest(extension_id='tools', name='Tools', version='1.0', description='Tools',
        tools=(ExtensionTool(tool_id='inspect', name='Inspect', description='Inspect', command='${F8_PACKAGE_ROOT}/inspect',
            fields=(ExtensionToolField(name='target', label='Target'), ExtensionToolField(name='target', label='Duplicate'))),))
    paths = ServicePaths(tmp_path, tmp_path, tmp_path, tmp_path)
    with pytest.raises(ValueError, match='fields'):
        validate_capabilities(manifest, paths)


def test_persistent_parallel_tools_are_explicit_and_default_tools_remain_exclusive(tmp_path: Path) -> None:
    defaults = ExtensionTool(tool_id='default', name='Default', description='Default', command='python')
    assert defaults.timeout_seconds == 300 and defaults.allow_concurrent is False
    persistent = msgspec.json.decode(b'{"toolId":"stream","name":"Stream","description":"Stream","command":"python","timeoutSeconds":null,"allowConcurrent":true}', type=ExtensionTool)
    manifest = ExtensionManifest(extension_id='debug', name='Debug', version='1.0', description='Debug',
        runtime=ExtensionRuntime(kind='bundled'), tools=(persistent,))
    validate_capabilities(manifest, ServicePaths(tmp_path, tmp_path, tmp_path, tmp_path))
    assert persistent.timeout_seconds is None and persistent.allow_concurrent


def test_tool_only_wheel_bundle_needs_no_service_index(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    (source / 'config').mkdir(parents=True)
    tool = ExtensionTool(tool_id='stream', name='Stream', description='Stream', command='python',
        args=('-m', 'example.stream'), timeout_seconds=None, allow_concurrent=True)
    manifest = ExtensionManifest(extension_id='debug', name='Debug', version='1.0', description='Debug',
        runtime=ExtensionRuntime(kind='workspace', environment='web-studio-runtime'), tools=(tool,))
    catalog = ExtensionCatalog(schema_version='f8extensionCatalog/1', extensions=(manifest,))
    (source / 'extension.json').write_bytes(msgspec.json.encode(catalog))
    wheel = tmp_path / 'example.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('example/stream.py', 'print("stream")')
    output = build_extension(source, tmp_path / 'extension.zip', wheel=wheel)
    with zipfile.ZipFile(output) as archive:
        assert 'python/example/stream.py' in archive.namelist()
        assert 'config/service-index.json' not in archive.namelist()
        published = msgspec.json.decode(archive.read('config/extensions.json'), type=ExtensionCatalog)
        assert published.extensions[0].runtime.kind == 'shared'
        assert published.extensions[0].tools[0].timeout_seconds is None
    assert output.with_suffix('.zip.sha256').is_file()
