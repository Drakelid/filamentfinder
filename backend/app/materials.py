"""
Centralized material registry for filament and resin types.
This module provides consistent material detection and categorization across the application.
"""

import re
from typing import Optional, Dict, List, Tuple

# Material categories
CATEGORY_FILAMENT = "filament"
CATEGORY_RESIN = "resin"

# Material registry with detection patterns and metadata
MATERIALS: Dict[str, Dict] = {
    # === STANDARD FILAMENTS ===
    "PLA": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PLA",
        "description": "Polylactic Acid - Easy to print, biodegradable",
        "patterns": [r"\bpla\b", r"\becopla\b", r"\bpla[\s-]?mat(?:te)?\b"],
        "variants": ["PLA+", "PLA Pro", "PLA Silk", "PLA Matte", "PLA Wood", "PLA Metal"],
        "priority": 100,  # Lower priority = matched later (base materials)
    },
    "PLA+": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PLA+",
        "description": "Enhanced PLA with better strength",
        "patterns": [r"\bpla\s*\+", r"\bpla\s*plus\b", r"\bpla[\s-]?pro\b", r"\bhyper\s*pla\b", r"\btough\s*pla\b", r"\bpla\s*tough\b"],
        "parent": "PLA",
        "priority": 50,
    },
    "PETG": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PETG",
        "description": "Polyethylene Terephthalate Glycol - Strong and flexible",
        "patterns": [r"\bpetg\b", r"\bpctg\b"],
        "priority": 100,
    },
    "PCTG": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PCTG",
        "description": "Polycyclohexylenedimethylene Terephthalate Glycol - Clearer than PETG",
        "patterns": [r"\bpctg\b"],
        "parent": "PETG",
        "priority": 50,
    },
    "ABS": {
        "category": CATEGORY_FILAMENT,
        "display_name": "ABS",
        "description": "Acrylonitrile Butadiene Styrene - Durable, heat resistant",
        "patterns": [r"\babs\b"],
        "priority": 100,
    },
    "ASA": {
        "category": CATEGORY_FILAMENT,
        "display_name": "ASA",
        "description": "Acrylonitrile Styrene Acrylate - UV resistant outdoor use",
        "patterns": [r"\basa\b"],
        "priority": 100,
    },
    "TPU": {
        "category": CATEGORY_FILAMENT,
        "display_name": "TPU",
        "description": "Thermoplastic Polyurethane - Flexible, rubber-like",
        "patterns": [r"\btpu\b", r"\btpu[\s-]?\d+[a-z]?\b", r"\bflex\b.*\bfilament\b", r"\bflexible\b.*\bfilament\b"],
        "priority": 50,  # Higher priority than TPE
    },
    "TPE": {
        "category": CATEGORY_FILAMENT,
        "display_name": "TPE",
        "description": "Thermoplastic Elastomer - Flexible material",
        "patterns": [r"\btpe\b"],
        "parent": "TPU",  # Group TPE under TPU for comparison
        "priority": 60,
    },
    
    # === ENGINEERING FILAMENTS ===
    "NYLON": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Nylon",
        "description": "Polyamide - Strong, wear resistant",
        "patterns": [r"\bnylon\b", r"\bpolyamide\b"],
        "priority": 100,
    },
    "PA6": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PA6",
        "description": "Polyamide 6 - Engineering nylon",
        "patterns": [r"\bpa6\b(?![\s-]?[cg]f)"],
        "parent": "NYLON",
        "priority": 50,
    },
    "PA12": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PA12",
        "description": "Polyamide 12 - Low moisture absorption nylon",
        "patterns": [r"\bpa12\b(?![\s-]?[cg]f)"],
        "parent": "NYLON",
        "priority": 50,
    },
    "PA6-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PA6-CF",
        "description": "Carbon fiber reinforced PA6",
        "patterns": [r"\bpa6[\s-]?cf\b"],
        "parent": "NYLON",
        "priority": 10,
    },
    "PA6-GF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PA6-GF",
        "description": "Glass fiber reinforced PA6",
        "patterns": [r"\bpa6[\s-]?gf\b"],
        "parent": "NYLON",
        "priority": 10,
    },
    "PA12-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PA12-CF",
        "description": "Carbon fiber reinforced PA12",
        "patterns": [r"\bpa12[\s-]?cf\b"],
        "parent": "NYLON",
        "priority": 10,
    },
    "PC": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PC",
        "description": "Polycarbonate - High impact resistance",
        "patterns": [r"\bpc\b(?!i|s|b)"],  # Avoid PCI, PCS, PCB
        "priority": 100,
    },
    "PC-ABS": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PC-ABS",
        "description": "Polycarbonate ABS blend",
        "patterns": [r"\bpc[\s-]?abs\b"],
        "parent": "PC",
        "priority": 50,
    },
    
    # === SPECIALTY FILAMENTS ===
    "HIPS": {
        "category": CATEGORY_FILAMENT,
        "display_name": "HIPS",
        "description": "High Impact Polystyrene - Support material",
        "patterns": [r"\bhips\b"],
        "priority": 100,
    },
    "PVA": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PVA",
        "description": "Polyvinyl Alcohol - Water soluble support",
        "patterns": [r"\bpva\b"],
        "priority": 100,
    },
    "PVB": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PVB",
        "description": "Polyvinyl Butyral - Smoothable with alcohol",
        "patterns": [r"\bpvb\b"],
        "priority": 100,
    },
    "PP": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PP",
        "description": "Polypropylene - Chemical resistant",
        "patterns": [r"\bpp\b(?!s|e)"],  # Avoid PPS, PPE
        "priority": 100,
    },
    "PET": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PET",
        "description": "Polyethylene Terephthalate",
        "patterns": [r"\bpet\b(?!g)"],  # Avoid PETG
        "priority": 100,
    },
    
    # === HIGH PERFORMANCE FILAMENTS ===
    "PEEK": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PEEK",
        "description": "Polyether Ether Ketone - High performance",
        "patterns": [r"\bpeek\b"],
        "priority": 100,
    },
    "PEKK": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PEKK",
        "description": "Polyetherketoneketone - High performance",
        "patterns": [r"\bpekk\b"],
        "priority": 100,
    },
    "PEI": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PEI",
        "description": "Polyetherimide (Ultem) - High temp resistant",
        "patterns": [r"\bpei\b", r"\bultem\b"],
        "priority": 100,
    },
    "PPS": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PPS",
        "description": "Polyphenylene Sulfide - Chemical resistant",
        "patterns": [r"\bpps\b"],
        "priority": 100,
    },
    
    # === CARBON/GLASS FIBER COMPOSITES ===
    "PLA-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PLA-CF",
        "description": "Carbon fiber reinforced PLA",
        "patterns": [r"\bpla[\s-]?cf\b", r"\bpla[\s-]?carbon\b"],
        "parent": "PLA",
        "priority": 10,
    },
    "PETG-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PETG-CF",
        "description": "Carbon fiber reinforced PETG",
        "patterns": [r"\bpetg[\s-]?cf\b", r"\bpetg[\s-]?carbon\b"],
        "parent": "PETG",
        "priority": 10,
    },
    "ABS-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "ABS-CF",
        "description": "Carbon fiber reinforced ABS",
        "patterns": [r"\babs[\s-]?cf\b", r"\babs[\s-]?carbon\b"],
        "parent": "ABS",
        "priority": 10,
    },
    "ASA-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "ASA-CF",
        "description": "Carbon fiber reinforced ASA",
        "patterns": [r"\basa[\s-]?cf\b", r"\basa[\s-]?carbon\b"],
        "parent": "ASA",
        "priority": 10,
    },
    "PC-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PC-CF",
        "description": "Carbon fiber reinforced PC",
        "patterns": [r"\bpc[\s-]?cf\b", r"\bpc[\s-]?carbon\b"],
        "parent": "PC",
        "priority": 10,
    },
    
    # === SPECIALTY/COMPOSITE FILAMENTS ===
    "WOOD": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Wood",
        "description": "Wood fiber composite filament",
        "patterns": [r"\bwood\b", r"\blaywood\b", r"\blaywoo\b", r"\bbamboo\b(?!.*lab)"],
        "parent": "PLA",
        "priority": 40,
    },
    "SILK": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Silk",
        "description": "Silk-like shiny finish PLA",
        "patterns": [r"\bsilk\b"],
        "parent": "PLA",
        "priority": 40,
    },
    "MARBLE": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Marble",
        "description": "Marble-effect filament",
        "patterns": [r"\bmarble\b"],
        "parent": "PLA",
        "priority": 40,
    },
    "METAL": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Metal Fill",
        "description": "Metal powder filled filament",
        "patterns": [r"\bmetal[\s-]?fill\b", r"\bcopper[\s-]?fill\b", r"\bbronze[\s-]?fill\b", r"\bsteel[\s-]?fill\b"],
        "parent": "PLA",
        "priority": 40,
    },
    "GLOW": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Glow in Dark",
        "description": "Phosphorescent glow in the dark",
        "patterns": [r"\bglow\b", r"\bphosphorescent\b", r"\bluminous\b"],
        "parent": "PLA",
        "priority": 40,
    },
    "CONDUCTIVE": {
        "category": CATEGORY_FILAMENT,
        "display_name": "Conductive",
        "description": "Electrically conductive filament",
        "patterns": [r"\bconductive\b", r"\besd\b", r"\b3dxstat\b"],
        "parent": "PLA",
        "priority": 30,
    },
    "PAHT-CF": {
        "category": CATEGORY_FILAMENT,
        "display_name": "PAHT-CF",
        "description": "High temperature PA with carbon fiber",
        "patterns": [r"\bpaht[\s-]?cf\b"],
        "parent": "NYLON",
        "priority": 10,
    },
    
    # === RESINS ===
    "STANDARD_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "Standard Resin",
        "description": "Basic UV curing resin",
        "patterns": [r"\bstandard\s+resin\b", r"\bbasic\s+resin\b"],
        "priority": 100,
    },
    "ABS_LIKE_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "ABS-Like Resin",
        "description": "Tough resin with ABS-like properties",
        "patterns": [r"\babs[\s-]?like\s+resin\b", r"\btough\s+resin\b"],
        "priority": 50,
    },
    "WATER_WASHABLE_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "Water Washable Resin",
        "description": "Resin that cleans with water",
        "patterns": [r"\bwater[\s-]?washable\b"],
        "priority": 50,
    },
    "FLEXIBLE_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "Flexible Resin",
        "description": "Flexible/rubber-like resin",
        "patterns": [r"\bflex(?:ible)?\s+resin\b", r"\brubber[\s-]?like\s+resin\b"],
        "priority": 50,
    },
    "DENTAL_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "Dental Resin",
        "description": "Biocompatible dental applications",
        "patterns": [r"\bdental\s+resin\b", r"\bdental\b.*\bresin\b"],
        "priority": 50,
    },
    "CASTABLE_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "Castable Resin",
        "description": "For jewelry casting",
        "patterns": [r"\bcastable\s+resin\b", r"\bcasting\s+resin\b"],
        "priority": 50,
    },
    "HIGH_TEMP_RESIN": {
        "category": CATEGORY_RESIN,
        "display_name": "High Temp Resin",
        "description": "Heat resistant resin",
        "patterns": [r"\bhigh[\s-]?temp\b.*\bresin\b", r"\bheat[\s-]?resistant\s+resin\b"],
        "priority": 50,
    },
}

