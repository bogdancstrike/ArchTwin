"""Idempotency-Key support for POST commands (stored responses, 24 h TTL) — design D13."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import text

from archtwin.common.db import Principal, unscoped
from archtwin.common.errors import problem


async def idempotent(request: Request, p: Principal, body: Any, compute: Callable[[], Awaitable[Any]], status: int = 201):
    key = request.headers.get("idempotency-key")
    if not key:
        return JSONResponse(jsonable_encoder(await compute()), status_code=status)
    rh = hashlib.sha256(json.dumps(jsonable_encoder(body), sort_keys=True).encode()).hexdigest()
    async with unscoped() as conn:
        await conn.execute(text("DELETE FROM idempotency_keys WHERE created_at < now() - interval '24 hours'"))
        prev = (await conn.execute(text("SELECT request_hash, status_code, response FROM idempotency_keys WHERE user_id=:u AND key=:k"),
                                   {"u": p.user_id, "k": key})).first()
    if prev:
        if prev.request_hash != rh:
            raise problem(422, "AT-IDEMPOTENCY-001", "Idempotency key reused with a different request")
        return JSONResponse(prev.response, status_code=prev.status_code, headers={"Idempotent-Replayed": "true"})
    result = jsonable_encoder(await compute())
    async with unscoped() as conn:
        await conn.execute(text("""INSERT INTO idempotency_keys (user_id, key, method, path, request_hash, status_code, response)
                                   VALUES (:u, :k, :m, :p, :h, :s, CAST(:r AS jsonb)) ON CONFLICT DO NOTHING"""),
                           {"u": p.user_id, "k": key, "m": request.method, "p": request.url.path, "h": rh, "s": status,
                            "r": json.dumps(result)})
    return JSONResponse(result, status_code=status)
