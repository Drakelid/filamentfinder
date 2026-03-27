"""Tests for the cross-source comparison service."""

import pytest
from unittest.mock import MagicMock
from app.services.cross_source import (
    extract_product_key,
    build_product_data,
    create_group_result,
    compare_products,
)


def _make_product(
    name="eSUN PLA+ 1.75mm 1kg Black",
    brand="eSUN",
    category="filament",
    product_type="pla",
    color="Black",
    gtin=None,
    canonical_url="https://store.example.com/esun-pla-plus-black",
    source_id=1,
    price_amount=None,
    **kwargs,
):
    """Create a mock product object for testing."""
    p = MagicMock()
    p.name = name
    p.brand = brand
    p.category = category
    p.product_type = product_type
    p.color = color
    p.gtin = gtin
    p.sku = kwargs.get("sku")
    p.canonical_url = canonical_url
    p.source_id = source_id
    p.id = kwargs.get("id", 1)
    p.size = kwargs.get("size")
    p.image_url = kwargs.get("image_url")
    p.latest_change_percent = kwargs.get("latest_change_percent")
    p.latest_change_type = kwargs.get("latest_change_type")

    if price_amount is not None:
        obs = MagicMock()
        obs.price_amount = price_amount
        obs.shipping_amount = kwargs.get("shipping_amount")
        obs.total_price_amount = kwargs.get("total_price_amount")
        obs.currency = kwargs.get("currency", "USD")
        obs.shipping_currency = kwargs.get("shipping_currency")
        obs.in_stock = kwargs.get("in_stock", True)
        obs.observed_at = MagicMock()
        obs.observed_at.isoformat.return_value = "2024-01-01T00:00:00"
        p.price_observations = [obs]
    else:
        p.price_observations = []

    source = MagicMock()
    source.name = kwargs.get("source_name", "Test Store")
    source.domain = kwargs.get("source_domain", "store.example.com")
    p.source = source
    return p


class TestExtractProductKey:
    def test_gtin_match(self):
        p = _make_product(gtin="1234567890123")
        key_type, key_value = extract_product_key(p)
        assert key_type == "gtin"
        assert key_value == "1234567890123"

    def test_name_match_with_brand_material_weight_color(self):
        p = _make_product(name="eSUN PLA+ 1.75mm 1kg Black", brand="eSUN")
        key_type, key_value = extract_product_key(p)
        assert key_type == "name"
        assert "esun" in key_value
        assert "pla" in key_value.lower()
        assert "black" in key_value

    def test_excludes_printer_accessories(self):
        p = _make_product(name="Creality Nozzle 0.4mm Brass", product_type=None)
        key_type, _ = extract_product_key(p)
        assert key_type == "none"

    def test_excludes_rc_products(self):
        p = _make_product(
            name="Traxxas TRX-4 RC Car Tire",
            canonical_url="https://store.example.com/radiostyrt/traxxas",
        )
        key_type, _ = extract_product_key(p)
        assert key_type == "none"

    def test_excludes_products_without_material(self):
        p = _make_product(name="Random Widget", brand="SomeBrand", product_type=None)
        key_type, _ = extract_product_key(p)
        assert key_type == "none"

    def test_no_brand_returns_none(self):
        p = _make_product(name="PLA 1kg", brand="")
        key_type, _ = extract_product_key(p)
        assert key_type == "none"

    def test_weight_normalization(self):
        p1 = _make_product(name="eSUN PLA+ 1kg Black", brand="eSUN")
        p2 = _make_product(name="eSUN PLA+ 1000g Black", brand="eSUN")
        _, key1 = extract_product_key(p1)
        _, key2 = extract_product_key(p2)
        assert key1 == key2

    def test_sku_extraction(self):
        p = _make_product(name="Polymaker PolyLite PLA PA02052 Black 1kg")
        key_type, key_value = extract_product_key(p)
        assert key_type == "sku"
        assert key_value == "PA02052"


class TestBuildProductData:
    def test_basic_serialization(self):
        p = _make_product(id=42, price_amount=29.99)
        data = build_product_data(p)
        assert data["id"] == 42
        assert data["name"] == "eSUN PLA+ 1.75mm 1kg Black"
        assert data["latest_price"]["amount"] == 29.99

    def test_no_price(self):
        p = _make_product()
        data = build_product_data(p)
        assert data["latest_price"] is None


class TestCreateGroupResult:
    def test_returns_none_for_single_source(self):
        prods = [
            {"source_id": 1, "latest_price": {"amount": 20, "total_amount": 20}},
            {"source_id": 1, "latest_price": {"amount": 22, "total_amount": 22}},
        ]
        assert create_group_result("key", prods, "name") is None

    def test_returns_group_for_multiple_sources(self):
        prods = [
            {"source_id": 1, "latest_price": {"amount": 20, "total_amount": 20}, "name": "PLA Black", "brand": "eSUN", "product_type": "pla", "color": "Black"},
            {"source_id": 2, "latest_price": {"amount": 30, "total_amount": 30}, "name": "PLA Black", "brand": "eSUN", "product_type": "pla", "color": "Black"},
        ]
        result = create_group_result("key", prods, "name")
        assert result is not None
        assert result["source_count"] == 2
        assert result["min_price"] == 20
        assert result["max_price"] == 30
        assert result["price_spread"] == 50.0


class TestCompareProducts:
    def test_empty_products(self):
        result = compare_products([])
        assert result["total_groups"] == 0
        assert result["groups"] == []

    def test_groups_matching_products(self):
        p1 = _make_product(id=1, source_id=1, price_amount=20, gtin="1234567890123", source_name="Store A")
        p2 = _make_product(id=2, source_id=2, price_amount=25, gtin="1234567890123", source_name="Store B")
        result = compare_products([p1, p2])
        assert result["total_groups"] >= 1
        gtin_groups = [g for g in result["groups"] if g["match_type"] == "gtin"]
        assert len(gtin_groups) == 1
        assert gtin_groups[0]["source_count"] == 2

    def test_no_group_for_single_source(self):
        p1 = _make_product(id=1, source_id=1, price_amount=20, gtin="1234567890123")
        p2 = _make_product(id=2, source_id=1, price_amount=25, gtin="1234567890123")
        result = compare_products([p1, p2])
        assert result["total_groups"] == 0