# Build sorted list by priority for matching (lower priority = matched first = more specific)
_SORTED_MATERIALS: List[Tuple[str, Dict]] = sorted(
    MATERIALS.items(),
    key=lambda x: x[1].get("priority", 100)
)


def detect_material(text: str, product_type: Optional[str] = None) -> Optional[str]:
    """
    Detect material type from product name or description.
    
    Args:
        text: Product name or description to analyze
        product_type: Optional product_type field from database
        
    Returns:
        Material key (e.g., "PLA", "PETG-CF") or None if not detected
    """
    if not text:
        return None
        
    text_lower = text.lower()
    
    # Check patterns in priority order (most specific first)
    for material_key, material_info in _SORTED_MATERIALS:
        for pattern in material_info.get("patterns", []):
            if re.search(pattern, text_lower):
                return material_key
    
    # Fall back to product_type field if available
    if product_type:
        pt_upper = product_type.upper()
        if pt_upper in MATERIALS:
            return pt_upper
        # Try to match product_type to a material
        pt_lower = product_type.lower()
        for material_key, material_info in _SORTED_MATERIALS:
            for pattern in material_info.get("patterns", []):
                if re.search(pattern, pt_lower):
                    return material_key
    
    return None


def get_material_info(material_key: str) -> Optional[Dict]:
    """Get material information by key."""
    return MATERIALS.get(material_key)


