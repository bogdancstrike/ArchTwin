"""Async engine, shared metadata and the tenant-scoped unit of work.

Every transaction that touches tenant data runs `set_config('app.org_id'/'app.project_id', ..., is_local=true)` first,
so pooled connections can never carry a stale tenant into the next transaction (design D6). Row-level security policies
read these settings; when unset they evaluate to NULL and deny (default deny).
"""
from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from archtwin.config import settings

metadata = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"})

_engine: AsyncEngine | None = None


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings().database_url, pool_size=10, max_overflow=20, pool_pre_ping=True)
    return _engine


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    subject: str
    username: str
    display_name: str
    org_id: uuid.UUID
    org_role: str                                  # org_owner | org_admin | member
    project_roles: dict[str, str] = field(default_factory=dict)   # project_id -> role
    realm_roles: frozenset[str] = frozenset()

    VIEW = {"project_owner", "architect", "tech_lead", "contributor", "reviewer", "viewer"}
    EDIT = {"project_owner", "architect", "tech_lead", "contributor"}
    MANAGE = {"project_owner"}
    APPROVE = {"project_owner", "architect", "reviewer"}

    def ids(self, roles: set[str]) -> list[str]:
        return sorted(pid for pid, r in self.project_roles.items() if r in roles)

    def cerbos(self) -> dict[str, Any]:
        return {"id": str(self.user_id), "roles": ["user"], "attr": {
            "org_id": str(self.org_id), "org_role": self.org_role, "username": self.username,
            "viewer_project_ids": self.ids(self.VIEW), "editor_project_ids": self.ids(self.EDIT),
            "manager_project_ids": self.ids(self.MANAGE), "approver_project_ids": self.ids(self.APPROVE)}}

    @property
    def is_org_admin(self) -> bool:
        return self.org_role in ("org_owner", "org_admin")


@dataclass(frozen=True)
class RequestContext:
    """Created once per request/job; repositories and services require it (design D5)."""
    principal: Principal | None
    org_id: uuid.UUID
    project_id: uuid.UUID | None = None
    trace_id: str = ""
    system: bool = False                            # worker/system jobs (still tenant-scoped)

    @property
    def actor_id(self) -> uuid.UUID | None:
        return self.principal.user_id if self.principal else None

    @property
    def actor_name(self) -> str:
        return self.principal.username if self.principal else "system"

    def for_project(self, project_id: uuid.UUID) -> RequestContext:
        return RequestContext(self.principal, self.org_id, project_id, self.trace_id, self.system)


async def set_tenant(conn: AsyncConnection, org_id: uuid.UUID | None, project_id: uuid.UUID | None) -> None:
    await conn.execute(text("SELECT set_config('app.org_id', :o, true), set_config('app.project_id', :p, true)"),
                       {"o": str(org_id) if org_id else "", "p": str(project_id) if project_id else ""})


@contextlib.asynccontextmanager
async def uow(ctx: RequestContext) -> AsyncIterator[AsyncConnection]:
    """One transaction with the tenant set. Commit on success, rollback on error."""
    async with engine().begin() as conn:
        await set_tenant(conn, ctx.org_id, ctx.project_id)
        yield conn


@contextlib.asynccontextmanager
async def unscoped() -> AsyncIterator[AsyncConnection]:
    """Transaction WITHOUT tenant: only for non-tenant tables (users, orgs, memberships, flags, outbox)."""
    async with engine().begin() as conn:
        await set_tenant(conn, None, None)
        yield conn


def row(r) -> dict[str, Any] | None:
    return dict(r._mapping) if r is not None else None


def rows(rs) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in rs]
