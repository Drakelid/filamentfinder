"""Cross-source product comparison service.

Extracts matching logic for grouping identical products across different
sources to enable price comparison.  Matching uses GTIN, extracted SKU,
and normalized product names (brand + material + weight + color).
"""

import re
from typing import Optional, List

from app.materials import (
    detect_material,
    get_material_display_name,
    normalize_material_for_grouping,
    MATERIALS,
)

# ---------------------------------------------------------------------------
# Exclusion patterns – products that are NOT filament/resin consumables
# ---------------------------------------------------------------------------

_EXCLUDE_NAME_PATTERNS = [
    r"\b(nozzle|hotend|extruder|heater|thermistor|sensor)\b",
    r"(plate|buildplate|build plate|print bed|heated bed|flexplate|flex plate|pei plate|glass plate)",
    r"\b(tensioner|belt|pulley|bearing|motor|stepper)\b",
    r"\b(panel|cover|enclosure|door|lid|frame)\b",
    r"\b(cable|wire|connector|adapter|power supply|psu)\b",
    r"\b(screen|display|lcd|touchscreen)\b",
    r"\b(fan|cooling|duct|shroud)\b",
    r"\b(tube|ptfe|bowden|coupler|fitting)\b",
    r"\b(scraper|spatula|tool|wrench|allen)\b",
    r"\b(tape|glue|adhesive|hairspray)\b",
    r"\b(silicone|sock|insulation)\b",
    r"\b(spring|magnet|clip|clamp)\b",
    r"\b(upgrade|kit|mod|replacement|spare)\b",
    r"\b(3d printer|printer|fdm printer|sla printer|resin printer)\b",
    r"\b(wash|cure|station|cleaning)\b",
    r"\b(tank|vat|fep|film)\b",
    r"\b(leveling|calibration|probe)\b",
    r"\b(spool\s*holder|filament\s*holder|dry\s*box|dryer)\b",
    r"\b(bed\s*adhesive|print\s*surface)\b",
    r"\b(radiostyrt|rc\s*(car|boat|plane|drone)|drone|helicopter|aircraft|propeller)\b",
    r"\b(serv[o|e]|receiver|transmitter|gimbal)\b",
    r"\b(battery|batteri|lipo|mah|charger)\b",
    r"\b(gear|gears|shock|shocks|tire|tires|wheel|wheels|axle|axles|suspension|suspensions|rim|rims)\b",
    r"\b(tilbeh[oø]r|tilbehor|accessor(?:y|ies))\b",
    r"\b(trykplade|trykplate|plade|platta|byggplate|byggplade)\b",
    r"\b(build\s*sheet|plate\s*film|surface\s*sheet)\b",
    r"\b(traxxas|trx-?\d{3,4}|1\/10\s*(scale)?|rc\s*wheels?)\b",
]

_EXCLUDE_URL_KEYWORDS = [
    'radiostyrt', 'rc/', '/rc-', 'rc-bil', 'rc-car', 'traxxas',
    '/servo', '/propeller', '/helicopter', '/drone',
]

# ---------------------------------------------------------------------------
# Known brands mapping  (input token → canonical key)
# ---------------------------------------------------------------------------

