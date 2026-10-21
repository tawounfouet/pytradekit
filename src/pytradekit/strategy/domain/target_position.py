"""Canonical desired portfolio target."""

from dataclasses import dataclass
from decimal import Decimal

from pytradekit.shared import DomainValidationError, InstrumentId, Money


@dataclass(frozen=True, slots=True)
class TargetPosition:
    """Desired position expressed in exactly one sizing mode."""

    instrument_id: InstrumentId
    target_quantity: Decimal | None = None
    target_notional: Money | None = None
    target_weight: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, InstrumentId):
            raise DomainValidationError("TargetPosition instrument_id must be an InstrumentId.")
        active = sum(
            value is not None
            for value in (self.target_quantity, self.target_notional, self.target_weight)
        )
        if active != 1:
            raise DomainValidationError("TargetPosition requires exactly one active target mode.")
        if self.target_quantity is not None and (
            not isinstance(self.target_quantity, Decimal) or not self.target_quantity.is_finite()
        ):
            raise DomainValidationError("TargetPosition target_quantity must be a finite Decimal.")
        if self.target_notional is not None and not isinstance(self.target_notional, Money):
            raise DomainValidationError("TargetPosition target_notional must be Money or None.")
        if self.target_weight is not None and (
            not isinstance(self.target_weight, Decimal) or not self.target_weight.is_finite()
        ):
            raise DomainValidationError("TargetPosition target_weight must be a finite Decimal.")
