"""Capability certification levels used by broker compliance."""

from enum import IntEnum


class CertificationLevel(IntEnum):
    """Evidence strength for one provider capability."""

    C0_DEFINED = 0
    C1_IMPLEMENTED = 1
    C2_INTEGRATION_QUALIFIED = 2
    C3_PAPER_QUALIFIED = 3
    C4_LIVE_LIMITED = 4
    C5_LIVE_QUALIFIED = 5

    @property
    def code(self) -> str:
        """Return the compact certification code."""

        return f"C{int(self)}"
