"""File-backed secret resolver for container and local development use."""

from pathlib import Path

from pytradekit.runtime.configuration import SecretRef
from pytradekit.runtime.errors import SecretResolutionError


class FileSecrets:
    """Resolve file:// references only from an explicitly allowed root."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()

    def resolve(self, reference: SecretRef) -> str:
        """Resolve a secret file without exposing its contents in diagnostics."""

        if reference.scheme != "file":
            raise SecretResolutionError(
                f"FileSecrets cannot resolve scheme {reference.scheme!r}."
            )
        locator = reference.locator.strip()
        if not locator:
            raise SecretResolutionError("File secret reference has an empty locator.")

        candidate = Path(locator).expanduser()
        path = candidate.resolve() if candidate.is_absolute() else (self._root / candidate).resolve()
        if not path.is_relative_to(self._root):
            raise SecretResolutionError(
                "File secret reference escapes the configured secret root."
            )
        try:
            value = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SecretResolutionError(
                f"Required secret {reference} is unavailable."
            ) from exc

        normalized = value.strip()
        if not normalized:
            raise SecretResolutionError(f"Required secret {reference} is empty.")
        return normalized

    def __repr__(self) -> str:
        """Return a secret-safe diagnostic representation."""

        return f"FileSecrets(root={str(self._root)!r})"
