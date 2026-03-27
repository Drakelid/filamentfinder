from typing import Dict

from worker.parsers.base import BaseParser, ParsedProduct
from worker.parsers.jsonld import JsonLdParser
from worker.parsers.shopify import ShopifyParser
from worker.parsers.woocommerce import WooCommerceParser
from worker.parsers.magento import MagentoParser
from worker.parsers.generic import GenericParser

# Parser classes in priority order (highest priority first).
# Fresh instances are created per call to avoid shared mutable state
# (e.g. selector_overrides) across concurrent crawls.
_PARSER_CLASSES = [
    (JsonLdParser, 100),       # structured data is most reliable
    (ShopifyParser, 90),
    (WooCommerceParser, 80),
    (MagentoParser, 70),
    (GenericParser, 0),        # fallback
]


def get_parser(html: str, url: str, headers: Dict[str, str] = None) -> BaseParser:
    """
    Get the appropriate parser for the given HTML content.
    
    Tries each parser in priority order and returns the first one that can parse the page.
    Falls back to GenericParser if no specific parser matches.
    
    A fresh parser instance is returned each time to ensure concurrent crawls
    do not share mutable state (e.g. selector_overrides).
    
    Args:
        html: The HTML content of the page
        url: The URL of the page
        headers: Optional response headers
        
    Returns:
        A parser instance that can handle the page
    """
    if headers is None:
        headers = {}
    
    for parser_cls, _priority in sorted(_PARSER_CLASSES, key=lambda x: x[1], reverse=True):
        try:
            parser = parser_cls()
            if parser.can_parse(html, url, headers):
                return parser
        except Exception:
            continue
    
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
