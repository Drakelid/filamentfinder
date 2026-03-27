from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.core.security import require_admin_api_key
from app.models import CrawlRun
from app.schemas import CrawlRunResponse, CrawlRunListResponse

router = APIRouter()


@router.get("", response_model=CrawlRunListResponse)
def list_runs(
    source_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    skip: int = Query(0, ge=0, le=100000, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Maximum runs to return"),
    db: Session = Depends(get_db),
):
    query = db.query(CrawlRun)
    
    if source_id:
        query = query.filter(CrawlRun.source_id == source_id)
    if status:
        query = query.filter(CrawlRun.status == status)
    if from_date:
        query = query.filter(CrawlRun.started_at >= from_date)
    if to_date:
        query = query.filter(CrawlRun.started_at <= to_date)
    
    total = query.count()
    runs = query.order_by(desc(CrawlRun.started_at)).offset(skip).limit(limit).all()
    
    return CrawlRunListResponse(
        items=[CrawlRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.get("/{run_id}", response_model=CrawlRunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return CrawlRunResponse.model_validate(run)


@router.delete("/{run_id}", status_code=204, dependencies=[Depends(require_admin_api_key)])
def delete_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    db.delete(run)
    db.commit()