KNOWN_BRANDS = {
    # Multi-word brands (longer strings matched first)
    'clas ohlson by flashforge': 'flashforge',
    'clas ohlson': 'clasohlson',
    'bambu lab': 'bambulab',
    'devil design': 'devildesign',
    'amazon basics': 'amazonbasics',
    'add north': 'addnorth',
    'add:north': 'addnorth',
    'lay filaments': 'layfilaments',
    'prima creator': 'primacreator',
    'siraya tech': 'siraya',
    'the filament': 'thefilament',
    '3d xtech': '3dxtech',
    'raise 3d': 'raise3d',
    'creality 3d': 'creality',
    'creality3d': 'creality',
    'copymaster 3d': 'copymaster',
    'copymaster3d': 'copymaster',
    'innofil 3d': 'innofil3d',
    'innofil3d': 'innofil3d',
    'xyz printing': 'xyzprinting',
    'filament pm': 'filamentpm',
    'c-tech': 'ctech',
    'poly filament': 'polymaker',
    # Polymaker product lines -> polymaker
    'polyterra': 'polymaker',
    'polylite': 'polymaker',
    'polysonic': 'polymaker',
    'polycast': 'polymaker',
    'panchroma': 'polymaker',
    'polymax': 'polymaker',
    'polysmooth': 'polymaker',
    'polywood': 'polymaker',
    'polymide': 'polymaker',
    'polyflex': 'polymaker',
    'polymaker': 'polymaker',
    # Single word brands - common
    'bambulab': 'bambulab',
    'bambu': 'bambulab',
    'prusament': 'prusament',
    'prusa': 'prusa',
    'esun': 'esun',
    'sunlu': 'sunlu',
    'overture': 'overture',
    'hatchbox': 'hatchbox',
    'eryone': 'eryone',
    'creality': 'creality',
    'elegoo': 'elegoo',
    'anycubic': 'anycubic',
    'flashforge': 'flashforge',
    'fiberlogy': 'fiberlogy',
    'colorfabb': 'colorfabb',
    'formfutura': 'formfutura',
    'fillamentum': 'fillamentum',
    'extrudr': 'extrudr',
    '3djake': '3djake',
    'spectrum': 'spectrum',
    'spektrum': 'spectrum',
    'rosa3d': 'rosa3d',
    'polyalkemi': 'polyalkemi',
    'jayo': 'jayo',
    'kingroon': 'kingroon',
    'qidi': 'qidi',
    'siraya': 'siraya',
    'phrozen': 'phrozen',
    'monocure': 'monocure',
    'liqcreate': 'liqcreate',
    'inland': 'inland',
    'geeetech': 'geeetech',
    'tianse': 'tianse',
    'ziro': 'ziro',
    'matterhackers': 'matterhackers',
    'protopasta': 'protopasta',
    'maertz': 'maertz',
    'real': 'real',
    'verbatim': 'verbatim',
    'basf': 'basf',
    'ultimaker': 'ultimaker',
    'zortrax': 'zortrax',
    # Lay filaments variants
    'laybrick': 'layfilaments',
    'laywood': 'layfilaments',
    'laywoo': 'layfilaments',
    # PrimaCreator variants
    'primacreator': 'primacreator',
    'primaselect': 'primacreator',
    'easyprint': 'primacreator',
    # Additional brands
    'gembird': 'gembird',
    'renkforce': 'renkforce',
    'copymaster': 'copymaster',
    'ordrett': 'ordrett',
    'panda': 'panda',
    'makerbot': 'makerbot',
    'radius': 'radius',
    'kruzzel': 'kruzzel',
    'azurefilm': 'azurefilm',
    'nobufil': 'nobufil',
    'r3d': 'r3d',
    'recreus': 'recreus',
    'formlabs': 'formlabs',
    'cctree': 'cctree',
    # 3DXTech variants
    '3dxtech': '3dxtech',
    'carbonx': '3dxtech',
    '3dxstat': '3dxtech',
    # More brands
    'addnorth': 'addnorth',
    '3dnet': '3dnet',
    'raise3d': 'raise3d',
    'devildesign': 'devildesign',
    'devil': 'devildesign',
    'smartfil': 'smartfil',
    'xyzprinting': 'xyzprinting',
    'filamentpm': 'filamentpm',
    'ctech': 'ctech',
    # Additional brand variations
    'ulti maker': 'ultimaker',
    'easy print': 'primacreator',
    'cr-pla': 'creality',
    'cr-petg': 'creality',
    'cr-abs': 'creality',
    'ender': 'creality',
    'cc tree': 'cctree',
    # Norwegian/European brands
    'tinmorry': 'tinmorry',
    'reprapper': 'reprapper',
    'gst3d': 'gst3d',
    'yousu': 'yousu',
    'amolen': 'amolen',
    'ttyt3d': 'ttyt3d',
    'mika3d': 'mika3d',
    'duramic': 'duramic',
    'stronghero3d': 'stronghero3d',
    'iwecolor': 'iwecolor',
    'novamaker': 'novamaker',
    'tecbears': 'tecbears',
    'voxelab': 'voxelab',
    'longer': 'longer',
    'sovol': 'sovol',
    'artillery': 'artillery',
    'tronxy': 'tronxy',
    'wanhao': 'wanhao',
    'monoprice': 'monoprice',
    'dremel': 'dremel',
    'snapmaker': 'snapmaker',
    'intamsys': 'intamsys',
    'markforged': 'markforged',
    'stratasys': 'stratasys',
    '3dsystems': '3dsystems',
    'peopoly': 'peopoly',
    'wham bam': 'whambam',
    'whambam': 'whambam',
    'buildtak': 'buildtak',
    'magigoo': 'magigoo',
    'dimafix': 'dimafix',
}

