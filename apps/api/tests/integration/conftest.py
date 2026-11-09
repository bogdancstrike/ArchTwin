import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine


def _env() -> dict:
    p = Path(__file__).resolve().parents[4] / ".env"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k] = v
    return out


E = _env()
HOST = os.environ.get("ARCHTWIN_TEST_DB_HOST", "localhost:5452")


APP_PW = os.environ.get("ARCHTWIN_APP_DB_PASSWORD") or E.get("ARCHTWIN_APP_DB_PASSWORD")
OWNER_PW = os.environ.get("POSTGRES_PASSWORD") or E.get("POSTGRES_PASSWORD")


@pytest.fixture(scope="session")
def app_engine():
    return create_async_engine(f"postgresql+asyncpg://archtwin_app:{APP_PW}@{HOST}/archtwin", pool_size=1, max_overflow=0)


@pytest.fixture(scope="session")
def owner_engine():
    return create_async_engine(f"postgresql+asyncpg://archtwin:{OWNER_PW}@{HOST}/archtwin")
