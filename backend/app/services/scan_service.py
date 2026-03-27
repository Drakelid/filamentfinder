import json
from datetime import datetime, timezone
from uuid import uuid4

import redis
import structlog

from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger(__name__)
SCAN_QUEUE = "scan_queue"

_redis_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def _get_redis() -> redis.Redis:
    """Return a Redis client backed by a shared connection pool."""
    return redis.Redis(connection_pool=_redis_pool)


def _build_scan_job(source_id: int) -> dict:
    return {
        "job_id": str(uuid4()),
        "job_type": "scan",
        "source_id": source_id,
        "attempt": 0,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }


def trigger_scan(source_id: int) -> dict:
    """Trigger a scan by enqueueing a durable Redis job."""
    job = _build_scan_job(source_id)
    try:
        r = _get_redis()
        r.rpush(SCAN_QUEUE, json.dumps(job))
        return job
    except Exception as e:
        logger.error("Failed to queue scan", source_id=source_id, error=str(e))
        raise
