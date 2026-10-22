"""Mapping between RiskPolicy and PostgreSQL JSON-safe values."""

from decimal import Decimal
from typing import cast

from pytradekit.persistence import PersistenceError
from pytradekit.risk.adapters.postgres.models import RiskPolicyModel
from pytradekit.risk.domain import RiskLimit, RiskPolicy, RiskPolicyId, RiskScope
from pytradekit.risk.domain.rules import (
    DailyLoss,
    MaxGrossExposure,
    MaxLeverage,
    MaxOrderSize,
    MaxPositionSize,
)
from pytradekit.shared import Currency, Money


def risk_policy_to_values(policy: RiskPolicy) -> dict[str, object]:
    """Return database values for one RiskPolicy."""
    return {
        "id": policy.id.value,
        "name": policy.name,
        "scope": policy.scope.value,
        "scope_id": policy.scope_id,
        "limits": [_serialize_limit(limit) for limit in policy.limits],
        "enabled": policy.enabled,
        "policy_version": policy.version,
        "allow_reduce_only_when_halted": policy.allow_reduce_only_when_halted,
    }


def risk_policy_from_model(model: RiskPolicyModel) -> RiskPolicy:
    """Rebuild a RiskPolicy and all supported P0 limits."""
    return RiskPolicy(
        id=RiskPolicyId(model.id),
        name=model.name,
        scope=RiskScope(model.scope),
        scope_id=model.scope_id,
        limits=tuple(_deserialize_limit(item) for item in model.limits),
        enabled=model.enabled,
        version=model.policy_version,
        allow_reduce_only_when_halted=model.allow_reduce_only_when_halted,
    )


def _money(value: Money) -> dict[str, str]:
    return {"amount": str(value.amount), "currency": value.currency.code}


def _money_from(value: object) -> Money:
    data = cast(dict[str, str], value)
    return Money(Decimal(data["amount"]), Currency(data["currency"]))


def _serialize_limit(limit: RiskLimit) -> dict[str, object]:
    if isinstance(limit, MaxOrderSize):
        return {
            "type": "max_order_size",
            "max_notional": _money(limit.max_notional),
            "max_quantity": str(limit.max_quantity) if limit.max_quantity is not None else None,
        }
    if isinstance(limit, MaxPositionSize):
        return {
            "type": "max_position_size",
            "max_quantity": str(limit.max_quantity),
            "max_notional": (
                _money(limit.max_notional) if limit.max_notional is not None else None
            ),
        }
    if isinstance(limit, MaxGrossExposure):
        return {"type": "max_gross_exposure", "maximum": _money(limit.maximum)}
    if isinstance(limit, MaxLeverage):
        return {"type": "max_leverage", "maximum": str(limit.maximum)}
    if isinstance(limit, DailyLoss):
        return {
            "type": "daily_loss",
            "maximum_loss_fraction": str(limit.maximum_loss_fraction),
        }
    raise PersistenceError(f"Unsupported risk limit type: {type(limit).__name__}.")


def _deserialize_limit(data: dict[str, object]) -> RiskLimit:
    limit_type = cast(str, data["type"])
    if limit_type == "max_order_size":
        raw_quantity = data.get("max_quantity")
        return MaxOrderSize(
            max_notional=_money_from(data["max_notional"]),
            max_quantity=Decimal(cast(str, raw_quantity)) if raw_quantity is not None else None,
        )
    if limit_type == "max_position_size":
        raw_notional = data.get("max_notional")
        return MaxPositionSize(
            max_quantity=Decimal(cast(str, data["max_quantity"])),
            max_notional=_money_from(raw_notional) if raw_notional is not None else None,
        )
    if limit_type == "max_gross_exposure":
        return MaxGrossExposure(maximum=_money_from(data["maximum"]))
    if limit_type == "max_leverage":
        return MaxLeverage(maximum=Decimal(cast(str, data["maximum"])))
    if limit_type == "daily_loss":
        return DailyLoss(
            maximum_loss_fraction=Decimal(cast(str, data["maximum_loss_fraction"]))
        )
    raise PersistenceError(f"Unsupported stored risk limit type: {limit_type}.")
