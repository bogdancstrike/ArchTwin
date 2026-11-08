"""FastAPI application: the `api` entrypoint of the modular monolith (same image as the worker, ADR-0001)."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from archtwin.api.routes import r as v1
from archtwin.common import authz
from archtwin.common.db import dispose, engine
from archtwin.common.errors import Problem, problem_handler
from archtwin.common.logging import configure, log
from archtwin.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure(settings().log_level)
    log.info("api_start", llm_mode=settings().llm_mode)
    yield
    await dispose()


app = FastAPI(title="ArchTwin API", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json",
              description="Living digital twin of your software architecture. All endpoints require an OIDC bearer token.")
app.add_exception_handler(Problem, problem_handler)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse({"type": "https://archtwin.dev/problems/AT-VALIDATION", "title": "Invalid request", "status": 422,
                         "code": "AT-VALIDATION", "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()][:20]},
                        status_code=422, media_type="application/problem+json")


@app.middleware("http")
async def trace_mw(request: Request, call_next):
    tid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.trace_id = tid
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = tid
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.get("/health/live", include_in_schema=False)
async def live():
    return {"ok": True}


@app.get("/health/ready", include_in_schema=False)
async def ready():
    checks = {}
    try:
        async with engine().connect() as c:
            await c.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:  # noqa: BLE001
        checks["postgres"] = False
    checks["cerbos"] = await authz.healthy()
    ok = all(checks.values())
    return JSONResponse({"ok": ok, "checks": checks}, status_code=200 if ok else 503)


app.include_router(v1)
