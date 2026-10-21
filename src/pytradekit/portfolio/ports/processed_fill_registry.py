"""Processed fill registry port."""

from typing import Protocol


class ProcessedFillRegistry(Protocol):
    """Idempotency boundary protecting portfolio economic effects."""

    def contains(self, fill_key: str) -> bool:
        ...

    def mark(self, fill_key: str) -> None:
        ...
