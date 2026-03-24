import re
import structlog
from decimal import Decimal
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

from worker.parsers.base import BaseParser, ParsedProduct

logger = structlog.get_logger()


class GenericParser(BaseParser):
    """Generic fallback parser using HTML heuristics."""
    
    name = "generic"
    priority = 10
    
    PRICE_SELECTORS = [
        '[itemprop="price"]',
        '[data-price]',
        '.price',
        '.product-price',
        '.current-price',
        '.sale-price',
        '.offer-price',
        '#price',
        '.price-current',
        '.price-now',
        'span[class*="price"]',
        'div[class*="price"]',
    ]
    
    NAME_SELECTORS = [
        '[itemprop="name"]',
        'h1.product-title',
        'h1.product-name',
        '.product-title h1',
        '.product-name',
        'h1[class*="product"]',
        '#product-title',
        '.pdp-title',
        'h1',
    ]
    
    IMAGE_SELECTORS = [
        '[itemprop="image"]',
        '.product-image img',
        '.product-gallery img',
        '#product-image',
        '.main-image img',
        'img[class*="product"]',
        '.gallery img',
    ]
    
    PRODUCT_CARD_SELECTORS = [
        '.product-card',
        '.product-item',
        '.product',
        '[data-product]',
        '[data-product-id]',
        '.grid-item',
        '.product-tile',
        '.product-box',
        'article.product',
        'li[class*="product"]',
        'div[class*="product-card"]',
        '.item',
        '.card',
        '[class*="ProductCard"]',
        '[class*="product-card"]',
        '[class*="productCard"]',
        '.products-grid > div',
        '.product-list > div',
        '.product-grid > div',
        '.site-productlist-item',  # Proshop.no
        '.category_prod',  # Elefun.no
        '.m-product-card',  # Computersalg.no
        '.plp-card',  # Clas Ohlson
        'li.product-card-view',  # Clas Ohlson
        '.thumbnail[itemtype*="Product"]',  # 3dnet.no (Shopify Turbo theme)
        '.product-wrap',  # 3dnet.no (Shopify Turbo theme)
        '.thumbnail .product-wrap',  # 3dnet.no combined
    ]
    STOCK_TRUE_KEYWORDS = [
        'in stock',
        'instock',
        'på lager',
        'lagervare',
        'available',
        'klar til levering',
        'klar for levering',
        'klar for sending',
        'på fjernlager',
        'få på lager',
        'few left',
        'low stock',
        'ships immediately',
        'ready to ship',
        'levering 1-3 dager',
        'leveringstid 1-3 dager',
        'leveringstid 2-5 dager',
    ]
    STOCK_FALSE_KEYWORDS = [
        'out of stock',
        'out-of-stock',
        'outofstock',
        'sold out',
        'ikke på lager',
        'ikke tilgjengelig',
        'ikke i butikk',
        'ik ke på lager',
        'utsolgt',
        'midlertidig utsolgt',
        'tomt på lager',
        'bestillingsvare',
        'backorder',
        'forhåndsbestilling',
        'preorder',
        'coming soon',
        'not available',
        'notify me',
    ]
    STOCK_TRUE_CLASSES = [
        'in-stock',
        'instock',
        'site-stocklevel--instock',
        'site-stocklevel--few',
        'site-stocklevel--green',
        'availability--instock',
        'stocklevel--instock',
        'stockstate-in-stock',
        'availability--available',
    ]
    STOCK_FALSE_CLASSES = [
        'out-of-stock',
        'soldout',
        'site-stocklevel--soldout',
        'site-stocklevel--nostock',
        'availability--soldout',
        'stocklevel--soldout',
        'stockstate-out-of-stock',
        'availability--unavailable',
    ]
    STOCK_ATTR_KEYS = [
        'data-stock',
        'data-stock-status',
        'data-availability',
        'data-in-stock',
        'data-available',
        'data-state',
        'data-status',
        'data-stocklevel',
        'aria-label',
        'title',
        'content',
    ]
    
    def can_parse(self, html: str, url: str, headers: Dict[str, str]) -> bool:
        """Generic parser can always attempt to parse."""
        return True
    
    def _find_element_text(self, soup, selectors: List[str]) -> Optional[str]:
        """Find text content using multiple selectors."""
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if text:
                    return text
        return None
    
    def _find_element_attr(self, soup, selectors: List[str], attr: str) -> Optional[str]:
        """Find attribute value using multiple selectors."""
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                value = elem.get(attr)
                if value:
                    return value
        return None
    
    def _extract_price_from_text(self, text: str, url: str = '') -> tuple[Optional[Decimal], Optional[str]]:
        """Extract price and currency from text."""
        if not text:
            return None, None
        
        currency = self._extract_currency(text, url)
        price = self._clean_price(text)
        
        return price, currency
    
    def _extract_from_shopify_data_product(self, soup, url: str) -> List[ParsedProduct]:
        """Extract products from Shopify data-product JSON attributes (used by 3dnet.no and similar)."""
        import json
        import html
        products = []
        
        # Find elements with data-product containing Shopify product JSON
        elements_with_product = soup.select('[data-product]')
        
        for elem in elements_with_product:
            try:
                raw_data = elem.get('data-product', '{}')
                # Unescape HTML entities in the JSON
                unescaped = html.unescape(raw_data)
                data = json.loads(unescaped)
                
                # Check if this looks like Shopify product data
                if not data.get('title') and not data.get('id'):
                    continue
                
                name = data.get('title', '')
                vendor = data.get('vendor', '')
                handle = data.get('handle', '')
                product_id = data.get('id', '')
                
                if not name:
                    continue
                
                # Build product URL from handle
                parsed = urlparse(url)
                product_url = f"{parsed.scheme}://{parsed.netloc}/products/{handle}" if handle else ''
                
                # Get price from variants (Shopify stores price in cents)
                price = None
                currency = None
                variants = data.get('variants', [])
                if variants:
                    first_variant = variants[0]
                    price_cents = first_variant.get('price')
                    if price_cents:
                        price = Decimal(str(price_cents)) / 100
                    currency = 'NOK'  # Default for Norwegian stores
                
                # Get image URL
                image_url = None
                images = data.get('images', [])
                featured_image = data.get('featured_image')
                if featured_image:
                    image_url = featured_image if featured_image.startswith('http') else f"https:{featured_image}"
                elif images:
                    image_url = images[0] if images[0].startswith('http') else f"https:{images[0]}"
                
                # Get SKU from first variant
                sku = None
                if variants:
                    sku = variants[0].get('sku', '')
                
                # Check availability
                in_stock = self._interpret_stock_value(data.get('available'))
                if in_stock is None:
                    in_stock = self._interpret_stock_value(data.get('in_stock'))
                if in_stock is None:
                    in_stock = self._detect_stock_from_text(data.get('availability') or data.get('availabilityText'))
                
                products.append(ParsedProduct(
                    name=name,
                    url=product_url or url,
                    price=price,
                    currency=currency,
                    brand=vendor,
                    image_url=image_url,
                    sku=sku,
                    in_stock=in_stock,
                    confidence=0.8,
                ))
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.debug("Failed to parse Shopify data-product", error=str(e))
                continue
        
        return products
    
    def _extract_from_data_json(self, soup, url: str) -> List[ParsedProduct]:
        """Extract products from data-json attributes (used by 3DJake and similar sites)."""
        import json
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
                product_id = data.get('id', '')
                
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
                
                in_stock = self._interpret_stock_value(data.get('available') or data.get('inStock') or data.get('instock'))
                if in_stock is None:
                    in_stock = self._detect_stock_from_text(data.get('availability') or data.get('availabilityText'))
                if in_stock is None:
                    raw_attr_stock = elem.get('data-in-stock') or elem.get('data-availability') or elem.get('data-stock')
                    in_stock = self._interpret_stock_value(raw_attr_stock)

                products.append(ParsedProduct(
                    name=name,
                    url=product_url or url,
                    price=price,
                    currency=currency,
                    brand=brand,
                    image_url=image_url,
                    sku=data.get('articleNumbers', '').split(',')[0] if data.get('articleNumbers') else None,
                    in_stock=in_stock,
                    confidence=0.7,
                ))
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return products
    
    def _extract_from_data_attributes(self, soup, url: str) -> List[ParsedProduct]:
        """Extract products from data-name/data-brand attributes (used by Clas Ohlson)."""
        products = []
        
        # Find elements with data-name attribute (Clas Ohlson style)
        elements_with_data = soup.select('.product-card[data-name], .plp-card[data-name], div[data-name][data-brand]')
        
        for elem in elements_with_data:
            name = elem.get('data-name', '')
            if not name:
                continue
            
            brand = elem.get('data-brand', '')
            product_id = elem.get('data-id', '')
            
            # Find the product URL from a link in this element
            link = elem.find('a', href=True)
            product_url = ''
            if link:
                product_url = link.get('href', '')
                if product_url and not product_url.startswith('http'):
                    product_url = urljoin(url, product_url)
            
            # Try to find price
            price = None
            currency = None
            price_elem = elem.select_one('.price, [class*="price"]')
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
            
            raw_stock = elem.get('data-in-stock') or elem.get('data-availability') or elem.get('data-stock')
            in_stock = self._interpret_stock_value(raw_stock)
            if in_stock is None:
                in_stock = self._detect_stock_from_element(elem)

            products.append(ParsedProduct(
                name=name,
                url=product_url or url,
                price=price,
                currency=currency,
                brand=brand,
                image_url=image_url,
                sku=product_id,
                in_stock=in_stock,
                confidence=0.7,
            ))
        
        return products
    
    def _is_product_page(self, soup, url: str) -> bool:
        """Heuristically determine if this is a product page."""
        indicators = 0
        
        if soup.select_one('[itemprop="product"], [itemtype*="Product"]'):
            indicators += 2
        
        if soup.select_one('button[class*="cart"], button[class*="buy"], .add-to-cart, #add-to-cart'):
            indicators += 2
        
        if soup.select_one('[itemprop="price"], .price'):
            indicators += 1
        
        url_lower = url.lower()
        if '/product/' in url_lower or '/p/' in url_lower or '/item/' in url_lower:
            indicators += 1
        
        return indicators >= 2
    
    def parse_product(self, html: str, url: str) -> Optional[ParsedProduct]:
        """Parse a single product page using generic heuristics."""
        soup = self._get_soup(html)
        
        name = self._find_element_text(soup, self.NAME_SELECTORS)
        if not name:
            title = soup.find('title')
            if title:
                name = title.get_text(strip=True).split('|')[0].split('-')[0].strip()
        
        if not name:
            logger.warning("No product name found", url=url)
            return None
        
        logger.info("Parsing product page", url=url, name=name[:50] if name else None)
        
        price = None
        currency = None
        list_price = None
        
        for selector in self.PRICE_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                data_price = elem.get('data-price') or elem.get('content')
                if data_price:
                    price = self._clean_price(data_price)
                else:
                    price_text = elem.get_text(strip=True)
                    price, currency = self._extract_price_from_text(price_text, url)
                
                if price:
                    if not currency:
                        currency = self._extract_currency(elem.get_text(), url)
                    break
        
        old_price_selectors = ['.was-price', '.old-price', '.original-price', 'del .price', '.list-price', 's .price']
        for selector in old_price_selectors:
            elem = soup.select_one(selector)
            if elem:
                list_price = self._clean_price(elem.get_text(strip=True))
                break
        
        image_url = None
        for selector in self.IMAGE_SELECTORS:
            elem = soup.select_one(selector)
            if elem:
                image_url = elem.get('src') or elem.get('data-src') or elem.get('content')
                if image_url:
                    if not image_url.startswith('http'):
                        image_url = urljoin(url, image_url)
                    break
        
        if not image_url:
            og_image = soup.select_one('meta[property="og:image"]')
            if og_image:
                image_url = og_image.get('content')
        
        in_stock = self._detect_stock_status(soup)
        
        sku = None
        sku_selectors = ['[itemprop="sku"]', '.sku', '#sku', '[data-sku]']
        for selector in sku_selectors:
            elem = soup.select_one(selector)
            if elem:
                sku = elem.get('content') or elem.get('data-sku') or elem.get_text(strip=True)
                break
        
        brand = None
        brand_selectors = ['[itemprop="brand"]', '.brand', '.manufacturer', '[data-brand]']
        for selector in brand_selectors:
            elem = soup.select_one(selector)
            if elem:
                brand = elem.get('content') or elem.get_text(strip=True)
                break
        
        return ParsedProduct(
            name=name,
            url=url,
            price=price,
            currency=currency,
            list_price=list_price,
            brand=brand,
            image_url=image_url,
            sku=sku,
            in_stock=in_stock,
            confidence=0.5,
        )
    
    def parse_product_list(self, html: str, url: str) -> List[ParsedProduct]:
        """Parse a category page using generic heuristics."""
        soup = self._get_soup(html)
        products = []
        
        # First, try Shopify data-product JSON (used by 3dnet.no and similar Shopify stores)
        shopify_products = self._extract_from_shopify_data_product(soup, url)
        if shopify_products:
            logger.info("Extracted products from Shopify data-product", url=url, count=len(shopify_products))
            return shopify_products
        
        # Try to extract products from data-json attributes (used by 3DJake and similar sites)
        json_products = self._extract_from_data_json(soup, url)
        if json_products:
            logger.info("Extracted products from data-json", url=url, count=len(json_products))
            return json_products
        
        # Try data-name/data-brand attributes (used by Clas Ohlson)
        data_attr_products = self._extract_from_data_attributes(soup, url)
        if data_attr_products:
            logger.info("Extracted products from data attributes", url=url, count=len(data_attr_products))
            return data_attr_products
        
        product_cards = []
        matched_selector = None
        for selector in self.PRODUCT_CARD_SELECTORS:
            cards = soup.select(selector)
            if len(cards) >= 2:
                product_cards = cards
                matched_selector = selector
                break
        
        logger.info(
            "Product card detection",
            url=url,
            matched_selector=matched_selector,
            cards_found=len(product_cards),
        )
        
        for card in product_cards:
            # Try to get name from data attributes first (Clas Ohlson)
            name = card.get('data-name')
            brand = card.get('data-brand')
            
            # Try standard name selectors
            if not name:
                name_selectors = [
                    'h2, h3, h4',
                    '.product-name, .product-title',
                    '.m-product-card__name',  # Computersalg
                    '.category_prod_name',  # Elefun
                    'a[class*="name"], a[class*="title"]',
                    '[class*="name"]',
                ]
                for sel in name_selectors:
                    name_elem = card.select_one(sel)
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        if name:
                            break
            
            # Try link title attribute (Elefun)
            if not name:
                link = card.find('a', href=True)
                if link and link.get('title'):
                    name = link.get('title')
            
            if not name:
                continue
            
            link_elem = card.find('a', href=True)
            if not link_elem:
                continue
            
            product_url = link_elem.get('href')
            if not product_url:
                continue
            
            if not product_url.startswith('http'):
                product_url = urljoin(url, product_url)
            
            price = None
            currency = None
            # Try multiple price selectors for different sites
            price_selectors = [
                '.site-currency-lg',  # Proshop.no
                '.m-product-card__price',  # Computersalg
                '.category_prod_price',  # Elefun
                '.price--current',
                '.price--reduced', 
                '.sale-price',
                '.current-price',
                '.price',
                '[class*="price"]',
            ]
            for price_sel in price_selectors:
                price_elem = card.select_one(price_sel)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price, currency = self._extract_price_from_text(price_text, url)
                    if price:
                        break
            
            image_url = None
            img_elem = card.find('img')
            if img_elem:
                image_url = img_elem.get('data-src') or img_elem.get('src')
                if image_url and not image_url.startswith('http'):
                    image_url = urljoin(url, image_url)
            
            card_stock = None
            attr_stock = card.get('data-in-stock') or card.get('data-availability') or card.get('data-stock')
            card_stock = self._interpret_stock_value(attr_stock)
            if card_stock is None:
                stock_elem = card.select_one('.category_prod_stock, .stock, .availability')
                card_stock = self._detect_stock_from_element(stock_elem)

            products.append(ParsedProduct(
                name=name,
                url=product_url,
                price=price,
                currency=currency,
                brand=brand,
                image_url=image_url,
                in_stock=card_stock,
                confidence=0.4,
            ))
        
        return products
    
    def extract_product_links(self, html: str, url: str) -> List[str]:
        """Extract product links using generic heuristics."""
        import json
        soup = self._get_soup(html)
        links = set()
        
        parsed = urlparse(url)
        base_domain = parsed.netloc
        
        # First, try to extract from JSON-LD ItemList (used by Shopify stores like 3dnet.no)
        jsonld_scripts = soup.find_all('script', type='application/ld+json')
        logger.info("Found JSON-LD scripts", url=url, count=len(jsonld_scripts))
        
        for script in jsonld_scripts:
            try:
                script_content = script.string or script.get_text()
                if not script_content:
                    continue
                data = json.loads(script_content)
                obj_type = data.get('@type', '') if isinstance(data, dict) else ''
                logger.debug("Parsed JSON-LD", url=url, type=obj_type)
                if isinstance(data, dict) and obj_type == 'ItemList':
                    items = data.get('itemListElement', [])
                    logger.info("Found ItemList", url=url, items_count=len(items))
                    for item in items:
                        if isinstance(item, dict):
                            item_url = item.get('url', '')
                            if item_url:
                                links.add(item_url)
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug("Failed to parse JSON-LD", error=str(e))
                continue
        
        # If we found links from JSON-LD, return them
        if links:
            logger.info("Extracted product links from JSON-LD ItemList", url=url, count=len(links))
            return list(links)
        
        product_url_patterns = [
            r'/product[s]?/',
            r'/p/',
            r'/item/',
            r'/dp/',
            r'/pd/',
            r'/-p-',
            r'/products/',
            r'/Filament[^/]*/[^/]+/\d+$',  # Proshop.no pattern: /Filament-3D-Printer/PRODUCT-NAME/ID
            r'/[^/]+/[^/]+/\d{6,}$',  # Generic pattern: category/name/numeric-id
            r'/i/\d+/',  # Computersalg pattern: /i/4832483/product-name
            r'/vare-\d+/',  # Elefun pattern: /vare-69949/product-name
            r'/[^/]+/[a-z]{2,4}\d{2,}[a-z]*/',  # PolyAlkemi pattern: /brand/SKU/product-name (SKU like anep17aub)
            r'/[^/]+/[^/]+/[^/]+-[^/]+-[^/]+$',  # Generic 3-segment with dashes: /brand/sku/product-name-with-dashes
        ]
        
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            if not href:
                continue
            
            if not href.startswith('http'):
                href = urljoin(url, href)
            
            link_parsed = urlparse(href)
            if link_parsed.netloc != base_domain:
                continue
            
            for pattern in product_url_patterns:
                if re.search(pattern, href, re.IGNORECASE):
                    href = href.split('#')[0]
                    links.add(href)
                    break
        
        for card in soup.select('.product-card, .product-item, .product, [data-product], article[class*="product"], li[class*="product"], div[class*="product-card"], .grid-item, .site-productlist-item, .category_prod, .m-product-card, .plp-card'):
            link = card.find('a', href=True)
            if link:
                href = link.get('href')
                if href:
                    if not href.startswith('http'):
                        href = urljoin(url, href)
                    link_parsed = urlparse(href)
                    if link_parsed.netloc == base_domain:
                        links.add(href.split('#')[0])
        
        filament_keywords = ['filament', 'pla', 'petg', 'abs', 'resin', 'material', 'consumable', 'spool']
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True).lower()
            
            if not href.startswith('http'):
                href = urljoin(url, href)
            
            link_parsed = urlparse(href)
            if link_parsed.netloc != base_domain:
                continue
            
            href_lower = href.lower()
            for kw in filament_keywords:
                if kw in href_lower or kw in text:
                    links.add(href.split('#')[0])
                    break
        
        return list(links)
    
    def extract_pagination_links(self, html: str, url: str) -> List[str]:
        """Extract pagination links using generic heuristics."""
        soup = self._get_soup(html)
        links = set()
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        
        # Standard pagination selectors
        pagination_selectors = [
            '.pagination a',
            '.pager a',
            'nav[aria-label*="pagination"] a',
            '.page-numbers a',
            '[class*="pagination"] a',
            'a[rel="next"]',
        ]
        
        for selector in pagination_selectors:
            for a in soup.select(selector):
                href = a.get('href')
                if href and not href.startswith('javascript:'):
                    if not href.startswith('http'):
                        href = urljoin(url, href)
                    links.add(href)
        
        # Handle 3DJake client-pagination custom element
        client_pagination = soup.select_one('client-pagination')
        if client_pagination:
            last_page = client_pagination.get('last-page')
            param_name = client_pagination.get('parameter-name', 'page')
            if last_page:
                try:
                    total_pages = int(last_page)
                    for page in range(2, total_pages + 1):
                        page_url = f"{base_url}?{param_name}={page}"
                        links.add(page_url)
                except ValueError:
                    pass
        
        # Handle Computersalg data-number-of-pages attribute
        pagination_div = soup.select_one('[data-number-of-pages]')
        if pagination_div:
            total_pages_str = pagination_div.get('data-number-of-pages')
            if total_pages_str:
                try:
                    total_pages = min(int(total_pages_str), 50)  # Limit to 50 pages
                    for page in range(2, total_pages + 1):
                        page_url = f"{base_url}?page={page}"
                        links.add(page_url)
                except ValueError:
                    pass
        
        # Handle Clas Ohlson data-page attributes
        page_links_with_data = soup.select('[data-page]')
        if page_links_with_data:
            max_page = 1
            for elem in page_links_with_data:
                page_val = elem.get('data-page', '')
                if page_val.isdigit():
                    max_page = max(max_page, int(page_val))
            if max_page > 1:
                for page in range(2, min(max_page + 1, 51)):
                    page_url = f"{base_url}?page={page}"
                    links.add(page_url)
        
        # Standard next/page number links
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            text = a.get_text(strip=True).lower()
            
            if href and not href.startswith('javascript:'):
                if text in ['next', 'next page', '>', '>>', '→', 'volgende', 'neste']:
                    if not href.startswith('http'):
                        href = urljoin(url, href)
                    links.add(href)
                elif re.match(r'^\d+$', text):
                    if not href.startswith('http'):
                        href = urljoin(url, href)
                    links.add(href)
        
        # Generate page URLs from URL patterns (for sites with ?pn=X, ?page=X, ?pageID=X)
        if '?' in url:
            # Already has query params, check for page param patterns
            pass
        else:
            # Check if this looks like a category page that might have pagination
            page_param_patterns = ['pn', 'page', 'pageID', 'p']
            for param in page_param_patterns:
                # Look for existing pagination links to determine the pattern
                for link in list(links):
                    if f'?{param}=' in link or f'&{param}=' in link:
                        # Found the pattern, generate more pages
                        for page in range(2, 11):  # Generate pages 2-10
                            page_url = f"{base_url}?{param}={page}"
                            links.add(page_url)
                        break
        
        return list(links)
