"""AT-PROJECT_BOUNDARIES-002..004 / design D6: RLS default deny, no stale tenant on pooled connections, append-only tables."""
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from archtwin.common.ids import new_id

pytestmark = pytest.mark.integration


async def tenant(conn, org, project=None):
    await conn.execute(text("SELECT set_config('app.org_id', :o, true), set_config('app.project_id', :p, true)"),
                       {"o": str(org) if org else "", "p": str(project) if project else ""})


@pytest.fixture(scope="module")
async def two_tenants(app_engine, owner_engine):
    orgs = {k: new_id() for k in "AB"}
    projs = {k: new_id() for k in "AB"}
    async with app_engine.begin() as c:
        for k in "AB":
            await c.execute(text("INSERT INTO organizations (id, name, slug) VALUES (:i, :n, :s)"),
                            {"i": orgs[k], "n": f"itest {k}", "s": f"itest-{k}-{orgs[k].hex[-12:]}"})
    for k in "AB":
        async with app_engine.begin() as c:
            await tenant(c, orgs[k])
            await c.execute(text("INSERT INTO projects (id, org_id, slug, title, created_by) VALUES (:i, :o, :s, :t, :i)"),
                            {"i": projs[k], "o": orgs[k], "s": f"p-{k.lower()}", "t": f"Project {k}"})
        async with app_engine.begin() as c:
            await tenant(c, orgs[k], projs[k])
            await c.execute(text("INSERT INTO connectors (id, org_id, project_id, kind, name) VALUES (:i, :o, :p, 'git', :n)"),
                            {"i": new_id(), "o": orgs[k], "p": projs[k], "n": f"conn-{k}"})
            await c.execute(text("""INSERT INTO observations (id, org_id, project_id, origin, subject_kind, subject_key, kind, name, parser_version)
                                    VALUES (:i, :o, :p, 'static', 'node', 'container:x/y', 'container', 'y', 't/1')"""),
                            {"i": new_id(), "o": orgs[k], "p": projs[k]})
    yield orgs, projs
    async with owner_engine.begin() as c:                       # cleanup as owner, explicit purge for append-only rows
        await c.execute(text("SELECT set_config('app.purge', 'on', true)"))
        await c.execute(text("DELETE FROM organizations WHERE id = ANY(:ids)"), {"ids": list(orgs.values())})


async def count(app_engine, sql, org=None, project=None):
    async with app_engine.begin() as c:
        await tenant(c, org, project)
        return (await c.execute(text(sql))).scalar()


async def test_org_rls_hides_other_orgs_projects(app_engine, two_tenants):
    orgs, projs = two_tenants
    assert await count(app_engine, f"SELECT count(*) FROM projects WHERE id = '{projs['B']}'", orgs["A"]) == 0
    assert await count(app_engine, f"SELECT count(*) FROM projects WHERE id = '{projs['A']}'", orgs["A"]) == 1


async def test_unset_tenant_is_default_deny(app_engine, two_tenants):
    assert await count(app_engine, "SELECT count(*) FROM projects") == 0
    assert await count(app_engine, "SELECT count(*) FROM connectors") == 0
    assert await count(app_engine, "SELECT count(*) FROM observations") == 0


async def test_project_rls_hides_sibling_project_in_same_org_context(app_engine, two_tenants):
    orgs, projs = two_tenants
    assert await count(app_engine, "SELECT count(*) FROM connectors", orgs["A"], projs["A"]) == 1
    # project id of B with org A (a forged combination) sees nothing
    assert await count(app_engine, "SELECT count(*) FROM connectors", orgs["A"], projs["B"]) == 0


async def test_cannot_write_into_another_tenant(app_engine, two_tenants):
    orgs, projs = two_tenants
    with pytest.raises(DBAPIError, match="row-level security"):
        async with app_engine.begin() as c:
            await tenant(c, orgs["A"], projs["A"])
            await c.execute(text("INSERT INTO connectors (id, org_id, project_id, kind, name) VALUES (:i, :o, :p, 'git', 'evil')"),
                            {"i": new_id(), "o": orgs["B"], "p": projs["B"]})


async def test_no_stale_tenant_on_pooled_connection(app_engine, two_tenants):
    orgs, projs = two_tenants
    assert await count(app_engine, "SELECT count(*) FROM connectors", orgs["A"], projs["A"]) == 1
    # same pooled connection (pool_size=1), new transaction without SET LOCAL: nothing visible
    async with app_engine.begin() as c:
        assert (await c.execute(text("SELECT count(*) FROM connectors"))).scalar() == 0
        assert (await c.execute(text("SELECT current_setting('app.org_id', true)"))).scalar() in ("", None)


async def test_observations_are_append_only(app_engine, two_tenants):
    orgs, projs = two_tenants
    for sql in ("UPDATE observations SET name = 'x'", "DELETE FROM observations"):
        with pytest.raises(DBAPIError, match="append-only"):
            async with app_engine.begin() as c:
                await tenant(c, orgs["A"], projs["A"])
                await c.execute(text(sql))


async def test_app_role_cannot_modify_audit(app_engine, two_tenants):
    orgs, _ = two_tenants
    with pytest.raises(DBAPIError, match="permission denied|append-only"):
        async with app_engine.begin() as c:
            await tenant(c, orgs["A"])
            await c.execute(text("UPDATE audit_events SET action = 'x'"))
    with pytest.raises(DBAPIError, match="permission denied|append-only"):
        async with app_engine.begin() as c:
            await tenant(c, orgs["A"])
            await c.execute(text("DELETE FROM audit_events"))


async def test_app_role_cannot_bypass_rls_or_alter_schema(app_engine):
    async with app_engine.begin() as c:
        assert (await c.execute(text("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = current_user"))).scalar() is False
    with pytest.raises(DBAPIError):
        async with app_engine.begin() as c:
            await c.execute(text("ALTER TABLE projects DISABLE ROW LEVEL SECURITY"))

_ = uuid
