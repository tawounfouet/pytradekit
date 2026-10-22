"""Deterministic authorization scope semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pytradekit.security.domain.permission import Permission
from pytradekit.shared import DomainValidationError


class AuthorizationEnvironment(StrEnum):
    """Environments governed by milestone 0.7."""

    BACKTEST = "BACKTEST"
    PAPER = "PAPER"


class AccountScopeKind(StrEnum):
    """Typed account scope."""

    ACCOUNT = "ACCOUNT"
    ALL_ACCOUNTS = "ALL_ACCOUNTS"


class OperationScopeKind(StrEnum):
    """Typed operation scope."""

    OPERATION = "OPERATION"
    ALL_OPERATIONS = "ALL_OPERATIONS"


@dataclass(frozen=True, slots=True)
class AuthorizationScope:
    """Scope constraining an assignment or requested action."""

    environment: AuthorizationEnvironment
    account_scope: AccountScopeKind
    operation_scope: OperationScopeKind
    account_id: str | None = None
    operation: Permission | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.environment, AuthorizationEnvironment):
            raise DomainValidationError("AuthorizationScope environment is invalid.")
        if not isinstance(self.account_scope, AccountScopeKind):
            raise DomainValidationError("AuthorizationScope account_scope is invalid.")
        if not isinstance(self.operation_scope, OperationScopeKind):
            raise DomainValidationError("AuthorizationScope operation_scope is invalid.")
        if self.account_scope is AccountScopeKind.ACCOUNT:
            if not isinstance(self.account_id, str) or not self.account_id.strip():
                raise DomainValidationError("ACCOUNT scope requires a non-empty account_id.")
            object.__setattr__(self, "account_id", self.account_id.strip())
        elif self.account_id is not None:
            raise DomainValidationError("ALL_ACCOUNTS must not define account_id.")
        if self.operation_scope is OperationScopeKind.OPERATION:
            if not isinstance(self.operation, Permission):
                raise DomainValidationError("OPERATION scope requires a Permission.")
        elif self.operation is not None:
            raise DomainValidationError("ALL_OPERATIONS must not define operation.")

    @classmethod
    def for_account(
        cls,
        *,
        environment: AuthorizationEnvironment,
        account_id: str,
        operation: Permission | None = None,
    ) -> Self:
        return cls(
            environment=environment,
            account_scope=AccountScopeKind.ACCOUNT,
            account_id=account_id,
            operation_scope=(
                OperationScopeKind.OPERATION
                if operation is not None
                else OperationScopeKind.ALL_OPERATIONS
            ),
            operation=operation,
        )

    @classmethod
    def all_accounts(
        cls,
        *,
        environment: AuthorizationEnvironment,
        operation: Permission | None = None,
    ) -> Self:
        return cls(
            environment=environment,
            account_scope=AccountScopeKind.ALL_ACCOUNTS,
            operation_scope=(
                OperationScopeKind.OPERATION
                if operation is not None
                else OperationScopeKind.ALL_OPERATIONS
            ),
            operation=operation,
        )

    def covers(self, requested: AuthorizationScope) -> bool:
        """Return whether this assignment scope covers a requested scope."""
        if self.environment is not requested.environment:
            return False
        if self.account_scope is AccountScopeKind.ACCOUNT:
            if requested.account_scope is not AccountScopeKind.ACCOUNT:
                return False
            if self.account_id != requested.account_id:
                return False
        if self.operation_scope is OperationScopeKind.OPERATION:
            if requested.operation_scope is not OperationScopeKind.OPERATION:
                return False
            if self.operation is not requested.operation:
                return False
        return True
