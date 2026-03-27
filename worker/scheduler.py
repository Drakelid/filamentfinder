import asyncio
import json
import random
import signal
from datetime import datetime, timedelta, timezone
from typing import Set, List, Optional
from uuid import uuid4
import redis
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from worker.config import get_settings, refresh_settings
from worker.database import get_db_session
from worker.models import Source, Product, PriceObservation
from worker.crawler.crawler import run_crawler
from worker.notifications import send_notification, trigger_price_alerts

logger = structlog.get_logger(__name__)
settings = get_settings()
SCAN_QUEUE = "scan_queue"
SCAN_PROCESSING_QUEUE = "scan_queue:processing"
SCAN_DEAD_LETTER_QUEUE = "scan_queue:dead"
MAX_SCAN_ATTEMPTS = 3


class ScanWorker:
    """Worker that processes scan jobs from Redis queue and runs scheduled scans."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.running = True
        self.active_crawls: Set[int] = set()  # Track active source IDs
        self.crawl_semaphore = asyncio.Semaphore(settings.crawler_max_concurrent_sources)
        self.crawl_tasks: Set[asyncio.Task] = set()

    def refresh_runtime_settings(self):
        refresh_settings()
        self.crawl_semaphore = asyncio.Semaphore(settings.crawler_max_concurrent_sources)

    def enqueue_scan_job(self, source_id: int, *, job_type: str = "scan", trigger: str = "scheduled") -> dict:
        """Enqueue a durable scan job."""
        job = {
            "job_id": str(uuid4()),
            "job_type": job_type,
            "source_id": source_id,
            "attempt": 0,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
        }
        self.redis_client.rpush(SCAN_QUEUE, json.dumps(job))
        return job

    def recover_inflight_jobs(self) -> int:
        """Move jobs left in the processing queue back to the waiting queue."""
        recovered = 0
        while True:
            job_json = self.redis_client.rpoplpush(SCAN_PROCESSING_QUEUE, SCAN_QUEUE)
            if job_json is None:
                break
            recovered += 1
        if recovered:
            logger.info("Recovered in-flight scan jobs", count=recovered)
        return recovered

    async def process_queue_job(self, job_json: str):
        """Process a single job payload pulled from Redis."""
        task = asyncio.create_task(self._process_queue_message(job_json))
        self.crawl_tasks.add(task)
        task.add_done_callback(self.crawl_tasks.discard)

    async def _process_queue_message(self, job_json: str):
        """Execute a queue message and ack/requeue it appropriately."""
        try:
            job_data = json.loads(job_json)
        except json.JSONDecodeError:
            logger.error("Invalid queue payload", payload=job_json)
            await self._remove_from_processing(job_json)
            await self._send_to_dead_letter({"raw_payload": job_json}, "invalid_json")
            return

        source_id = job_data.get("source_id")
        if not source_id:
            logger.error("Invalid job data", job=job_data)
            await self._remove_from_processing(job_json)
            await self._send_to_dead_letter(job_data, "missing_source_id")
            return

        if source_id in self.active_crawls:
            logger.info("Source already being crawled, skipping", source_id=source_id)
            await self._remove_from_processing(job_json)
            return

        success = False
        try:
            async with self.crawl_semaphore:
                success = await self._execute_crawl(source_id)
        except Exception as e:
            logger.error("Queue job failed", source_id=source_id, error=str(e))
        finally:
            await self._finalize_queue_message(job_json, job_data, success)

    async def _remove_from_processing(self, job_json: str):
        await asyncio.to_thread(self.redis_client.lrem, SCAN_PROCESSING_QUEUE, 1, job_json)

    async def _send_to_waiting_queue(self, job_data: dict):
        await asyncio.to_thread(self.redis_client.rpush, SCAN_QUEUE, json.dumps(job_data))

    async def _send_to_dead_letter(self, job_data: dict, reason: str):
        dead_letter = dict(job_data)
        dead_letter["failed_at"] = datetime.now(timezone.utc).isoformat()
        dead_letter["failure_reason"] = reason
        await asyncio.to_thread(self.redis_client.rpush, SCAN_DEAD_LETTER_QUEUE, json.dumps(dead_letter))

    async def _finalize_queue_message(self, job_json: str, job_data: dict, success: bool):
        await self._remove_from_processing(job_json)
        if success:
            return

        attempts = int(job_data.get("attempt", 0)) + 1
        retry_job = dict(job_data)
        retry_job["attempt"] = attempts
        retry_job["last_error_at"] = datetime.now(timezone.utc).isoformat()

        if attempts >= MAX_SCAN_ATTEMPTS:
            retry_job["failure_reason"] = "max_attempts_exceeded"
            await self._send_to_dead_letter(retry_job, "max_attempts_exceeded")
            logger.error(
                "Scan job moved to dead letter queue",
                source_id=job_data.get("source_id"),
                attempts=attempts,
            )
        else:
            await self._send_to_waiting_queue(retry_job)
            logger.warning(
                "Requeued failed scan job",
                source_id=job_data.get("source_id"),
                attempts=attempts,
            )
    
    async def _run_crawl_with_semaphore(self, source_id: int):
        """Run a crawl with semaphore to limit concurrency."""
        async with self.crawl_semaphore:
            await self._execute_crawl(source_id)

    def _get_source_status(self, source_id: int) -> Optional[str]:
        """Get the persisted status for a source after a crawl."""
        db = get_db_session()
        try:
            source = db.query(Source).filter(Source.id == source_id).first()
            return source.status if source else None
        finally:
            db.close()
    
    async def _execute_crawl(self, source_id: int) -> bool:
        """Execute the actual crawl for a source."""
        self.refresh_runtime_settings()
        self.active_crawls.add(source_id)
        logger.info("Processing scan job", source_id=source_id, active_crawls=len(self.active_crawls))
        
        try:
            stats = await run_crawler(source_id)
            
            if stats.price_changes > 0:
                await send_notification(
                    f"Price changes detected for source {source_id}",
                    f"Found {stats.price_changes} price changes, "
                    f"{stats.products_found} new products, "
                    f"{stats.products_updated} updated products.",
                )
            
            logger.info("Scan job completed", source_id=source_id, stats=stats.to_dict())
            status = self._get_source_status(source_id)
            return status is not None and status != "failed"
            
        except Exception as e:
            logger.error("Scan job failed", source_id=source_id, error=str(e))
            return False
        finally:
            self.active_crawls.discard(source_id)
    
    async def poll_queue(self):
        """Poll Redis queue for new jobs."""
        loop = asyncio.get_running_loop()
        
        while self.running:
            try:
                # Non-blocking check if we have capacity
                if len(self.active_crawls) + len(self.crawl_tasks) >= settings.crawler_max_concurrent_sources:
                    await asyncio.sleep(1)
                    continue
                
                # Atomically move a job from the waiting queue into the processing queue.
                result = await loop.run_in_executor(
                    None, 
                    lambda: self.redis_client.brpoplpush(SCAN_QUEUE, SCAN_PROCESSING_QUEUE, timeout=1)
                )
                if result:
                    await self.process_queue_job(result)
            except redis.ConnectionError:
                logger.warning("Redis connection lost, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("Queue polling error", error=str(e))
                await asyncio.sleep(1)
    
    async def run_scheduled_scans(self):
        """Run scans for all active sources concurrently."""
        self.refresh_runtime_settings()
        logger.info("Running scheduled scans")
        
        db = get_db_session()
        enqueued = 0
        try:
            sources = db.query(Source).filter(Source.active == True).all()
            now = datetime.now(timezone.utc)
            for source in sources:
                if source.id in self.active_crawls or source.status == "scanning":
                    continue
                if source.next_retry_at and source.next_retry_at > now:
                    continue
                self.enqueue_scan_job(source.id, trigger="scheduled")
                enqueued += 1
        finally:
            db.close()

        logger.info("Scheduled scans enqueued", count=enqueued)

    async def check_stale_sources(self):
        """Send alerts for sources that haven't scanned within their stale window."""
        logger.info("Checking for stale sources")
        db = get_db_session()
        stale_alerts = []
        stale_source_ids: List[int] = []
        try:
            sources = db.query(Source).filter(Source.active == True).all()
            now = datetime.now(timezone.utc)
            for source in sources:
                alerts = source.alert_settings or {}
                stale_hours = alerts.get("stale_hours")
                if not stale_hours:
                    continue
                cutoff = now - timedelta(hours=stale_hours)
                last_scan = source.last_scan_at
                is_stale = last_scan is None or last_scan < cutoff
                has_stale_message = bool(source.status_message and source.status_message.startswith("Stale:"))
                if is_stale:
                    stale_source_ids.append(source.id)
                    if not has_stale_message:
                        hours_since = None
                        if last_scan:
                            delta_hours = (now - last_scan).total_seconds() / 3600
                            hours_since = max(int(delta_hours), stale_hours)
                        description = (
                            f"Stale: no scans in {hours_since or stale_hours}+ hours"
                        )
                        source.status_message = description
                        if alerts.get("notify_email") or alerts.get("notify_webhook"):
                            stale_alerts.append({
                                "source_id": source.id,
                                "source_name": source.name or source.domain,
                                "hours": hours_since or stale_hours,
                                "notify_email": alerts.get("notify_email", False),
                                "notify_webhook": alerts.get("notify_webhook", False),
                            })
                else:
                    if has_stale_message:
                        source.status_message = None
            db.commit()
        finally:
            db.close()

        for alert in stale_alerts:
            await send_notification(
                subject=f"Source {alert['source_name']} stale",
                body=(
                    f"Source {alert['source_name']} (ID {alert['source_id']}) has not run in "
                    f"{alert['hours']}+ hours."
                ),
                use_email=alert["notify_email"],
                use_webhook=alert["notify_webhook"],
            )
        
        # Reuse the durable queue path for stale source rescans.
        if stale_source_ids:
            for source_id in stale_source_ids:
                if source_id in self.active_crawls:
                    continue
                self.enqueue_scan_job(source_id, trigger="stale")
            logger.info("Stale source rescans enqueued", count=len(stale_source_ids))
    
    async def run_price_checks(self):
        """Check prices for products that haven't been checked in 48+ hours."""
        from sqlalchemy import func
        from urllib.parse import urlparse
        
        self.refresh_runtime_settings()
        logger.info("Running scheduled price checks")
        
        # Calculate cutoff time (48 hours ago with some random jitter)
        jitter_hours = random.uniform(-6, 6)  # Random jitter of +/- 6 hours
        cutoff = datetime.utcnow() - timedelta(hours=settings.price_check_interval_hours + jitter_hours)
        
        db = get_db_session()
        try:
            # Find products that need price checking
            # Get products where last_seen_at is older than cutoff or null
            products_to_check = db.query(Product).filter(
                Product.active == True,
                (Product.last_seen_at < cutoff) | (Product.last_seen_at == None)
            ).order_by(
                Product.last_seen_at.asc().nullsfirst()
            ).limit(settings.price_check_batch_size).all()
            
            if not products_to_check:
                logger.info("No products need price checking")
                return
            
            logger.info("Products to check", count=len(products_to_check))
            
            # Extract product IDs grouped by source (to avoid detached session issues)
            products_by_source = {}
            for product in products_to_check:
                if product.source_id not in products_by_source:
                    products_by_source[product.source_id] = []
                products_by_source[product.source_id].append(product.id)
            
        finally:
            db.close()
        
        # Process each source's products
        for source_id, product_ids in products_by_source.items():
            await self._check_product_prices(source_id, product_ids)
    
    async def _check_product_prices(self, source_id: int, product_ids: List[int]):
        """Check prices for a batch of products from a single source."""
        from worker.crawler.browser import requires_browser, fetch_with_browser
        from worker.crawler.vpn import vpn_manager
        import httpx
        
        logger.info("Checking prices for source", source_id=source_id, product_count=len(product_ids))
        
        db = get_db_session()
        try:
            source = db.query(Source).filter(Source.id == source_id).first()
            if not source:
                logger.error("Source not found", source_id=source_id)
                return
            
            for product_id in product_ids:
                product = db.query(Product).filter(Product.id == product_id).first()
                if not product:
                    continue
                try:
                    # Add random delay between requests (2-5 seconds)
                    await asyncio.sleep(random.uniform(settings.crawler_min_delay, settings.crawler_max_delay))
                    
                    url = product.canonical_url
                    logger.info("Checking price", product_id=product.id, url=url)
                    
                    # Fetch the product page
                    if requires_browser(url):
                        html, headers = await fetch_with_browser(url)
                    else:
                        proxy_url = vpn_manager.require_proxy() if vpn_manager.is_enabled else vpn_manager.get_proxy_url()
                        client_kwargs = {"timeout": settings.crawler_timeout}
                        if proxy_url:
                            client_kwargs["proxy"] = proxy_url
                        async with httpx.AsyncClient(**client_kwargs) as client:
                            response = await client.get(
                                url,
                                headers={
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en-US;q=0.7,en;q=0.6",
                                },
                                follow_redirects=True,
                            )
                            html = response.text
                            headers = dict(response.headers)
                    
                    # Parse the product page
                    from worker.parsers import get_parser
                    parser = get_parser(html, url, headers)
                    parsed_product = parser.parse_product(html, url)
                    
                    if parsed_product and parsed_product.price:
                        # Get the last price observation
                        last_observation = db.query(PriceObservation).filter(
                            PriceObservation.product_id == product.id
                        ).order_by(PriceObservation.observed_at.desc()).first()
                        
                        # Create new price observation
                        new_observation = PriceObservation(
                            product_id=product.id,
                            price_amount=parsed_product.price,
                            currency=parsed_product.currency,
                            list_price_amount=parsed_product.list_price,
                            in_stock=parsed_product.in_stock,
                        )
                        db.add(new_observation)
                        db.flush()
                        
                        # Check for price change
                        if last_observation and last_observation.price_amount:
                            old_price = float(last_observation.price_amount)
                            new_price = float(parsed_product.price)
                            if old_price != new_price:
                                change_percent = ((new_price - old_price) / old_price) * 100
                                product.latest_change_percent = change_percent
                                product.latest_change_type = "decrease" if change_percent < 0 else "increase"
                                product.latest_change_at = datetime.utcnow()
                                
                                logger.info("Price change detected",
                                    product=product.name,
                                    old_price=old_price,
                                    new_price=new_price,
                                    change_percent=round(change_percent, 2)
                                )
                        
                        # Update last_seen_at
                        product.last_seen_at = datetime.utcnow()
                        await trigger_price_alerts(db, product, new_observation)
                        db.commit()
                        
                        logger.info("Price check complete", product_id=product.id, price=float(parsed_product.price))
                    else:
                        # Still update last_seen_at even if no price found
                        product.last_seen_at = datetime.utcnow()
                        db.commit()
                        logger.warning("No price found", product_id=product.id, url=url)
                        
                except Exception as e:
                    logger.error("Price check failed", product_id=product.id, error=str(e))
                    db.rollback()
                    continue
                    
        finally:
            db.close()
    
    def setup_scheduler(self):
        """Setup the APScheduler for periodic scans."""
        self.refresh_runtime_settings()
        if not settings.scan_schedule_enabled:
            logger.info("Scheduled scans disabled")
            return
        
        cron_parts = settings.scan_schedule_cron.split()
        if len(cron_parts) == 5:
            trigger = CronTrigger(
                minute=cron_parts[0],
                hour=cron_parts[1],
                day=cron_parts[2],
                month=cron_parts[3],
                day_of_week=cron_parts[4],
            )
        else:
            trigger = CronTrigger(hour=6, minute=0)
        
        self.scheduler.add_job(
            self.run_scheduled_scans,
            trigger=trigger,
            id="scheduled_scans",
            name="Run scheduled scans for all active sources",
            replace_existing=True,
        )
        
        logger.info("Scheduler configured", cron=settings.scan_schedule_cron)
        
        # Setup price check scheduler (runs every 4 hours, checks products not seen in 48+ hours)
        if settings.price_check_enabled:
            # Add random jitter to the start time (0-60 minutes)
            jitter_minutes = random.randint(0, 60)
            
            self.scheduler.add_job(
                self.run_price_checks,
                trigger=IntervalTrigger(hours=4, jitter=3600),  # Run every 4 hours with up to 1 hour jitter
                id="price_checks",
                name="Check prices for products not seen in 48+ hours",
                replace_existing=True,
            )
            
            logger.info("Price check scheduler configured", 
                interval_hours=4, 
                check_interval_hours=settings.price_check_interval_hours,
                batch_size=settings.price_check_batch_size)

        # Stale source alert job (runs every 30 minutes)
        self.scheduler.add_job(
            self.check_stale_sources,
            trigger=IntervalTrigger(minutes=30, jitter=300),
            id="stale_source_alerts",
            name="Send alerts for stale sources",
            replace_existing=True,
        )
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received")
        self.running = False
        self.scheduler.shutdown(wait=False)

    async def _drain_crawl_tasks(self):
        """Wait for in-flight crawl tasks before exiting."""
        if not self.crawl_tasks:
            return

        pending = list(self.crawl_tasks)
        logger.info("Waiting for in-flight crawl tasks", count=len(pending))
        await asyncio.gather(*pending, return_exceptions=True)
    
    async def run(self):
        """Run the worker."""
        logger.info("Starting scan worker")
        self.refresh_runtime_settings()
        
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        # Initialize VPN from database configuration
        try:
            from worker.crawler.vpn import initialize_vpn_from_config
            await initialize_vpn_from_config()
        except Exception as e:
            logger.warning("VPN initialization failed (continuing without VPN)", error=str(e))
        
        self.recover_inflight_jobs()
        self.setup_scheduler()
        self.scheduler.start()
        
        await self.poll_queue()
        await self._drain_crawl_tasks()
        
        # Cleanup VPN on shutdown
        try:
            from worker.crawler.vpn import vpn_manager
            await vpn_manager.stop_auto_rotation()
            await vpn_manager.disconnect()
        except Exception:
            pass
        
        logger.info("Scan worker stopped")


def main():
    """Main entry point."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    
    worker = ScanWorker()
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
