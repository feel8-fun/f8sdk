from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from f8pysdk.resource_paths import model_root, resource_root
from f8pysdk.service_paths import ServicePaths
from f8pysdk.service_runtime_tools.inventory.index import indexed_entry, read_service_index


def test_index_paths_follow_package_relocation_and_separate_writable_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "installation" / "nested package"
    config = package / "config"
    config.mkdir(parents=True)
    user_config = tmp_path / "user config"
    resources = tmp_path / "resources"
    models = tmp_path / "independent models"
    monkeypatch.setenv("F8_CONFIG_ROOT", str(user_config))
    monkeypatch.setenv("F8_RESOURCE_ROOT", str(resources))
    monkeypatch.setenv("F8_MODEL_ROOT", str(models))
    monkeypatch.chdir(tmp_path)
    (config / "entry.yml").write_text(
        "schemaVersion: f8serviceEntry/1\nserviceClass: test.native\nlabel: Native\nversion: 1.0.0\n"
        "launch:\n  command: ${F8_BUNDLE_ROOT}/native\n  workdir: ${F8_BUNDLE_ROOT}\n"
        "  args: ['${F8_CONFIG_ROOT}/native.ini']\n"
    )
    index_path = config / "service-index.json"
    index_path.write_text(json.dumps({
        "schemaVersion": "f8serviceIndex/1", "modelRoot": "${F8_MODEL_ROOT}",
        "services": [{
            "serviceClass": "test.native", "manifests": {"any": "${F8_PACKAGE_ROOT}/config/entry.yml"},
            "describe": "${F8_PACKAGE_ROOT}/config/native.json",
            "bundleRoots": {"any": "${F8_PACKAGE_ROOT}/runtime/native/1.0.0"},
        }],
    }))
    relocated = tmp_path / "relocated"
    package.rename(relocated)
    index_path = relocated / "config/service-index.json"
    index = read_service_index(index_path)
    entry = indexed_entry(index_path, index, index.services[0])
    assert entry is not None
    bundle = relocated / "runtime/native/1.0.0"
    assert entry.launch.command == str(bundle / "native")
    assert entry.launch.workdir == str(bundle)
    assert entry.launch.args == [str(user_config / "native.ini")]
    assert entry.launch.env == {
        "F8_PACKAGE_ROOT": str(relocated), "F8_BUNDLE_ROOT": str(bundle),
        "F8_CONFIG_ROOT": str(user_config), "F8_RESOURCE_ROOT": str(resources), "F8_MODEL_ROOT": str(models),
    }
    assert not models.exists()


@pytest.mark.parametrize("reference", [
    "${HOME}/secret", "${F8_UNKNOWN_ROOT}", "${F8_PACKAGE_ROOT}/../../secret",
    "${F8_PACKAGE_ROOT}//absolute", "${F8_PACKAGE_ROOT}/C:/absolute", "${F8_PACKAGE_ROOT}/dir/../../../secret",
    "${F8_PACKAGE_ROOT}suffix", "${F8_PACKAGE_ROOT}/${HOME}", "${F8_PACKAGE_ROOT}/..\\secret",
])
def test_invalid_references_fail_explicitly(tmp_path: Path, reference: str) -> None:
    paths = ServicePaths(tmp_path, tmp_path, tmp_path, tmp_path)
    with pytest.raises(ValueError):
        paths.resolve(reference, relative_to=tmp_path)


def test_bundle_root_requires_explicit_registration(tmp_path: Path) -> None:
    paths = ServicePaths(tmp_path, tmp_path, tmp_path, tmp_path)
    with pytest.raises(ValueError, match="not configured"):
        paths.resolve("${F8_BUNDLE_ROOT}/native", relative_to=tmp_path)


@pytest.mark.skipif(sys.platform == "win32", reason="Creating directory symlinks requires Windows privileges")
def test_package_metadata_cannot_escape_through_symlinks(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (package / "link").symlink_to(outside, target_is_directory=True)
    paths = ServicePaths(package, outside, outside, outside)
    with pytest.raises(ValueError, match="escapes"):
        paths.package_path("${F8_PACKAGE_ROOT}/link/entry.yml", relative_to=package)
    with pytest.raises(ValueError, match="outside the package"):
        paths.package_path("${F8_CONFIG_ROOT}/entry.yml", relative_to=package)


def test_model_root_follows_resource_root_unless_overridden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("F8_MODEL_ROOT", raising=False)
    monkeypatch.setenv("F8_RESOURCE_ROOT", str(tmp_path))
    assert resource_root() == tmp_path
    assert model_root() == tmp_path / "models"
    monkeypatch.setenv("F8_MODEL_ROOT", str(tmp_path / "custom"))
    assert model_root() == tmp_path / "custom"
    monkeypatch.setenv("F8_RESOURCE_ROOT", "relative")
    with pytest.raises(ValueError, match="must be absolute"):
        resource_root()
