import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import case, func

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import require_admin_api_key
from app.models import Source, Product, CrawlRun
from app.schemas import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    SourceListResponse,
    CrawlRules,
    SelectorOverrides,
)
from app.schemas.source import (
    ScrapeStats,
    CrawlRunSummary,
    RetryPolicy,
    CrawlDurationStats,
    AlertSettings,
)
from app.services.scan_service import trigger_scan

router = APIRouter()


def get_scrape_stats(source_id: int, db: Session) -> ScrapeStats:
    """Get product scrape counts for last 1h, 12h, and 24h."""
    now = datetime.now(timezone.utc)
    
    last_1h = db.query(func.count(Product.id)).filter(
        Product.source_id == source_id,
        Product.last_seen_at >= now - timedelta(hours=1)
    ).scalar() or 0
    
    last_12h = db.query(func.count(Product.id)).filter(
        Product.source_id == source_id,
        Product.last_seen_at >= now - timedelta(hours=12)
    ).scalar() or 0
    
    last_24h = db.query(func.count(Product.id)).filter(
        Product.source_id == source_id,
        Product.last_seen_at >= now - timedelta(hours=24)
    ).scalar() or 0
    
    return ScrapeStats(last_1h=last_1h, last_12h=last_12h, last_24h=last_24h)


def _build_run_summary(run: CrawlRun) -> CrawlRunSummary:
    duration_seconds = None
    if run.finished_at and run.started_at:
        duration_seconds = (run.finished_at - run.started_at).total_seconds()

    return CrawlRunSummary(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=duration_seconds,
        pages_visited=run.pages_visited,
        products_found=run.products_found,
        products_updated=run.products_updated,
        price_changes_detected=run.price_changes_detected,
        errors_count=run.errors_count,
    )


def get_latest_run(source_id: int, db: Session) -> Optional[CrawlRunSummary]:
    run = (
        db.query(CrawlRun)
        .filter(CrawlRun.source_id == source_id)
        .order_by(CrawlRun.started_at.desc())
        .first()
    )
    if not run:
        return None
    return _build_run_summary(run)


def get_success_rate_24h(source_id: int, db: Session) -> Optional[float]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    total = (
        db.query(func.count(CrawlRun.id))
        .filter(CrawlRun.source_id == source_id, CrawlRun.started_at >= cutoff)
        .scalar()
    )
    if not total:
        return None
    successes = (
        db.query(func.count(CrawlRun.id))
        .filter(
            CrawlRun.source_id == source_id,
            CrawlRun.started_at >= cutoff,
            CrawlRun.status == "completed",
        )
        .scalar()
    )
    return successes / total if total else None


def _batch_source_summary_data(db: Session, source_ids: list[int]) -> dict[int, dict]:
    source_ids = list(dict.fromkeys(source_ids))
    if not source_ids:
        return {}

    summary = {
        source_id: {
            "product_count": 0,
            "scrape_stats": ScrapeStats(),
            "latest_run": None,
            "success_rate_24h": None,
        }
        for source_id in source_ids
    }

    product_counts = (
        db.query(Product.source_id, func.count(Product.id))
        .filter(Product.source_id.in_(source_ids))
        .group_by(Product.source_id)
        .all()
    )
    for source_id, count in product_counts:
        summary[source_id]["product_count"] = count or 0

    for key, hours in (("last_1h", 1), ("last_12h", 12), ("last_24h", 24)):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        scrape_rows = (
            db.query(Product.source_id, func.count(Product.id))
            .filter(
                Product.source_id.in_(source_ids),
                Product.last_seen_at >= cutoff,
            )
            .group_by(Product.source_id)
            .all()
        )
        for source_id, count in scrape_rows:
            setattr(summary[source_id]["scrape_stats"], key, count or 0)

    latest_runs = (
        db.query(CrawlRun)
        .filter(CrawlRun.source_id.in_(source_ids))
        .order_by(CrawlRun.source_id.asc(), CrawlRun.started_at.desc(), CrawlRun.id.desc())
        .all()
    )
    seen_latest = set()
    for run in latest_runs:
        if run.source_id in seen_latest:
            continue
        summary[run.source_id]["latest_run"] = _build_run_summary(run)
        seen_latest.add(run.source_id)

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    success_rows = (
        db.query(
            CrawlRun.source_id,
            func.count(CrawlRun.id).label("total_runs"),
            func.sum(case((CrawlRun.status == "completed", 1), else_=0)).label("completed_runs"),
        )
        .filter(CrawlRun.source_id.in_(source_ids), CrawlRun.started_at >= cutoff_24h)
        .group_by(CrawlRun.source_id)
        .all()
    )
    for row in success_rows:
        total_runs = row.total_runs or 0
        completed_runs = row.completed_runs or 0
        summary[row.source_id]["success_rate_24h"] = completed_runs / total_runs if total_runs else None

    return summary


