from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CrawlRunResponse(BaseModel):
    id: int
    source_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    pages_visited: int
    products_found: int
    products_updated: int
    price_changes_detected: int
    errors_count: int
    error_messages: Optional[List[str]]
    stats_json: Optional[dict]

    class Config:
        from_attributes = True


class CrawlRunListResponse(BaseModel):
    items: List[CrawlRunResponse]
    total: int
