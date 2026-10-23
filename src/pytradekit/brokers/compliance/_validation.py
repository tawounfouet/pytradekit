"""Internal validation helpers for broker compliance models."""

from __future__ import annotations

from collections.abc import Iterable


def required_text(value: str, *, field_name: str) -> str:
    """Return stripped non-empty text or fail closed."""

    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def normalized_texts(values: Iterable[str], *, field_name: str) -> tuple[str, ...]:
    """Normalize a text collection while preserving order and uniqueness."""

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = required_text(value, field_name=field_name)
        if item in seen:
            raise ValueError(f"{field_name} values must be unique.")
        seen.add(item)
        normalized.append(item)
    return tuple(normalized)
