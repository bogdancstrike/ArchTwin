"""Back-compat import path; the implementation lives in `sql_catalog` (shared by every SQLAlchemy dialect)."""
from archtwin.connectors.adapters.sql_catalog import SENSITIVE, PostgresCatalogConnector

__all__ = ["SENSITIVE", "PostgresCatalogConnector"]
