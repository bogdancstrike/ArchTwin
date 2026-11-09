"""Relational catalog connectors (read-only, SQLAlchemy `inspect()` reflection — AT-DATA_TOPOLOGY-001).

One reflection path for every SQLAlchemy dialect (TECHNOLOGIES.md: no custom catalog SQL per engine). Only metadata is read
(schemas, tables, columns, FKs), never rows, inside a READ ONLY transaction. Sensitive column names are classified and
flagged so they are masked in UI/search/AI (AT-DATA_TOPOLOGY-003).

Keys: `database:{system}/{service}/{db}` and `table:{system}/{service}/{db}/{schema}.{table}` — `service` is the compose
service hosting the engine, so catalog evidence attaches to the same container the code analyzer and Docker runtime see.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Connection

from archtwin.common.egress import EgressDenied, check_url
from archtwin.connectors.sdk import ScanResult, TestResult

SENSITIVE = re.compile(r"(pass(word)?|secret|token|ssn|social|iban|card|cvv|email|phone|birth|salary|api_?key|private)", re.IGNORECASE)
MAX_TABLES = 5000


class SqlCatalogConnector:
    kind = ""
    flag = ""
    engine_name = ""
    driver = ""
    default_port = 0
    parser = ""
    system_schemas: set[str] = set()
    manifest: dict[str, Any] = {}

    # ---- dialect hooks
    def _url(self, cfg: dict[str, Any], secret: dict[str, Any]) -> URL:
        return URL.create(self.driver, username=cfg.get("username"), password=secret.get("password"), host=cfg.get("host"),
                          port=int(cfg.get("port") or self.default_port), database=cfg.get("database"))

    def _begin_read_only(self, c: Connection) -> None:
        c.execute(text("SET TRANSACTION READ ONLY"))

    def _version(self, c: Connection) -> str:
        return str(c.execute(text("SELECT version()")).scalar())

    def _privilege_warnings(self, c: Connection) -> list[str]:
        return []

    def _revision(self, c: Connection) -> str:
        return ""

    def _default_schemas(self, insp, cfg: dict[str, Any]) -> list[str]:
        return [s for s in insp.get_schema_names() if s not in self.system_schemas and not s.startswith("pg_")]

    # ---- shared
    def _check_host(self, cfg: dict[str, Any]) -> None:
        check_url(f"http://{cfg.get('host')}:{cfg.get('port') or self.default_port}/")

    def _test_sync(self, cfg, secret) -> TestResult:
        eng = create_engine(self._url(cfg, secret), pool_pre_ping=True)
        try:
            with eng.connect() as c:
                self._begin_read_only(c)
                ver = self._version(c)
                return TestResult(ok=True, scopes=self.manifest["scopes"], warnings=self._privilege_warnings(c),
                                  details={"server_version": ver})
        finally:
            eng.dispose()

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            self._check_host(cfg)
            return await asyncio.to_thread(self._test_sync, cfg, secret)
        except EgressDenied as e:
            return TestResult(ok=False, warnings=[str(e)])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[type(e).__name__ + ": " + str(e).split("\n")[0][:200]])

    def _scan_sync(self, cfg, secret) -> ScanResult:
        r = ScanResult()
        system, service, db = cfg.get("system") or "external", cfg.get("service") or cfg.get("host"), cfg.get("database")
        host = cfg.get("host")
        eng = create_engine(self._url(cfg, secret))
        n_tables = 0
        try:
            with eng.connect() as c:
                self._begin_read_only(c)
                r.revision = self._revision(c)
                insp = inspect(c)
                dbk = f"database:{system}/{service}/{db}"
                r.node("runtime", dbk, "database", str(db), self.parser, attrs={"engine": self.engine_name, "host": host,
                                                                                "server_version": self._version(c)[:80]},
                       ref=f"{self.kind}://{host}/{db}")
                r.edge("runtime", f"container:{system}/{service}", "contains", dbk, self.parser)
                schemas = cfg.get("schemas") or self._default_schemas(insp, cfg)
                for sch in schemas:
                    for t in insp.get_table_names(schema=sch):
                        n_tables += 1
                        if n_tables > MAX_TABLES:
                            r.complete = False
                            r.warnings.append(f"stopped after {MAX_TABLES} tables: unseen tables stay UNKNOWN (not deleted)")
                            break
                        cols = insp.get_columns(t, schema=sch)
                        sens = [col["name"] for col in cols if SENSITIVE.search(col["name"])]
                        label = f"{sch}.{t}" if sch else t
                        tk = f"table:{system}/{service}/{db}/{label}"
                        r.node("runtime", tk, "table", label, self.parser, ref=f"{self.kind}://{host}/{db}#{label}",
                               attrs={"columns": [{"name": col["name"], "type": str(col["type"]), "nullable": bool(col.get("nullable", True)),
                                                   "sensitive": col["name"] in sens} for col in cols][:200],
                                      "primary_key": (insp.get_pk_constraint(t, schema=sch) or {}).get("constrained_columns", []),
                                      "sensitive_columns": sens}, sensitive=bool(sens))
                        r.edge("runtime", dbk, "contains", tk, self.parser)
                        for fk in insp.get_foreign_keys(t, schema=sch):
                            if fk.get("referred_table"):
                                rs = fk.get("referred_schema") or sch
                                rk = f"table:{system}/{service}/{db}/{rs}.{fk['referred_table']}" if rs else f"table:{system}/{service}/{db}/{fk['referred_table']}"
                                r.edge("runtime", tk, "references", rk, self.parser, attrs={"columns": fk.get("constrained_columns", [])})
                    if not r.complete:
                        break
        finally:
            eng.dispose()
        r.coverage = {"origin": "runtime", "prefixes": [f"table:{system}/{service}/{db}/", f"database:{system}/{service}/{db}"]}
        r.stats = {"tables": min(n_tables, MAX_TABLES), "schemas": len(schemas)}
        return r

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        self._check_host(cfg)
        return await asyncio.to_thread(self._scan_sync, cfg, secret)


_COMMON_CFG = {"host": "", "database": "", "username": "", "system": "system the database belongs to",
               "service": "container (compose service) that hosts it"}


class PostgresCatalogConnector(SqlCatalogConnector):
    kind, flag, engine_name, driver, default_port, parser = "postgresql", "connector.postgresql", "postgresql", "postgresql+psycopg", 5432, "pg-catalog/1.1"
    system_schemas = {"information_schema"}
    manifest = {"name": "PostgreSQL catalog", "category": "data", "origin": "runtime", "scopes": ["CONNECT", "USAGE on schemas (catalog only)"],
                "freshness_sla_s": 86400, "config": {**_COMMON_CFG, "port": 5432, "schemas": ["public"]}, "secret": {"password": ""}}

    def _version(self, c: Connection) -> str:
        return str(c.execute(text("SHOW server_version")).scalar())

    def _privilege_warnings(self, c: Connection) -> list[str]:
        superuser = c.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar()
        return ["connected as a superuser: use a dedicated read-only role"] if superuser else []

    def _revision(self, c: Connection) -> str:
        return str(c.execute(text("SELECT txid_current_snapshot()::text")).scalar())


class MySqlCatalogConnector(SqlCatalogConnector):
    kind, flag, engine_name, driver, default_port, parser = "mysql", "connector.mysql", "mysql", "mysql+pymysql", 3306, "mysql-catalog/1.0"
    system_schemas = {"information_schema", "mysql", "performance_schema", "sys"}
    manifest = {"name": "MySQL / MariaDB catalog", "category": "data", "origin": "runtime",
                "scopes": ["REFERENCES (metadata visibility) on the database — no SELECT needed"],
                "freshness_sla_s": 86400, "config": {**_COMMON_CFG, "port": 3306}, "secret": {"password": ""}}

    def _begin_read_only(self, c: Connection) -> None:
        c.execute(text("SET SESSION TRANSACTION READ ONLY"))

    def _default_schemas(self, insp, cfg: dict[str, Any]) -> list[str]:
        return [cfg["database"]] if cfg.get("database") else super()._default_schemas(insp, cfg)

    def _privilege_warnings(self, c: Connection) -> list[str]:
        grants = " ".join(str(g[0]) for g in c.execute(text("SHOW GRANTS")).all()).upper()
        w = []
        if "ALL PRIVILEGES" in grants or "SUPER" in grants:
            w.append("account has ALL PRIVILEGES/SUPER: use a dedicated metadata-only account")
        for p in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"):
            if re.search(rf"\b{p}\b", grants):
                w.append(f"excess privilege: {p}")
        return w
