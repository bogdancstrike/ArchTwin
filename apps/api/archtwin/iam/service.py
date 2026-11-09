"""Identity → Principal. Keycloak proves identity; memberships in PostgreSQL are authoritative (design D4)."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from archtwin.common.auth import Identity
from archtwin.common.db import Principal, set_tenant, unscoped
from archtwin.common.errors import problem
from archtwin.common.ids import new_id
from archtwin.common.schema import org_members, organizations, project_members, users
from archtwin.config import settings


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "item"


LEGACY_DEFAULT_ORG_SLUGS = ("demo-organization",)       # earlier default name; renamed in place (id and slug kept)


async def ensure_default_org(conn) -> uuid.UUID:
    name = settings().default_org_name
    slug = slugify(name)
    r = (await conn.execute(select(organizations.c.id).where(organizations.c.slug == slug))).first()
    if r:
        return r.id
    legacy = (await conn.execute(select(organizations.c.id, organizations.c.name)
                                 .where(organizations.c.slug.in_(LEGACY_DEFAULT_ORG_SLUGS)).limit(1))).first()
    if legacy:
        if legacy.name != name:
            await conn.execute(organizations.update().where(organizations.c.id == legacy.id).values(name=name))
        return legacy.id
    oid = new_id()
    await conn.execute(pg_insert(organizations).values(id=oid, name=name, slug=slug).on_conflict_do_nothing())
    return (await conn.execute(select(organizations.c.id).where(organizations.c.slug == slug))).first().id


async def upsert_user(conn, ident: Identity) -> uuid.UUID:
    stmt = pg_insert(users).values(id=new_id(), subject=ident.subject, username=ident.username, email=ident.email,
                                   display_name=ident.display_name, realm_roles=sorted(ident.realm_roles))
    stmt = stmt.on_conflict_do_update(index_elements=["subject"], set_={
        "username": ident.username, "email": ident.email, "display_name": ident.display_name,
        "realm_roles": sorted(ident.realm_roles), "last_seen_at": func.now()}).returning(users.c.id)
    return (await conn.execute(stmt)).scalar_one()


async def first_login_membership(conn, user_id: uuid.UUID, ident: Identity) -> None:
    """Users with no org get onboarded: platform admins own the default org, others join it as members.
    The `mallory` demo user is placed in a separate org so isolation can be demonstrated end to end."""
    has = (await conn.execute(select(func.count()).select_from(org_members).where(org_members.c.user_id == user_id))).scalar()
    if has:
        return
    if ident.username == "mallory":
        oid = new_id()
        await conn.execute(pg_insert(organizations).values(id=oid, name="Outsider Org", slug="outsider-org").on_conflict_do_nothing())
        oid = (await conn.execute(select(organizations.c.id).where(organizations.c.slug == "outsider-org"))).scalar_one()
        await conn.execute(pg_insert(org_members).values(org_id=oid, user_id=user_id, role="org_owner").on_conflict_do_nothing())
        return
    oid = await ensure_default_org(conn)
    role = "org_owner" if "platform_admin" in ident.realm_roles else "member"
    await conn.execute(pg_insert(org_members).values(org_id=oid, user_id=user_id, role=role).on_conflict_do_nothing())


async def load_principal(ident: Identity, requested_org: str | None) -> Principal:
    async with unscoped() as conn:
        uid = await upsert_user(conn, ident)
        await first_login_membership(conn, uid, ident)
        mems = (await conn.execute(select(org_members.c.org_id, org_members.c.role, organizations.c.created_at)
                                   .join(organizations, organizations.c.id == org_members.c.org_id)
                                   .where(org_members.c.user_id == uid).order_by(organizations.c.created_at))).all()
        if not mems:
            raise problem(403, "AT-IAM-001", "No organization", "You are not a member of any organization.")
        chosen = mems[0]
        if requested_org:
            # a client-supplied org is only a *selection* among the caller's own memberships, never an assertion
            match = [m for m in mems if str(m.org_id) == requested_org]
            if not match:
                raise problem(404, "AT-NOT-FOUND", "Not found", "The organization does not exist or you cannot access it.")
            chosen = match[0]
        await set_tenant(conn, chosen.org_id, None)
        pr = (await conn.execute(select(project_members.c.project_id, project_members.c.role)
                                 .where(project_members.c.user_id == uid))).all()
    return Principal(user_id=uid, subject=ident.subject, username=ident.username, display_name=ident.display_name,
                     org_id=chosen.org_id, org_role=chosen.role, project_roles={str(p.project_id): p.role for p in pr},
                     realm_roles=ident.realm_roles)


async def my_orgs(user_id: uuid.UUID) -> list[dict[str, Any]]:
    async with unscoped() as conn:
        rs = await conn.execute(select(organizations.c.id, organizations.c.name, organizations.c.slug, org_members.c.role)
                                .join(org_members, org_members.c.org_id == organizations.c.id).where(org_members.c.user_id == user_id))
        return [dict(r._mapping) for r in rs]


async def get_preferences(user_id: uuid.UUID) -> dict[str, Any]:
    async with unscoped() as conn:
        return (await conn.execute(select(users.c.preferences).where(users.c.id == user_id))).scalar_one() or {}


async def set_preferences(user_id: uuid.UUID, prefs: dict[str, Any]) -> dict[str, Any]:
    async with unscoped() as conn:
        cur = (await conn.execute(select(users.c.preferences).where(users.c.id == user_id))).scalar_one() or {}
        cur.update(prefs)
        await conn.execute(users.update().where(users.c.id == user_id).values(preferences=cur))
    return cur


async def org_users(org_id: uuid.UUID) -> list[dict[str, Any]]:
    async with unscoped() as conn:
        rs = await conn.execute(select(users.c.id, users.c.username, users.c.display_name, users.c.email, org_members.c.role)
                                .join(org_members, org_members.c.user_id == users.c.id).where(org_members.c.org_id == org_id)
                                .order_by(users.c.username))
        return [dict(r._mapping) for r in rs]
