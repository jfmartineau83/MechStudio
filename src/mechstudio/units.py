from __future__ import annotations

from fractions import Fraction
from typing import Any

from .models import ParameterSpec, ParameterType
from .numbers import NumericInputError, as_finite_float, parse_number


MM_PER_INCH = Fraction(127, 5)  # exact 25.4


class ParameterValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{name}: {message}" for name, message in errors.items()))


def _parse_vector(text: str) -> list[float]:
    raw = text.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise NumericInputError("Enter a comma-separated numeric vector")
    return [as_finite_float(parse_number(part)) for part in parts]


def convert_parameter(spec: ParameterSpec, text: str, mode: str) -> Any:
    kind = spec.parameter_type
    if kind == ParameterType.BOOLEAN:
        normalized = text.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise NumericInputError("Choose true or false")
    if kind in {ParameterType.TEXT, ParameterType.ENUM}:
        if kind == ParameterType.ENUM and spec.options:
            valid = {str(option.value) for option in spec.options}
            if text not in valid:
                raise NumericInputError("Choose one of the available options")
        return text
    if kind == ParameterType.VECTOR:
        return _parse_vector(text)

    value = parse_number(text)
    if kind == ParameterType.INTEGER and value.denominator != 1:
        raise NumericInputError("Enter a whole number")
    if kind == ParameterType.LENGTH and mode == "sae":
        value *= MM_PER_INCH
    result = as_finite_float(value)
    if spec.minimum is not None and result < spec.minimum:
        raise NumericInputError(f"Must be at least {spec.minimum:g}")
    if spec.maximum is not None and result > spec.maximum:
        raise NumericInputError(f"Must be at most {spec.maximum:g}")
    return int(result) if kind == ParameterType.INTEGER else result


def convert_parameters(
    specs: list[ParameterSpec], values: dict[str, str], mode: str
) -> dict[str, Any]:
    if mode not in {"metric", "sae"}:
        raise ValueError(f"Unknown generation mode: {mode}")
    converted: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for spec in specs:
        text = values.get(spec.name, str(spec.default))
        try:
            converted[spec.name] = convert_parameter(spec, text, mode)
        except (NumericInputError, ValueError) as exc:
            errors[spec.name] = str(exc)
    if errors:
        raise ParameterValidationError(errors)
    return converted

