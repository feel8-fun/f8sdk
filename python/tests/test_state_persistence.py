import msgspec
import pytest

from f8pysdk.specs import (
    F8StateAccess, F8StateSpec, integer_schema, normalize_state_policy,
    state_is_persistent, state_is_publishable,
)


@pytest.mark.parametrize('access,persistent,publishable', [
    (F8StateAccess.rw, True, True), (F8StateAccess.wo, True, True), (F8StateAccess.ro, False, False),
])
def test_legacy_defaults_preserve_writable_configuration(access: F8StateAccess, persistent: bool, publishable: bool) -> None:
    field = F8StateSpec(name='state', access=access, valueSchema=integer_schema())
    assert 'persistent' not in msgspec.to_builtins(field)
    assert 'publishable' not in msgspec.to_builtins(field)
    normalized = normalize_state_policy(field)
    assert normalized.persistent is persistent
    assert normalized.publishable is publishable


def test_runtime_only_and_redacted_values_cannot_be_shared() -> None:
    field = F8StateSpec(name='state', access=F8StateAccess.rw, valueSchema=integer_schema(), persistent=False)
    assert not state_is_persistent(field)
    assert not state_is_publishable(field)
    redacted = msgspec.structs.replace(field, persistent=True, publishable=True, redactOnPublish=True)
    assert state_is_persistent(redacted)
    assert not normalize_state_policy(redacted).publishable


@pytest.mark.parametrize('access,persistent,publishable', [
    (F8StateAccess.rw, False, True), (F8StateAccess.ro, True, False), (F8StateAccess.ro, False, True),
])
def test_inconsistent_explicit_policies_fail(access: F8StateAccess, persistent: bool, publishable: bool) -> None:
    with pytest.raises(ValueError, match='state'):
        normalize_state_policy(F8StateSpec(name='state', access=access, valueSchema=integer_schema(),
                                         persistent=persistent, publishable=publishable))


def test_policy_wire_values_must_be_boolean() -> None:
    with pytest.raises(msgspec.ValidationError, match='bool'):
        msgspec.json.decode(b'{"name":"state","access":"rw","valueSchema":{"type":"integer"},"persistent":"false"}', type=F8StateSpec)