# Pre-sorted by length descending for longest-match-first semantics
_SORTED_BRANDS = sorted(KNOWN_BRANDS.items(), key=lambda x: len(x[0]), reverse=True)

# ---------------------------------------------------------------------------
# Product-line patterns
# ---------------------------------------------------------------------------

_LINE_PATTERNS = [
    ('polylite', r'\bpolylite\b'),
    ('polyterra', r'\bpolyterra\b'),
    ('polymax', r'\bpolymax\b'),
    ('polywood', r'\bpolywood\b'),
    ('polysmooth', r'\bpolysmooth\b'),
    ('polyflex', r'\bpolyflex\b'),
    ('polycast', r'\bpolycast\b'),
    ('polymide', r'\bpolymide\b'),
    ('panchroma', r'\bpanchroma\b'),
    ('basic', r'\bbasic\b'),
    ('matte', r'\bmatte\b'),
    ('silk', r'\bsilk\b'),
    ('sparkle', r'\bsparkle\b'),
    ('metal', r'\bmetal\b'),
    ('marble', r'\bmarble\b'),
    ('wood', r'\bwood\b'),
    ('aero', r'\baero\b'),
    ('gradient', r'\bgradient\b'),
    ('hf', r'\bhf\b'),
    ('hs', r'\bhs\b'),
    ('highspeed', r'\bhigh[\s-]?speed\b'),
    ('hyper', r'\bhyper\b'),
    ('pro', r'\bpro\b'),
    ('plus', r'\bplus\b'),
    ('premium', r'\bpremium\b'),
    ('lite', r'\blite\b'),
    ('refill', r'\brefill\b'),
    ('translucent', r'\btranslucent\b'),
    ('transparent', r'\btransparent\b'),
    ('glow', r'\bglow\b'),
    ('glitter', r'\bglitter\b'),
    ('rainbow', r'\brainbow\b'),
    ('multicolor', r'\bmulti[\s-]?colou?r\b'),
]

# ---------------------------------------------------------------------------
# Color detection
# ---------------------------------------------------------------------------

