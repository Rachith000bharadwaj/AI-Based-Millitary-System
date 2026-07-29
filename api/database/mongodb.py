"""MongoDB access layer.

The connection is established lazily and cached. If MongoDB is unavailable the
API keeps serving the stateless endpoints and ``get_db()`` returns ``None``,
so every caller has one obvious thing to check.
"""
import logging
import threading
import time

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from config import config

logger = logging.getLogger(__name__)

# After a failed connection, wait this long before trying again. Without a
# cooldown every request pays the full server-selection timeout, which turns a
# health check into a multi-second call when MongoDB is down.
RETRY_COOLDOWN_SECONDS = 30

_client = None
_db = None
_lock = threading.Lock()
_indexes_ready = False
_last_failure_at = 0.0


def _create_indexes(db) -> None:
    """Create the indexes the query patterns rely on. Idempotent."""
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        # Login looks users up by username on every request; it must be unique.
        db.users.create_index([("username", ASCENDING)], unique=True, name="uniq_username")
        # Every history/audit view is "newest first, limit N".
        db.vision_detections.create_index([("created_at", DESCENDING)], name="recent_detections")
        db.threat_predictions.create_index([("created_at", DESCENDING)], name="recent_predictions")
        db.audit_logs.create_index([("timestamp", DESCENDING)], name="recent_audit")
        db.intelligence_reports.create_index([("created_at", DESCENDING)], name="recent_reports")
        _indexes_ready = True
        logger.info("MongoDB indexes verified.")
    except PyMongoError:
        logger.exception("Could not create MongoDB indexes.")


def get_db():
    """Return the database handle, or None when MongoDB is unreachable."""
    global _client, _db, _last_failure_at
    if _db is not None:
        return _db

    # Fail fast during the cooldown instead of blocking on server selection.
    if time.monotonic() - _last_failure_at < RETRY_COOLDOWN_SECONDS:
        return None

    with _lock:
        if _db is not None:  # another thread won the race
            return _db
        if time.monotonic() - _last_failure_at < RETRY_COOLDOWN_SECONDS:
            return None
        try:
            client = MongoClient(
                config.MONGO_URI,
                serverSelectionTimeoutMS=config.MONGO_TIMEOUT_MS,
                tz_aware=True,
            )
            client.admin.command("ping")
            db = client[config.MONGO_DB_NAME]
            _create_indexes(db)
            _client, _db = client, db
            logger.info("Connected to MongoDB database '%s'.", config.MONGO_DB_NAME)
            return _db
        except PyMongoError as exc:
            _last_failure_at = time.monotonic()
            logger.warning(
                "MongoDB unavailable (%s). Stateful endpoints disabled; "
                "retrying in %ds.",
                exc.__class__.__name__, RETRY_COOLDOWN_SECONDS,
            )
            return None


def is_connected() -> bool:
    """Cheap health probe used by /api/health."""
    return get_db() is not None


def close() -> None:
    """Close the pooled connection (used by tests and graceful shutdown)."""
    global _client, _db, _indexes_ready, _last_failure_at
    with _lock:
        if _client is not None:
            _client.close()
        _client = _db = None
        _indexes_ready = False
        _last_failure_at = 0.0
