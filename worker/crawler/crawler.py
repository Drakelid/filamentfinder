import asyncio
import fnmatch
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Set, Any
from urllib.parse import urlparse, urljoin
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from worker.config import get_settings
from worker.database import get_db_session
from worker.models import Source, Product, PriceObservation, PriceChange, CrawlRun
from worker.notifications import send_notification, trigger_price_alerts
from worker.parsers import (
    BaseParser,
    ParsedProduct,
    JsonLdParser,
    ShopifyParser,
    WooCommerceParser,
    MagentoParser,
    GenericParser,
)
from worker.crawler.robots import RobotsChecker
from worker.crawler.product_matcher import ProductMatcher
from worker.crawler.browser import requires_browser, fetch_with_browser
from worker.crawler.antibot import (
    antibot_manager,
    get_random_headers,
    get_adaptive_delay,
    record_request_result,
)

logger = structlog.get_logger(__name__)
settings = get_settings()


class CrawlStats:
    """Track crawl statistics."""
    
    def __init__(self):
        self.pages_visited = 0
        self.products_found = 0
        self.products_updated = 0
        self.price_changes = 0
        self.errors = 0
        self.error_messages: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pages_visited": self.pages_visited,
            "products_found": self.products_found,
            "products_updated": self.products_updated,
            "price_changes": self.price_changes,
            "errors": self.errors,
        }