def source_to_response(source: Source, db: Session, summary_data: Optional[dict[int, dict]] = None) -> SourceResponse:
    if summary_data is None or source.id not in summary_data:
        summary_data = _batch_source_summary_data(db, [source.id])

    source_summary = summary_data.get(source.id, {})
    product_count = source_summary.get("product_count", 0)
    scrape_stats = source_summary.get("scrape_stats", ScrapeStats())
    latest_run = source_summary.get("latest_run")
    success_rate_24h = source_summary.get("success_rate_24h")

    crawl_rules = CrawlRules(**source.crawl_rules)
    selector_overrides = SelectorOverrides(**source.selector_overrides) if source.selector_overrides else None
    retry_policy = RetryPolicy(**source.retry_policy) if source.retry_policy else None
    alert_settings = AlertSettings(**source.alert_settings) if source.alert_settings else None
    duration_stats = (
        CrawlDurationStats(**source.crawl_duration_stats)
        if source.crawl_duration_stats
        else None
    )
    
    return SourceResponse(
        id=source.id,
        url=source.url,
        domain=source.domain,
        name=source.name,
        active=source.active,
        crawl_rules=crawl_rules,
        selector_overrides=selector_overrides,
        shipping_fee=source.shipping_fee,
        robots_txt_allowed=source.robots_txt_allowed,
        retry_policy=retry_policy,
        crawl_duration_stats=duration_stats,
        alert_settings=alert_settings,
        failure_streak=source.failure_streak,
        next_retry_at=source.next_retry_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
        last_scan_at=source.last_scan_at,
        status=source.status,
        status_message=source.status_message,
        product_count=product_count,
        scrape_stats=scrape_stats,
        latest_run=latest_run,
        success_rate_24h=success_rate_24h,
    )


