"""Generic external secret-provider adapter."""

from collections.abc import Callable

from pytradekit.runtime.configuration import SecretRef
from pytradekit.runtime.errors import SecretResolutionError

ExternalSecretLookup = Callable[[str], str | None]


class ExternalSecretsProvider:
    """Resolve external:// references through an injected secret-manager lookup."""

    def __init__(self, lookup: ExternalSecretLookup) -> None:
        self._lookup = lookup

    def resolve(self, reference: SecretRef) -> str:
        """Resolve one external secret and fail closed with sanitized errors."""

        if reference.scheme != "external":
            raise SecretResolutionError(
                f"ExternalSecretsProvider cannot resolve scheme {reference.scheme!r}."
            )
        locator = reference.locator.strip()
        if not locator:
            raise SecretResolutionError(
                "External secret reference has an empty locator."
            )
        try:
            raw = self._lookup(locator)
        except Exception:
            raise SecretResolutionError(
                f"External secret provider could not resolve {reference}."
            ) from None

        normalized = raw.strip() if isinstance(raw, str) else ""
        if not normalized:
            raise SecretResolutionError(
                f"Required external secret {reference} is unavailable."
            )
        return normalized

    def __repr__(self) -> str:
        """Return a representation that never includes provider results."""

        return "ExternalSecretsProvider(lookup=<configured>)"
