"""RFC 9457 problem+json errors."""
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class Problem(HTTPException):
    def __init__(self, status: int, code: str, title: str, detail: str | None = None, *, retryable: bool = False,
                 extra: dict[str, Any] | None = None):
        super().__init__(status_code=status, detail=detail or title)
        self.code, self.title, self.problem_detail, self.retryable, self.extra = code, title, detail, retryable, extra or {}


def problem(status: int, code: str, title: str, detail: str | None = None, **kw) -> Problem:
    return Problem(status, code, title, detail, **kw)


def not_found(what: str = "resource") -> Problem:
    # identical response for "missing" and "not yours" so foreign IDs cannot be probed (AT-PROJECT_BOUNDARIES)
    return problem(404, "AT-NOT-FOUND", "Not found", f"The {what} does not exist or you cannot access it.")


async def problem_handler(request: Request, exc: Problem) -> JSONResponse:
    body = {"type": f"https://archtwin.dev/problems/{exc.code}", "title": exc.title, "status": exc.status_code,
            "code": exc.code, "detail": exc.problem_detail, "instance": str(request.url.path)}
    if exc.retryable:
        body["retryable"] = True
    body.update(exc.extra)
    return JSONResponse(body, status_code=exc.status_code, media_type="application/problem+json")
