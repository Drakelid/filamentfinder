import json
from datetime import datetime, timezone
from uuid import uuid4

import redis

from app.core.config import get_settings

settings = get_settings()
SCAN_QUEUE = "scan_queue"


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
        r = redis.from_url(settings.redis_url, decode_responses=True)
        r.rpush(SCAN_QUEUE, json.dumps(job))
        return job
    except Exception as e:
        print(f"Failed to queue scan: {e}")
        raise
