"""Route secret references to scheme-specific providers."""

from collections.abc import Mapping

from pytradekit.runtime.configuration import SecretRef
from pytradekit.runtime.errors import SecretResolutionError
from pytradekit.runtime.ports import SecretsPort


class RoutedSecrets:
    """Dispatch SecretRef values without exposing provider-specific logic."""

    def __init__(self, providers: Mapping[str, SecretsPort]) -> None:
        normalized = {
            scheme.strip().lower(): provider
            for scheme, provider in providers.items()
            if scheme.strip()
        }
        if not normalized:
            raise ValueError("RoutedSecrets requires at least one provider.")
        self._providers = normalized

    def resolve(self, reference: SecretRef) -> str:
        """Resolve through the provider registered for the reference scheme."""

        provider = self._providers.get(reference.scheme)
        if provider is None:
            raise SecretResolutionError(
                f"No secret provider is configured for scheme {reference.scheme!r}."
            )
        return provider.resolve(reference)

    def __repr__(self) -> str:
        """Expose schemes only, never provider state or secret values."""

        schemes = ",".join(sorted(self._providers))
        return f"RoutedSecrets(schemes={schemes!r})"
