import json
import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

from worker.parsers.base import BaseParser, ParsedProduct


class WooCommerceParser(BaseParser):
    """Parser for WooCommerce stores."""
    
    name = "woocommerce"
    priority = 85
    
    WOOCOMMERCE_INDICATORS = [
        'woocommerce',
        'wc-product',
        'wp-content/plugins/woocommerce',
        'wc_add_to_cart',
        'wc-add-to-cart',
    ]
    
    def can_parse(self, html: str, url: str, headers: Dict[str, str]) -> bool:
        """Check if this is a WooCommerce store."""
        html_lower = html.lower()
        
        # Need at least 2 indicators to be confident it's WooCommerce
        matches = 0
        for indicator in self.WOOCOMMERCE_INDICATORS:
            if indicator.lower() in html_lower:
                matches += 1
        
        # Strong indicator - single match is enough
        if 'wp-content/plugins/woocommerce' in html_lower:
            return True
        
        return matches >= 2
    
    def _extract_wc_product_data(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract WooCommerce product data from page."""
        patterns = [
            r'var\s+wc_single_product_params\s*=\s*(\{.*?\});',
            r'woocommerce_params\s*=\s*(\{.*?\});',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def parse_product(self, html: str, url: str) -> Optional[ParsedProduct]:
        """Parse a single WooCommerce product page."""
        soup = self._get_soup(html)
        
        name = None
        name_elem = soup.select_one('.product_title, h1.entry-title, .woocommerce-product-title')
        if name_elem:
            name = name_elem.get_text(strip=True)
        
        if not name:
            return None
        
        price = None
        currency = None
        list_price = None

        sale_price_selectors = [
            '.price ins .woocommerce-Price-amount',
            '.price ins .amount',
            '.price .price--current',
            '.price .sale-price',
            '.woocommerce-Price-amount.price--current',
        ]
        base_price_selectors = [
            '.price .woocommerce-Price-amount',
            '.woocommerce-Price-amount',
            '.price .amount',
        ]

        price_elem = None
        for selector in sale_price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                break
        if not price_elem:
            for selector in base_price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    break

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = self._clean_price(price_text)
            currency = self._extract_currency(price_text, url)

        regular_price_selectors = [
            '.price del .amount',
            '.price del .woocommerce-Price-amount',
            '.price .regular-price',
            '.price .price--regular',
            '.price .woocommerce-Price-amount.amount--regular',
        ]
        for selector in regular_price_selectors:
            del_price = soup.select_one(selector)
            if del_price:
                list_price = self._clean_price(del_price.get_text(strip=True))
                if list_price:
                    break
        if list_price and price and list_price <= price:
            list_price = None
        
        in_stock = None
        stock_elem = soup.select_one('.stock, .in-stock, .out-of-stock')
        if stock_elem:
            stock_text = stock_elem.get_text(strip=True).lower()
            in_stock = 'in stock' in stock_text or 'in-stock' in stock_elem.get('class', [])
        
        image_url = None
        img_elem = soup.select_one('.woocommerce-product-gallery__image img, .product-image img, .wp-post-image')
        if img_elem:
            image_url = img_elem.get('data-large_image') or img_elem.get('src')
        
        sku = None
        sku_elem = soup.select_one('.sku, [itemprop="sku"]')
        if sku_elem:
            sku = sku_elem.get_text(strip=True)
        
        brand = None
        brand_elem = soup.select_one('[itemprop="brand"], .product-brand')
        if brand_elem:
            brand = brand_elem.get_text(strip=True)
        
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
            confidence=0.8,
        )
    
    def parse_product_list(self, html: str, url: str) -> List[ParsedProduct]:
        """Parse a WooCommerce category page."""
        soup = self._get_soup(html)
        products = []
        
        product_cards = soup.select('.product, .wc-block-grid__product, li.product')
        
        for card in product_cards:
            name_elem = card.select_one('.woocommerce-loop-product__title, h2, .product-title')
            if not name_elem:
                continue
            
            name = name_elem.get_text(strip=True)
            
            link_elem = card.select_one('a.woocommerce-LoopProduct-link, a[href*="/product/"]')
            if not link_elem:
                link_elem = card.find('a', href=True)
            
            product_url = link_elem.get('href') if link_elem else None
            if not product_url:
                continue
            
            if not product_url.startswith('http'):
                product_url = urljoin(url, product_url)
            
            price = None
            list_price = None
            currency = None
            price_selectors = [
                '.price ins .woocommerce-Price-amount',
                '.price ins .amount',
                '.woocommerce-Price-amount.price--current',
                '.price .woocommerce-Price-amount',
                '.woocommerce-Price-amount',
                '.price .amount',
            ]
            price_elem = None
            for selector in price_selectors:
                price_elem = card.select_one(selector)
                if price_elem:
                    break
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._clean_price(price_text)
                currency = self._extract_currency(price_text, url)
            regular_price_selectors = [
                '.price del .amount',
                '.price del .woocommerce-Price-amount',
                '.price .regular-price',
                '.price .price--regular',
                '.woocommerce-Price-amount.amount--regular',
            ]
            for selector in regular_price_selectors:
                regular_elem = card.select_one(selector)
                if regular_elem:
                    list_price = self._clean_price(regular_elem.get_text(strip=True))
                    if list_price:
                        break
            if list_price and price and list_price <= price:
                list_price = None
            
            image_url = None
            img_elem = card.select_one('img')
            if img_elem:
                image_url = img_elem.get('data-src') or img_elem.get('src')
            
            products.append(ParsedProduct(
                name=name,
                url=product_url,
                price=price,
                currency=currency,
                list_price=list_price,
                image_url=image_url,
                confidence=0.7,
            ))
        
        return products
    
    def extract_product_links(self, html: str, url: str) -> List[str]:
        """Extract product links from a WooCommerce category page."""
        soup = self._get_soup(html)
        links = set()
        
        for a in soup.select('a.woocommerce-LoopProduct-link, a[href*="/product/"]'):
            href = a.get('href')
            if href:
                if not href.startswith('http'):
                    href = urljoin(url, href)
                href = href.split('?')[0].split('#')[0]
                links.add(href)
        
        return list(links)
    
    def extract_pagination_links(self, html: str, url: str) -> List[str]:
        """Extract pagination links from a WooCommerce category page."""
        soup = self._get_soup(html)
        links = set()
        
        for a in soup.select('.woocommerce-pagination a, .page-numbers a'):
            href = a.get('href')
            if href:
                if not href.startswith('http'):
                    href = urljoin(url, href)
                links.add(href)
        
        return list(links)
