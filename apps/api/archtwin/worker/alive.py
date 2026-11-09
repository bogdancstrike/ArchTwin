"""Healthcheck: the worker loop wrote its heartbeat recently."""
import sys
import time
from pathlib import Path

p = Path("/tmp/archtwin-worker-alive")
sys.exit(0 if p.exists() and time.time() - p.stat().st_mtime < 30 else 1)
