"""Currency value object."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.shared.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class Currency:
    """Canonical three-letter currency code.

    Input is normalized by trimming surrounding whitespace and converting
    ASCII letters to uppercase. The canonical representation always contains
    exactly three ASCII alphabetic characters.
    """

    code: str

    def __post_init__(self) -> None:
        """Normalize and validate the canonical currency code."""
        if not isinstance(self.code, str):
            raise DomainValidationError("Currency code must be a string.")

        normalized = self.code.strip().upper()

        if not normalized:
            raise DomainValidationError("Currency code must not be empty.")

        if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
            raise DomainValidationError(
                "Currency code must contain exactly three ASCII letters."
            )

        object.__setattr__(self, "code", normalized)

    def __str__(self) -> str:
        """Return the canonical currency code."""
        return self.code
