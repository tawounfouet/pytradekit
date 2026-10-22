"""PostgreSQL OrderRepository implementation."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pytradekit.orders.adapters.postgres.mapper import order_from_model, order_to_values
from pytradekit.orders.adapters.postgres.models import OrderModel
from pytradekit.orders.domain import (
    Order,
    OrderAlreadyExistsError,
    OrderId,
    OrderNotFoundError,
)
from pytradekit.persistence import ConcurrentWriteError


class PostgresOrderRepository:
    """Durable Order aggregate repository with optimistic concurrency."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen_versions: dict[OrderId, int] = {}

    def get(self, order_id: OrderId) -> Order | None:
        row = self._session.get(OrderModel, order_id.value)
        if row is None:
            return None
        self._seen_versions[order_id] = row.version
        return order_from_model(row)

    def add(self, order: Order) -> None:
        self._session.add(OrderModel(**order_to_values(order)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise OrderAlreadyExistsError(f"Order {order.id} already exists.") from exc
        self._seen_versions[order.id] = order.version

    def save(self, order: Order) -> None:
        statement = select(OrderModel).where(OrderModel.id == order.id.value).with_for_update()
        row = self._session.execute(statement).scalar_one_or_none()
        if row is None:
            raise OrderNotFoundError(f"Order {order.id} was not found.")

        expected = self._seen_versions.get(order.id, row.version)
        if row.version != expected:
            raise ConcurrentWriteError(
                f"Order {order.id} changed concurrently: expected version "
                f"{expected}, found {row.version}."
            )
        if order.version < expected:
            raise ConcurrentWriteError(
                f"Order {order.id} cannot persist version {order.version} "
                f"over version {expected}."
            )

        values = order_to_values(order)
        for key, value in values.items():
            if key != "id":
                setattr(row, key, value)
        self._session.flush()
        self._seen_versions[order.id] = order.version
