"""Secret-safe sanitization for broker compliance evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from enum import Enum

from ._validation import required_text

_REDACTED = "[REDACTED]"
_FORBIDDEN_KEY_FRAGMENTS = (
    "secret",
    "password",
    "api_key",
    "apikey",
    "token",
    "credential",
    "authorization",
    "cookie",
    "private_key",
    "access_key",
)
_SECRET_VALUE_MARKERS = (
    "bearer ",
    "basic ",
    "password=",
    "secret=",
    "api_key=",
    "apikey=",
    "token=",
    "credential=",
    "authorization:",
    "-----begin private key-----",
)


class EvidenceSanitizer:
    """Convert evidence payloads into JSON-safe structures without credentials."""

    def sanitize(
        self,
        payload: Mapping[str, object],
        *,
        sensitive_values: Iterable[str] = (),
    ) -> dict[str, object]:
        """Return sanitized evidence and verify no known secret material remains."""

        secrets = tuple(
            required_text(value, field_name="sensitive_values")
            for value in sensitive_values
        )
        result = {
            required_text(str(key), field_name="evidence key"): self._sanitize_value(
                value,
                key=str(key),
                sensitive_values=secrets,
            )
            for key, value in payload.items()
        }
        self.assert_safe(result, sensitive_values=secrets)
        return result

    def assert_safe(
        self,
        payload: Mapping[str, object],
        *,
        sensitive_values: Iterable[str] = (),
    ) -> None:
        """Fail if a purportedly sanitized payload still contains secret material."""

        secrets = tuple(
            required_text(value, field_name="sensitive_values")
            for value in sensitive_values
        )
        findings = self._scan(payload, sensitive_values=secrets)
        if findings:
            raise ValueError(
                "Compliance evidence contains secret-like material: "
                + ", ".join(findings)
            )

    def _sanitize_value(
        self,
        value: object,
        *,
        key: str | None,
        sensitive_values: tuple[str, ...],
    ) -> object:
        if key is not None and self._forbidden_key(key):
            return _REDACTED
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return str(value.value)
        if isinstance(value, str):
            return self._sanitize_text(value, sensitive_values=sensitive_values)
        if isinstance(value, Mapping):
            return {
                required_text(str(nested_key), field_name="evidence key"):
                self._sanitize_value(
                    nested_value,
                    key=str(nested_key),
                    sensitive_values=sensitive_values,
                )
                for nested_key, nested_value in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return [
                self._sanitize_value(
                    item,
                    key=None,
                    sensitive_values=sensitive_values,
                )
                for item in value
            ]
        raise ValueError(
            "Compliance evidence supports only JSON-like values, datetime, Decimal, and Enum."
        )

    @staticmethod
    def _forbidden_key(key: str) -> bool:
        lowered = key.lower()
        return any(fragment in lowered for fragment in _FORBIDDEN_KEY_FRAGMENTS)

    @staticmethod
    def _sanitize_text(value: str, *, sensitive_values: tuple[str, ...]) -> str:
        lowered = value.lower()
        if any(marker in lowered for marker in _SECRET_VALUE_MARKERS):
            return _REDACTED
        sanitized = value
        for secret in sensitive_values:
            sanitized = sanitized.replace(secret, _REDACTED)
        return sanitized

    def _scan(
        self,
        payload: Mapping[str, object],
        *,
        sensitive_values: tuple[str, ...],
        path: str = "$",
    ) -> list[str]:
        findings: list[str] = []
        for key, value in payload.items():
            current = f"{path}.{key}"
            if self._forbidden_key(key) and value != _REDACTED:
                findings.append(current)
                continue
            findings.extend(
                self._scan_value(
                    value,
                    sensitive_values=sensitive_values,
                    path=current,
                )
            )
        return findings

    def _scan_value(
        self,
        value: object,
        *,
        sensitive_values: tuple[str, ...],
        path: str,
    ) -> list[str]:
        if isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in _SECRET_VALUE_MARKERS):
                return [path]
            if any(secret in value for secret in sensitive_values):
                return [path]
            return []
        if isinstance(value, Mapping):
            typed = {str(key): nested for key, nested in value.items()}
            return self._scan(
                typed,
                sensitive_values=sensitive_values,
                path=path,
            )
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            findings: list[str] = []
            for index, item in enumerate(value):
                findings.extend(
                    self._scan_value(
                        item,
                        sensitive_values=sensitive_values,
                        path=f"{path}[{index}]",
                    )
                )
            return findings
        return []
