"""Authorization scope mapping for safety governance actions."""

from pytradekit.safety.domain import KillSwitch, KillSwitchScope, RiskOverrideScope
from pytradekit.security.domain import (
    AuthorizationEnvironment,
    AuthorizationScope,
    Permission,
)


def kill_switch_authorization_scope(
    *,
    environment: AuthorizationEnvironment,
    permission: Permission,
    switch: KillSwitch | None = None,
    scope: KillSwitchScope | None = None,
    scope_id: str | None = None,
) -> AuthorizationScope:
    effective_scope = switch.scope if switch is not None else scope
    effective_scope_id = switch.scope_id if switch is not None else scope_id
    if effective_scope is KillSwitchScope.ACCOUNT:
        if effective_scope_id is None:
            raise ValueError("ACCOUNT KillSwitch requires scope_id.")
        return AuthorizationScope.for_account(
            environment=environment,
            account_id=effective_scope_id,
            operation=permission,
        )
    return AuthorizationScope.all_accounts(
        environment=environment,
        operation=permission,
    )


def risk_override_authorization_scope(
    *,
    environment: AuthorizationEnvironment,
    permission: Permission,
    override_scope: RiskOverrideScope,
) -> AuthorizationScope:
    return AuthorizationScope.for_account(
        environment=environment,
        account_id=override_scope.account_id,
        operation=permission,
    )
