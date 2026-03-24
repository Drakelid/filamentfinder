import pytest
from app.utils.weight import extract_weight_grams


# --- kg patterns ---
def test_kg_integer():
    assert extract_weight_grams("Bambu PLA 1kg spool") == 1000.0

def test_kg_decimal():
    assert extract_weight_grams("Filament 2.3 kg") == 2300.0

def test_kg_no_space():
    assert extract_weight_grams("Polymaker PLA 1kg") == 1000.0


# --- g patterns ---
def test_grams_integer():
    assert extract_weight_grams("Sample spool 500g") == 500.0

def test_grams_with_space():
    assert extract_weight_grams("Mini spool 250 g") == 250.0

def test_grams_not_diameter():
    # 1.75mm should NOT be interpreted as 1.75g
    assert extract_weight_grams("PLA 1.75mm filament") is None

def test_grams_small_number_with_mm():
    # 3mm diameter filament — should not match as weight
    assert extract_weight_grams("ABS 3mm spool") is None


# --- lbs patterns ---
def test_lbs():
    result = extract_weight_grams("1 lb spool")
    assert result is not None
    assert abs(result - 453.592) < 1.0

def test_lb_singular():
    result = extract_weight_grams("2lb roll")
    assert result is not None
    assert abs(result - 907.18) < 1.0


# --- guard cases ---
def test_empty_string():
    assert extract_weight_grams("") is None

def test_no_weight():
    assert extract_weight_grams("PLA Matte Black") is None

def test_below_minimum():
    # 30g is noise — ignore
    assert extract_weight_grams("Sample 30g") is None

def test_above_maximum():
    # 25000g implausible spool
    assert extract_weight_grams("Industrial 25000g") is None

def test_combined_fields():
    # Simulates concatenated name + variant + size
    assert extract_weight_grams("Bambu PLA  1kg") == 1000.0

def test_case_insensitive():
    assert extract_weight_grams("PETG 1KG BLACK") == 1000.0
