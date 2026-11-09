"""Database schema declared in code (tables and columns) — so "what is the DB structure of X?" is answered from code.

Sources (static, deterministic, best-effort text parsing; every table keeps file:line evidence):
  * SQL:        CREATE TABLE [IF NOT EXISTS] [schema.]name ( col type [NOT NULL] [PRIMARY KEY] [REFERENCES t(c)], ... ) and
                ALTER TABLE name ADD [COLUMN] col type — in .sql files (Flyway, Liquibase SQL, init scripts) and in SQL strings
                inside code (Alembic `op.execute("CREATE TABLE ...")`, raw DDL in Python or Java)
  * Alembic:    op.create_table("name", sa.Column("col", sa.Type, ...), ...) and op.add_column("name", sa.Column(...))
  * SQLAlchemy: Table("name", metadata, Column("col", Type, ...)); declarative classes with __tablename__ and
                `col = Column(...)` / `col: Mapped[T] = mapped_column(...)` / `col = db.Column(...)`
  * Django:     class X(models.Model) with `field = models.XxxField(...)` (table <app>_<x> unless Meta.db_table)
Declarations of the same table across files (migration + model) are merged; later columns never erase earlier ones.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

V_SCHEMA = "code-schema/1.0"
SQL_CREATE = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([`\"\[]?[\w.]+[`\"\]]?)\s*\(", re.IGNORECASE)
SQL_ALTER_ADD = re.compile(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([`\"\[]?[\w.]+[`\"\]]?)\s+add\s+(?:column\s+)?(?:if\s+not\s+exists\s+)?"
                           r"([`\"\[]?\w+[`\"\]]?)\s+([\w\[\]()]+)([^,;\n]*)", re.IGNORECASE)
SQL_CONSTRAINT = re.compile(r"^\s*(constraint|primary\s+key|foreign\s+key|unique|check|index|key|exclude)\b", re.IGNORECASE)
CALL_TABLE = re.compile(r"(?:\bop\.create_table|(?<![\w.])(?:sa\.|sqlalchemy\.)?Table)\s*\(\s*['\"]([\w.]+)['\"]")
ADD_COLUMN = re.compile(r"\bop\.add_column\s*\(\s*['\"]([\w.]+)['\"]")
COLUMN_CALL = re.compile(r"(?:sa\.|db\.|sqlalchemy\.)?Column\s*\(\s*['\"](\w+)['\"]\s*,\s*([\w.]+)")
TABLENAME = re.compile(r"__tablename__\s*=\s*['\"]([\w.]+)['\"]")
ORM_COL = re.compile(r"^[ \t]+(\w+)[ \t]*(?::[ \t]*Mapped\[(.+?)\])?[ \t]*=[ \t]*(?:db\.|sa\.|sqlalchemy\.|orm\.)?(?:mapped_column|Column)[ \t]*\(",
                     re.MULTILINE)
DJANGO_MODEL = re.compile(r"^class\s+(\w+)\s*\(([^)]*models\.Model[^)]*)\)\s*:", re.MULTILINE)
DJANGO_FIELD = re.compile(r"^[ \t]+(\w+)[ \t]*=[ \t]*models\.(\w+Field|ForeignKey|OneToOneField|ManyToManyField)[ \t]*\(([^\n]*)", re.MULTILINE)
TYPE_IN_ARGS = re.compile(r"(?:sa\.|db\.|sqlalchemy\.|postgresql\.)?([A-Z][A-Za-z0-9_]*)(?:\(|\b)")
FK_IN_ARGS = re.compile(r"ForeignKey\s*\(\s*['\"]([\w.]+)['\"]")
MAX_TABLES = 600


@dataclass
class Column:
    name: str
    type: str = ""
    nullable: bool | None = None
    primary_key: bool = False
    references: str = ""


@dataclass
class TableDecl:
    name: str
    columns: dict[str, Column] = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)          # {"path", "line", "kind"}

    def add(self, c: Column) -> None:
        cur = self.columns.get(c.name)
        if cur is None:
            self.columns[c.name] = c
            return
        cur.type = cur.type or c.type
        cur.primary_key = cur.primary_key or c.primary_key
        cur.references = cur.references or c.references
        if cur.nullable is None:
            cur.nullable = c.nullable


def _balanced(text: str, start: int) -> str:
    """Text inside the parenthesis that opens at `start` (exclusive), honoring nesting and quotes."""
    depth, i, q = 0, start, ""
    while i < len(text):
        ch = text[i]
        if q:
            if ch == q and text[i - 1] != "\\":
                q = ""
        elif ch in "'\"":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return text[start + 1:start + 20000]


def _split_top(body: str) -> list[str]:
    parts, depth, cur, q = [], 0, [], ""
    for ch in body:
        if q:
            cur.append(ch)
            if ch == q:
                q = ""
            continue
        if ch in "'\"":
            q = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _clean(name: str) -> str:
    return name.strip("`\"[] ").split(".")[-1]


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def parse_sql(text: str) -> list[tuple[str, int, list[Column]]]:
    out = []
    for m in SQL_CREATE.finditer(text):
        body = _balanced(text, m.end() - 1)
        cols = []
        for part in _split_top(body):
            p = " ".join(part.split())
            if not p or SQL_CONSTRAINT.match(p):
                continue
            toks = p.split(" ")
            name = _clean(toks[0])
            if not re.fullmatch(r"\w+", name):
                continue
            typ = toks[1] if len(toks) > 1 else ""
            low = p.lower()
            ref = re.search(r"references\s+([\w.\"`]+)\s*\(\s*([\w\"`]+)", p, re.IGNORECASE)
            cols.append(Column(name, typ.rstrip(","), False if "not null" in low else (None if "primary key" in low else True),
                               "primary key" in low, f"{_clean(ref.group(1))}.{_clean(ref.group(2))}" if ref else ""))
        out.append((_clean(m.group(1)), _line(text, m.start()), cols))
    for m in SQL_ALTER_ADD.finditer(text):
        col, rest = _clean(m.group(2)), m.group(4).lower()
        if col.lower() in ("constraint", "primary", "foreign", "unique", "check", "index"):
            continue
        ref = re.search(r"references\s+([\w.\"`]+)\s*\(\s*([\w\"`]+)", m.group(4), re.IGNORECASE)
        out.append((_clean(m.group(1)), _line(text, m.start()),
                    [Column(col, m.group(3), "not null" not in rest, "primary key" in rest,
                            f"{_clean(ref.group(1))}.{_clean(ref.group(2))}" if ref else "")]))
    return out


def _col_from_args(name: str, args: str) -> Column:
    tm = TYPE_IN_ARGS.search(args)
    typ = tm.group(1) if tm and tm.group(1) not in ("Column", "ForeignKey", "Mapped") else ""
    fk = FK_IN_ARGS.search(args)
    nullable = False if re.search(r"nullable\s*=\s*False", args) else (True if re.search(r"nullable\s*=\s*True", args) else None)
    return Column(name, typ, nullable, bool(re.search(r"primary_key\s*=\s*True", args)), fk.group(1) if fk else "")


def parse_python(text: str) -> list[tuple[str, int, list[Column], str]]:
    out: list[tuple[str, int, list[Column], str]] = []
    for m in CALL_TABLE.finditer(text):
        body = _balanced(text, text.index("(", m.start()))
        cols = []
        for part in _split_top(body):
            cm = COLUMN_CALL.search(part)
            if cm:
                cols.append(_col_from_args(cm.group(1), part[cm.end(1):]))
        out.append((_clean(m.group(1)), _line(text, m.start()), cols, "alembic" if "create_table" in m.group(0) else "sqlalchemy-core"))
    for m in ADD_COLUMN.finditer(text):
        body = _balanced(text, text.index("(", m.start()))
        cm = COLUMN_CALL.search(body)
        if cm:
            out.append((_clean(m.group(1)), _line(text, m.start()), [_col_from_args(cm.group(1), body[cm.end(1):])], "alembic"))
    # declarative ORM: split into class blocks
    for cm in re.finditer(r"^class\s+\w+\s*\([^)]*\)\s*:", text, re.MULTILINE):
        end = re.search(r"^\S", text[cm.end():], re.MULTILINE)
        block = text[cm.start(): cm.end() + (end.start() if end else len(text))]
        tn = TABLENAME.search(block)
        if not tn:
            continue
        cols = []
        for lm in ORM_COL.finditer(block):
            col = _col_from_args(lm.group(1), _balanced(block, lm.end() - 1))
            if not col.type and lm.group(2):
                col.type = lm.group(2).strip()
                if col.nullable is None and ("Optional" in col.type or "| None" in col.type):
                    col.nullable = True
            cols.append(col)
        out.append((_clean(tn.group(1)), _line(text, cm.start()), cols, "orm"))
    return out


def parse_django(text: str, app_label: str) -> list[tuple[str, int, list[Column], str]]:
    out = []
    for m in DJANGO_MODEL.finditer(text):
        end = re.search(r"^\S", text[m.end():], re.MULTILINE)
        block = text[m.start(): m.end() + (end.start() if end else len(text))]
        dbt = re.search(r"db_table\s*=\s*['\"]([\w.]+)['\"]", block)
        table = dbt.group(1) if dbt else f"{app_label}_{m.group(1).lower()}"
        cols = [Column("id", "AutoField", False, True)]
        for fm in DJANGO_FIELD.finditer(block):
            ftype, args = fm.group(2), fm.group(3)
            ref = re.match(r"\s*['\"]?([\w.]+)", args) if ftype in ("ForeignKey", "OneToOneField") else None
            name = fm.group(1) + ("_id" if ftype in ("ForeignKey", "OneToOneField") else "")
            if ftype == "ManyToManyField":
                continue
            cols.append(Column(name, ftype, bool(re.search(r"null\s*=\s*True", args)), bool(re.search(r"primary_key\s*=\s*True", args)),
                               ref.group(1) if ref else ""))
        out.append((table, _line(text, m.start()), cols, "django"))
    return out


def extract(root: Path, files: list[Path], read) -> dict[str, TableDecl]:
    """All tables declared in the repository, merged by name."""
    tables: dict[str, TableDecl] = {}

    def add(name: str, rel: str, line: int, cols: list[Column], kind: str) -> None:
        if not re.fullmatch(r"\w+", name) or (name not in tables and len(tables) >= MAX_TABLES):
            return
        t = tables.setdefault(name, TableDecl(name))
        for c in cols:
            t.add(c)
        t.sources.append({"path": rel, "line": line, "kind": kind})
    for f in files:
        suf = f.suffix.lower()
        if suf not in (".sql", ".py", ".java", ".kt") or f.stat().st_size > 600_000:
            continue
        rel = str(f.relative_to(root))
        if any(p in ("tests", "test", "node_modules") for p in f.relative_to(root).parts):
            continue
        text = read(f)
        low = text.lower()
        if suf == ".sql" or "create table" in low or "alter table" in low:
            if "create table" in low or "alter table" in low:
                for name, line, cols in parse_sql(text):
                    add(name, rel, line, cols, "sql" if suf == ".sql" else "sql-in-code")
            if suf != ".py":
                continue
        if not any(k in text for k in ("create_table", "Table(", "__tablename__", "add_column", "models.Model")):
            continue
        for name, line, cols, kind in parse_python(text):
            add(name, rel, line, cols, kind)
        if "models.Model" in text:
            for name, line, cols, kind in parse_django(text, f.parent.name):
                add(name, rel, line, cols, kind)
    return tables
