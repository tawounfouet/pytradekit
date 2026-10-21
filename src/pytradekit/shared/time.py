"""Time primitives for PyTradeKit domain values."""

from __future__ import annotations

from datetime import datetime, timedelta

from pytradekit.shared.errors import DomainValidationError


def require_utc_datetime(value: datetime, *, field_name: str = "datetime") -> datetime:
    """Validate that a datetime is timezone-aware and represents UTC."""
    raw_value: object = value

    if not isinstance(raw_value, datetime):
        raise DomainValidationError(f"{field_name} must be a datetime.")

    offset = raw_value.utcoffset()

    if raw_value.tzinfo is None or offset is None:
        raise DomainValidationError(f"{field_name} must be timezone-aware.")

    if offset != timedelta(0):
        raise DomainValidationError(f"{field_name} must use UTC.")

    return raw_value
