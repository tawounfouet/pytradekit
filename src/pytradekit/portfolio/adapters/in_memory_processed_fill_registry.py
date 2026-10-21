"""In-memory ProcessedFillRegistry implementation."""


class InMemoryProcessedFillRegistry:
    """Deterministic set-backed fill idempotency registry."""

    def __init__(self) -> None:
        self._keys: set[str] = set()

    def contains(self, fill_key: str) -> bool:
        return fill_key in self._keys

    def mark(self, fill_key: str) -> None:
        if not isinstance(fill_key, str) or not fill_key.strip():
            raise ValueError("Processed fill key must be a non-empty string.")
        self._keys.add(fill_key)
