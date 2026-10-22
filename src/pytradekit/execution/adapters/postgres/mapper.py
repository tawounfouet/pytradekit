"""Mapping between Fill domain facts and PostgreSQL rows."""

from pytradekit.execution.adapters.postgres.models import FillModel
from pytradekit.execution.domain import Fill, FillId
from pytradekit.orders.domain import OrderId
from pytradekit.persistence import PersistenceError
from pytradekit.shared import Currency, Money, Price, Quantity


def fill_to_values(fill: Fill) -> dict[str, object]:
    """Return database values for one Fill."""
    return {
        "id": fill.id.value,
        "order_id": fill.order_id.value,
        "quantity": fill.quantity.value,
        "price_value": fill.price.value,
        "price_currency": fill.price.currency.code,
        "external_fill_id": fill.external_fill_id,
        "fee_amount": fill.fee.amount if fill.fee is not None else None,
        "fee_currency": fill.fee.currency.code if fill.fee is not None else None,
        "occurred_at": fill.occurred_at,
    }


def fill_from_model(model: FillModel) -> Fill:
    """Rebuild an immutable Fill."""
    fee: Money | None = None
    if model.fee_amount is not None or model.fee_currency is not None:
        if model.fee_amount is None or model.fee_currency is None:
            raise PersistenceError("Stored fill fee is incomplete.")
        fee = Money(model.fee_amount, Currency(model.fee_currency))

    return Fill(
        id=FillId(model.id),
        order_id=OrderId(model.order_id),
        quantity=Quantity(model.quantity),
        price=Price(model.price_value, Currency(model.price_currency)),
        occurred_at=model.occurred_at,
        external_fill_id=model.external_fill_id,
        fee=fee,
    )
