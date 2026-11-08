"""PostgreSQL catalog connector (read-only transaction, SQLAlchemy `inspect()` reflection — AT-DATA_TOPOLOGY-001).

Only metadata is read (schemas, tables, columns, FKs), never rows. Sensitive column names are classified and flagged so
they are masked in UI/search/AI (AT-DATA_TOPOLOGY-003).
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

from archtwin.common.egress import EgressDenied, check_url
from archtwin.connectors.sdk import ScanResult, TestResult

V = "pg-catalog/1.0"
SENSITIVE = re.compile(r"(pass(word)?|secret|token|ssn|social|iban|card|cvv|email|phone|birth|salary|api_?key|private)", re.IGNORECASE)


def _url(cfg: dict[str, Any], secret: dict[str, Any]) -> URL:
    return URL.create("postgresql+psycopg", username=cfg.get("username"), password=secret.get("password"),
                      host=cfg.get("host"), port=int(cfg.get("port") or 5432), database=cfg.get("database"))


def _check_host(cfg: dict[str, Any]) -> None:
    check_url(f"http://{cfg.get('host')}:{cfg.get('port') or 5432}/")


class PostgresCatalogConnector:
    kind = "postgresql"
    flag = "connector.postgresql"
    manifest = {"name": "PostgreSQL catalog", "origin": "runtime", "scopes": ["CONNECT", "USAGE on schemas (catalog only)"],
                "freshness_sla_s": 86400,
                "config": {"host": "", "port": 5432, "database": "", "username": "", "schemas": ["public"],
                           "system": "system the database belongs to", "service": "container (compose service) that hosts it"},
                "secret": {"password": ""}}

    def _test_sync(self, cfg, secret) -> TestResult:
        eng = create_engine(_url(cfg, secret), pool_pre_ping=True)
        try:
            with eng.connect() as c:
                c.execute(text("SET TRANSACTION READ ONLY"))
                ver = c.execute(text("SHOW server_version")).scalar()
                superuser = c.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar()
                warnings = ["connected as a superuser: use a dedicated read-only role"] if superuser else []
                return TestResult(ok=True, scopes=self.manifest["scopes"], warnings=warnings, details={"server_version": ver})
        finally:
            eng.dispose()

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            _check_host(cfg)
            return await asyncio.to_thread(self._test_sync, cfg, secret)
        except EgressDenied as e:
            return TestResult(ok=False, warnings=[str(e)])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[type(e).__name__ + ": " + str(e).split("\n")[0][:200]])

    def _scan_sync(self, cfg, secret) -> ScanResult:
        r = ScanResult()
        system, service, db = cfg.get("system") or "external", cfg.get("service") or cfg.get("host"), cfg.get("database")
        eng = create_engine(_url(cfg, secret))
        try:
            with eng.connect() as c:
                c.execute(text("SET TRANSACTION READ ONLY"))
                r.revision = str(c.execute(text("SELECT txid_current_snapshot()::text")).scalar())
                insp = inspect(c)
                dbk = f"database:{system}/{service}/{db}"
                r.node("runtime", dbk, "database", str(db), V, attrs={"engine": "postgresql", "host": cfg.get("host")},
                       ref=f"postgresql://{cfg.get('host')}/{db}")
                r.edge("runtime", f"container:{system}/{service}", "contains", dbk, V)
                schemas = cfg.get("schemas") or [s for s in insp.get_schema_names() if not s.startswith("pg_") and s != "information_schema"]
                for sch in schemas:
                    for t in insp.get_table_names(schema=sch):
                        cols = insp.get_columns(t, schema=sch)
                        sens = [col["name"] for col in cols if SENSITIVE.search(col["name"])]
                        tk = f"table:{system}/{service}/{db}/{sch}.{t}"
                        r.node("runtime", tk, "table", f"{sch}.{t}", V, ref=f"postgresql://{cfg.get('host')}/{db}#{sch}.{t}",
                               attrs={"columns": [{"name": col["name"], "type": str(col["type"]),
                                                   "sensitive": col["name"] in sens} for col in cols][:200],
                                      "sensitive_columns": sens}, sensitive=bool(sens))
                        r.edge("runtime", dbk, "contains", tk, V)
                        for fk in insp.get_foreign_keys(t, schema=sch):
                            if fk.get("referred_table"):
                                rk = f"table:{system}/{service}/{db}/{fk.get('referred_schema') or sch}.{fk['referred_table']}"
                                r.edge("runtime", tk, "references", rk, V, attrs={"columns": fk.get("constrained_columns", [])})
        finally:
            eng.dispose()
        r.coverage = {"origin": "runtime", "prefixes": [f"table:{system}/{service}/{db}/", f"database:{system}/{service}/{db}"]}
        r.stats = {"tables": len([o for o in r.observations if o.kind == "table"])}
        return r

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        _check_host(cfg)
        return await asyncio.to_thread(self._scan_sync, cfg, secret)
