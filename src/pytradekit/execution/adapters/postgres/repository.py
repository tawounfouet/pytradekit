"""PostgreSQL FillRepository implementation."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pytradekit.execution.adapters.postgres.mapper import fill_from_model, fill_to_values
from pytradekit.execution.adapters.postgres.models import FillModel
from pytradekit.execution.domain import Fill, FillId
from pytradekit.orders.domain import OrderId
from pytradekit.persistence import DuplicatePersistenceRecordError


class PostgresFillRepository:
    """Durable immutable fill repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, fill_id: FillId) -> Fill | None:
        row = self._session.get(FillModel, fill_id.value)
        return fill_from_model(row) if row is not None else None

    def add(self, fill: Fill) -> None:
        self._session.add(FillModel(**fill_to_values(fill)))
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise DuplicatePersistenceRecordError(
                f"Fill {fill.deduplication_key} already exists."
            ) from exc

    def list_for_order(self, order_id: OrderId) -> tuple[Fill, ...]:
        statement = (
            select(FillModel)
            .where(FillModel.order_id == order_id.value)
            .order_by(FillModel.occurred_at, FillModel.id)
        )
        rows = self._session.execute(statement).scalars().all()
        return tuple(fill_from_model(row) for row in rows)

    def contains_external(self, external_fill_id: str) -> bool:
        if not isinstance(external_fill_id, str) or not external_fill_id.strip():
            raise ValueError("External fill id must be a non-empty string.")
        statement = select(FillModel.id).where(
            FillModel.external_fill_id == external_fill_id.strip()
        )
        return self._session.execute(statement).first() is not None
