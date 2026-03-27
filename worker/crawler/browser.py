"""Browser-based page fetching for JavaScript-rendered sites."""
import asyncio
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse
import structlog

logger = structlog.get_logger(__name__)

# Domains that require JavaScript rendering or block regular HTTP requests
JS_RENDERED_DOMAINS = {
    'elefun.no',
    'computersalg.no',
    'clasohlson.com',
    '3djake.no',       # Products loaded via JS
    'proshop.no',      # Blocks regular HTTP requests with 403
    '3dnet.no',        # JSON-LD ItemList loaded via JS
    'polyalkemi.no',   # Custom Knockout.js platform with JS-loaded content
    'multicom.no',     # JS-rendered product listings
    'csmegastore.no',  # Products loaded via JS (empty Items array in static HTML)
}

DOMAIN_READY_SELECTORS = {
    'elefun.no': [
        '.category_prod',
        '.category_prod_name',
        'a[href*="/vare-"]',
    ],
    'polyalkemi.no': [
        # polyalkemi.no uses a custom Knockout.js platform — NOT WooCommerce.
        # Wait for the rendered product card container.
        '.WebPubElement.pub-productlisting',
        '.pub-productlisting',
        '.ad-buy-button',  # "Kjøp" buttons confirm products have loaded
    ],
    '3dnet.no': [
        '.thumbnail[itemtype*="Product"]',
        '.product-wrap',
        'script[type="application/ld+json"]',
    ],
    'proshop.no': [
        '.site-productlist-item',
        '.site-currency-lg',
    ],
    '3djake.no': [
        '[data-json]',
        '[data-product]',
    ],
    'multicom.no': [
        '.product-list-item',
        '.product-item',
        'li[class*="product"]',
        '[class*="price"]',
    ],
    'csmegastore.no': [
        # Products are rendered via JS; wait for product anchor links
        'a[href*="/i/"]',
        '[class*="product"]',
        'h3',
    ],
}


def requires_browser(url: str) -> bool:
    """Check if URL requires browser rendering.

    Checks both the hardcoded JS_RENDERED_DOMAINS set and any extra domains
    added at runtime via the crawler_js_domains config setting.
    """
    from urllib.parse import urlparse
    from worker.config import get_settings
    domain = urlparse(url).netloc.lower()

    all_domains = set(JS_RENDERED_DOMAINS)
    extra = get_settings().crawler_js_domains
    if extra:
        for d in extra.split(','):
            d = d.strip().lower()
            if d:
                all_domains.add(d)

    for js_domain in all_domains:
        if domain == js_domain or domain.endswith('.' + js_domain):
            return True
    return False


async def fetch_with_browser(url: str, timeout: int = 30) -> Tuple[str, Dict[str, str]]:
    """Fetch page using Playwright browser for JavaScript rendering with anti-bot evasion."""
    import random
    from playwright.async_api import async_playwright
    from worker.crawler.antibot import antibot_manager
    from worker.crawler.vpn import vpn_manager
    
    domain = urlparse(url).netloc.lower()
    logger.info("Fetching with browser", url=url, domain=domain)
    
    # Get browser context options from anti-bot manager
    context_options = antibot_manager.get_browser_context_options(domain)
    
    async with async_playwright() as p:
        proxy = vpn_manager.get_playwright_proxy()
        if vpn_manager.is_enabled and not proxy and not getattr(vpn_manager, "_gluetun_enabled", False):
            raise RuntimeError("VPN is enabled but Playwright has no proxy configuration")

        # Launch with additional stealth options
        browser = await p.chromium.launch(
            headless=True,
            proxy=proxy,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-infobars',
                '--window-position=0,0',
                '--ignore-certificate-errors',
                '--ignore-certificate-errors-spki-list',
            ]
        )
        try:
            context = await browser.new_context(**context_options)
            
            # Add stealth scripts to evade detection
            await context.add_init_script("""
                // Override webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['nb-NO', 'nb', 'no', 'en-US', 'en']
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Override chrome property
                window.chrome = {
                    runtime: {}
                };
                
                // Override connection property
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false
                    })
                });
            """)
            
            page = await context.new_page()
            
            # Simulate human-like mouse movement before navigation
            await page.mouse.move(
                random.randint(100, 500),
                random.randint(100, 400)
            )
            
            # DOMContentLoaded is more reliable than networkidle on pages with long-lived analytics calls.
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)

            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout * 1000 // 2, 10000))
            except Exception:
                logger.debug("Network idle wait skipped", url=url, domain=domain)
            
            # Wait a random amount of time to appear more human-like
            await asyncio.sleep(random.uniform(1.5, 3.5))
            
            # Simulate human-like scrolling pattern
            scroll_patterns = antibot_manager.get_human_scroll_pattern()
            for pattern in scroll_patterns[:10]:  # Limit to first 10 scroll actions
                await page.evaluate(f"window.scrollTo(0, {pattern['y']})")
                await asyncio.sleep(pattern['pause'])
            
            # Random mouse movements while "reading"
            mouse_patterns = antibot_manager.get_mouse_movement_pattern()
            for movement in mouse_patterns[:5]:  # Limit to 5 movements
                await page.mouse.move(movement['x'], movement['y'])
                await asyncio.sleep(movement['duration'])
            
            # Wait for any lazy-loaded content
            await asyncio.sleep(random.uniform(0.5, 1.5))

            ready_selectors = DOMAIN_READY_SELECTORS.get(domain, [])
            for selector in ready_selectors:
                try:
                    await page.wait_for_selector(selector, state="attached", timeout=5000)
                    logger.info("Browser content selector matched", url=url, domain=domain, selector=selector)
                    break
                except Exception:
                    continue
            
            html = await page.content()
            
            headers = {}
            if response:
                headers = {k.lower(): v for k, v in response.headers.items()}
            
            logger.info("Browser fetch complete", url=url, html_length=len(html))
            return html, headers
            
        finally:
            await browser.close()
