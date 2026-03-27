from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Query
import redis
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text, case
from sqlalchemy.exc import OperationalError

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Source, Product, CrawlRun, PriceObservation, PriceChange

router = APIRouter()


def _summarize_run(run: CrawlRun) -> dict:
    duration = None
    if run.finished_at and run.started_at:
        duration = (run.finished_at - run.started_at).total_seconds()

    return {
        "id": run.id,
        "source_id": run.source_id,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_seconds": duration,
        "status": run.status,
        "pages_visited": run.pages_visited,
        "products_found": run.products_found,
        "products_updated": run.products_updated,
        "price_changes_detected": run.price_changes_detected,
        "errors_count": run.errors_count,
    }


def _hour_bucket_value(value):
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return value


def _group_hourly_activity(db: Session, model, timestamp_column, hours: int, start_time: datetime):
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "sqlite":
        bucket_expr = func.strftime("%Y-%m-%d %H:00:00", timestamp_column)
    else:
        bucket_expr = func.date_trunc("hour", timestamp_column)

    rows = (
        db.query(bucket_expr.label("hour_bucket"), func.count(model.id).label("count"))
        .filter(timestamp_column >= start_time, timestamp_column < start_time + timedelta(hours=hours))
        .group_by(bucket_expr)
        .all()
    )

    counts = {_hour_bucket_value(row.hour_bucket): row.count for row in rows}
    hourly_data = []
    for i in range(hours):
        hour_start = start_time + timedelta(hours=i)
        bucket_key = hour_start.replace(minute=0, second=0, microsecond=0)
        hourly_data.append(
            {
                "hour": bucket_key.isoformat(),
                "count": counts.get(bucket_key, 0),
            }
        )
    return hourly_data


@router.get("")
def get_stats(db: Session = Depends(get_db)):
    """Get overall crawler statistics."""
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    # Source stats
    total_sources = db.query(Source).count()
    active_sources = db.query(Source).filter(Source.active == True).count()
    scanning_sources = db.query(Source).filter(Source.status == "scanning").count()
    
    # Product stats
    total_products = db.query(Product).count()
    active_products = db.query(Product).filter(Product.active == True).count()
    
    # Products by category
    products_by_category = db.query(
        Product.category,
        func.count(Product.id).label("count")
    ).group_by(Product.category).all()
    
    # Crawl run stats
    total_runs = db.query(CrawlRun).count()
    runs_24h = db.query(CrawlRun).filter(CrawlRun.started_at >= last_24h).count()
    runs_7d = db.query(CrawlRun).filter(CrawlRun.started_at >= last_7d).count()
    
    # Running/recent crawls
    running_crawls = db.query(CrawlRun).filter(CrawlRun.status == "running").count()
    
    # Price observations
    observations_24h = db.query(PriceObservation).filter(
        PriceObservation.observed_at >= last_24h
    ).count()
    observations_7d = db.query(PriceObservation).filter(
        PriceObservation.observed_at >= last_7d
    ).count()
    
    # Price changes
    changes_24h = db.query(PriceChange).filter(
        PriceChange.changed_at >= last_24h
    ).count()
    changes_7d = db.query(PriceChange).filter(
        PriceChange.changed_at >= last_7d
    ).count()
    
    # Recent crawl runs with source info
    recent_runs = db.query(
        CrawlRun.id,
        CrawlRun.source_id,
        Source.name.label("source_name"),
        Source.domain.label("source_domain"),
        CrawlRun.started_at,
        CrawlRun.finished_at,
        CrawlRun.status,
        CrawlRun.pages_visited,
        CrawlRun.products_found,
        CrawlRun.products_updated,
        CrawlRun.price_changes_detected,
        CrawlRun.errors_count,
    ).join(Source).order_by(
        desc(CrawlRun.started_at)
    ).limit(10).all()
    
    recent_runs_data = []
    for run in recent_runs:
        row = _summarize_run(run)
        row["source_name"] = run.source_name or run.source_domain
        recent_runs_data.append(row)
    
    # Source activity summary
    sources_data = db.query(
        Source.id,
        Source.name,
        Source.domain,
        Source.status,
        Source.last_scan_at,
    ).order_by(desc(Source.last_scan_at)).all()
    sources_summary = []
    source_ids = [source.id for source in sources_data]
    product_counts = {}
    latest_runs = {}

    if source_ids:
        product_rows = (
            db.query(Product.source_id, func.count(Product.id).label("count"))
            .filter(Product.source_id.in_(source_ids))
            .group_by(Product.source_id)
            .all()
        )
        product_counts = {source_id: count for source_id, count in product_rows}

        latest_run_rows = (
            db.query(CrawlRun)
            .filter(CrawlRun.source_id.in_(source_ids))
            .order_by(CrawlRun.source_id.asc(), CrawlRun.started_at.desc(), CrawlRun.id.desc())
            .all()
        )
        for run in latest_run_rows:
            latest_runs.setdefault(run.source_id, run)

    for source in sources_data:
        latest_run = latest_runs.get(source.id)
        
        sources_summary.append({
            "id": source.id,
            "name": source.name or source.domain,
            "domain": source.domain,
            "status": source.status,
            "product_count": product_counts.get(source.id, 0),
            "last_scan_at": source.last_scan_at.isoformat() if source.last_scan_at else None,
            "latest_run": _summarize_run(latest_run) if latest_run else None,
        })
    
    return {
        "overview": {
            "total_sources": total_sources,
            "active_sources": active_sources,
            "scanning_sources": scanning_sources,
            "total_products": total_products,
            "active_products": active_products,
            "running_crawls": running_crawls,
        },
        "products_by_category": {
            cat: count for cat, count in products_by_category
        },
        "activity": {
            "runs_24h": runs_24h,
            "runs_7d": runs_7d,
            "total_runs": total_runs,
            "observations_24h": observations_24h,
            "observations_7d": observations_7d,
            "changes_24h": changes_24h,
            "changes_7d": changes_7d,
        },
        "recent_runs": recent_runs_data,
        "sources": sources_summary,
    }


