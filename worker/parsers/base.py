from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup


@dataclass
class ParsedProduct:
    """Represents a parsed product from a webpage."""
    name: str
    url: str
    price: Optional[Decimal] = None
    currency: Optional[str] = None
    list_price: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    shipping_currency: Optional[str] = None
    total_price: Optional[Decimal] = None
    brand: Optional[str] = None
    category: str = "unknown"
    product_type: Optional[str] = None
    variant: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    image_url: Optional[str] = None
    sku: Optional[str] = None
    gtin: Optional[str] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    confidence: float = 0.0
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "price": float(self.price) if self.price else None,
            "currency": self.currency,
            "list_price": float(self.list_price) if self.list_price else None,
            "shipping_cost": float(self.shipping_cost) if self.shipping_cost else None,
            "shipping_currency": self.shipping_currency,
            "total_price": float(self.total_price) if self.total_price else None,
            "brand": self.brand,
            "category": self.category,
            "product_type": self.product_type,
            "variant": self.variant,
            "color": self.color,
            "size": self.size,
            "image_url": self.image_url,
            "sku": self.sku,
            "gtin": self.gtin,
            "in_stock": self.in_stock,
            "stock_quantity": self.stock_quantity,
            "confidence": self.confidence,
        }


class BaseParser(ABC):
    """Base class for all product parsers."""
    
    name: str = "base"
    priority: int = 0
    
    def __init__(self) -> None:
        self.selector_overrides: Dict[str, str] = {}
    
    @abstractmethod
    def can_parse(self, html: str, url: str, headers: Dict[str, str]) -> bool:
        """Check if this parser can handle the given page."""
        pass
    
    @abstractmethod
    def parse_product(self, html: str, url: str) -> Optional[ParsedProduct]:
        """Parse a single product page."""
        pass
    
    @abstractmethod
    def parse_product_list(self, html: str, url: str) -> List[ParsedProduct]:
        """Parse a category/list page for products."""
        pass
    
    def extract_product_links(self, html: str, url: str) -> List[str]:
        """Extract product links from a category page."""
        return []
    
    def extract_pagination_links(self, html: str, url: str) -> List[str]:
        """Extract pagination links from a category page."""
        return []
    
    def _get_soup(self, html: str) -> BeautifulSoup:
        """Create a BeautifulSoup object from HTML."""
        return BeautifulSoup(html, "lxml")
    
    def _clean_price(self, price_str: Optional[str]) -> Optional[Decimal]:
        """Clean and parse a price string to Decimal."""
        if not price_str:
            return None
        
        import re
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        
        if ',' in cleaned and '.' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        try:
            return Decimal(cleaned)
        except:
            return None
    
    def _extract_currency(self, text: str, url: str = '') -> Optional[str]:
        """Extract currency code from text, with URL as fallback context."""
        import re
        
        currency_symbols = {
            '$': 'USD',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            '₹': 'INR',
            'zł': 'PLN',
            'Kč': 'CZK',
            'CHF': 'CHF',
            'R$': 'BRL',
            'A$': 'AUD',
            'C$': 'CAD',
        }
        
        # Handle 'kr' based on context - check for specific Nordic patterns
        if 'kr' in text.lower():
            # Norwegian sites typically use "kr" after the number or "NOK"
            if 'nok' in text.lower() or '.no' in text.lower() or '.no' in url.lower():
                return 'NOK'
            # Swedish sites use "kr" or "SEK"  
            elif 'sek' in text.lower() or '.se' in text.lower() or '.se' in url.lower():
                return 'SEK'
            # Danish sites use "kr" or "DKK"
            elif 'dkk' in text.lower() or '.dk' in text.lower() or '.dk' in url.lower():
                return 'DKK'
            # Default to NOK for "kr" since it's most common in our use case
            return 'NOK'
        
        for symbol, code in currency_symbols.items():
            if symbol in text:
                return code
        
        currency_codes = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN', 'HRK', 'RUB', 'TRY', 'BRL', 'MXN', 'INR', 'CNY', 'KRW', 'SGD', 'HKD', 'TWD', 'THB', 'MYR', 'PHP', 'IDR', 'VND', 'NZD', 'ZAR']
        
        for code in currency_codes:
            if code in text.upper():
                return code
        
        # If no currency found in text, infer from URL TLD or path
        if url:
            url_lower = url.lower()
            # Check TLD first
            if '.no/' in url_lower or url_lower.endswith('.no'):
                return 'NOK'
            elif '.se/' in url_lower or url_lower.endswith('.se'):
                return 'SEK'
            elif '.dk/' in url_lower or url_lower.endswith('.dk'):
                return 'DKK'
            elif '.de/' in url_lower or '.at/' in url_lower or url_lower.endswith('.de') or url_lower.endswith('.at'):
                return 'EUR'
            elif '.uk/' in url_lower or '.co.uk/' in url_lower or url_lower.endswith('.uk'):
                return 'GBP'
            elif '.pl/' in url_lower or url_lower.endswith('.pl'):
                return 'PLN'
            elif '.cz/' in url_lower or url_lower.endswith('.cz'):
                return 'CZK'
            # Check for country code in URL path (e.g., clasohlson.com/no/, 3djake.no/)
            elif '/no/' in url_lower or url_lower.endswith('/no'):
                return 'NOK'
            elif '/se/' in url_lower or url_lower.endswith('/se'):
                return 'SEK'
            elif '/dk/' in url_lower or url_lower.endswith('/dk'):
                return 'DKK'
            elif '/de/' in url_lower or url_lower.endswith('/de'):
                return 'EUR'
        
        return None

    def set_selector_overrides(self, overrides: Optional[Dict[str, str]]) -> None:
        """Apply per-source selector overrides (if any)."""
        self.selector_overrides = overrides or {}

    def _get_selector_override_values(self, key: str) -> List[str]:
        """Return override selectors split on '||' for a key."""
        value = (self.selector_overrides or {}).get(key)
        if not value:
            return []
        return [chunk.strip() for chunk in value.split('||') if chunk.strip()]