_COLORS = {
    'black': [r'\bblack\b', r'\bsvart\b', r'\bsort\b', r'\bnero\b', r'\bschwarz\b', r'\bjuodas\b', r'\bczarny\b', r'\bdeep\s*black\b'],
    'white': [r'\bwhite\b', r'\bhvit\b', r'\bhvitt\b', r'\bbianco\b', r'\bweiss\b', r'\bbaltas\b', r'\bbialy\b', r'\bpure\s*white\b'],
    'red': [r'\bred\b', r'\brød\b', r'\brod\b', r'\brosso\b', r'\brot\b', r'\braudonas\b', r'\bczerwony\b'],
    'blue': [r'\bblue\b', r'\bblå\b', r'\bbla\b', r'\bblu\b', r'\bblau\b', r'\bmelynas\b', r'\bniebieski\b'],
    'green': [r'\bgreen\b', r'\bgrønn\b', r'\bgronn\b', r'\bverde\b', r'\bgrün\b', r'\bzalias\b', r'\bzielony\b', r'\bemerald\b'],
    'yellow': [r'\byellow\b', r'\bgul\b', r'\bgiallo\b', r'\bgelb\b', r'\bgeltonas\b', r'\bzolty\b'],
    'orange': [r'\borange\b', r'\boransje\b', r'\barancione\b', r'\boranžinis\b', r'\bpomaranczowy\b'],
    'purple': [r'\bpurple\b', r'\blilla\b', r'\bviola\b', r'\bvioletine\b', r'\bfioletowy\b', r'\bviolet\b'],
    'pink': [r'\bpink\b', r'\brosa\b', r'\brozine\b', r'\brozowy\b'],
    'grey': [r'\bgrey\b', r'\bgray\b', r'\bgrå\b', r'\bgra\b', r'\bgrigio\b', r'\bgrau\b', r'\bpilkas\b', r'\bszary\b', r'\bdark\s*grey\b', r'\bmørkegrå\b'],
    'brown': [r'\bbrown\b', r'\bbrun\b', r'\bmarrone\b', r'\bbraun\b', r'\brudas\b', r'\bbrazowy\b'],
    'clear': [r'\bclear\b', r'\btransparent\b', r'\bgjennomsiktig\b', r'\bskaidrus\b', r'\bprzezroczysty\b'],
    'natural': [r'\bnatural\b', r'\bnatur\b', r'\bnaturale\b', r'\bnaturalus\b', r'\bnaturalny\b', r'\bnatūralus\b'],
    'silver': [r'\bsilver\b', r'\bsølv\b', r'\bargento\b', r'\bsilber\b', r'\bsidabrinis\b', r'\bsrebrny\b'],
    'gold': [r'\bgold\b', r'\bgull\b', r'\boro\b', r'\bauksinis\b', r'\bzloty\b', r'\bgolden\b'],
    'jade': [r'\bjade\b', r'\bjadeit\b'],
    'ivory': [r'\bivory\b', r'\belfenbein\b'],
    'beige': [r'\bbeige\b', r'\bbež\b'],
    'olive': [r'\bolive\b', r'\bolivgrun\b'],
    'navy': [r'\bnavy\b', r'\bmarine\b'],
    'cyan': [r'\bcyan\b', r'\btürkis\b'],
    'magenta': [r'\bmagenta\b', r'\bfuchsia\b'],
    'teal': [r'\bteal\b', r'\bpetrol\b'],
    'coral': [r'\bcoral\b', r'\bkoralle\b'],
    'charcoal': [r'\bcharcoal\b', r'\banthrazit\b'],
    'cream': [r'\bcream\b', r'\bcreme\b'],
    'burgundy': [r'\bburgundy\b', r'\bweinrot\b'],
    'lime': [r'\blime\b', r'\blimette\b'],
    'mint': [r'\bmint\b', r'\bminze\b'],
    'peach': [r'\bpeach\b', r'\bpfirsich\b'],
    'lavender': [r'\blavender\b', r'\blavendel\b'],
    'turquoise': [r'\bturquoise\b', r'\btürkis\b'],
    'copper': [r'\bcopper\b', r'\bkupfer\b'],
    'bronze': [r'\bbronze\b'],
    'army': [r'\barmy\b'],
    'sand': [r'\bsand\b'],
    'sky': [r'\bsky\b'],
    'ocean': [r'\bocean\b'],
    'forest': [r'\bforest\b'],
    'midnight': [r'\bmidnight\b'],
    'melon': [r'\bmelon\b'],
    'multicolor': [r'\bmulti[\s-]?colou?r\b', r'\bflerfarve\b', r'\bflerfarget\b'],
    'pumpkin': [r'\bpumpkin\b'],
    'cappuccino': [r'\bcappuccino\b'],
}

_COLOR_NAMES = set(_COLORS.keys()) | {
    'gray', 'transparent', 'navy', 'cyan', 'magenta', 'teal', 'beige', 'ivory',
}

# ---------------------------------------------------------------------------
# Weight patterns
# ---------------------------------------------------------------------------

_WEIGHT_PATTERNS = [
    (r'(\d+(?:[.,]\d+)?)\s*kg\b', 'kg'),
    (r'(\d+(?:[.,]\d+)?)\s*kilo\b', 'kg'),
    (r'(\d+(?:[.,]\d+)?)\s*g\b', 'g'),
    (r'(\d+)\s*(?:gram|grams)\b', 'g'),
    (r'-\s*(\d+(?:[.,]\d+)?)\s*kg\b', 'kg'),
    (r'-\s*(\d+)\s*g\b', 'g'),
    (r'x\s*(\d+)\s*g\b', 'g'),
    (r'/\s*(\d+)\s*g\b', 'g'),
    (r'\((\d+)\s*g\)', 'g'),
    (r'\((\d+(?:[.,]\d+)?)\s*kg\)', 'kg'),
    (r'\b(1000|750|500|250|2000|3000|2300)\b', 'g'),
    (r'\((\d{3,4})\s*g?\)$', 'g'),
]

