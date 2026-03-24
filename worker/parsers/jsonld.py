import json
import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

from worker.parsers.base import BaseParser, ParsedProduct


class JsonLdParser(BaseParser):
    """Parser for JSON-LD structured data (schema.org/Product)."""
    
    name = "jsonld"
    priority = 100
    
    def can_parse(self, html: str, url: str, headers: Dict[str, str]) -> bool:
        """Check if page contains JSON-LD product data."""
        return 'application/ld+json' in html and ('Product' in html or 'product' in html.lower())
    
    def _extract_jsonld(self, html: str) -> List[Dict[str, Any]]:
        """Extract all JSON-LD blocks from HTML."""
        soup = self._get_soup(html)
        scripts = soup.find_all('script', type='application/ld+json')
        
        results = []
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    results.extend(data)
                else:
                    results.append(data)
            except (json.JSONDecodeError, TypeError):
                continue
        
        return results
    
    def _find_products(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find Product objects in JSON-LD data."""
        products = []
        
        def search(obj, depth=0):
            if depth > 10:
                return
            
            if isinstance(obj, dict):
                obj_type = obj.get('@type', '')
                if isinstance(obj_type, list):
                    obj_type = ' '.join(obj_type)
                
                if 'Product' in str(obj_type):
                    products.append(obj)
                
                if '@graph' in obj:
                    search(obj['@graph'], depth + 1)
                
                for value in obj.values():
                    search(value, depth + 1)
            
            elif isinstance(obj, list):
                for item in obj:
                    search(item, depth + 1)
        
        search(data)
        return products
    
    def _parse_product_data(self, data: Dict[str, Any], url: str) -> Optional[ParsedProduct]:
        """Parse a JSON-LD Product object."""
        name = data.get('name', '')
        if not name:
            return None
        
        offers = data.get('offers', {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        
        price = None
        currency = None
        list_price = None
        in_stock = None
        
        if offers:
            price_str = offers.get('price') or offers.get('lowPrice')
            if price_str:
                price = self._clean_price(str(price_str))
            
            currency = offers.get('priceCurrency')
            # Fall back to URL-based currency detection if not in JSON-LD
            if not currency:
                currency = self._extract_currency(str(price_str) if price_str else '', url)
            
            high_price = offers.get('highPrice')
            if high_price and high_price != price_str:
                list_price = self._clean_price(str(high_price))
            
            availability = offers.get('availability', '')
            if availability:
                in_stock = 'InStock' in availability or 'instock' in availability.lower()
        
        brand = None
        brand_data = data.get('brand', {})
        if isinstance(brand_data, dict):
            brand = brand_data.get('name')
        elif isinstance(brand_data, str):
            brand = brand_data
        
        image_url = None
        image = data.get('image')
        if isinstance(image, list):
            first_image = image[0] if image else None
            if isinstance(first_image, dict):
                image_url = first_image.get('url') or first_image.get('@id')
            elif isinstance(first_image, str):
                image_url = first_image
        elif isinstance(image, dict):
            image_url = image.get('url') or image.get('@id')
        elif isinstance(image, str):
            image_url = image
        
        # Ensure image_url is a string, not a dict
        if isinstance(image_url, dict):
            image_url = image_url.get('url') or image_url.get('@id') or None
        
        sku = data.get('sku')
        gtin = data.get('gtin') or data.get('gtin13') or data.get('gtin12') or data.get('gtin8')
        
        product_url = data.get('url') or offers.get('url') or url
        
        return ParsedProduct(
            name=name,
            url=product_url,
            price=price,
            currency=currency,
            list_price=list_price,
            brand=brand,
            image_url=image_url,
            sku=str(sku) if sku else None,
            gtin=str(gtin) if gtin else None,
            in_stock=in_stock,
            confidence=0.9,
            raw_data=data,
        )
    
    def parse_product(self, html: str, url: str) -> Optional[ParsedProduct]:
        """Parse a single product page."""
        jsonld_data = self._extract_jsonld(html)
        products = self._find_products(jsonld_data)
        
        if products:
            return self._parse_product_data(products[0], url)
        return None
    
    def parse_product_list(self, html: str, url: str) -> List[ParsedProduct]:
        """Parse a category/list page for products."""
        jsonld_data = self._extract_jsonld(html)
        products = self._find_products(jsonld_data)
        
        parsed = []
        for product_data in products:
            product = self._parse_product_data(product_data, url)
            if product:
                parsed.append(product)
        
        # If JSON-LD didn't yield products, fall back to data-json extraction (used by 3DJake etc)
        if not parsed:
            parsed = self._extract_from_data_json(html, url)
        
        return parsed
    
    def _extract_from_data_json(self, html: str, url: str) -> List[ParsedProduct]:
        """Extract products from data-json attributes (used by 3DJake and similar sites)."""
        from urllib.parse import urljoin
        soup = self._get_soup(html)
        products = []
        
        # Find elements with data-json containing product info
        elements_with_json = soup.select('[data-json]')
        
        for elem in elements_with_json:
            try:
                data = json.loads(elem.get('data-json', '{}'))
                
                # Check if this looks like product data
                if not data.get('name') and not data.get('id'):
                    continue
                
                name = data.get('name', '')
                brand = data.get('brand', '')
                
                if not name:
                    continue
                
                # Find the product URL from a link in this element
                link = elem.find('a', href=True)
                product_url = ''
                if link:
                    product_url = link.get('href', '')
                    if product_url and not product_url.startswith('http'):
                        product_url = urljoin(url, product_url)
                
                # Try to find price in the element - get the current/sale price, not the old price
                price = None
                currency = None
                # Try specific price selectors first (current price, not crossed-out)
                price_elem = elem.select_one('.price--reduced, .price-current, .sale-price, .current-price')
                if not price_elem:
                    # Fall back to first price span that's not a strikethrough/old price
                    price_container = elem.select_one('[class*="price"]')
                    if price_container:
                        # Get the first span that's not an "instead" or "old" price
                        for span in price_container.find_all(['span', 'div']):
                            span_class = span.get('class', [])
                            class_str = ' '.join(span_class) if isinstance(span_class, list) else str(span_class)
                            if 'instead' not in class_str and 'old' not in class_str and 'was' not in class_str:
                                text = span.get_text(strip=True)
                                if text and any(c.isdigit() for c in text):
                                    price_elem = span
                                    break
                
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = self._clean_price(price_text)
                    currency = self._extract_currency(price_text, url)
                
                # Try to find image
                image_url = None
                img_elem = elem.find('img')
                if img_elem:
                    image_url = img_elem.get('src') or img_elem.get('data-src')
                    if image_url and not image_url.startswith('http'):
                        image_url = urljoin(url, image_url)
                
                products.append(ParsedProduct(
                    name=name,
                    url=product_url or url,
                    price=price,
                    currency=currency,
                    brand=brand,
                    image_url=image_url,
                    sku=data.get('articleNumbers', '').split(',')[0] if data.get('articleNumbers') else None,
                    confidence=0.7,
                ))
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return products
    
    def extract_product_links(self, html: str, url: str) -> List[str]:
        """Extract product links from a category page."""
        from urllib.parse import urljoin, urlparse
        soup = self._get_soup(html)
        links = set()
        
        # First, try to extract from JSON-LD ItemList (used by Shopify stores like 3dnet.no)
        jsonld_data = self._extract_jsonld(html)
        for data in jsonld_data:
            if isinstance(data, dict):
                # Check for ItemList type
                obj_type = data.get('@type', '')
                if obj_type == 'ItemList':
                    items = data.get('itemListElement', [])
                    for item in items:
                        if isinstance(item, dict):
                            item_url = item.get('url', '')
                            if item_url:
                                links.add(item_url)
        
        # Extract links from data-json elements (3DJake style)
        for elem in soup.select('[data-json]'):
            link = elem.find('a', href=True)
            if link:
                href = link.get('href', '')
                if href and not href.startswith('#'):
                    full_url = urljoin(url, href) if not href.startswith('http') else href
                    # Filter out review links and non-product links
                    if '#' not in full_url and '/info/' not in full_url:
                        links.add(full_url)
        
        # Also look for product links in standard product card structures
        product_selectors = [
            '.product-card a[href]',
            '.product-item a[href]',
            '.productCard a[href]',
            '[class*="product"] a[href]',
            'article a[href]',
        ]
        
        base_domain = urlparse(url).netloc
        
        for selector in product_selectors:
            for link in soup.select(selector):
                href = link.get('href', '')
                if href and not href.startswith('#'):
                    full_url = urljoin(url, href) if not href.startswith('http') else href
                    # Only include links from same domain that look like product pages
                    parsed = urlparse(full_url)
                    if parsed.netloc == base_domain:
                        path = parsed.path.lower()
                        # Skip category/collection pages, reviews, info pages
                        if '#' not in full_url and '/info/' not in path and '/category/' not in path:
                            # Must have at least 2 path segments to be a product
                            segments = [s for s in path.split('/') if s]
                            if len(segments) >= 2:
                                links.add(full_url.split('#')[0])  # Remove any fragment
        
        return list(links)
    
    def extract_pagination_links(self, html: str, url: str) -> List[str]:
        """Extract pagination links from a category page."""
        from urllib.parse import urljoin, urlparse, parse_qs, urlencode
        import re
        soup = self._get_soup(html)
        links = set()
        
        # Look for client-pagination element (3DJake style)
        client_pagination = soup.select_one('client-pagination')
        if client_pagination:
            current_page = client_pagination.get('current-page', '1')
            last_page = client_pagination.get('last-page', '1')
            param_name = client_pagination.get('parameter-name', 'page')
            
            try:
                current = int(current_page)
                last = int(last_page)
                
                # Generate links for all remaining pages
                for page_num in range(current + 1, last + 1):
                    parsed = urlparse(url)
                    query_params = parse_qs(parsed.query)
                    query_params[param_name] = [str(page_num)]
                    new_query = urlencode(query_params, doseq=True)
                    page_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
                    links.add(page_url)
            except (ValueError, TypeError):
                pass
        
        # Also look for standard pagination links
        pagination_selectors = [
            '.pagination a[href]',
            '[class*="pagination"] a[href]',
            'nav[aria-label*="page"] a[href]',
            '.pager a[href]',
            'a[rel="next"]',
        ]
        
        for selector in pagination_selectors:
            for link in soup.select(selector):
                href = link.get('href', '')
                if href and not href.startswith('#'):
                    full_url = urljoin(url, href) if not href.startswith('http') else href
                    links.add(full_url)
        
        # Look for "next page" patterns in href attributes
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if 'page=' in href or 'p=' in href or re.search(r'/page/\d+', href):
                full_url = urljoin(url, href) if not href.startswith('http') else href
                links.add(full_url)
        
        return list(links)
