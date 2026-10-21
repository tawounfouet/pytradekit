"""Tests for the common domain error hierarchy."""

from pytradekit.shared.errors import (
    DomainValidationError,
    InvariantViolationError,
    PyTradeKitError,
)


def test_domain_validation_error_inherits_from_pytradekit_error() -> None:
    assert issubclass(DomainValidationError, PyTradeKitError)


def test_invariant_violation_error_inherits_from_pytradekit_error() -> None:
    assert issubclass(InvariantViolationError, PyTradeKitError)