class Crawler:
    """Main crawler class for scraping product data."""
    
    def __init__(self, source_id: int):
        self.source_id = source_id
        self.source: Optional[Source] = None
        self.crawl_run: Optional[CrawlRun] = None
        self.stats = CrawlStats()
        
        self.robots_checker = RobotsChecker()
        self.product_matcher = ProductMatcher()
        
        self.parsers: List[BaseParser] = [
            JsonLdParser(),
            ShopifyParser(),
            WooCommerceParser(),
            MagentoParser(),
            GenericParser(),
        ]
        self.parsers.sort(key=lambda p: p.priority, reverse=True)
        
        self.visited_urls: Set[str] = set()
        self.product_urls: Set[str] = set()
        self.pending_urls: List[tuple[str, int]] = []
        
        self._rate_limiter: Dict[str, float] = {}
        self._domain_delays: Dict[str, float] = {}
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        url = url.split('#')[0]
        if url.endswith('/'):
            url = url[:-1]
        return url
    
    def _matches_patterns(self, url: str, patterns: List[str], exclude: bool = False) -> bool:
        """Check if URL matches any of the patterns."""
        if not patterns:
            return not exclude
        
        for pattern in patterns:
            if fnmatch.fnmatch(url, pattern):
                return True
        return False
    
    # URLs containing these keywords are likely relevant to filament/resin
    RELEVANT_URL_KEYWORDS = [
        'filament', 'resin', 'pla', 'petg', 'abs', 'asa', 'tpu', 'nylon',
        '3d-print', '3dprint', '3d_print', 'fdm', 'sla', 'dlp', 'msla',
        'forbruksvarer', 'material', 'consumable', 'spool', 'printing',
        'printer-tilbehor', 'tilbehor', 'filamenter', 'product', 'products',
        'item', 'vare', 'produkt',
    ]
    
    # URLs containing these keywords should be excluded (unrelated categories)
    EXCLUDE_URL_KEYWORDS = [
        'drone', 'quadcopter', 'fpv', 'rc-', 'remote-control',
        'arduino', 'raspberry', 'elektronikk', 'electronic',
        'laser', 'cnc', 'router', 'engraver',
        'scanner', 'scan', 
        'clothing', 'apparel', 'shirt', 'hoodie',
        'book', 'magazine', 'manual', 'guide',
        'gift-card', 'giftcard', 'gavekort',
        'service', 'repair', 'reparasjon',
        'workshop', 'kurs', 'course',
        'used', 'brukt', 'second-hand',
        'bundle', 'pakke', 'starter-kit',
        'krympeplast', 'shrink', 'heat-shrink',
        'cable', 'kabel', 'wire', 'ledning',
        'tool', 'verktoy', 'verksted',
        'model-kit', 'modelkit', 'scale-model',
        'paint', 'maling', 'brush', 'pensel',
        'glue', 'lim', 'adhesive',
        'nozzle', 'nozzles', 'dyse', 'dyser', 'hotend', 'hot-end', 'heatbreak',
        'extruder', 'extruders', 'hotend-kit', 'nozzle-kit',
    ]
    
    def _is_url_relevant(self, url: str) -> bool:
        """Check if URL is likely relevant to filament/resin products."""
        url_lower = url.lower()
        
        # Check for exclusion keywords first
        for keyword in self.EXCLUDE_URL_KEYWORDS:
            if keyword in url_lower:
                return False
        
        # If URL contains relevant keywords, it's likely good
        for keyword in self.RELEVANT_URL_KEYWORDS:
            if keyword in url_lower:
                return True
        
        # For product pages (contain /product/, /vare/, etc.), allow them
        product_indicators = ['/product/', '/products/', '/vare/', '/item/', '/p/', '/produkt/']
        for indicator in product_indicators:
            if indicator in url_lower:
                return True
        
        # For category/collection pages, be more strict
        category_indicators = ['/category/', '/collection/', '/kategori/', '/filter/']
        for indicator in category_indicators:
            if indicator in url_lower:
                # Only allow if it also has relevant keywords
                return any(kw in url_lower for kw in self.RELEVANT_URL_KEYWORDS)
        
        # Default: allow if it's a product-like URL structure
        return True
    
    def _should_crawl_url(self, url: str) -> bool:
        """Determine if URL should be crawled based on rules."""
        if not self.source:
            return False
        
        rules = self.source.crawl_rules
        parsed = urlparse(url)
        
        if rules.get('same_domain_only', True):
            if parsed.netloc != self.source.domain and not parsed.netloc.endswith('.' + self.source.domain):
                return False
        
        url_patterns = rules.get('url_patterns', [])
        if url_patterns and not self._matches_patterns(url, url_patterns):
            return False
        
        exclude_patterns = rules.get('exclude_patterns', [])
        if exclude_patterns and self._matches_patterns(url, exclude_patterns):
            return False
        
        # Check URL relevance to filament/resin
        if not self._is_url_relevant(url):
            return False
        
        return True
    
    async def _rate_limit(self, domain: str):
        """Apply adaptive rate limiting for a domain based on anti-bot manager."""
        import random
        
        # Check if we should skip this domain temporarily
        should_skip, reason = antibot_manager.should_skip_domain(domain)
        if should_skip:
            logger.warning("Skipping domain temporarily", domain=domain, reason=reason)
            raise Exception(f"Domain temporarily blocked: {reason}")
        
        now = asyncio.get_event_loop().time()
        
        # Get adaptive delay from anti-bot manager
        delay = await get_adaptive_delay(domain)
        
        if domain in self._rate_limiter:
            elapsed = now - self._rate_limiter[domain]
            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug("Rate limiting", domain=domain, wait_seconds=round(wait_time, 2))
                await asyncio.sleep(wait_time)
        else:
            # First request to this domain, add a small initial delay
            await asyncio.sleep(random.uniform(1.0, 3.0))
        
        self._rate_limiter[domain] = asyncio.get_event_loop().time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    )
    async def _fetch_page(self, url: str) -> tuple[str, Dict[str, str]]:
        """Fetch a page with retries and rate limiting."""
        domain = self._get_domain(url)
        await self._rate_limit(domain)
        
        # Use browser for JavaScript-rendered sites
        if requires_browser(url):
            try:
                result = await fetch_with_browser(url, timeout=settings.crawler_timeout)
                record_request_result(domain, success=True)
                return result
            except Exception as e:
                is_blocked = "403" in str(e) or "blocked" in str(e).lower()
                record_request_result(domain, success=False, is_blocked=is_blocked)
                raise
        
        # Get randomized headers from anti-bot manager
        headers = get_random_headers(domain, url)
        
        # Check if VPN SOCKS5 proxy is enabled
        from worker.crawler.vpn import vpn_manager
        proxy_url = vpn_manager.require_proxy() if vpn_manager.is_enabled else vpn_manager.get_proxy_url()
        
        try:
            client_kwargs = {"timeout": settings.crawler_timeout}
            if proxy_url:
                client_kwargs["proxy"] = proxy_url
                logger.debug("Using SOCKS5 proxy", proxy=proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url)
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    follow_redirects=True,
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning("Rate limited (429)", url=url, retry_after=retry_after)
                    record_request_result(domain, success=False, status_code=429, is_blocked=True)
                    await asyncio.sleep(retry_after)
                    raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
                
                # Handle blocked responses
                if response.status_code == 403:
                    logger.warning("Forbidden (403)", url=url)
                    record_request_result(domain, success=False, status_code=403, is_blocked=True)
                    raise httpx.HTTPStatusError("Forbidden", request=response.request, response=response)
                
                # Handle service unavailable (often anti-bot)
                if response.status_code == 503:
                    logger.warning("Service unavailable (503)", url=url)
                    record_request_result(domain, success=False, status_code=503, is_blocked=True)
                    raise httpx.HTTPStatusError("Service unavailable", request=response.request, response=response)
                
                response.raise_for_status()
                
                # Check for soft blocks (CAPTCHA pages, etc.)
                content = response.text
                if self._is_soft_blocked(content):
                    logger.warning("Soft block detected (CAPTCHA/challenge page)", url=url)
                    record_request_result(domain, success=False, is_blocked=True)
                    raise Exception("Soft block detected - CAPTCHA or challenge page")
                
                # Success!
                record_request_result(domain, success=True)
                
                resp_headers = dict(response.headers)
                return content, resp_headers
                
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            record_request_result(domain, success=False)
            raise
    
    def _is_soft_blocked(self, content: str) -> bool:
        """Check if the response is a soft block (CAPTCHA, challenge page, etc.)."""
        content_lower = content.lower()
        
        # Common indicators of bot detection pages
        block_indicators = [
            "captcha",
            "robot check",
            "are you a robot",
            "verify you are human",
            "access denied",
            "blocked",
            "cloudflare",
            "ddos protection",
            "please wait while we verify",
            "checking your browser",
            "just a moment",
            "enable javascript and cookies",
            "unusual traffic",
            "automated access",
            "bot detected",
        ]
        
        for indicator in block_indicators:
            if indicator in content_lower:
                # Make sure it's not just a product description mentioning these words
                # Check if the page is very short (typical for block pages)
                if len(content) < 10000:
                    return True
        
        return False
    
    def _select_parser(self, html: str, url: str, headers: Dict[str, str]) -> BaseParser:
        """Select the best parser for the page."""
        overrides = self.source.selector_overrides if self.source else None
        for parser in self.parsers:
            if parser.can_parse(html, url, headers):
                parser.set_selector_overrides(overrides)
                return parser
        fallback = self.parsers[-1]
        fallback.set_selector_overrides(overrides)
        return fallback
    
    def _is_product_page(self, url: str, html: str) -> bool:
        """Heuristically determine if URL is a product page."""
        url_lower = url.lower()
        html_lower = html.lower()
        
        # Definitely NOT a product page if it's a homepage or category listing
        if url_lower.endswith('/') and url_lower.count('/') <= 3:
            return False
        
        # Category/listing page indicators - if present, NOT a product page
        listing_indicators = ['/category/', '/categories/', '/collection/', '/collections/', '/search', '?filter=', '&filter=', '?page=', '&page=']
        for indicator in listing_indicators:
            if indicator in url_lower:
                return False
        
        # URL-based detection for product pages
        product_indicators = ['/product/', '/products/', '/p/', '/item/', '/dp/', '/-p-', '/pd/']
        for indicator in product_indicators:
            if indicator in url_lower:
                return True
        
        # Check for product schema markup (single product) - most reliable indicator
        product_schema_count = html_lower.count('"@type":"product"') + html_lower.count('"@type": "product"')
        if product_schema_count == 1:
            return True
        
        # Count "add to cart" occurrences - multiple means listing page
        add_to_cart_patterns = ['add to cart', 'add-to-cart', 'addtocart', 'add to basket', 'add-to-basket', 'legg i handlekurv', 'legg til i handlekurv', 'legg i handlevogn', 'legg til i handlevogn', 'kjøp nå', 'buy now']
        add_to_cart_count = sum(html_lower.count(p) for p in add_to_cart_patterns)
        
        # Check for single product page indicators in HTML
        single_product_indicators = [
            'itemprop="price"',
            'class="product-price"',
            'class="product-detail"',
            'class="product-info"',
            'class="product-page"',
            'id="product-',
            'data-product-id',
            'product-single',
            'product-template',
        ]
        single_product_score = sum(1 for ind in single_product_indicators if ind in html_lower)
        
        # If there's exactly 1 add-to-cart and URL has 2+ path segments, likely a product page
        if add_to_cart_count == 1:
            path_segments = [s for s in urlparse(url_lower).path.split('/') if s]
            if len(path_segments) >= 2:
                return True
        
        # If we have strong single-product indicators and few add-to-cart buttons
        if single_product_score >= 2 and add_to_cart_count <= 2:
            return True
        
        # If URL has a long path with product-like structure (brand/sku/name pattern)
        path_segments = [s for s in urlparse(url_lower).path.split('/') if s]
        if len(path_segments) >= 3:
            # Check if any segment looks like a SKU (alphanumeric mix)
            for segment in path_segments:
                if re.match(r'^[a-z]{2,4}\d{2,}[a-z]*\d*$', segment) or re.match(r'^\d{5,}$', segment):
                    return True
            # If add-to-cart count is low, likely a product page
            if add_to_cart_count <= 2:
                return True

        # ASP.NET product pages (e.g., avxperten.no) — every .asp slug is a product page;
        # non-product .asp pages (contact, about) return None from parse_product which is harmless.
        if url_lower.endswith('.asp'):
            return True

        return False
    
    async def _process_product(self, product: ParsedProduct, parser_name: str, page_url: str = '') -> Optional[Product]:
        """Process a parsed product and save to database."""
        source_url = self.source.url if self.source else ''
        match_result = self.product_matcher.match(product, source_url=source_url)
        
        logger.info(
            "Product match result",
            name=product.name[:80] if product.name else None,
            is_match=match_result.is_match,
            category=match_result.category,
            confidence=match_result.confidence,
            matched_keywords=match_result.matched_keywords,
            parser=parser_name,
        )
        
        if not match_result.is_match:
            return None
        
        product.category = match_result.category
        product.product_type = match_result.product_type
        product.confidence = match_result.confidence * product.confidence
        
        db = get_db_session()
        try:
            existing = db.query(Product).filter(
                Product.source_id == self.source_id,
                Product.canonical_url == product.url,
            ).first()
            
            now = datetime.now(timezone.utc)
            
            # Absolutize image URL if it came through as a relative path
            if product.image_url and not product.image_url.startswith('http'):
                product.image_url = urljoin(product.url or '', product.image_url) or None
            # Discard obviously broken image URLs (root-relative with no host after urljoin)
            if product.image_url and not product.image_url.startswith('http'):
                product.image_url = None

            if existing:
                existing.name = product.name
                existing.brand = product.brand
                existing.category = product.category
                existing.product_type = product.product_type
                existing.variant = product.variant
                existing.color = product.color
                existing.size = product.size
                # Only update image_url if the new parse actually found one; don't clobber a
                # valid existing URL with None when a detail page simply has no image selector match.
                existing.image_url = product.image_url or existing.image_url
                existing.sku = product.sku
                existing.gtin = product.gtin
                existing.confidence = product.confidence
                existing.raw_data_json = product.raw_data
                existing.last_seen_at = now
                existing.active = True
                
                db_product = existing
                self.stats.products_updated += 1
            else:
                db_product = Product(
                    source_id=self.source_id,
                    canonical_url=product.url,
                    name=product.name,
                    brand=product.brand,
                    category=product.category,
                    product_type=product.product_type,
                    variant=product.variant,
                    color=product.color,
                    size=product.size,
                    image_url=product.image_url,
                    sku=product.sku,
                    gtin=product.gtin,
                    confidence=product.confidence,
                    raw_data_json=product.raw_data,
                    last_seen_at=now,
                    active=True,
                )
                db.add(db_product)
                db.flush()
                self.stats.products_found += 1
            
            last_observation = db.query(PriceObservation).filter(
                PriceObservation.product_id == db_product.id
            ).order_by(PriceObservation.observed_at.desc()).first()
            
            observation = PriceObservation(
                product_id=db_product.id,
                observed_at=now,
                price_amount=product.price,
                currency=product.currency,
                list_price_amount=product.list_price,
                in_stock=product.in_stock,
                raw_json=product.to_dict(),
                crawl_run_id=self.crawl_run.id if self.crawl_run else None,
            )
            db.add(observation)
            db.flush()
            
            if last_observation:
                price_changed = (
                    last_observation.price_amount != product.price or
                    last_observation.currency != product.currency
                )
                
                if price_changed and (last_observation.price_amount or product.price):
                    change_percent = None
                    if last_observation.price_amount and product.price:
                        change_percent = float(
                            (product.price - last_observation.price_amount) / 
                            last_observation.price_amount * 100
                        )
                    
                    change_type = "price_change"
                    if last_observation.price_amount and product.price:
                        if product.price < last_observation.price_amount:
                            change_type = "price_decrease"
                        else:
                            change_type = "price_increase"
                    elif not product.price:
                        change_type = "price_removed"
                    elif not last_observation.price_amount:
                        change_type = "price_added"
                    
                    price_change = PriceChange(
                        product_id=db_product.id,
                        changed_at=now,
                        old_price=last_observation.price_amount,
                        new_price=product.price,
                        old_currency=last_observation.currency,
                        new_currency=product.currency,
                        change_type=change_type,
                        change_percent=change_percent,
                    )
                    db.add(price_change)
                    self.stats.price_changes += 1
                    
                    db_product.latest_change_percent = change_percent
                    db_product.latest_change_type = change_type
                    db_product.latest_change_at = now
                    
                    logger.info(
                        "Price change detected",
                        product=product.name,
                        old_price=float(last_observation.price_amount) if last_observation.price_amount else None,
                        new_price=float(product.price) if product.price else None,
                        change_percent=change_percent,
                    )

            await trigger_price_alerts(db, db_product, observation)
            
            db.commit()
            return db_product
            
        except Exception as e:
            db.rollback()
            logger.error("Failed to save product", error=str(e), product=product.name)
            raise
        finally:
            db.close()
    
    async def _crawl_page(self, url: str, depth: int) -> List[str]:
        """Crawl a single page and return discovered URLs."""
        normalized_url = self._normalize_url(url)
        if normalized_url in self.visited_urls:
            return []
        
        self.visited_urls.add(normalized_url)
        
        if self.source and self.source.crawl_rules.get('respect_robots_txt', True):
            if not await self.robots_checker.is_allowed(url):
                logger.info("URL disallowed by robots.txt", url=url)
                return []
        
        try:
            html, headers = await self._fetch_page(url)
            self.stats.pages_visited += 1
            logger.info("Fetched page", url=url, html_length=len(html))
        except Exception as e:
            self.stats.errors += 1
            self.stats.error_messages.append(f"Failed to fetch {url}: {str(e)}")
            logger.error("Failed to fetch page", url=url, error=str(e))
            return []
        
        parser = self._select_parser(html, url, headers)
        logger.info("Selected parser", parser=parser.name, url=url)
        
        discovered_urls = []
        
        is_product = self._is_product_page(url, html)

        try:
            if is_product:
                logger.info("Detected as product page", url=url)
                product = parser.parse_product(html, url)
                if product:
                    logger.info("Parsed product", name=product.name[:80] if product.name else None, price=float(product.price) if product.price else None)
                    await self._process_product(product, parser.name, page_url=url)
                else:
                    logger.info("No product parsed from page", url=url)
            else:
                logger.info("Detected as listing page", url=url)
                products = parser.parse_product_list(html, url)
                logger.info("Parsed products from listing", count=len(products), sample_names=[p.name[:50] for p in products[:3]] if products else [])
                for product in products:
                    saved = await self._process_product(product, parser.name, page_url=url)
                    if saved:
                        logger.info("Product saved to database", name=product.name[:50] if product.name else None)

                product_links = parser.extract_product_links(html, url)
                logger.info("Extracted product links", count=len(product_links), sample=product_links[:3] if product_links else [])
                for link in product_links:
                    if self._should_crawl_url(link):
                        discovered_urls.append(link)
                    else:
                        logger.debug("Link filtered by crawl rules", link=link)

                if depth < self.source.crawl_rules.get('max_depth', 3):
                    pagination_links = parser.extract_pagination_links(html, url)
                    logger.info("Extracted pagination links", count=len(pagination_links))
                    for link in pagination_links:
                        if self._should_crawl_url(link):
                            discovered_urls.append(link)
        except Exception as e:
            self.stats.errors += 1
            self.stats.error_messages.append(f"Failed to parse {url}: {str(e)}")
            logger.error("Failed to parse page", url=url, parser=parser.name, error=str(e))
            return []
        
        logger.info("Discovered URLs to crawl", count=len(discovered_urls), sample=discovered_urls[:5] if discovered_urls else [])
        return discovered_urls
    
    async def _mark_missing_products(self):
        """Mark products not seen in recent crawls as inactive.

        Products that were not seen in the last 3 days are marked inactive.
        This prevents stale products from polluting price comparisons.
        """
        STALE_DAYS = 3
        db = get_db_session()
        try:
            if not self.crawl_run:
                return

            now = datetime.now(timezone.utc)
            stale_cutoff = now - timedelta(days=STALE_DAYS)

            stale_products = db.query(Product).filter(
                Product.source_id == self.source_id,
                Product.active == True,
                Product.last_seen_at < stale_cutoff,
            ).all()

            deactivated = 0
            for product in stale_products:
                product.active = False
                deactivated += 1

            if deactivated:
                logger.info(
                    "Deactivated stale products",
                    source_id=self.source_id,
                    count=deactivated,
                    stale_days=STALE_DAYS,
                )

            db.commit()
        finally:
            db.close()
    
    async def run(self) -> CrawlStats:
        """Run the crawler for the source."""
        db = get_db_session()
        try:
            self.source = db.query(Source).filter(Source.id == self.source_id).first()
            if not self.source:
                raise ValueError(f"Source {self.source_id} not found")
            
            if not self.source.active:
                raise ValueError(f"Source {self.source_id} is not active")
            
            self.crawl_run = CrawlRun(
                source_id=self.source_id,
                status="running",
            )
            db.add(self.crawl_run)
            db.commit()
            db.refresh(self.crawl_run)
            
            self.source.status = "scanning"
            db.commit()
            
            crawl_run_id = self.crawl_run.id
            source_url = self.source.url
            max_pages = self.source.crawl_rules.get('max_pages', settings.crawler_max_pages)
            
        finally:
            db.close()
        
        logger.info("Starting crawl", source_id=self.source_id, url=source_url)
        
        try:
            self.pending_urls.append((source_url, 0))
            
            while self.pending_urls and self.stats.pages_visited < max_pages:
                url, depth = self.pending_urls.pop(0)
                
                discovered = await self._crawl_page(url, depth)
                
                # Separate product URLs from category/filter URLs
                product_urls = []
                other_urls = []
                for new_url in discovered:
                    normalized = self._normalize_url(new_url)
                    if normalized not in self.visited_urls:
                        # Prioritize product-like URLs (no filter params, has SKU-like segments)
                        url_lower = new_url.lower()
                        if '?filter=' in url_lower or '&filter=' in url_lower or '?page=' in url_lower:
                            other_urls.append((new_url, depth + 1))
                        elif re.search(r'/[a-z]{2,4}\d{2,}[a-z]*/', url_lower) or '/product' in url_lower:
                            product_urls.append((new_url, depth + 1))
                        else:
                            other_urls.append((new_url, depth + 1))
                
                # Add product URLs first (at front of queue), then other URLs
                self.pending_urls = product_urls + self.pending_urls + other_urls
            
            await self._mark_missing_products()
            
            status = "completed"
            
        except Exception as e:
            logger.error("Crawl failed", error=str(e))
            self.stats.errors += 1
            self.stats.error_messages.append(str(e))
            status = "failed"
        
        db = get_db_session()
        failure_alert_payload = None
        try:
            now = datetime.now(timezone.utc)
            crawl_run = db.query(CrawlRun).filter(CrawlRun.id == crawl_run_id).first()
            if crawl_run:
                crawl_run.finished_at = now
                crawl_run.status = status
                crawl_run.pages_visited = self.stats.pages_visited
                crawl_run.products_found = self.stats.products_found
                crawl_run.products_updated = self.stats.products_updated
                crawl_run.price_changes_detected = self.stats.price_changes
                crawl_run.errors_count = self.stats.errors
                crawl_run.error_messages = self.stats.error_messages if self.stats.error_messages else None
                crawl_run.stats_json = self.stats.to_dict()

            source = db.query(Source).filter(Source.id == self.source_id).first()
            if source:
                source.status = status
                source.last_scan_at = now

                duration_seconds = None
                if crawl_run and crawl_run.finished_at and crawl_run.started_at:
                    duration_seconds = (crawl_run.finished_at - crawl_run.started_at).total_seconds()

                # Update duration stats
                if duration_seconds is not None:
                    stats = source.crawl_duration_stats or {}
                    previous_avg = stats.get("avg_seconds")
                    if previous_avg is None:
                        avg_seconds = duration_seconds
                    else:
                        avg_seconds = (previous_avg + duration_seconds) / 2

                    p95 = stats.get("p95_seconds")
                    if p95 is None:
                        p95_seconds = duration_seconds
                    else:
                        p95_seconds = max(p95, duration_seconds * 0.95 + p95 * 0.05)

                    stats_update = {
                        "avg_seconds": avg_seconds,
                        "p95_seconds": p95_seconds,
                        "last_seconds": duration_seconds,
                    }
                    source.crawl_duration_stats_json = stats_update

                # Update retry/failure tracking
                retry_policy = source.retry_policy
                track_statuses = retry_policy.get("retry_statuses", ["failed"])
                alerts = source.alert_settings
                should_track = status in track_statuses
                if should_track and status == "failed":
                    source.failure_streak = (source.failure_streak or 0) + 1
                    backoff = retry_policy.get("backoff_seconds", 300)
                    source.next_retry_at = now + timedelta(seconds=backoff)
                    if alerts and source.failure_streak >= alerts.get("failure_threshold", 3):
                        if alerts.get("notify_email") or alerts.get("notify_webhook"):
                            failure_alert_payload = {
                                "source_id": source.id,
                                "source_name": source.name or source.domain,
                                "failure_streak": source.failure_streak,
                                "notify_email": alerts.get("notify_email", False),
                                "notify_webhook": alerts.get("notify_webhook", False),
                            }
                            source.status_message = f"{source.failure_streak} consecutive failures"
                else:
                    source.failure_streak = 0
                    source.next_retry_at = None
                    if source.status_message and "consecutive failures" in source.status_message:
                        source.status_message = None

            db.commit()
        finally:
            db.close()
        
        if failure_alert_payload:
            await send_notification(
                subject=f"Source {failure_alert_payload['source_name']} failing",
                body=(
                    f"Source {failure_alert_payload['source_name']} (ID {failure_alert_payload['source_id']}) "
                    f"has {failure_alert_payload['failure_streak']} consecutive failed crawls."
                ),
                use_email=failure_alert_payload["notify_email"],
                use_webhook=failure_alert_payload["notify_webhook"],
            )
        
        logger.info(
            "Crawl completed",
            source_id=self.source_id,
            status=status,
            pages=self.stats.pages_visited,
            products_found=self.stats.products_found,
            price_changes=self.stats.price_changes,
        )
        
        return self.stats


async def run_crawler(source_id: int) -> CrawlStats:
    """Run crawler for a source."""
    crawler = Crawler(source_id)
    return await crawler.run()
