"""archtwin CLI: `seed` (idempotent demo data), `audit verify|export`."""
from __future__ import annotations

import asyncio
import json
import sys
import uuid

from sqlalchemy import select

from archtwin.common.db import RequestContext, rows, unscoped, uow
from archtwin.common.ids import new_id
from archtwin.common.schema import audit_events, organizations
from archtwin.config import settings
from archtwin.flags import service as flags
from archtwin.iam.service import ensure_default_org

PILOT_FLAGS = [  # the demo org is a pilot: modules whose phase is implemented are enabled for it (docs/feature-flags)
    "module.llm-gateway", "module.connector-platform", "module.source-code-discovery", "module.runtime-discovery",
    "module.data-topology", "module.document-parsing", "module.normalization-freshness", "module.architecture-graph",
    "module.diagram-studio", "module.documentation-engine", "module.adr-workflow", "module.drift-engine",
    "module.continuous-watchers", "module.drift-triage", "module.architecture-notifications", "module.architecture-assistant",
    "module.integration-designer", "module.work-connectors", "connector.git", "connector.gitlab", "connector.taiga", "connector.docker", "connector.postgresql", "connector.http_openapi",
    "connector.file_upload", "connector.github", "connector.mysql", "connector.kafka", "connector.opentelemetry",
    "ai.answers", "ai.adr_drafting", "ai.integration_design", "ai.general_chat", "ai.architecture_draft", "ai.text_extend", "connectors.full_reconciliation", "connectors.webhooks",
]


async def seed() -> None:
    async with unscoped() as conn:
        oid = await ensure_default_org(conn)
    for k in PILOT_FLAGS:
        await flags.set_override(k, "org", str(oid), True, reason="pilot org (seed)")
    print(f"seeded org {oid} with {len(PILOT_FLAGS)} pilot flags")


async def audit_cmd(cmd: str, org: str | None) -> None:
    from archtwin.audit.service import verify_events
    async with unscoped() as conn:
        orgs = [r.id for r in (await conn.execute(select(organizations.c.id))).all()] if not org else [uuid.UUID(org)]
    ok = True
    for o in orgs:
        async with uow(RequestContext(None, o)) as conn:
            evs = rows(await conn.execute(select(audit_events).where(audit_events.c.org_id == o).order_by(audit_events.c.seq)))
        if cmd == "export":
            for e in evs:
                print(json.dumps(e, default=str))
        else:
            res = verify_events(evs)
            ok &= res["ok"]
            print(json.dumps({"org_id": str(o), **res}))
    sys.exit(0 if ok else 2)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "seed":
        asyncio.run(seed())
    elif args[0] == "audit":
        asyncio.run(audit_cmd(args[1] if len(args) > 1 else "verify", args[2] if len(args) > 2 else None))
    else:
        print("usage: python -m archtwin.cli [seed | audit verify|export [org_id]]")
        sys.exit(1)

_ = (new_id, settings)

if __name__ == "__main__":
    main()
