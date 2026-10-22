"""Default secret routing for environment and container file references."""

from pathlib import Path

from pytradekit.runtime.adapters.environment_secrets import EnvironmentSecrets
from pytradekit.runtime.adapters.file_secrets import FileSecrets
from pytradekit.runtime.adapters.routed_secrets import RoutedSecrets


def build_default_secrets(
    *,
    file_root: Path = Path("/run/secrets"),
) -> RoutedSecrets:
    """Build default env:// and file:// providers without external-manager assumptions."""

    return RoutedSecrets(
        {
            "env": EnvironmentSecrets(),
            "file": FileSecrets(file_root),
        }
    )
