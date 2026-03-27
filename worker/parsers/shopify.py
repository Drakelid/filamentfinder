import json
import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

from worker.parsers.base import BaseParser, ParsedProduct


class ShopifyParser(BaseParser):
    """Parser for Shopify stores."""
    
    name = "shopify"
    priority = 90
    
    SHOPIFY_INDICATORS = [
        'cdn.shopify.com',
        'Shopify.theme',
        'shopify-section',
        '/cart.js',
        'shopify_analytics',
        'myshopify.com',
    ]
    
    def can_parse(self, html: str, url: str, headers: Dict[str, str]) -> bool:
        """Check if this is a Shopify store."""
        html_lower = html.lower()
        
        for indicator in self.SHOPIFY_INDICATORS:
            if indicator.lower() in html_lower:
                return True
        
        server = headers.get('server', '').lower()
        if 'shopify' in server:
            return True
        
        if headers.get('x-shopify-stage'):
            return True
        
        return False
    
    def _extract_product_json(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract product JSON from Shopify page."""
        patterns = [
            r'var\s+meta\s*=\s*(\{.*?"product".*?\});',
            r'window\.ShopifyAnalytics\.meta\s*=\s*(\{.*?\});',
            r'"product"\s*:\s*(\{.*?\})\s*[,}]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if 'product' in data:
                        return data['product']
                    return data
                except json.JSONDecodeError:
                    continue
        
        script_pattern = r'<script[^>]*type="application/json"[^>]*data-product-json[^>]*>(.*?)</script>'
        match = re.search(script_pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _parse_shopify_product(self, data: Dict[str, Any], url: str) -> Optional[ParsedProduct]:
        """Parse Shopify product JSON."""
        title = data.get('title', '')
        if not title:
            return None
        
        variants = data.get('variants', [])
        first_variant = variants[0] if variants else {}
        
        price = None
        list_price = None
        
        price_str = first_variant.get('price') or data.get('price')
        if price_str:
            if isinstance(price_str, (int, float)):
                price = self._adjust_store_price(Decimal(str(price_str)) / 100, url)
            else:
                price = self._clean_price(str(price_str))
        
        compare_price = first_variant.get('compare_at_price') or data.get('compare_at_price')
        if compare_price:
            if isinstance(compare_price, (int, float)):
                list_price = self._adjust_store_price(Decimal(str(compare_price)) / 100, url)
            else:
                list_price = self._clean_price(str(compare_price))
        
        in_stock = first_variant.get('available', True)
        
        image_url = None
        images = data.get('images', [])
        if images:
            if isinstance(images[0], dict):
                image_url = images[0].get('src')
            else:
                image_url = images[0]
        if not image_url:
            image_url = data.get('featured_image')
        
        sku = first_variant.get('sku')
        gtin = first_variant.get('barcode')
        
        vendor = data.get('vendor')
        
        product_url = data.get('url')
        if product_url and not product_url.startswith('http'):
            parsed = urlparse(url)
            product_url = f"{parsed.scheme}://{parsed.netloc}{product_url}"
        if not product_url:
            product_url = url
        
        variant_title = first_variant.get('title', '')
        if variant_title and variant_title != 'Default Title':
            variant = variant_title
        else:
            variant = None
        
        return ParsedProduct(
            name=title,
            url=product_url,
            price=price,
            currency=self._extract_currency('', url=url),
            list_price=list_price,
            brand=vendor,
            variant=variant,
            image_url=image_url,
            sku=str(sku) if sku else None,
            gtin=str(gtin) if gtin else None,
            in_stock=in_stock,
            confidence=0.85,
            raw_data=data,
        )
    
    def parse_product(self, html: str, url: str) -> Optional[ParsedProduct]:
        """Parse a single Shopify product page."""
        product_data = self._extract_product_json(html)
        if product_data:
            return self._parse_shopify_product(product_data, url)
        return None
    
    def parse_product_list(self, html: str, url: str) -> List[ParsedProduct]:
        """Parse a Shopify collection page."""
        products = []
        
        collection_pattern = r'"products"\s*:\s*(\[.*?\])\s*[,}]'
        match = re.search(collection_pattern, html, re.DOTALL)
        if match:
            try:
                products_data = json.loads(match.group(1))
                for product_data in products_data:
                    product = self._parse_shopify_product(product_data, url)
                    if product:
                        products.append(product)
            except json.JSONDecodeError:
                pass
        
        return products
    
    def extract_product_links(self, html: str, url: str) -> List[str]:
        """Extract product links from a Shopify collection page."""
        soup = self._get_soup(html)
        links = set()
        
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/products/' in href:
                if href.startswith('/'):
                    href = base_url + href
                elif not href.startswith('http'):
                    href = urljoin(url, href)
                
                href = href.split('?')[0].split('#')[0]
                links.add(href)
        
        return list(links)
    
    def extract_pagination_links(self, html: str, url: str) -> List[str]:
        """Extract pagination links from a Shopify collection page."""
        soup = self._get_soup(html)
        links = set()
        
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        pagination_selectors = [
            '.pagination a',
            '.paginate a',
            'nav.pagination a',
            '[aria-label="Pagination"] a',
            '.collection-pagination a',
        ]
        
        for selector in pagination_selectors:
            for a in soup.select(selector):
                href = a.get('href')
                if href:
                    if href.startswith('/'):
                        href = base_url + href
                    elif not href.startswith('http'):
                        href = urljoin(url, href)
                    links.add(href)
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'page=' in href or '/page/' in href:
                if href.startswith('/'):
                    href = base_url + href
                elif not href.startswith('http'):
                    href = urljoin(url, href)
                links.add(href)
        
        return list(links)
