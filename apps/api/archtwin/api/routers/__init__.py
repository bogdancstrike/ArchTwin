"""Feature routers mounted under /api/v1 next to the core `api.routes` router (one module per bounded area)."""
from archtwin.api.routers import audit, exploration, exports, operations

ROUTERS = [operations.router, exploration.router, audit.router, exports.router]
