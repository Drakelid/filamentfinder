import pytest
from decimal import Decimal

from worker.parsers.base import ParsedProduct
from worker.crawler.product_matcher import ProductMatcher


class TestProductMatcher:
    @pytest.fixture
    def matcher(self):
        return ProductMatcher()
    
    def test_match_filament_by_keyword(self, matcher):
        product = ParsedProduct(
            name="PLA Filament 1.75mm 1kg",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "filament"
        assert result.confidence >= 0.3
    
    def test_match_filament_by_material(self, matcher):
        product = ParsedProduct(
            name="PETG Blue 1kg Spool",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "filament"
        assert result.product_type == "petg"
    
    def test_match_resin_by_keyword(self, matcher):
        product = ParsedProduct(
            name="UV Resin 500ml Standard Grey",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "resin"
        assert result.confidence >= 0.3
    
    def test_match_resin_405nm(self, matcher):
        product = ParsedProduct(
            name="405nm Photopolymer Resin 1L",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "resin"
    
    def test_match_resin_water_washable(self, matcher):
        product = ParsedProduct(
            name="Water-Washable Resin Grey 500g",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "resin"
        assert result.product_type == "water-washable"
    
    def test_no_match_printer(self, matcher):
        product = ParsedProduct(
            name="3D Printer Ender 3 V2",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == False
    
    def test_no_match_nozzle(self, matcher):
        product = ParsedProduct(
            name="Brass Nozzle 0.4mm for 3D Printer",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == False
    
    def test_no_match_random_product(self, matcher):
        product = ParsedProduct(
            name="Coffee Mug Blue",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == False
    
    def test_no_match_accessory(self, matcher):
        product = ParsedProduct(
            name="3D Printer Tool Kit",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == False

    def test_no_match_accessory_even_with_brand(self, matcher):
        product = ParsedProduct(
            name="Prusa Enclosure for MK4",
            url="https://example.com/product",
            brand="Prusa",
        )
        result = matcher.match(product)

        assert result.is_match == False

    def test_no_match_brand_only_signal(self, matcher):
        product = ParsedProduct(
            name="Polymaker Tool Kit",
            url="https://example.com/product",
            brand="Polymaker",
        )
        result = matcher.match(product)

        assert result.is_match == False

    def test_filament_type_detection_pla(self, matcher):
        product = ParsedProduct(
            name="PLA+ Pro Filament Black",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.product_type == "pla"
    
    def test_filament_type_detection_tpu(self, matcher):
        product = ParsedProduct(
            name="TPU 95A Flexible Filament",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.product_type == "tpu"
    
    def test_filament_type_detection_carbon(self, matcher):
        product = ParsedProduct(
            name="Carbon Fiber PETG CF Filament",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.product_type == "carbon"
    
    def test_resin_type_detection_abs_like(self, matcher):
        product = ParsedProduct(
            name="ABS-Like Tough Resin Grey",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "resin"
        assert result.product_type == "abs-like"
    
    def test_match_with_brand(self, matcher):
        product = ParsedProduct(
            name="Prusament PLA Galaxy Black",
            url="https://example.com/product",
            brand="Prusa",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.category == "filament"
    
    def test_match_url_filament(self, matcher):
        assert matcher.match_url("https://store.com/filament/pla") == True
        assert matcher.match_url("https://store.com/3d-print/petg") == True
    
    def test_match_url_resin(self, matcher):
        assert matcher.match_url("https://store.com/resin/standard") == True
    
    def test_match_url_no_match(self, matcher):
        assert matcher.match_url("https://store.com/printers") == False
        assert matcher.match_url("https://store.com/tools") == False
    
    def test_confidence_high_for_explicit_filament(self, matcher):
        product = ParsedProduct(
            name="PLA Filament 1.75mm 1kg Spool",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.confidence >= 0.5
    
    def test_confidence_lower_for_ambiguous(self, matcher):
        product = ParsedProduct(
            name="PLA Material",
            url="https://example.com/product",
        )
        result = matcher.match(product)
        
        assert result.is_match == True
        assert result.confidence < 0.8
