from pathlib import Path

import msgspec
import pytest

from f8pysdk.extension_capabilities import validate_capabilities
from f8pysdk.extension_packaging import validate_package
from f8pysdk.extension_spec import ExtensionCatalog, ExtensionManifest, ExtensionSkill, ExtensionTool, ExtensionToolField
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
