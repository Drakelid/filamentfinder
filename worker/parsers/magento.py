import json
import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse

from worker.parsers.base import BaseParser, ParsedProduct


class MagentoParser(BaseParser):
    """Parser for Magento stores."""
    
    name = "magento"
    priority = 80
    
    MAGENTO_INDICATORS = [
        'mage/cookies',
        'Magento_',
        'magento',
        'mage-init',
        'data-mage-init',
        'catalog-product-view',
        'catalogsearch',
    ]
    
    def can_parse(self, html: str, url: str, headers: Dict[str, str]) -> bool:
        """Check if this is a Magento store."""
        for indicator in self.MAGENTO_INDICATORS:
            if indicator in html:
                return True
        
        x_magento = headers.get('x-magento-vary') or headers.get('x-magento-cache-debug')
        if x_magento:
            return True
        
        return False
    
    def _extract_magento_product_data(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract Magento product data from page."""
        patterns = [
            r'var\s+spConfig\s*=\s*new\s+Product\.Config\((\{.*?\})\)',
            r'"product"\s*:\s*(\{[^}]+\})',
            r'data-product-info\s*=\s*[\'"](\{.*?\})[\'"]',
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
        """Parse a single Magento product page."""
        soup = self._get_soup(html)
        
        name = None
        name_elem = soup.select_one('.page-title span, h1.product-name, [itemprop="name"]')
        if name_elem:
            name = name_elem.get_text(strip=True)
        
        if not name:
            return None
        
        price = None
        currency = None
        list_price = None
        
        price_elem = soup.select_one('[data-price-type="finalPrice"] .price, .price-final_price .price, .special-price .price')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = self._clean_price(price_text)
            currency = self._extract_currency(price_text, url)
        
        if not price:
            price_elem = soup.select_one('.price-box .price, [itemprop="price"]')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._clean_price(price_text)
                currency = self._extract_currency(price_text, url)
        
        old_price_elem = soup.select_one('.old-price .price, [data-price-type="oldPrice"] .price')
        if old_price_elem:
            list_price = self._clean_price(old_price_elem.get_text(strip=True))
        
        in_stock = None
        stock_elem = soup.select_one('.stock, [title="Availability"]')
        if stock_elem:
            stock_text = stock_elem.get_text(strip=True).lower()
            in_stock = 'in stock' in stock_text or 'available' in stock_text
        
        image_url = None
        img_elem = soup.select_one('.product.media img, .gallery-placeholder img, [itemprop="image"]')
        if img_elem:
            image_url = img_elem.get('data-src') or img_elem.get('src')
        
        sku = None
        sku_elem = soup.select_one('[itemprop="sku"], .product.attribute.sku .value')
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
            confidence=0.75,
        )
    
    def parse_product_list(self, html: str, url: str) -> List[ParsedProduct]:
        """Parse a Magento category page."""
        soup = self._get_soup(html)
        products = []
        
        product_cards = soup.select('.product-item, .item.product, li.product-item')
        
        for card in product_cards:
            name_elem = card.select_one('.product-item-name, .product-name, a.product-item-link')
            if not name_elem:
                continue
            
            name = name_elem.get_text(strip=True)
            
            link_elem = card.select_one('a.product-item-link, a.product-image')
            if not link_elem:
                link_elem = card.find('a', href=True)
            
            product_url = link_elem.get('href') if link_elem else None
            if not product_url:
                continue
            
            if not product_url.startswith('http'):
                product_url = urljoin(url, product_url)
            
            price = None
            currency = None
            price_elem = card.select_one('[data-price-type="finalPrice"] .price, .price-final_price .price, .price')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._clean_price(price_text)
                currency = self._extract_currency(price_text, url)
            
            image_url = None
            img_elem = card.select_one('img.product-image-photo, img')
            if img_elem:
                image_url = img_elem.get('data-src') or img_elem.get('src')
            
            products.append(ParsedProduct(
                name=name,
                url=product_url,
                price=price,
                currency=currency,
                image_url=image_url,
                confidence=0.65,
            ))
        
        return products
    
    def extract_product_links(self, html: str, url: str) -> List[str]:
        """Extract product links from a Magento category page."""
        soup = self._get_soup(html)
        links = set()
        
        for a in soup.select('a.product-item-link, a.product-image'):
            href = a.get('href')
            if href:
                if not href.startswith('http'):
                    href = urljoin(url, href)
                href = href.split('?')[0].split('#')[0]
                links.add(href)
        
        return list(links)
    
    def extract_pagination_links(self, html: str, url: str) -> List[str]:
        """Extract pagination links from a Magento category page."""
        soup = self._get_soup(html)
        links = set()
        
        for a in soup.select('.pages a, .pagination a, .toolbar-products a.page'):
            href = a.get('href')
            if href:
                if not href.startswith('http'):
                    href = urljoin(url, href)
                links.add(href)
        
        return list(links)
