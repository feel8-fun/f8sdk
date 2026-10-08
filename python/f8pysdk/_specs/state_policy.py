"""Explicit authoring policy for saved and shared state values."""
from __future__ import annotations

import msgspec
from typing import overload

from ..generated import F8OperatorSchemaVersion, F8OperatorSpec, F8ServiceSchemaVersion, F8ServiceSpec, F8StateAccess, F8StateSpec

__all__ = ["normalize_spec_policy", "normalize_state_policy", "state_is_persistent", "state_is_publishable"]


def state_is_persistent(field: F8StateSpec) -> bool:
    return field.access != F8StateAccess.ro and field.persistent is not False


def state_is_publishable(field: F8StateSpec) -> bool:
    return state_is_persistent(field) and field.publishable is not False and field.redactOnPublish is not True


def normalize_state_policy(field: F8StateSpec) -> F8StateSpec:
    if field.persistent is False and field.publishable is True:
        raise ValueError(f"state {field.name!r}: a runtime-only value cannot be publishable")
    if field.access == F8StateAccess.ro and (field.persistent is True or field.publishable is True):
        raise ValueError(f"state {field.name!r}: read-only runtime values cannot be persistent or publishable")
    return msgspec.structs.replace(
        field, persistent=state_is_persistent(field), publishable=state_is_publishable(field),
    )


@overload
def normalize_spec_policy(spec: F8ServiceSpec) -> F8ServiceSpec: ...


@overload
def normalize_spec_policy(spec: F8OperatorSpec) -> F8OperatorSpec: ...


def normalize_spec_policy(spec: F8ServiceSpec | F8OperatorSpec) -> F8ServiceSpec | F8OperatorSpec:
    fields = spec.stateFields
    normalized = fields if isinstance(fields, msgspec.UnsetType) else [normalize_state_policy(field) for field in fields]
    if isinstance(spec, F8ServiceSpec):
        return msgspec.structs.replace(spec, schemaVersion=F8ServiceSchemaVersion.f8service_2, stateFields=normalized)
    return msgspec.structs.replace(spec, schemaVersion=F8OperatorSchemaVersion.f8operator_2, stateFields=normalized)
