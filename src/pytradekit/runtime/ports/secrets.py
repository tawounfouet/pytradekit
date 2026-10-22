"""Secret resolution port used by runtime composition."""

from typing import Protocol

from pytradekit.runtime.configuration import SecretRef


class SecretsPort(Protocol):
    """Resolve opaque secret references without exposing storage details."""

    def resolve(self, reference: SecretRef) -> str:
        """Resolve one secret reference."""

        ...
