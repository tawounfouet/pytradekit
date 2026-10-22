"""Simple principal adapters for CLI, services, and tests."""

from pytradekit.security.domain import AuthenticatedPrincipal


class StaticPrincipalProvider:
    """Return one explicitly configured authenticated principal."""

    def __init__(self, principal: AuthenticatedPrincipal) -> None:
        self._principal = principal

    def current_principal(self) -> AuthenticatedPrincipal:
        return self._principal
