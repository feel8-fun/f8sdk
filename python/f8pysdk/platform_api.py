"""Public request contracts for the authenticated launcher API."""
from pydantic import BaseModel, ConfigDict


class ImportApplication(BaseModel):
    model_config = ConfigDict(extra='forbid')
    location: str
    sha256: str


class ApplicationConfiguration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    endpoints: dict[str, str]


class ApplicationVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sha256: str


