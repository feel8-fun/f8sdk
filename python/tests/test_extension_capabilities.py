from pathlib import Path
import json

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


def test_explicit_shared_tool_only_wheel_bundle_needs_no_service_index(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    (source / 'config').mkdir(parents=True)
    tool = ExtensionTool(tool_id='stream', name='Stream', description='Stream', command='python',
        args=('-m', 'example.stream'), timeout_seconds=None, allow_concurrent=True)
    manifest = ExtensionManifest(extension_id='debug', name='Debug', version='1.0', description='Debug',
        runtime=ExtensionRuntime(kind='shared', environment='debug'), tools=(tool,))
    catalog = ExtensionCatalog(schema_version='f8extensionCatalog/1', extensions=(manifest,))
    (source / 'extension.json').write_bytes(msgspec.json.encode(catalog))
    wheel = tmp_path / 'example-1.0-py3-none-any.whl'
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


def test_independent_tool_packages_its_own_locked_runtime(tmp_path: Path) -> None:
    from unittest.mock import patch
    import yaml
    from f8pysdk.runtime_package import validate_runtime_package

    source = tmp_path / 'source'
    (source / 'config').mkdir(parents=True)
    tool = ExtensionTool(tool_id='run', name='Run', description='Run', command='python', args=('-m', 'example.stream'))
    manifest = ExtensionManifest(extension_id='independent', name='Independent', version='1.0', description='Independent',
        runtime=ExtensionRuntime(kind='pixi', environment='independent'), tools=(tool,))
    (source / 'extension.json').write_bytes(msgspec.json.encode(ExtensionCatalog(schema_version='f8extensionCatalog/1', extensions=(manifest,))))
    runtime = tmp_path / 'runtime'
    workspace = runtime / 'runtimes/independent'
    workspace.mkdir(parents=True)
    (runtime / 'config').mkdir()
    (runtime / 'wheels').mkdir()
    wheel = runtime / 'wheels/example-1.0-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('example/stream.py', 'print("run")')
    (workspace / 'pixi.toml').write_text('[workspace]\nname="private"\nchannels=["conda-forge"]\nplatforms=["linux-64"]\n'
        '[pypi-dependencies]\nexample={path="../../wheels/' + wheel.name + '"}\n[environments]\nindependent=[]\n')
    (workspace / 'pixi.lock').write_text(yaml.safe_dump({'version': 6, 'environments': {'independent': {}},
        'packages': [{'pypi': '../../wheels/' + wheel.name, 'name': 'example', 'version': '1.0'}]}))
    (runtime / 'config/runtime-environments.json').write_text(json.dumps({'schemaVersion': 'f8runtimeCatalog/1', 'runtimes': [{
        'runtimeId': 'independent', 'providerId': 'example.private', 'version': '1.0', 'abi': 'py3',
        'manifest': '${F8_PACKAGE_ROOT}/runtimes/independent/pixi.toml',
    }]}))
    with patch('f8pysdk.extension_packaging.subprocess.run') as run:
        output = build_extension(source, tmp_path / 'extension.zip', wheel=wheel, runtime_root=runtime)
        assert len(run.call_args_list) == 1
        assert run.call_args.args[0][-1] == '--check'
    with zipfile.ZipFile(output) as archive:
        destination = tmp_path / 'package'
        archive.extractall(destination)
    catalog = validate_runtime_package(destination)
    assert catalog.runtimes[0].provider_id == 'example.private'
    assert catalog.runtimes[0].manifest.startswith('${F8_PACKAGE_ROOT}/runtime-definition/')
    published = msgspec.json.decode((destination / 'config/extensions.json').read_bytes(), type=ExtensionCatalog)
    assert published.extensions[0].runtime.kind == 'pixi'
    definition_path = runtime / 'config/runtime-environments.json'
    definitions = json.loads(definition_path.read_text())
    second = dict(definitions['runtimes'][0])
    second['runtimeId'] = 'second'
    second['manifest'] = '${F8_PACKAGE_ROOT}/runtimes/second/pixi.toml'
    definitions['runtimes'].append(second)
    definition_path.write_text(json.dumps(definitions))
    second_workspace = runtime / 'runtimes/second'
    second_workspace.mkdir()
    (second_workspace / 'pixi.toml').write_text((workspace / 'pixi.toml').read_text().replace('independent=[]', 'second=[]'))
    (second_workspace / 'pixi.lock').write_text((workspace / 'pixi.lock').read_text().replace('independent:', 'second:'))
    with patch('f8pysdk.extension_packaging.subprocess.run'):
        multiple = build_extension(source, tmp_path / 'two-environments.zip', wheel=wheel, runtime_root=runtime)
    with zipfile.ZipFile(multiple) as archive:
        declared = json.loads(archive.read('config/runtime-environments.json'))
        assert {item['runtimeId'] for item in declared['runtimes']} == {'independent', 'second'}



def test_package_rejects_multiple_extension_owners(tmp_path: Path) -> None:
    tool = ExtensionTool(tool_id='run', name='Run', description='Run', command='python')
    first = ExtensionManifest(extension_id='first', name='First', version='1.0', description='First', tools=(tool,))
    second = ExtensionManifest(extension_id='second', name='Second', version='1.0', description='Second', tools=(tool,))
    catalog = ExtensionCatalog(schema_version='f8extensionCatalog/1', extensions=(first, second))
    (tmp_path / 'extension.json').write_bytes(msgspec.json.encode(catalog))
    with pytest.raises(ValueError, match='exactly one extension'):
        validate_package(tmp_path)


def test_source_publisher_preserves_custom_names_and_multiple_environments(tmp_path: Path) -> None:
    import subprocess
    import tomllib
    from unittest.mock import patch
    import yaml
    from f8pysdk.runtime_package import validate_runtime_package

    source = tmp_path / 'source'
    (source / 'config').mkdir(parents=True)
    dependency = tmp_path / 'sdk-1.0-py3-none-any.whl'
    wheel = tmp_path / 'example-1.0-py3-none-any.whl'
    for path, module in ((dependency, 'sdk'), (wheel, 'example')):
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(f'{module}/__init__.py', '')
    tool = ExtensionTool(tool_id='run', name='Run', description='Run', command='python', args=('-m', 'example'))
    extension = ExtensionManifest(extension_id='custom', name='Custom', version='1.0', description='Custom',
        runtime=ExtensionRuntime(kind='workspace', environment='runtime'), tools=(tool,))
    (source / 'extension.json').write_bytes(msgspec.json.encode(ExtensionCatalog(
        schema_version='f8extensionCatalog/1', extensions=(extension,))))
    (source / 'pixi.toml').write_text('[workspace]\nname="custom"\nchannels=["conda-forge"]\nplatforms=["linux-64"]\n'
        '[pypi-dependencies]\nexample={path=".",editable=true}\nsdk={path="../' + dependency.name + '"}\n'
        '[environments]\nruntime=[]\nchecks=[]\n')
    original = (source / 'pixi.toml').read_bytes()
    (source / 'pixi.lock').write_text('source lock\n')

    def resolve(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command[:2] == ['pixi', 'lock']
        manifest_path = Path(command[command.index('--manifest-path') + 1])
        if '--check' not in command:
            manifest = tomllib.loads(manifest_path.read_text())
            entries = [{'pypi': item['path']} for item in manifest['pypi-dependencies'].values()]
            manifest_path.with_name('pixi.lock').write_text(yaml.safe_dump({'version': 6,
                'environments': {name: {'packages': {'linux-64': entries}} for name in manifest['environments']},
                'packages': entries}))
        return subprocess.CompletedProcess(command, 0)

    with patch('subprocess.run', side_effect=resolve):
        output = build_extension(source, tmp_path / 'extension.zip', wheel=wheel)
    with zipfile.ZipFile(output) as archive:
        destination = tmp_path / 'published'
        archive.extractall(destination)
    catalog = validate_runtime_package(destination)
    assert {item.runtime_id for item in catalog.runtimes} == {'runtime', 'checks'}
    assert len({item.manifest for item in catalog.runtimes}) == 1
    published = msgspec.json.decode((destination / 'config/extensions.json').read_bytes(), type=ExtensionCatalog)
    assert published.extensions[0].runtime == ExtensionRuntime(kind='pixi', environment='runtime')
    assert (source / 'pixi.toml').read_bytes() == original
