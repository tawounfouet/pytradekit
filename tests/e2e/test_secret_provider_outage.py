"""End-to-end LOT-07 secret outage containment."""

import pytest

from pytradekit.brokers.adapters.alpaca import build_alpaca_paper_runtime
from pytradekit.runtime import RuntimeProfile, SecretRef
from pytradekit.runtime.errors import SecretResolutionError


class _UnavailableSecrets:
    def __init__(self) -> None:
        self.references: list[SecretRef] = []

    def resolve(self, reference: SecretRef) -> str:
        self.references.append(reference)
        raise SecretResolutionError(
            f"Required secret {reference} is unavailable."
        )


def test_required_secret_outage_stops_before_runtime_infrastructure() -> None:
    profile = RuntimeProfile.alpaca_paper_from_environment(
        {
            "PYTRADEKIT_RUNTIME_ENVIRONMENT": "PAPER",
            "PYTRADEKIT_ALPACA_EXPECTED_ACCOUNT_ID": "account-12345678",
        }
    )
    secrets = _UnavailableSecrets()

    with pytest.raises(SecretResolutionError):
        build_alpaca_paper_runtime(profile, secrets)

    assert secrets.references == [profile.api_key_ref]
