"""Typed roots and explicit path references for installed service metadata."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path, PureWindowsPath

from .resource_paths import model_root, resource_root, service_config_root


@dataclass(frozen=True)
class ServicePaths:
    package_root: Path
    config_root: Path
    resource_root: Path
    model_root: Path
    bundle_root: Path | None = None

    def __post_init__(self) -> None:
        roots = (self.package_root, self.config_root, self.resource_root, self.model_root)
        if any(not root.is_absolute() for root in roots):
            raise ValueError("Service path roots must be absolute")
        if self.bundle_root is not None and not self.bundle_root.is_absolute():
            raise ValueError("Service bundle root must be absolute")

    @classmethod
    def for_index(cls, index_path: Path) -> ServicePaths:
        directory = index_path.resolve().parent
        package = directory.parent if directory.name == "config" else directory
        return cls(package, service_config_root().resolve(), resource_root().resolve(), model_root().resolve())

    def with_bundle(self, path: Path) -> ServicePaths:
        return replace(self, bundle_root=path.resolve())

    def resolve(self, value: str, *, relative_to: Path) -> Path:
        if "${" not in value:
            path = Path(value).expanduser()
            return (path if path.is_absolute() else relative_to / path).resolve()
        name, separator, suffix = value.partition("}")
        if not separator or "${" in suffix or (suffix and not suffix.startswith("/")):
            raise ValueError(f"Invalid service path reference: {value!r}")
        if name == "${F8_PACKAGE_ROOT":
            root = self.package_root
        elif name == "${F8_CONFIG_ROOT":
            root = self.config_root
        elif name == "${F8_RESOURCE_ROOT":
            root = self.resource_root
        elif name == "${F8_MODEL_ROOT":
            root = self.model_root
        elif name == "${F8_BUNDLE_ROOT":
            if self.bundle_root is None:
                raise ValueError("F8_BUNDLE_ROOT is not configured for this service/platform")
            root = self.bundle_root
        else:
            raise ValueError(f"Unknown service path root: {name + '}'!r}")
        root = root.resolve()
        tail = suffix[1:] if suffix else ""
        if "\\" in tail or Path(tail).is_absolute() or PureWindowsPath(tail).drive:
            raise ValueError(f"Invalid service path suffix: {value!r}")
        result = (root / tail).resolve()
        if not result.is_relative_to(root):
            raise ValueError(f"Service path escapes its declared root: {value!r}")
        return result

    def package_path(self, value: str, *, relative_to: Path) -> Path:
        path = self.resolve(value, relative_to=relative_to)
        if not path.is_relative_to(self.package_root.resolve()):
            raise ValueError(f"Service metadata path is outside the package: {value!r}")
        return path

    def environment(self) -> dict[str, str]:
        result = {
            "F8_PACKAGE_ROOT": str(self.package_root),
            "F8_CONFIG_ROOT": str(self.config_root),
            "F8_RESOURCE_ROOT": str(self.resource_root),
            "F8_MODEL_ROOT": str(self.model_root),
        }
        if self.bundle_root is not None:
            result["F8_BUNDLE_ROOT"] = str(self.bundle_root)
        return result
