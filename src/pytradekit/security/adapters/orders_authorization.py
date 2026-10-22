"""Security adapter implementing the Orders-owned authorization port."""

from pytradekit.portfolio.domain import AccountId
from pytradekit.security.application import AuthorizeAction
from pytradekit.security.domain import (
    AuthorizationEnvironment,
    AuthorizationScope,
    Permission,
)


class OrdersAuthorizationGate:
    """Map Orders actions to canonical security permissions."""

    def __init__(
        self,
        *,
        authorize_action: AuthorizeAction,
        environment: AuthorizationEnvironment,
    ) -> None:
        self._authorize_action = authorize_action
        self._environment = environment

    def ensure_submit_allowed(self, account_id: AccountId) -> None:
        self._authorize_action.ensure_allowed(
            permission=Permission.SUBMIT_ORDER,
            scope=AuthorizationScope.for_account(
                environment=self._environment,
                account_id=str(account_id),
                operation=Permission.SUBMIT_ORDER,
            ),
        )

    def ensure_cancel_allowed(self, account_id: AccountId) -> None:
        self._authorize_action.ensure_allowed(
            permission=Permission.CANCEL_ORDER,
            scope=AuthorizationScope.for_account(
                environment=self._environment,
                account_id=str(account_id),
                operation=Permission.CANCEL_ORDER,
            ),
        )
