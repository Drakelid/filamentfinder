import json
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from worker.scheduler import ScanWorker


class FakeRedis:
    def __init__(self):
        self.lists: dict[str, list[str]] = {
            "scan_queue": [],
            "scan_queue:processing": [],
            "scan_queue:dead": [],
        }

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    def lrem(self, key, count, value):
        items = self.lists.setdefault(key, [])
        removed = 0
        kept = []
        for item in items:
            if item == value and (count == 0 or removed < count):
                removed += 1
            else:
                kept.append(item)
        self.lists[key] = kept
        return removed

    def rpoplpush(self, source, dest):
        items = self.lists.setdefault(source, [])
        if not items:
            return None
        value = items.pop()
        self.lists.setdefault(dest, []).insert(0, value)
        return value

    def brpoplpush(self, source, dest, timeout=0):
        return self.rpoplpush(source, dest)


class DummyQuery:
    def __init__(self, sources):
        self._sources = sources

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._sources


class DummySession:
    def __init__(self, sources):
        self._sources = sources
        self.committed = False

    def query(self, *args, **kwargs):
        return DummyQuery(self._sources)

    def commit(self):
        self.committed = True

    def close(self):
        pass


def _make_source(source_id: int, hours_since_last_scan: float | None = None, stale_hours: int = 2):
    last_scan = None
    if hours_since_last_scan is not None:
        last_scan = datetime.now(timezone.utc) - timedelta(hours=hours_since_last_scan)
    return SimpleNamespace(
        id=source_id,
        active=True,
        status="idle",
        next_retry_at=None,
        alert_settings={
            "stale_hours": stale_hours,
            "notify_email": True,
            "notify_webhook": False,
        },
        last_scan_at=last_scan,
        status_message=None,
        name=f"Source {source_id}",
        domain=f"source{source_id}.com",
    )


@pytest.fixture
def fake_redis(monkeypatch):
    redis_client = FakeRedis()
    monkeypatch.setattr("worker.scheduler.redis.from_url", lambda *args, **kwargs: redis_client)
    return redis_client


def test_scan_worker_initializes_crawl_semaphore(fake_redis):
    worker = ScanWorker()

    assert isinstance(worker.crawl_semaphore, asyncio.Semaphore)


@pytest.mark.asyncio
async def test_run_scheduled_scans_enqueues_active_sources(monkeypatch, fake_redis):
    sources = [
        _make_source(1),
        _make_source(2),
    ]
    session = DummySession(sources)
    monkeypatch.setattr("worker.scheduler.get_db_session", lambda: session)

    worker = ScanWorker()
    await worker.run_scheduled_scans()

    queued_jobs = [json.loads(item)["source_id"] for item in fake_redis.lists["scan_queue"]]
    assert queued_jobs == [1, 2]


@pytest.mark.asyncio
async def test_check_stale_sources_enqueues_rescans(monkeypatch, fake_redis):
    stale_source = _make_source(1, hours_since_last_scan=5)
    fresh_source = _make_source(2, hours_since_last_scan=1)
    session = DummySession([stale_source, fresh_source])
    monkeypatch.setattr("worker.scheduler.get_db_session", lambda: session)

    sent_notifications = []

    async def fake_send_notification(subject, body, use_email=False, use_webhook=False):
        sent_notifications.append((subject, body, use_email, use_webhook))

    monkeypatch.setattr("worker.scheduler.send_notification", fake_send_notification)

    worker = ScanWorker()
    await worker.check_stale_sources()

    queued_jobs = [json.loads(item)["source_id"] for item in fake_redis.lists["scan_queue"]]
    assert queued_jobs == [1]
    assert any("stale" in subject.lower() for subject, *_ in sent_notifications)
    assert session.committed is True


@pytest.mark.asyncio
async def test_recover_inflight_jobs_moves_processing_back_to_waiting(monkeypatch, fake_redis):
    job = json.dumps({"job_id": "abc", "source_id": 7, "attempt": 0})
    fake_redis.lists["scan_queue:processing"].append(job)

    worker = ScanWorker()
    recovered = worker.recover_inflight_jobs()

    assert recovered == 1
    assert fake_redis.lists["scan_queue"] == [job]
    assert fake_redis.lists["scan_queue:processing"] == []


@pytest.mark.asyncio
async def test_failed_queue_job_is_requeued_with_incremented_attempt(monkeypatch, fake_redis):
    worker = ScanWorker()

    async def fake_execute_crawl(source_id):
        return False

    monkeypatch.setattr(worker, "_execute_crawl", fake_execute_crawl)

    job = json.dumps({"job_id": "abc", "source_id": 7, "attempt": 0})
    fake_redis.lists["scan_queue:processing"].append(job)

    await worker._process_queue_message(job)

    assert fake_redis.lists["scan_queue:processing"] == []
    assert len(fake_redis.lists["scan_queue"]) == 1
    requeued_job = json.loads(fake_redis.lists["scan_queue"][0])
    assert requeued_job["source_id"] == 7
    assert requeued_job["attempt"] == 1


@pytest.mark.asyncio
async def test_successful_queue_job_is_acknowledged(monkeypatch, fake_redis):
    worker = ScanWorker()

    async def fake_execute_crawl(source_id):
        return True

    monkeypatch.setattr(worker, "_execute_crawl", fake_execute_crawl)

    job = json.dumps({"job_id": "abc", "source_id": 7, "attempt": 0})
    fake_redis.lists["scan_queue:processing"].append(job)

    await worker._process_queue_message(job)

    assert fake_redis.lists["scan_queue:processing"] == []
    assert fake_redis.lists["scan_queue"] == []
    assert fake_redis.lists["scan_queue:dead"] == []
