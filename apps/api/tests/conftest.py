import base64
import os
import uuid
from datetime import UTC, datetime

import pytest

os.environ.setdefault("ARCHTWIN_KEK", base64.b64encode(b"k" * 32).decode())
os.environ.setdefault("ARCHTWIN_LLM_MODE", "fake")


def obs(key, kind, *, subject="node", origin="static", attrs=None, conf=1.0, name=None, connector=None):
    return {"id": uuid.uuid4(), "connector_id": connector, "origin": origin, "subject_kind": subject, "subject_key": key, "kind": kind,
            "name": name or key.rsplit("/", 1)[-1], "attributes": attrs or {}, "source_ref": "compose.yaml", "source_revision": "abc",
            "evidence": {"path": "compose.yaml", "line_start": 1}, "observed_at": datetime.now(UTC), "parser_version": "t/1",
            "confidence": conf, "sensitive": False}


def edge(src, rel, dst, **kw):
    return obs(f"{src}|{rel}|{dst}", rel, subject="edge", attrs={"source": src, "target": dst, **kw.pop("attrs", {})}, **kw)


@pytest.fixture
def make_obs():
    return obs


@pytest.fixture
def make_edge():
    return edge
