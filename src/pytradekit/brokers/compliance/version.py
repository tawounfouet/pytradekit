"""Version identity for the candidate broker adapter contract."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CONTRACT_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-rc([1-9][0-9]*))?$"
)


@dataclass(frozen=True, slots=True)
class ContractVersion:
    """Validated semantic identity for a broker adapter contract revision."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip() if isinstance(self.value, str) else ""
        if not _CONTRACT_VERSION_PATTERN.fullmatch(normalized):
            raise ValueError(
                "ContractVersion must use '<major>.<minor>' or '<major>.<minor>-rc<n>'."
            )
        object.__setattr__(self, "value", normalized)

    @property
    def is_candidate(self) -> bool:
        """Return whether this contract version is still a release candidate."""

        return "-rc" in self.value

    def __str__(self) -> str:
        """Return the stable textual version."""

        return self.value


BROKER_ADAPTER_CONTRACT_V1_CANDIDATE_VERSION = ContractVersion("1.0-rc1")
