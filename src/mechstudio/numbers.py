from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction


class NumericInputError(ValueError):
    pass


_DECIMAL = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_FRACTION = re.compile(r"^([+-]?\d+)\s*/\s*(\d+)$")
_MIXED_SPACE = re.compile(r"^([+-]?\d+)\s+(\d+)\s*/\s*(\d+)$")
_MIXED_HYPHEN = re.compile(r"^([+-]?\d+)-(\d+)\s*/\s*(\d+)$")


def _fraction(numerator: int, denominator: int) -> Fraction:
    if denominator == 0:
        raise NumericInputError("Division by zero is not allowed")
    return Fraction(numerator, denominator)


def parse_number(text: str) -> Fraction:
    """Parse a decimal, fraction, or mixed fraction without evaluating code."""
    raw = text.strip()
    if not raw:
        raise NumericInputError("A value is required")

    match = _MIXED_SPACE.fullmatch(raw) or _MIXED_HYPHEN.fullmatch(raw)
    if match:
        whole, numerator, denominator = map(int, match.groups())
        part = _fraction(numerator, denominator)
        if part >= 1:
            raise NumericInputError("The fractional part of a mixed number must be less than one")
        return Fraction(whole, 1) + (-part if whole < 0 else part)

    match = _FRACTION.fullmatch(raw)
    if match:
        return _fraction(int(match.group(1)), int(match.group(2)))

    if _DECIMAL.fullmatch(raw):
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise NumericInputError(f"Invalid number: {text}") from exc
        if not value.is_finite():
            raise NumericInputError("Nonfinite values are not allowed")
        return Fraction(value)

    raise NumericInputError(
        "Use a decimal, fraction (1/8), or mixed fraction (1 1/2 or 1-1/2)"
    )


def as_finite_float(value: Fraction) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise NumericInputError("Value is outside the supported numeric range")
    return result

