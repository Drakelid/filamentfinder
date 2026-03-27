from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from urllib.parse import urlparse


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

        normalized = str(price_str).replace('\xa0', ' ').strip()
        if not normalized:
            return None

        candidate_pattern = re.compile(r'\d+(?:[\s.,]\d+)*')
        candidates = []

        for match in candidate_pattern.finditer(normalized):
            token = match.group(0).strip()
            if not token or len(re.sub(r'\D', '', token)) > 9:
                continue

            cleaned = token.replace(' ', '')
            if ',' in cleaned and '.' in cleaned:
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                parts = cleaned.split(',')
                if len(parts) == 2 and len(parts[1]) in {2, 3}:
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif '.' in cleaned:
                parts = cleaned.split('.')
                if len(parts) > 2:
                    cleaned = ''.join(parts)
                elif len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
                    cleaned = ''.join(parts)

            try:
                value = Decimal(cleaned)
            except Exception:
                continue

            if value <= 0:
                continue

            decimal_score = 1 if any(sep in token for sep in [',', '.']) else 0
            candidates.append((decimal_score, match.start(), value))

        if not candidates:
            return None

        decimal_candidates = [candidate for candidate in candidates if candidate[0] == 1]
        chosen = decimal_candidates[-1] if decimal_candidates else candidates[-1]
        return chosen[2]
    
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

    def _adjust_store_price(self, price: Optional[Decimal], url: str) -> Optional[Decimal]:
        if price is None:
            return None

        domain = urlparse(url).netloc.lower()
        if domain == "3dnet.no" or domain.endswith(".3dnet.no"):
            return (price * Decimal("1.25")).quantize(Decimal("0.01"))

        return price

    def _normalize_text(self, value: Any) -> str:
        """Normalize text for case-insensitive keyword checks."""
        if value is None:
            return ""
        return " ".join(str(value).strip().lower().split())

    def _interpret_stock_value(self, value: Any) -> Optional[bool]:
        """Interpret an explicit stock value from text, numbers, or booleans."""
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value > 0

        normalized = self._normalize_text(value)
        if not normalized:
            return None

        true_values = {
            "1",
            "true",
            "yes",
            "y",
            "available",
            "availability: instock",
            "instock",
            "in stock",
        }
        false_values = {
            "0",
            "false",
            "no",
            "n",
            "unavailable",
            "availability: outofstock",
            "outofstock",
            "out of stock",
            "sold out",
        }

        if normalized in true_values:
            return True
        if normalized in false_values:
            return False

        if "schema.org/instock" in normalized:
            return True
        if "schema.org/outofstock" in normalized:
            return False

        return None

    def _detect_stock_from_text(self, text: Optional[str]) -> Optional[bool]:
        """Detect stock state from free-form text."""
        import re

        normalized = self._normalize_text(text)
        if not normalized:
            return None

        explicit = self._interpret_stock_value(normalized)
        if explicit is not None:
            return explicit

        false_keywords = [
            self._normalize_text(keyword)
            for keyword in getattr(self, "STOCK_FALSE_KEYWORDS", [])
            if keyword
        ]
        true_keywords = [
            self._normalize_text(keyword)
            for keyword in getattr(self, "STOCK_TRUE_KEYWORDS", [])
            if keyword
        ]

        for keyword in false_keywords:
            if keyword and keyword in normalized:
                return False

        for keyword in true_keywords:
            if keyword and keyword in normalized:
                return True

        if re.search(r"\b\d+\s*(?:stk\.?\s*)?(?:pa|på)\s+lager\b", normalized):
            return True
        if re.search(r"\b\d+\s+in stock\b", normalized):
            return True

        return None

    def _detect_stock_from_element(self, elem: Any) -> Optional[bool]:
        """Detect stock state from an HTML element and its attributes."""
        if elem is None:
            return None

        class_names = elem.get("class", []) if hasattr(elem, "get") else []
        if not isinstance(class_names, list):
            class_names = [class_names]

        false_classes = {
            self._normalize_text(keyword)
            for keyword in getattr(self, "STOCK_FALSE_CLASSES", [])
            if keyword
        }
        true_classes = {
            self._normalize_text(keyword)
            for keyword in getattr(self, "STOCK_TRUE_CLASSES", [])
            if keyword
        }

        for class_name in class_names:
            normalized_class = self._normalize_text(class_name)
            if any(keyword and keyword in normalized_class for keyword in false_classes):
                return False
            if any(keyword and keyword in normalized_class for keyword in true_classes):
                return True

        for attr_key in getattr(self, "STOCK_ATTR_KEYS", []):
            if not hasattr(elem, "get"):
                continue
            attr_value = elem.get(attr_key)
            explicit = self._interpret_stock_value(attr_value)
            if explicit is not None:
                return explicit
            detected = self._detect_stock_from_text(attr_value)
            if detected is not None:
                return detected

        text = elem.get_text(" ", strip=True) if hasattr(elem, "get_text") else str(elem)
        return self._detect_stock_from_text(text)

    def _detect_stock_status(self, soup: BeautifulSoup) -> Optional[bool]:
        """Detect stock state from a full product page."""
        availability_elem = soup.select_one(
            'link[itemprop="availability"], meta[itemprop="availability"], [itemprop="availability"]'
        )
        if availability_elem:
            availability_value = (
                availability_elem.get("href")
                or availability_elem.get("content")
                or availability_elem.get_text(" ", strip=True)
            )
            explicit = self._interpret_stock_value(availability_value)
            if explicit is not None:
                return explicit
            detected = self._detect_stock_from_text(availability_value)
            if detected is not None:
                return detected

        stock_selectors = [
            ".stock",
            ".product-stock",
            ".availability",
            ".in-stock",
            ".out-of-stock",
            '[class*="stock"]',
            '[class*="avail"]',
            '[data-stock]',
            '[data-stock-status]',
            '[data-availability]',
        ]
        for selector in stock_selectors:
            for elem in soup.select(selector):
                detected = self._detect_stock_from_element(elem)
                if detected is not None:
                    return detected

        body = soup.body
        if body:
            detected = self._detect_stock_from_element(body)
            if detected is not None:
                return detected

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
