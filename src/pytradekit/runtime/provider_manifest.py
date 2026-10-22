"""Provider manifest describing the qualified runtime capability envelope."""

from __future__ import annotations

from dataclasses import dataclass

from pytradekit.runtime.configuration import RuntimeEnvironment
from pytradekit.runtime.errors import RuntimeConfigurationError


@dataclass(frozen=True, slots=True)
class ProviderManifest:
    """Immutable description of one qualified provider runtime contract."""

    provider: str
    environment: RuntimeEnvironment
    sdk_name: str
    sdk_version: str
    asset_scope: tuple[str, ...]
    order_types: tuple[str, ...]
    time_in_force: tuple[str, ...]
    capabilities: tuple[str, ...]
    market_data_feed: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise RuntimeConfigurationError("ProviderManifest provider must not be empty.")
        if not self.sdk_name.strip() or not self.sdk_version.strip():
            raise RuntimeConfigurationError(
                "ProviderManifest SDK name and version must not be empty."
            )
        if not self.asset_scope:
            raise RuntimeConfigurationError("ProviderManifest asset_scope must not be empty.")
        if not self.order_types:
            raise RuntimeConfigurationError("ProviderManifest order_types must not be empty.")
        if not self.time_in_force:
            raise RuntimeConfigurationError(
                "ProviderManifest time_in_force must not be empty."
            )
        if not self.capabilities:
            raise RuntimeConfigurationError(
                "ProviderManifest capabilities must not be empty."
            )
        if not self.market_data_feed.strip():
            raise RuntimeConfigurationError(
                "ProviderManifest market_data_feed must not be empty."
            )

    def to_dict(self) -> dict[str, object]:
        """Return a stable diagnostic representation."""

        return {
            "provider": self.provider,
            "environment": self.environment.value,
            "sdk": {
                "name": self.sdk_name,
                "version": self.sdk_version,
            },
            "asset_scope": list(self.asset_scope),
            "order_types": list(self.order_types),
            "time_in_force": list(self.time_in_force),
            "capabilities": list(self.capabilities),
            "market_data_feed": self.market_data_feed,
        }
