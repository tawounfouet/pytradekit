"""In-memory SafetyEvidenceProvider."""

from copy import deepcopy

from pytradekit.portfolio.domain import AccountId
from pytradekit.safety.domain import SafetyEvidence


class InMemorySafetyEvidenceProvider:
    """Deterministic safety evidence registry for composition and tests."""

    def __init__(self) -> None:
        self._evidence: dict[AccountId, SafetyEvidence] = {}

    def set(self, account_id: AccountId, evidence: SafetyEvidence) -> None:
        self._evidence[account_id] = deepcopy(evidence)

    def get(self, account_id: AccountId) -> SafetyEvidence | None:
        evidence = self._evidence.get(account_id)
        return deepcopy(evidence) if evidence is not None else None