@router.post("", response_model=SourceResponse, status_code=201, dependencies=[Depends(require_admin_api_key)])
def create_source(source_in: SourceCreate, db: Session = Depends(get_db)):
    parsed = urlparse(source_in.url)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    
    source = Source(
        url=source_in.url,
        domain=domain,
        name=source_in.name or domain,
        crawl_rules_json=source_in.crawl_rules.model_dump() if source_in.crawl_rules else None,
        selector_overrides_json=source_in.selector_overrides.model_dump() if source_in.selector_overrides else None,
        shipping_fee=source_in.shipping_fee,
        retry_policy_json=source_in.retry_policy.model_dump() if source_in.retry_policy else None,
        alert_settings_json=source_in.alert_settings.model_dump() if source_in.alert_settings else None,
        status="pending",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    
    return source_to_response(source, db)


@router.get("", response_model=SourceListResponse)
def list_sources(
    active: Optional[bool] = None,
    skip: int = Query(0, ge=0, le=100000, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum sources to return"),
    db: Session = Depends(get_db),
):
    query = db.query(Source)
    if active is not None:
        query = query.filter(Source.active == active)
    
    total = query.count()
    sources = query.order_by(Source.created_at.desc()).offset(skip).limit(limit).all()
    summary_data = _batch_source_summary_data(db, [source.id for source in sources])
    
    return SourceListResponse(
        items=[source_to_response(s, db, summary_data) for s in sources],
        total=total,
    )


@router.get("/export")
def export_sources(
    api_key: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    configured_key = (settings.admin_api_key or "").strip()
    if configured_key and api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    sources = db.query(Source).order_by(Source.created_at.desc()).all()
    data = [
        {
            "url": source.url,
            "domain": source.domain,
            "name": source.name,
            "active": source.active,
            "crawl_rules": source.crawl_rules,
            "selector_overrides": source.selector_overrides or None,
            "shipping_fee": source.shipping_fee,
            "robots_txt_allowed": source.robots_txt_allowed,
            "retry_policy": source.retry_policy or None,
            "alert_settings": source.alert_settings or None,
        }
        for source in sources
    ]
    return Response(
        content=json.dumps(jsonable_encoder(data)),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="sources.json"'},
    )


@router.post("/import", dependencies=[Depends(require_admin_api_key)])
async def import_sources(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    result = {"imported": 0, "skipped": 0, "errors": []}

    try:
        content = await file.read()
        if len(content) > 1024 * 1024:
            result["errors"].append({"url": "", "reason": "File exceeds 1 MB limit"})
            return result

        payload = json.loads(content.decode("utf-8"))
        if not isinstance(payload, list):
            result["errors"].append({"url": "", "reason": "Expected a JSON array"})
            return result
    except Exception as exc:
        result["errors"].append({"url": "", "reason": f"Invalid JSON file: {exc}"})
        return result

    for entry in payload:
        url = ""
        try:
            if not isinstance(entry, dict):
                raise ValueError("Entry must be an object")

            url = str(entry.get("url") or "").strip()
            if not url:
                raise ValueError("Missing required field: url")

            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")

            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            crawl_rules = entry.get("crawl_rules") or {}
            existing = db.query(Source).filter(Source.url == url).first()
            if existing:
                existing.crawl_rules_json = crawl_rules or None
                db.commit()
                result["skipped"] += 1
                continue

            source = Source(
                url=url,
                domain=domain,
                name=entry.get("name") or domain,
                active=True,
                crawl_rules_json=crawl_rules or None,
                selector_overrides_json=entry.get("selector_overrides") or None,
                shipping_fee=entry.get("shipping_fee"),
                robots_txt_allowed=entry.get("robots_txt_allowed"),
                retry_policy_json=entry.get("retry_policy") or None,
                alert_settings_json=entry.get("alert_settings") or None,
                status="pending",
            )
            db.add(source)
            db.commit()
            result["imported"] += 1
        except Exception as exc:
            db.rollback()
            result["errors"].append({"url": url or "", "reason": str(exc)})

    return result


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source_to_response(source, db)


@router.put("/{source_id}", response_model=SourceResponse, dependencies=[Depends(require_admin_api_key)])
def update_source(source_id: int, source_in: SourceUpdate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Respect explicit nulls so callers can clear fields intentionally.
    if "name" in source_in.model_fields_set:
        source.name = source_in.name
    if source_in.active is not None:
        source.active = source_in.active
    if "crawl_rules" in source_in.model_fields_set:
        source.crawl_rules_json = source_in.crawl_rules.model_dump() if source_in.crawl_rules else None
    if "selector_overrides" in source_in.model_fields_set:
        source.selector_overrides_json = (
            source_in.selector_overrides.model_dump() if source_in.selector_overrides else None
        )
    if "shipping_fee" in source_in.model_fields_set:
        source.shipping_fee = source_in.shipping_fee
    if "retry_policy" in source_in.model_fields_set:
        source.retry_policy_json = source_in.retry_policy.model_dump() if source_in.retry_policy else None
    if "alert_settings" in source_in.model_fields_set:
        source.alert_settings_json = source_in.alert_settings.model_dump() if source_in.alert_settings else None
    
    db.commit()
    db.refresh(source)
    
    return source_to_response(source, db)


@router.delete("/{source_id}", status_code=204, dependencies=[Depends(require_admin_api_key)])
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    db.delete(source)
    db.commit()
    return None


@router.post("/{source_id}/scan", response_model=dict, dependencies=[Depends(require_admin_api_key)])
def scan_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if not source.active:
        raise HTTPException(status_code=400, detail="Source is not active")
    
    if source.status == "scanning":
        raise HTTPException(status_code=400, detail="Scan already in progress")
    
    try:
        job = trigger_scan(source_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Failed to queue scan job") from exc

    source.status = "scanning"
    db.commit()

    return {"message": "Scan started", "source_id": source_id, "job_id": job["job_id"]}
