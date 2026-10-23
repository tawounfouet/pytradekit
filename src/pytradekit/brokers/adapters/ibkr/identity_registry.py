"""Conflict-safe runtime registry for IBKR order identities."""

from __future__ import annotations

from .identities import (
    IBKRClientId,
    IBKRIdentityError,
    IBKROrderIdentity,
    IBKROrderReference,
    IBKRPermanentOrderId,
    IBKRSessionOrderId,
)


class IBKROrderIdentityRegistry:
    """Track provider routing identities without making orderId canonical."""

    def __init__(self) -> None:
        self._by_routing_key: dict[tuple[int, int], IBKROrderIdentity] = {}
        self._by_permanent_id: dict[int, IBKROrderIdentity] = {}
        self._by_reference: dict[str, IBKROrderIdentity] = {}

    def register(self, identity: IBKROrderIdentity) -> IBKROrderIdentity:
        """Register an identity while rejecting conflicting economic correlation."""

        if not isinstance(identity, IBKROrderIdentity):
            raise IBKRIdentityError("identity must be an IBKROrderIdentity.")

        existing_route = self._by_routing_key.get(identity.routing_key)
        if existing_route is not None:
            if existing_route.client_reference != identity.client_reference:
                raise IBKRIdentityError(
                    "IBKR routing identity already belongs to a different order observation."
                )
            old_perm = existing_route.permanent_order_id
            new_perm = identity.permanent_order_id
            if old_perm is not None and new_perm is not None and old_perm != new_perm:
                raise IBKRIdentityError(
                    "IBKR routing identity cannot be rebound to another permId."
                )
            if old_perm is not None and new_perm is None:
                identity = existing_route

        reference_key = identity.client_reference.value
        existing_reference = self._by_reference.get(reference_key)
        if existing_reference is not None:
            old_perm = existing_reference.permanent_order_id
            new_perm = identity.permanent_order_id
            if old_perm is not None and new_perm is not None and old_perm != new_perm:
                raise IBKRIdentityError(
                    "IBKR orderRef cannot be associated with conflicting permId values."
                )

        if identity.permanent_order_id is not None:
            permanent_key = identity.permanent_order_id.value
            existing_permanent = self._by_permanent_id.get(permanent_key)
            if (
                existing_permanent is not None
                and existing_permanent.client_reference != identity.client_reference
            ):
                raise IBKRIdentityError(
                    "IBKR permId cannot be associated with conflicting orderRef values."
                )
            self._by_permanent_id[permanent_key] = identity

        self._by_routing_key[identity.routing_key] = identity
        self._by_reference[reference_key] = identity
        return identity

    def bind_permanent_order_id(
        self,
        *,
        client_id: IBKRClientId,
        session_order_id: IBKRSessionOrderId,
        permanent_order_id: IBKRPermanentOrderId,
    ) -> IBKROrderIdentity:
        """Attach a stable permId to an existing session order observation."""

        if not isinstance(client_id, IBKRClientId):
            raise IBKRIdentityError("client_id must be an IBKRClientId.")
        if not isinstance(session_order_id, IBKRSessionOrderId):
            raise IBKRIdentityError("session_order_id must be an IBKRSessionOrderId.")
        if not isinstance(permanent_order_id, IBKRPermanentOrderId):
            raise IBKRIdentityError(
                "permanent_order_id must be an IBKRPermanentOrderId."
            )

        routing_key = (client_id.value, session_order_id.value)
        current = self._by_routing_key.get(routing_key)
        if current is None:
            raise IBKRIdentityError(
                "Cannot bind permId before the IBKR routing identity is registered."
            )
        bound = current.bind_permanent_order_id(permanent_order_id)
        return self.register(bound)

    def find_by_routing_key(
        self,
        *,
        client_id: IBKRClientId,
        session_order_id: IBKRSessionOrderId,
    ) -> IBKROrderIdentity | None:
        """Find an order by clientId plus session-scoped orderId."""

        if not isinstance(client_id, IBKRClientId):
            raise IBKRIdentityError("client_id must be an IBKRClientId.")
        if not isinstance(session_order_id, IBKRSessionOrderId):
            raise IBKRIdentityError("session_order_id must be an IBKRSessionOrderId.")
        return self._by_routing_key.get((client_id.value, session_order_id.value))

    def find_by_permanent_order_id(
        self,
        permanent_order_id: IBKRPermanentOrderId,
    ) -> IBKROrderIdentity | None:
        """Find the latest routing observation for a stable permId."""

        if not isinstance(permanent_order_id, IBKRPermanentOrderId):
            raise IBKRIdentityError(
                "permanent_order_id must be an IBKRPermanentOrderId."
            )
        return self._by_permanent_id.get(permanent_order_id.value)

    def find_by_reference(
        self,
        reference: IBKROrderReference,
    ) -> IBKROrderIdentity | None:
        """Find the latest observation associated with an orderRef."""

        if not isinstance(reference, IBKROrderReference):
            raise IBKRIdentityError("reference must be an IBKROrderReference.")
        return self._by_reference.get(reference.value)

    def __len__(self) -> int:
        return len(self._by_routing_key)
