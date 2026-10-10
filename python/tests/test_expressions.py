import pytest

from f8pysdk.expressions import (
    GLOBAL_FUNCTIONS, ExpressionValidator, JsonRef, compile_expression,
    evaluate_expression, sigmoid, unwrap_value, wrap_value,
)


def test_nested_json_values_preserve_sequence_operations() -> None:
    code, error = compile_expression("len(payload.items) + sum(payload.items[1:])", functions=GLOBAL_FUNCTIONS.keys())
    assert code is not None and error is None
    assert evaluate_expression(code, names={"payload": wrap_value({"items": [10, 20, 30]})},
                               functions=GLOBAL_FUNCTIONS) == 53
    assert unwrap_value(wrap_value({"items": [{"id": 1}]})) == {"items": [{"id": 1}]}


@pytest.mark.parametrize("index", [True, "1", 1.5])
def test_sequence_indexes_reject_coercion(index: object) -> None:
    with pytest.raises(TypeError, match="integer or slice"):
        JsonRef([10, 20])[index]


def test_json_private_keys_cannot_be_read() -> None:
    value = JsonRef({"_private": 1})
    with pytest.raises(KeyError):
        value["_private"]
    with pytest.raises(AttributeError):
        value._private


def test_validator_does_not_keep_errors_between_expressions() -> None:
    validator = ExpressionValidator(functions=GLOBAL_FUNCTIONS.keys())
    assert validator.validate("payload.__class__")[0] is None
    assert validator.validate("len(payload)")[1] is None


def test_scalar_sigmoid_handles_extreme_values_and_reports_invalid_input() -> None:
    assert sigmoid(-1000) == 0
    assert sigmoid(1000) == 1
    with pytest.raises(ValueError):
        sigmoid("invalid")
