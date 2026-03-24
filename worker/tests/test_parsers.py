import pytest
from decimal import Decimal

from worker.parsers import (
    JsonLdParser,
    ShopifyParser,
    WooCommerceParser,
    MagentoParser,
    GenericParser,
    ParsedProduct,
)


class TestJsonLdParser:
    @pytest.fixture
    def parser(self):
        return JsonLdParser()
    
    def test_can_parse_with_jsonld(self, parser):
        html = '''
        <html>
        <head>
            <script type="application/ld+json">
            {"@type": "Product", "name": "Test"}
            </script>
        </head>
        </html>
        '''
        assert parser.can_parse(html, "https://example.com", {}) == True
    
    def test_can_parse_without_jsonld(self, parser):
        html = '<html><body>No JSON-LD here</body></html>'
        assert parser.can_parse(html, "https://example.com", {}) == False
    
    def test_parse_product_basic(self, parser):
        html = '''
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@type": "Product",
                "name": "PLA Filament 1kg",
                "brand": {"@type": "Brand", "name": "TestBrand"},
                "sku": "PLA-001",
                "image": "https://example.com/image.jpg",
                "offers": {
                    "@type": "Offer",
                    "price": "24.99",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock"
                }
            }
            </script>
        </head>
        </html>
        '''
        product = parser.parse_product(html, "https://example.com/product")
        
        assert product is not None
        assert product.name == "PLA Filament 1kg"
        assert product.brand == "TestBrand"
        assert product.sku == "PLA-001"
        assert product.price == Decimal("24.99")
        assert product.currency == "USD"
        assert product.in_stock == True
        assert product.image_url == "https://example.com/image.jpg"
    
    def test_parse_product_with_graph(self, parser):
        html = '''
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@graph": [
                    {"@type": "WebPage"},
                    {
                        "@type": "Product",
                        "name": "UV Resin 500ml",
                        "offers": {"price": "19.99", "priceCurrency": "EUR"}
                    }
                ]
            }
            </script>
        </head>
        </html>
        '''
        product = parser.parse_product(html, "https://example.com/product")
        
        assert product is not None
        assert product.name == "UV Resin 500ml"
        assert product.price == Decimal("19.99")
        assert product.currency == "EUR"
    
    def test_parse_product_list(self, parser):
        html = '''
        <html>
        <head>
            <script type="application/ld+json">
            [
                {"@type": "Product", "name": "Product 1", "offers": {"price": "10"}},
                {"@type": "Product", "name": "Product 2", "offers": {"price": "20"}}
            ]
            </script>
        </head>
        </html>
        '''
        products = parser.parse_product_list(html, "https://example.com")
        
        assert len(products) == 2
        assert products[0].name == "Product 1"
        assert products[1].name == "Product 2"


class TestShopifyParser:
    @pytest.fixture
    def parser(self):
        return ShopifyParser()
    
    def test_can_parse_shopify_cdn(self, parser):
        html = '<html><script src="https://cdn.shopify.com/s/files/1/script.js"></script></html>'
        assert parser.can_parse(html, "https://example.com", {}) == True
    
    def test_can_parse_shopify_header(self, parser):
        html = '<html><body>Regular page</body></html>'
        headers = {"server": "Shopify"}
        assert parser.can_parse(html, "https://example.com", headers) == True
    
    def test_can_parse_not_shopify(self, parser):
        html = '<html><body>Regular page</body></html>'
        assert parser.can_parse(html, "https://example.com", {}) == False
    
    def test_extract_product_links(self, parser):
        html = '''
        <html>
        <body>
            <a href="/products/pla-filament">PLA</a>
            <a href="/products/petg-filament">PETG</a>
            <a href="/about">About</a>
        </body>
        </html>
        '''
        links = parser.extract_product_links(html, "https://store.example.com/collections/filaments")
        
        assert len(links) == 2
        assert "https://store.example.com/products/pla-filament" in links
        assert "https://store.example.com/products/petg-filament" in links


