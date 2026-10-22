"""PostgreSQL models owned by Security."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from pytradekit.persistence.database import Base


class SecurityActorModel(Base):
    __tablename__ = "actors"
    __table_args__ = ({"schema": "security"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SecurityRoleModel(Base):
    __tablename__ = "roles"
    __table_args__ = ({"schema": "security"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)


class SecurityRolePermissionModel(Base):
    __tablename__ = "role_permissions"
    __table_args__ = ({"schema": "security"},)

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("security.roles.id", name="fk_security_role_permissions_role_id"),
        primary_key=True,
    )
    permission: Mapped[str] = mapped_column(String(64), primary_key=True)


class SecurityRoleAssignmentModel(Base):
    __tablename__ = "role_assignments"
    __table_args__ = ({"schema": "security"},)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    actor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("security.actors.id", name="fk_security_role_assignments_actor_id"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("security.roles.id", name="fk_security_role_assignments_role_id"),
        nullable=False,
        index=True,
    )
    environment: Mapped[str] = mapped_column(String(16), nullable=False)
    account_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(200))
    operation_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str | None] = mapped_column(String(64))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("security.actors.id", name="fk_security_role_assignments_assigned_by"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