# ---------------------------------------------------------------------------
# SKU extraction patterns
# ---------------------------------------------------------------------------

_SKU_PATTERNS = [
    r'\b([A-Z]{2}\d{5,})\b',
    r'\b(\d{10,13})\b',
    r'\((\d{10})\)',
]

# Material keywords that must be present in the product name
# when material was only detected from metadata.
_MATERIAL_KEYWORDS = [
    'filament', 'resin', 'pla', 'petg', 'abs', 'asa', 'tpu', 'tpe', 'nylon',
    'pa6', 'pa12', 'pctg', 'pc', 'peek', 'pekk', 'pei', 'hips', 'pva',
    'carbon fiber', 'cf', 'glass fiber', 'gf',
]


# ===================================================================
# Public helpers
# ===================================================================

def extract_product_key(product) -> tuple:
    """Return *(key_type, key_value)* for cross-source grouping.

    *key_type* is one of ``'gtin'``, ``'sku'``, ``'name'``, or ``'none'``
    (meaning the product cannot be matched).
    """
    name_lower = product.name.lower()

    # --- Exclusion filters ---
    for pattern in _EXCLUDE_NAME_PATTERNS:
        if re.search(pattern, name_lower):
            return ('none', None)

    canonical_lower = (product.canonical_url or "").lower()
    if any(kw in canonical_lower for kw in _EXCLUDE_URL_KEYWORDS):
        return ('none', None)

    # --- Material detection ---
    material_from_name = detect_material(product.name, None)
    material_key = material_from_name or detect_material(product.name, product.product_type)
    material_info = MATERIALS.get(material_key) if material_key else None
    if not material_info:
        return ('none', None)
    if material_info.get('category') not in {'filament', 'resin'}:
        return ('none', None)

    if not material_from_name:
        if not any(kw in name_lower for kw in _MATERIAL_KEYWORDS):
            return ('none', None)

    # --- GTIN ---
    if product.gtin and len(product.gtin) >= 8:
        return ('gtin', product.gtin)

    # Normalize unicode
    name_lower = name_lower.replace('\u00e3', 'a').replace('\u00e2', 'a').replace('\u00e5', 'a')
    name_lower = name_lower.replace('\u00f8', 'o').replace('\u00e6', 'ae')

    # --- SKU extraction ---
    for pattern in _SKU_PATTERNS:
        m = re.search(pattern, product.name, re.IGNORECASE)
        if m:
            sku_code = m.group(1).upper()
            if not re.match(r'^\d+[GKM]?$', sku_code):
                return ('sku', sku_code)

    # --- Brand resolution ---
    brand = (product.brand or "").lower().strip()
    if not brand:
        for b_name, b_key in _SORTED_BRANDS:
            if b_name in name_lower:
                brand = b_key
                break
    else:
        brand_lower = brand.replace(' ', '')
        for b_name, b_key in _SORTED_BRANDS:
            b_normalized = b_name.replace(' ', '')
            if b_normalized == brand_lower or b_name in brand_lower:
                brand = b_key
                break
        else:
            brand = re.sub(r'[^a-z0-9]', '', brand_lower)

    if not brand:
        for b_name, b_key in _SORTED_BRANDS:
            if b_name in name_lower:
                brand = b_key
                break

    if not brand:
        return ('none', None)

    # --- Material ---
    detected_material = detect_material(product.name, product.product_type)
    if not detected_material:
        return ('none', None)
    material = detected_material.lower()

    # --- Weight ---
    weight = ""
    for pattern, unit in _WEIGHT_PATTERNS:
        wm = re.search(pattern, name_lower)
        if wm:
            num = float(wm.group(1).replace(',', '.'))
            num = int(num * 1000) if unit == 'kg' else int(num)
            if 50 <= num <= 10000:
                weight = f"{num}g"
                break

    # --- Product line ---
    product_lines = []
    for line_name, pat in _LINE_PATTERNS:
        if re.search(pat, name_lower):
            product_lines.append(line_name)
    product_line = '_'.join(sorted(product_lines)) if product_lines else ""

    # --- Color ---
    color = _detect_color(name_lower)
    if not color and product.color:
        color = _detect_color(product.color.lower())

    # --- Build key ---
    key_parts = [brand, material]
    if product_line:
        key_parts.append(product_line)

    normalized_weight = _normalize_weight(weight)
    if normalized_weight:
        key_parts.append(normalized_weight)

    key_parts.append(color if color else 'anycolor')
    return ('name', '_'.join(p for p in key_parts if p))