class TestWooCommerceParser:
    @pytest.fixture
    def parser(self):
        return WooCommerceParser()
    
    def test_can_parse_woocommerce(self, parser):
        html = '<html><body class="woocommerce">Shop</body></html>'
        assert parser.can_parse(html, "https://example.com", {}) == True
    
    def test_can_parse_not_woocommerce(self, parser):
        html = '<html><body>Regular page</body></html>'
        assert parser.can_parse(html, "https://example.com", {}) == False
    
    def test_parse_product(self, parser):
        html = '''
        <html>
        <body class="woocommerce">
            <h1 class="product_title">PETG Filament Blue</h1>
            <span class="woocommerce-Price-amount">$29.99</span>
            <span class="sku">PETG-BLUE-001</span>
            <p class="stock in-stock">In stock</p>
        </body>
        </html>
        '''
        product = parser.parse_product(html, "https://example.com/product/petg")
        
        assert product is not None
        assert product.name == "PETG Filament Blue"
        assert product.price == Decimal("29.99")
        assert product.sku == "PETG-BLUE-001"
        assert product.in_stock == True


class TestMagentoParser:
    @pytest.fixture
    def parser(self):
        return MagentoParser()
    
    def test_can_parse_magento(self, parser):
        html = '<html><script>require(["mage/cookies"])</script></html>'
        assert parser.can_parse(html, "https://example.com", {}) == True
    
    def test_can_parse_magento_header(self, parser):
        html = '<html><body>Page</body></html>'
        headers = {"x-magento-vary": "abc123"}
        assert parser.can_parse(html, "https://example.com", headers) == True
    
    def test_can_parse_not_magento(self, parser):
        html = '<html><body>Regular page</body></html>'
        assert parser.can_parse(html, "https://example.com", {}) == False


class TestGenericParser:
    @pytest.fixture
    def parser(self):
        return GenericParser()
    
    def test_can_parse_always(self, parser):
        html = '<html><body>Any page</body></html>'
        assert parser.can_parse(html, "https://example.com", {}) == True
    
    def test_parse_product_with_itemprop(self, parser):
        html = '''
        <html>
        <body>
            <h1 itemprop="name">ABS Filament 1kg Black</h1>
            <span itemprop="price" content="34.99">$34.99</span>
            <span itemprop="sku">ABS-BLK-1KG</span>
            <img itemprop="image" src="https://example.com/abs.jpg">
            <link itemprop="availability" href="https://schema.org/InStock">
        </body>
        </html>
        '''
        product = parser.parse_product(html, "https://example.com/product")
        
        assert product is not None
        assert product.name == "ABS Filament 1kg Black"
        assert product.price == Decimal("34.99")
        assert product.sku == "ABS-BLK-1KG"
    
    def test_parse_product_with_classes(self, parser):
        html = '''
        <html>
        <body>
            <h1 class="product-title">TPU Flexible Filament</h1>
            <span class="price">€19.99</span>
        </body>
        </html>
        '''
        product = parser.parse_product(html, "https://example.com/product")
        
        assert product is not None
        assert product.name == "TPU Flexible Filament"
        assert product.price == Decimal("19.99")
        assert product.currency == "EUR"
    
    def test_extract_product_links(self, parser):
        html = '''
        <html>
        <body>
            <a href="/product/item1">Item 1</a>
            <a href="/products/item2">Item 2</a>
            <a href="/p/item3">Item 3</a>
            <a href="/about">About</a>
        </body>
        </html>
        '''
        links = parser.extract_product_links(html, "https://example.com/category")
        
        assert len(links) >= 2
    
    def test_clean_price_usd(self, parser):
        assert parser._clean_price("$24.99") == Decimal("24.99")
        assert parser._clean_price("USD 24.99") == Decimal("24.99")
        assert parser._clean_price("24.99") == Decimal("24.99")
    
    def test_clean_price_eur(self, parser):
        assert parser._clean_price("€19,99") == Decimal("19.99")
        assert parser._clean_price("19,99 €") == Decimal("19.99")
    
    def test_clean_price_thousands(self, parser):
        assert parser._clean_price("$1,234.56") == Decimal("1234.56")
        assert parser._clean_price("1.234,56 €") == Decimal("1234.56")
    
    def test_extract_currency(self, parser):
        assert parser._extract_currency("$24.99") == "USD"
        assert parser._extract_currency("€19.99") == "EUR"
        assert parser._extract_currency("£15.99") == "GBP"
        assert parser._extract_currency("24.99 USD") == "USD"
