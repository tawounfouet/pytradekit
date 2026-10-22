"""Safety evidence provider boundary."""

from typing import Protocol

from pytradekit.portfolio.domain import AccountId
from pytradekit.safety.domain import SafetyEvidence


class SafetyEvidenceProvider(Protocol):
    """Return fresh enough safety evidence for one account."""

    def get(self, account_id: AccountId) -> SafetyEvidence | None:
        ...
