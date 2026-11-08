"""structlog JSON logging with secret redaction (AT-IDENTITY_POLICY-004)."""
import logging
import re
import sys

import structlog

SENSITIVE_KEYS = re.compile(r"(pass(word)?|secret|token|api[_-]?key|authorization|credential|private[_-]?key|^kek$|dsn)", re.IGNORECASE)
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?<=://)[^:/@\s]+:[^@/\s]+@"),          # user:password@ in URLs
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ARCHTWIN-CANARY-[A-Za-z0-9]+"),
]


def redact_text(s: str) -> str:
    for p in SECRET_PATTERNS:
        s = p.sub("[REDACTED]", s)
    return s


def redact(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SENSITIVE_KEYS.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def _redact_processor(_, __, event_dict):
    return {k: (v if k in ("event", "level", "timestamp") else redact({k: v})[k]) for k, v in event_dict.items()}


def configure(level: str = "info") -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=lvl)
    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars, structlog.processors.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso", utc=True), _redact_processor,
                    structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
    )


log = structlog.get_logger("archtwin")