def build_product_data(product) -> dict:
    """Serialize a product ORM instance into a plain dict for comparison results."""
    latest_price = None
    if product.price_observations:
        latest = product.price_observations[0]
        amount = float(latest.price_amount) if latest.price_amount is not None else None
        shipping_amount = float(latest.shipping_amount) if latest.shipping_amount is not None else None
        total_amount = float(latest.total_price_amount) if latest.total_price_amount is not None else None
        if total_amount is None and (amount is not None or shipping_amount is not None):
            total_amount = (amount or 0) + (shipping_amount or 0)
        latest_price = {
            "amount": amount,
            "currency": latest.currency,
            "shipping_amount": shipping_amount,
            "shipping_currency": latest.shipping_currency or latest.currency,
            "total_amount": total_amount,
            "in_stock": latest.in_stock,
            "observed_at": latest.observed_at.isoformat() if latest.observed_at else None,
        }

    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "product_type": product.product_type,
        "color": product.color,
        "size": product.size,
        "image_url": product.image_url,
        "source_id": product.source_id,
        "source_name": product.source.name if product.source else None,
        "source_domain": product.source.domain if product.source else None,
        "canonical_url": product.canonical_url,
        "latest_price": latest_price,
        "latest_change_percent": product.latest_change_percent,
        "latest_change_type": product.latest_change_type,
        "gtin": product.gtin,
        "sku": product.sku,
    }


def create_group_result(key: str, prods: list, match_type: str) -> Optional[dict]:
    """Build a comparison group dict, or *None* if < 2 sources."""
    source_ids = set(p["source_id"] for p in prods)
    if len(source_ids) < 2:
        return None

    def _delivered_price(p: dict) -> Optional[float]:
        lp = p.get("latest_price")
        if not lp:
            return None
        return lp.get("total_amount") or lp.get("amount")

    sorted_prods = sorted(
        prods,
        key=lambda p: _delivered_price(p) if _delivered_price(p) is not None else float('inf'),
    )
    prices = [_delivered_price(p) for p in prods if _delivered_price(p) is not None]
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    price_spread = None
    if min_price and max_price and min_price > 0:
        price_spread = round(((max_price - min_price) / min_price) * 100, 1)

    first = sorted_prods[0]
    detected = detect_material(first.get("name", ""), first.get("product_type"))
    material_display = get_material_display_name(detected) if detected else (first['product_type'] or '')
    brand_part = first['brand'] or ''
    color_part = first['color'] or ''
    display_name = f"{brand_part} {material_display} {color_part}".strip() or first['name'][:50]

    return {
        "key": key,
        "display_name": display_name,
        "match_type": match_type,
        "products": sorted_prods,
        "source_count": len(source_ids),
        "min_price": min_price,
        "max_price": max_price,
        "price_spread": price_spread,
    }


