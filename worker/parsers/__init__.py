from typing import Dict

from worker.parsers.base import BaseParser, ParsedProduct
from worker.parsers.jsonld import JsonLdParser
from worker.parsers.shopify import ShopifyParser
from worker.parsers.woocommerce import WooCommerceParser
from worker.parsers.magento import MagentoParser
from worker.parsers.generic import GenericParser

# All available parsers in priority order (highest priority first)
_PARSERS = [
    JsonLdParser(),      # priority 100 - structured data is most reliable
    ShopifyParser(),     # priority 90
    WooCommerceParser(), # priority 80
    MagentoParser(),     # priority 70
    GenericParser(),     # priority 0 - fallback
]


def get_parser(html: str, url: str, headers: Dict[str, str] = None) -> BaseParser:
    """
    Get the appropriate parser for the given HTML content.
    
    Tries each parser in priority order and returns the first one that can parse the page.
    Falls back to GenericParser if no specific parser matches.
    
    Args:
        html: The HTML content of the page
        url: The URL of the page
        headers: Optional response headers
        
    Returns:
        A parser instance that can handle the page
    """
    if headers is None:
        headers = {}
    
    # Sort by priority (highest first) and try each parser
    for parser in sorted(_PARSERS, key=lambda p: p.priority, reverse=True):
        try:
            if parser.can_parse(html, url, headers):
                return parser
        except Exception:
            # If can_parse fails, skip this parser
            continue
    
    # Fallback to generic parser
    return GenericParser()


__all__ = [
    "BaseParser",
    "ParsedProduct",
    "JsonLdParser",
    "ShopifyParser",
    "WooCommerceParser",
    "MagentoParser",
    "GenericParser",
    "get_parser",
]
