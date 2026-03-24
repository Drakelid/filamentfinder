import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.api.endpoints import sources as sources_endpoint
from app.main import app
from app.core.database import get_db
from app.models import Base, Source, Product, CrawlRun, PriceObservation


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as c:
        yield c
    
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestSourcesAPI:
    def test_create_source(self, client):
        response = client.post(
            "/api/sources",
            json={"url": "https://example.com/filaments", "name": "Test Store"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com/filaments"
        assert data["name"] == "Test Store"
        assert data["domain"] == "example.com"
        assert data["active"] == True
        assert data["status"] == "pending"
    
    def test_create_source_invalid_url(self, client):
        response = client.post(
            "/api/sources",
            json={"url": "not-a-valid-url"}
        )
        assert response.status_code == 400
    
    def test_list_sources_empty(self, client):
        response = client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_list_sources(self, client):
        client.post("/api/sources", json={"url": "https://store1.com/filaments"})
        client.post("/api/sources", json={"url": "https://store2.com/resins"})
        
        response = client.get("/api/sources")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_sources_includes_batch_metrics(self, client):
        create_response = client.post(
            "/api/sources",
            json={"url": "https://example.com/filaments"}
        )
        source_id = create_response.json()["id"]

        db = TestingSessionLocal()
        try:
            now = datetime.now(timezone.utc)
            db.add(
                Product(
                    source_id=source_id,
                    canonical_url="https://example.com/products/pla",
                    name="Example PLA",
                    category="filament",
                    confidence=0.9,
                    active=True,
                    last_seen_at=now - timedelta(minutes=10),
                )
            )
            db.add(
                CrawlRun(
                    source_id=source_id,
                    started_at=now - timedelta(minutes=45),
                    finished_at=now,
                    status="completed",
                    pages_visited=4,
                    products_found=1,
                    products_updated=1,
                    price_changes_detected=0,
                    errors_count=0,
                )
            )
            db.commit()
        finally:
            db.close()

        response = client.get("/api/sources")
        assert response.status_code == 200
        source = response.json()["items"][0]
        assert source["product_count"] == 1
        assert source["latest_run"]["status"] == "completed"
        assert source["success_rate_24h"] == 1.0
        assert source["scrape_stats"]["last_1h"] == 1
        assert source["scrape_stats"]["last_12h"] == 1
        assert source["scrape_stats"]["last_24h"] == 1
    
    def test_get_source(self, client):
        create_response = client.post(
            "/api/sources",
            json={"url": "https://example.com/filaments"}
        )
        source_id = create_response.json()["id"]
        
        response = client.get(f"/api/sources/{source_id}")
        assert response.status_code == 200
        assert response.json()["id"] == source_id
    
    def test_get_source_not_found(self, client):
        response = client.get("/api/sources/999")
        assert response.status_code == 404
    
    def test_update_source(self, client):
        create_response = client.post(
            "/api/sources",
            json={"url": "https://example.com/filaments"}
        )
        source_id = create_response.json()["id"]
        
        response = client.put(
            f"/api/sources/{source_id}",
            json={"name": "Updated Name", "active": False}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
        assert response.json()["active"] == False

    def test_update_source_can_clear_nullable_and_json_fields(self, client):
        create_response = client.post(
            "/api/sources",
            json={
                "url": "https://example.com/filaments",
                "name": "Original Name",
                "crawl_rules": {
                    "max_pages": 25,
                    "max_depth": 2,
                    "same_domain_only": True,
                    "url_patterns": ["*/pla/*"],
                    "exclude_patterns": ["*/outlet/*"],
                    "respect_robots_txt": True,
                },
                "selector_overrides": {
                    "price": ".price",
                    "currency": ".currency",
                },
                "shipping_fee": "12.50",
                "retry_policy": {
                    "max_retries": 2,
                    "backoff_seconds": 120,
                    "retry_statuses": ["failed"],
                },
                "alert_settings": {
                    "failure_threshold": 2,
                    "stale_hours": 12,
                    "notify_webhook": True,
                    "notify_email": True,
                },
            }
        )
        source_id = create_response.json()["id"]

        response = client.put(
            f"/api/sources/{source_id}",
            json={
                "name": None,
                "crawl_rules": None,
                "selector_overrides": None,
                "shipping_fee": None,
                "retry_policy": None,
                "alert_settings": None,
            },
        )
        assert response.status_code == 200
        assert response.json()["name"] is None
        assert response.json()["selector_overrides"] is None
        assert response.json()["shipping_fee"] is None

        db = TestingSessionLocal()
        try:
            source = db.query(Source).filter(Source.id == source_id).first()
            assert source is not None
            assert source.name is None
            assert source.crawl_rules_json is None
            assert source.selector_overrides_json is None
            assert source.shipping_fee is None
            assert source.retry_policy_json is None
            assert source.alert_settings_json is None
        finally:
            db.close()
    
    def test_delete_source(self, client):
        create_response = client.post(
            "/api/sources",
            json={"url": "https://example.com/filaments"}
        )
        source_id = create_response.json()["id"]
        
        response = client.delete(f"/api/sources/{source_id}")
        assert response.status_code == 204
        
        get_response = client.get(f"/api/sources/{source_id}")
        assert get_response.status_code == 404

    def test_scan_source_queue_failure_does_not_mark_scanning(self, client, monkeypatch):
        create_response = client.post(
            "/api/sources",
            json={"url": "https://example.com/filaments"}
        )
        source_id = create_response.json()["id"]

        def fail_trigger_scan(source_id: int):
            raise RuntimeError("queue unavailable")

        monkeypatch.setattr(sources_endpoint, "trigger_scan", fail_trigger_scan)

        response = client.post(f"/api/sources/{source_id}/scan")
        assert response.status_code == 503
        assert response.json()["detail"] == "Failed to queue scan job"

        get_response = client.get(f"/api/sources/{source_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "pending"


class TestProductsAPI:
    def test_list_products_empty(self, client):
        response = client.get("/api/products")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_get_product_not_found(self, client):
        response = client.get("/api/products/999")
        assert response.status_code == 404
    
    def test_get_product_history_not_found(self, client):
        response = client.get("/api/products/999/history")
        assert response.status_code == 404
    
    def test_get_product_changes_not_found(self, client):
        response = client.get("/api/products/999/changes")
        assert response.status_code == 404

    def test_list_products_filters_on_delivered_price(self, client):
        db = TestingSessionLocal()
        try:
            source = Source(
                url="https://example.com/filaments",
                domain="example.com",
                name="Example",
                status="pending",
            )
            db.add(source)
            db.commit()
            db.refresh(source)

            product = Product(
                source_id=source.id,
                canonical_url="https://example.com/products/pla",
                name="PLA Filament",
                category="filament",
                active=True,
                confidence=1.0,
            )
            db.add(product)
            db.commit()
            db.refresh(product)

            observation = PriceObservation(
                product_id=product.id,
                price_amount=Decimal("10.00"),
                shipping_amount=Decimal("5.00"),
                total_price_amount=None,
                currency="USD",
            )
            db.add(observation)
            db.commit()
        finally:
            db.close()

        under_response = client.get("/api/products?max_price=14.99")
        assert under_response.status_code == 200
        assert under_response.json()["total"] == 0

        exact_response = client.get("/api/products?max_price=15")
        assert exact_response.status_code == 200
        data = exact_response.json()
        assert data["total"] == 1
        assert data["items"][0]["latest_price"]["total_price_amount"] == "15.00"


class TestRunsAPI:
    def test_list_runs_empty(self, client):
        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_get_run_not_found(self, client):
        response = client.get("/api/runs/999")
        assert response.status_code == 404


class TestStatsAPI:
    def test_health_without_alembic_version_table(self, client):
        response = client.get("/api/stats/health")
        assert response.status_code == 200
        data = response.json()
        assert data["migrations"]["pending"] == 0
        assert data["migrations"]["current_revision"] is None
