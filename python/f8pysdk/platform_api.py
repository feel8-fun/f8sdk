"""Public request contracts for the authenticated launcher API."""
from pydantic import BaseModel, ConfigDict
import msgspec


class ImportApplication(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    location: str
    sha256: str


class ApplicationConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    endpoints: dict[str, str]


class ApplicationVersion(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    sha256: str


class PlatformStartup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    applications: tuple[str, ...]