def get_material_display_name(material_key: str) -> str:
    """Get display name for a material, or the key itself if not found."""
    info = MATERIALS.get(material_key)
    return info.get("display_name", material_key) if info else material_key


def get_material_category(material_key: str) -> Optional[str]:
    """Get category (filament/resin) for a material."""
    info = MATERIALS.get(material_key)
    return info.get("category") if info else None


def get_parent_material(material_key: str) -> Optional[str]:
    """Get parent material for variants (e.g., PLA-CF -> PLA)."""
    info = MATERIALS.get(material_key)
    return info.get("parent") if info else None


def get_base_material(material_key: str) -> str:
    """Get the base material, following parent chain."""
    parent = get_parent_material(material_key)
    if parent:
        return get_base_material(parent)
    return material_key


def get_all_materials(category: Optional[str] = None) -> List[str]:
    """Get all material keys, optionally filtered by category."""
    if category:
        return [k for k, v in MATERIALS.items() if v.get("category") == category]
    return list(MATERIALS.keys())


def get_filament_materials() -> List[str]:
    """Get all filament material keys."""
    return get_all_materials(CATEGORY_FILAMENT)


def get_resin_materials() -> List[str]:
    """Get all resin material keys."""
    return get_all_materials(CATEGORY_RESIN)


def normalize_material_for_grouping(material_key: Optional[str]) -> str:
    """
    Normalize material key for grouping purposes.
    This groups variants under their parent material for comparison.
    
    E.g., PLA+, PLA-CF all become "PLA" for grouping.
    """
    if not material_key:
        return "OTHER"
    
    # Get base material for grouping
    base = get_base_material(material_key)
    return base if base in MATERIALS else "OTHER"
