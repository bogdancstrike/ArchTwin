"""Answer from the code: DB schema declared in code (SQL, Alembic, SQLAlchemy Core/ORM, Django) and code passages."""
from pathlib import Path

from archtwin.connectors.analyzers import db_schema
from archtwin.connectors.analyzers.common import read, walk
from archtwin.connectors.analyzers.repo import analyze_repository
from archtwin.documents.service import split_code


def _w(root: Path, files: dict[str, str]) -> Path:
    for k, v in files.items():
        (root / k).parent.mkdir(parents=True, exist_ok=True)
        (root / k).write_text(v)
    return root


def test_every_schema_notation(tmp_path):
    root = _w(tmp_path, {
        "db/init.sql": "CREATE TABLE IF NOT EXISTS public.users (\n  id SERIAL PRIMARY KEY,\n  email VARCHAR(255) NOT NULL,\n  CONSTRAINT u UNIQUE(email)\n);\n"
                       "create table orders (id bigint primary key, user_id int references users(id), total numeric(10,2));\n",
        "alembic/versions/0001.py": "def upgrade():\n    op.create_table(\n        'invoices',\n        sa.Column('id', sa.Integer(), primary_key=True),\n"
                                    "        sa.Column('order_id', sa.Integer, sa.ForeignKey('orders.id'), nullable=False),\n    )\n"
                                    "    op.add_column('orders', sa.Column('status', sa.Text(), nullable=True))\n",
        "app/core.py": "audit = Table('audit', metadata, Column('id', BigInteger, primary_key=True), Column('payload', JSONB))\n",
        "app/models.py": "class Item(Base):\n    __tablename__ = 'items'\n\n    id: Mapped[int] = mapped_column(Integer, primary_key=True)\n"
                         "    name: Mapped[str | None] = mapped_column(\n        String(80), nullable=True\n    )\n    tags: Mapped[list[str]] = mapped_column(ARRAY(String))\n"
                         "    order_id = Column(Integer, ForeignKey('orders.id'))\n\n\nclass NotATable:\n    x = 1\n",
        "shop/models.py": "from django.db import models\n\nclass Product(models.Model):\n    title = models.CharField(max_length=10)\n"
                          "    category = models.ForeignKey('Category', on_delete=models.CASCADE)\n    tags = models.ManyToManyField('Tag')\n",
        "tests/test_x.py": "op.create_table('should_not_count', sa.Column('id', sa.Integer))\n"})
    t = db_schema.extract(root, list(walk(root)), read)
    assert set(t) == {"users", "orders", "invoices", "audit", "items", "shop_product"}
    u = t["users"].columns
    assert u["id"].primary_key and u["email"].type.startswith("VARCHAR") and u["email"].nullable is False and "u" not in u
    assert t["orders"].columns["user_id"].references == "users.id" and "status" in t["orders"].columns       # add_column merged
    assert {s["kind"] for s in t["orders"].sources} == {"sql", "alembic"}
    assert t["invoices"].columns["order_id"].references == "orders.id" and t["invoices"].columns["order_id"].nullable is False
    i = t["items"].columns
    assert i["id"].primary_key and i["name"].type == "String" and i["name"].nullable is True and i["order_id"].references == "orders.id"
    assert t["shop_product"].columns["category_id"].type == "ForeignKey" and "tags" not in t["shop_product"].columns


def test_tables_become_elements_and_code_is_indexed(tmp_path):
    root = _w(tmp_path, {"compose.yaml": "services:\n  api:\n    build: .\n", "Dockerfile": "FROM python:3.12\n",
                         "app/models.py": "class Item(Base):\n    __tablename__ = 'items'\n    id = Column(Integer, primary_key=True)\n",
                         "app/routes.py": "def list_items():\n    return []\n", "tests/test_a.py": "def test_x():\n    pass\n"})
    r = analyze_repository(root, "rev", "demo")
    t = next(o for o in r.observations if o.subject_key == "table:demo/code/items")
    assert t.kind == "table" and t.attributes["columns"][0]["name"] == "id" and t.attributes["declared_in"][0]["path"] == "app/models.py"
    assert any(o.subject_key == "container:demo/api|references|table:demo/code/items" for o in r.observations)
    code = {d.path for d in r.documents if "code" in d.tags}
    assert {"app/models.py", "app/routes.py"} <= code and "tests/test_a.py" not in code
    assert all(d.mime == "text/x-code" for d in r.documents if "code" in d.tags)
    assert "table:demo/code/" in r.coverage["prefixes"]
    docs_mode = analyze_repository(root, "rev", "demo", content="docs")
    assert not any("code" in d.tags for d in docs_mode.documents)


def test_split_code_breaks_at_definitions():
    src = "import os\n\n\nclass A:\n" + "    x = 1\n" * 10 + "\n\ndef f():\n" + "    return 1\n" * 10 + "\n" + "y = 2\n" * 200
    parts = split_code(src)
    assert parts[0]["line_start"] == 1 and any(p["heading"].startswith("def f") for p in parts)
    assert all(p["line_end"] - p["line_start"] < 75 for p in parts) and parts[-1]["line_end"] == len(src.splitlines())


def test_code_passages_preserve_exact_line_numbers():
    src = "\n\n# header comment\nimport os\n\n\nclass A:\n    x = '" + "a" * 3000 + "'\n" + "\n".join(f"    v{i} = {i}" for i in range(150)) + "\n\n\ndef f():\n    return 1\n"
    lines = src.splitlines()
    rebuilt: dict[int, str] = {}
    for p in split_code(src):
        for i, ln in enumerate(p["text"].split("\n")):
            rebuilt.setdefault(p["line_start"] + i, ln)
    assert all(rebuilt.get(n) == lines[n - 1] for n in range(1, len(lines) + 1) if lines[n - 1].strip())   # every code line, same number
    assert any(len(p["text"]) > 1800 for p in split_code(src))                                         # long chunks are not truncated


def test_complete_adr_normalization_keeps_author_text():
    from archtwin.intelligence.assistant import normalize_adr
    written = {"title": "Use Kafka", "context": "We need events.", "decision_drivers": ["throughput"], "considered_options": ["Kafka", "RabbitMQ"],
               "decision_outcome": "", "consequences": ""}
    out = normalize_adr({"context": "We need durable events between services.", "decision_drivers": "- throughput\n- replay",
                         "considered_options": [{"name": "Kafka", "pros": ["replay"], "cons": "ops cost"}, "RabbitMQ"],
                         "decision_outcome": "Chosen option: Kafka, because replay."}, written)
    assert out["title"] == "Use Kafka" and out["decision_drivers"] == ["throughput", "replay"]
    assert out["considered_options"][0] == {"name": "Kafka", "pros": ["replay"], "cons": ["ops cost"]}
    assert out["considered_options"][1]["name"] == "RabbitMQ" and out["consequences"] == ""
    assert normalize_adr({}, written)["considered_options"] == [{"name": "Kafka", "pros": [], "cons": []}, {"name": "RabbitMQ", "pros": [], "cons": []}]
