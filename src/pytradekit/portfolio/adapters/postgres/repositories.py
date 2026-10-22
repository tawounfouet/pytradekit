"""PostgreSQL repositories owned by Portfolio."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from pytradekit.persistence import ConcurrentWriteError
from pytradekit.portfolio.adapters.postgres.models import (
    AccountModel,
    BalanceModel,
    PositionModel,
    ProcessedFillModel,
)
from pytradekit.portfolio.domain import Account, AccountId, Balance, Position
from pytradekit.shared import Currency, InstrumentId, Money, Price


class PostgresAccountRepository:
    """Durable repository for canonical economic accounts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, account_id: AccountId) -> Account | None:
        row = self._session.get(AccountModel, account_id.value)
        if row is None:
            return None
        return Account(
            id=AccountId(row.id),
            base_currency=Currency(row.base_currency),
            name=row.name,
        )

    def save(self, account: Account) -> None:
        row = self._session.get(AccountModel, account.id.value)
        if row is None:
            self._session.add(
                AccountModel(
                    id=account.id.value,
                    base_currency=account.base_currency.code,
                    name=account.name,
                )
            )
        else:
            row.base_currency = account.base_currency.code
            row.name = account.name
        self._session.flush()

    def list_all(self) -> tuple[Account, ...]:
        rows = self._session.execute(
            select(AccountModel).order_by(AccountModel.id)
        ).scalars().all()
        return tuple(
            Account(
                id=AccountId(row.id),
                base_currency=Currency(row.base_currency),
                name=row.name,
            )
            for row in rows
        )


class PostgresPositionRepository:
    """Durable PositionRepository with row-version concurrency."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen_versions: dict[tuple[AccountId, InstrumentId], int] = {}

    def get(self, account_id: AccountId, instrument_id: InstrumentId) -> Position | None:
        row = self._session.get(PositionModel, (account_id.value, instrument_id.value))
        if row is None:
            return None
        self._seen_versions[(account_id, instrument_id)] = row.version
        return _position_from_model(row)

    def save(self, position: Position) -> None:
        key = (position.account_id, position.instrument_id)
        statement = (
            select(PositionModel)
            .where(
                PositionModel.account_id == position.account_id.value,
                PositionModel.instrument_id == position.instrument_id.value,
            )
            .with_for_update()
        )
        row = self._session.execute(statement).scalar_one_or_none()
        if row is None:
            row = PositionModel(**_position_values(position), version=1)
            self._session.add(row)
            self._session.flush()
            self._seen_versions[key] = 1
            return

        expected = self._seen_versions.get(key, row.version)
        if row.version != expected:
            raise ConcurrentWriteError(
                f"Position {position.account_id}/{position.instrument_id} changed concurrently."
            )
        for name, value in _position_values(position).items():
            setattr(row, name, value)
        row.version += 1
        self._session.flush()
        self._seen_versions[key] = row.version

    def list_for_account(self, account_id: AccountId) -> tuple[Position, ...]:
        statement = (
            select(PositionModel)
            .where(PositionModel.account_id == account_id.value)
            .order_by(PositionModel.instrument_id)
        )
        rows = self._session.execute(statement).scalars().all()
        for row in rows:
            self._seen_versions[(account_id, InstrumentId(row.instrument_id))] = row.version
        return tuple(_position_from_model(row) for row in rows)


class PostgresBalanceRepository:
    """Durable BalanceRepository with row-version concurrency."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._seen_versions: dict[tuple[AccountId, Currency], int] = {}

    def get(self, account_id: AccountId, currency: Currency) -> Balance | None:
        row = self._session.get(BalanceModel, (account_id.value, currency.code))
        if row is None:
            return None
        self._seen_versions[(account_id, currency)] = row.version
        return _balance_from_model(row)

    def save(self, balance: Balance) -> None:
        key = (balance.account_id, balance.currency)
        statement = (
            select(BalanceModel)
            .where(
                BalanceModel.account_id == balance.account_id.value,
                BalanceModel.currency == balance.currency.code,
            )
            .with_for_update()
        )
        row = self._session.execute(statement).scalar_one_or_none()
        if row is None:
            row = BalanceModel(**_balance_values(balance), version=1)
            self._session.add(row)
            self._session.flush()
            self._seen_versions[key] = 1
            return

        expected = self._seen_versions.get(key, row.version)
        if row.version != expected:
            raise ConcurrentWriteError(
                f"Balance {balance.account_id}/{balance.currency.code} changed concurrently."
            )
        for name, value in _balance_values(balance).items():
            setattr(row, name, value)
        row.version += 1
        self._session.flush()
        self._seen_versions[key] = row.version

    def list_for_account(self, account_id: AccountId) -> tuple[Balance, ...]:
        statement = (
            select(BalanceModel)
            .where(BalanceModel.account_id == account_id.value)
            .order_by(BalanceModel.currency)
        )
        rows = self._session.execute(statement).scalars().all()
        for row in rows:
            currency = Currency(row.currency)
            self._seen_versions[(account_id, currency)] = row.version
        return tuple(_balance_from_model(row) for row in rows)


class PostgresProcessedFillRegistry:
    """Durable idempotency registry for portfolio economic effects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def contains(self, fill_key: str) -> bool:
        statement = select(ProcessedFillModel.fill_key).where(
            ProcessedFillModel.fill_key == _normalize_fill_key(fill_key)
        )
        return self._session.execute(statement).first() is not None

    def mark(self, fill_key: str) -> None:
        normalized = _normalize_fill_key(fill_key)
        statement = (
            insert(ProcessedFillModel)
            .values(fill_key=normalized, processed_at=datetime.now(UTC))
            .on_conflict_do_nothing(index_elements=["fill_key"])
        )
        self._session.execute(statement)


def _position_values(position: Position) -> dict[str, object]:
    return {
        "account_id": position.account_id.value,
        "instrument_id": position.instrument_id.value,
        "quantity": position.quantity,
        "average_price": (
            position.average_price.value if position.average_price is not None else None
        ),
        "currency": position.realized_pnl.currency.code,
        "realized_pnl": position.realized_pnl.amount,
        "opened_at": position.opened_at,
        "updated_at": position.updated_at,
    }


def _position_from_model(row: PositionModel) -> Position:
    currency = Currency(row.currency)
    return Position(
        account_id=AccountId(row.account_id),
        instrument_id=InstrumentId(row.instrument_id),
        quantity=row.quantity,
        average_price=(
            Price(row.average_price, currency) if row.average_price is not None else None
        ),
        realized_pnl=Money(row.realized_pnl, currency),
        opened_at=row.opened_at,
        updated_at=row.updated_at,
    )


def _balance_values(balance: Balance) -> dict[str, object]:
    return {
        "account_id": balance.account_id.value,
        "currency": balance.currency.code,
        "cash": balance.cash.amount,
        "available": balance.available.amount if balance.available is not None else None,
        "reserved": balance.reserved.amount if balance.reserved is not None else None,
        "updated_at": balance.updated_at,
    }


def _balance_from_model(row: BalanceModel) -> Balance:
    currency = Currency(row.currency)
    return Balance(
        account_id=AccountId(row.account_id),
        currency=currency,
        cash=Money(row.cash, currency),
        available=Money(row.available, currency) if row.available is not None else None,
        reserved=Money(row.reserved, currency) if row.reserved is not None else None,
        updated_at=row.updated_at,
    )


def _normalize_fill_key(fill_key: str) -> str:
    if not isinstance(fill_key, str) or not fill_key.strip():
        raise ValueError("Processed fill key must be a non-empty string.")
    return fill_key.strip()
