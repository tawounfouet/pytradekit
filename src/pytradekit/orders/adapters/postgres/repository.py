"""PostgreSQL OrderRepository implementation."""

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pytradekit.orders.adapters.postgres.mapper import order_from_model, order_to_values
from pytradekit.orders.adapters.postgres.models import OrderModel
from pytradekit.orders.domain import (
    ExecutionCertainty,
    Order,
    OrderAlreadyExistsError,
    OrderId,
    OrderNotFoundError,
)
from pytradekit.orders.domain.transitions import TERMINAL_ORDER_STATUSES
from pytradekit.persistence import ConcurrentWriteError


class PostgresOrderRepository:
    """Durable Order aggregate repository with optimistic concurrency."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen_versions: dict[OrderId, int] = {}

    def get(self, order_id: OrderId) -> Order | None:
        row = self._session.get(OrderModel, order_id.value)
        return self._remember(row)

    def get_by_client_order_id(self, client_order_id: str) -> Order | None:
        normalized = _identity(client_order_id, field_name="Client order id")
        row = self._session.execute(
            select(OrderModel).where(OrderModel.client_order_id == normalized)
        ).scalar_one_or_none()
        return self._remember(row)

    def get_by_external_order_id(self, external_order_id: str) -> Order | None:
        normalized = _identity(external_order_id, field_name="External order id")
        row = self._session.execute(
            select(OrderModel).where(OrderModel.external_order_id == normalized)
        ).scalar_one_or_none()
        return self._remember(row)

    def list_reconcilable(self) -> tuple[Order, ...]:
        terminal = tuple(status.value for status in TERMINAL_ORDER_STATUSES)
        statement = (
            select(OrderModel)
            .where(
                or_(
                    OrderModel.status.not_in(terminal),
                    OrderModel.execution_certainty
                    == ExecutionCertainty.UNCERTAIN.value,
                )
            )
            .order_by(OrderModel.created_at, OrderModel.id)
        )
        rows = self._session.execute(statement).scalars().all()
        return tuple(self._remember_required(row) for row in rows)

    def add(self, order: Order) -> None:
        self._session.add(OrderModel(**order_to_values(order)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise OrderAlreadyExistsError(f"Order {order.id} already exists.") from exc
        self._seen_versions[order.id] = order.version

    def save(self, order: Order) -> None:
        statement = (
            select(OrderModel)
            .where(OrderModel.id == order.id.value)
            .with_for_update()
        )
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

    def _remember(self, row: OrderModel | None) -> Order | None:
        if row is None:
            return None
        return self._remember_required(row)

    def _remember_required(self, row: OrderModel) -> Order:
        order_id = OrderId(row.id)
        self._seen_versions[order_id] = row.version
        return order_from_model(row)


def _identity(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()