@router.get("/activity")
def get_activity_timeline(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """Get hourly activity breakdown."""
    now = datetime.utcnow()
    start_time = now - timedelta(hours=hours)
    observation_rows = _group_hourly_activity(db, PriceObservation, PriceObservation.observed_at, hours, start_time)
    change_rows = _group_hourly_activity(db, PriceChange, PriceChange.changed_at, hours, start_time)
    change_counts = {datetime.fromisoformat(row["hour"]): row["count"] for row in change_rows}
    
    return {
        "hours": hours,
        "data": [
            {
                "hour": row["hour"],
                "observations": row["count"],
                "price_changes": change_counts.get(datetime.fromisoformat(row["hour"]), 0),
            }
            for row in observation_rows
        ],
    }


def _get_alembic_script() -> ScriptDirectory:
    base_dir = Path(__file__).resolve().parents[3]
    app_dir = Path(__file__).resolve().parents[2]
    candidate_dirs = [base_dir / "alembic", app_dir / "alembic"]
    alembic_dir = next((path for path in candidate_dirs if path.exists()), candidate_dirs[0])
    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option("script_location", str(alembic_dir))
    return ScriptDirectory.from_config(alembic_cfg)


def _count_pending_migrations(db: Session) -> Tuple[int, Optional[str], Optional[str]]:
    script = _get_alembic_script()
    head_revision = script.get_current_head()
    bind = db.get_bind()
    try:
        with bind.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            current_revision = row[0] if row else None
    except OperationalError:
        return 0, None, head_revision

    if not head_revision:
        return 0, current_revision, head_revision

    if current_revision == head_revision:
        return 0, current_revision, head_revision

    pending = 0
    for revision in script.walk_revisions(head_revision, "base"):
        if current_revision and revision.revision == current_revision:
            break
        pending += 1

    return pending, current_revision, head_revision


def _get_path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size

    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _get_database_size_bytes(db: Session) -> Optional[int]:
    bind = db.get_bind()
    dialect_name = bind.dialect.name

    try:
        if dialect_name == "postgresql":
            result = db.execute(text("SELECT pg_database_size(current_database())"))
            value = result.scalar()
            return int(value) if value is not None else None

        if dialect_name == "sqlite":
            database_name = bind.url.database
            if database_name:
                return Path(database_name).stat().st_size
    except Exception:
        return None

    return None


def _get_redis_memory_bytes() -> Optional[int]:
    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        info = client.info("memory")
        value = info.get("used_memory")
        return int(value) if value is not None else None
    except Exception:
        return None


def _get_storage_summary(db: Session) -> dict:
    database_bytes = _get_database_size_bytes(db)
    redis_bytes = _get_redis_memory_bytes()
    gluetun_data_bytes = _get_path_size_bytes(Path("/gluetun"))

    known_values = [value for value in [database_bytes, redis_bytes, gluetun_data_bytes] if value is not None]
    total_known_bytes = sum(known_values) if known_values else None

    return {
        "database_bytes": database_bytes,
        "redis_bytes": redis_bytes,
        "gluetun_data_bytes": gluetun_data_bytes,
        "total_known_bytes": total_known_bytes,
    }


@router.get("/health")
def get_system_health(db: Session = Depends(get_db)):
    latest_scan: Optional[datetime] = db.query(func.max(Source.last_scan_at)).scalar()
    active_crawls = db.query(Source).filter(Source.status == "scanning").count()
    worker_status = "active" if active_crawls > 0 else "idle"
    pending_migrations, current_revision, head_revision = _count_pending_migrations(db)

    return {
        "worker": {
            "status": worker_status,
            "active_crawls": active_crawls,
        },
        "latest_scan_at": latest_scan.isoformat() if latest_scan else None,
        "migrations": {
            "pending": pending_migrations,
            "current_revision": current_revision,
            "head_revision": head_revision,
        },
        "storage": _get_storage_summary(db),
    }
