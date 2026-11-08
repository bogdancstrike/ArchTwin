"""UUIDv7 identifiers (time-ordered, index friendly)."""
import uuid

import uuid_utils


def new_id() -> uuid.UUID:
    return uuid.UUID(str(uuid_utils.uuid7()))