def compare_products(products, *, limit: int = 50) -> dict:
    """Run the full cross-source comparison pipeline.

    Returns a dict with ``groups``, ``total_groups``, and ``by_type``.
    """
    gtin_groups: dict[str, list] = {}
    sku_groups: dict[str, list] = {}
    name_groups: dict[str, list] = {}
    name_groups_noweight: dict[str, list] = {}

    for product in products:
        key_type, key_value = extract_product_key(product)
        if key_type == 'none' or not key_value:
            continue

        product_data = build_product_data(product)

        if key_type == 'gtin':
            gtin_groups.setdefault(key_value, []).append(product_data)
        elif key_type == 'sku':
            sku_groups.setdefault(key_value, []).append(product_data)
        else:
            name_groups.setdefault(key_value, []).append(product_data)

            key_parts = key_value.split('_')
            noweight_parts = [p for p in key_parts if not re.match(r'^\d+g$', p)]
            noweight_key = '_'.join(noweight_parts)
            if noweight_key != key_value:
                name_groups_noweight.setdefault(noweight_key, []).append(product_data)

            nocolor_parts = [p for p in noweight_parts if p != 'anycolor' and p not in _COLOR_NAMES]
            nocolor_key = '_'.join(nocolor_parts)
            if nocolor_key and nocolor_key != key_value and nocolor_key != noweight_key:
                name_groups_noweight.setdefault(nocolor_key, []).append(product_data)

    # Assemble results
    results: List[dict] = []
    for key, prods in gtin_groups.items():
        g = create_group_result(key, prods, "gtin")
        if g:
            results.append(g)
    for key, prods in sku_groups.items():
        g = create_group_result(key, prods, "sku")
        if g:
            results.append(g)
    for key, prods in name_groups.items():
        g = create_group_result(key, prods, "name")
        if g:
            results.append(g)

    matched_ids = {p["id"] for g in results for p in g["products"]}
    for key, prods in name_groups_noweight.items():
        unmatched = [p for p in prods if p["id"] not in matched_ids]
        if len(unmatched) >= 2:
            g = create_group_result(key, unmatched, "name_fallback")
            if g:
                results.append(g)
                matched_ids.update(p["id"] for p in g["products"])

    results.sort(key=lambda g: (g["price_spread"] or 0, g["source_count"]), reverse=True)

    # Group by material type
    by_type = _group_by_material_type(results, limit)

    return {
        "groups": results[:limit],
        "total_groups": len(results),
        "by_type": by_type,
    }


# ===================================================================
# Private helpers
# ===================================================================

def _detect_color(text: str) -> str:
    for color_key, patterns in _COLORS.items():
        for pat in patterns:
            if re.search(pat, text):
                return color_key
    return ""


def _normalize_weight(weight: str) -> str:
    if not weight:
        return ""
    num = int(weight.replace('g', ''))
    if 200 <= num <= 400:
        return '250g'
    if 400 < num <= 650:
        return '500g'
    if 650 < num <= 900:
        return '750g'
    if 900 < num <= 1200:
        return '1000g'
    if 1700 <= num <= 2500:
        return '2000g'
    if 2500 < num <= 3500:
        return '3000g'
    return weight


def _group_by_material_type(results: list, limit: int) -> list:
    type_groups: dict[str, dict[str, list]] = {}
    for group in results:
        first_product = group["products"][0]
        detected = detect_material(first_product.get("name", ""), first_product.get("product_type"))
        base_material = normalize_material_for_grouping(detected)
        specific_variant = detected if detected else base_material
        type_groups.setdefault(base_material, {}).setdefault(specific_variant, []).append(group)

    type_summaries = []
    for material_key, variant_groups in type_groups.items():
        all_prices: List[float] = []
        total_product_count = 0
        variant_summaries = []
        for variant_key, groups in variant_groups.items():
            variant_prices: List[float] = []
            for g in groups:
                if g["min_price"]:
                    variant_prices.append(g["min_price"])
                    all_prices.append(g["min_price"])
                if g["max_price"]:
                    variant_prices.append(g["max_price"])
                    all_prices.append(g["max_price"])
            total_product_count += len(groups)
            variant_summaries.append({
                "variant": get_material_display_name(variant_key),
                "variant_key": variant_key,
                "product_count": len(groups),
                "min_price": min(variant_prices) if variant_prices else None,
                "max_price": max(variant_prices) if variant_prices else None,
                "groups": groups[:limit],
            })
        variant_summaries.sort(key=lambda v: v["product_count"], reverse=True)

        all_groups = [g for v in variant_summaries for g in v["groups"]]
        type_summaries.append({
            "type": get_material_display_name(material_key),
            "type_key": material_key,
            "product_count": total_product_count,
            "min_price": min(all_prices) if all_prices else None,
            "max_price": max(all_prices) if all_prices else None,
            "variants": variant_summaries,
            "groups": all_groups[:limit],
        })

    type_summaries.sort(key=lambda t: t["product_count"], reverse=True)
    return type_summaries
