import re
import structlog
from typing import Tuple, Optional, List
from dataclasses import dataclass

from worker.parsers.base import ParsedProduct

logger = structlog.get_logger(__name__)


@dataclass
class MatchResult:
    """Result of product matching."""
    is_match: bool
    category: str
    product_type: Optional[str]
    confidence: float
    matched_keywords: list[str]


class ProductMatcher:
    """Matches products to filament/resin categories."""

    FILAMENT_KEYWORDS = {
        'high': [
            'filament', '1.75mm', '1,75mm', '2.85mm', '2,85mm', '3mm filament', 'spool',
            '1.75 mm', '2.85 mm', '1kg', '0.5kg', '500g', '750g', '1000g', '250g',
            '1 kg', '0,5 kg', '0.5 kg', '500 g', '750 g', '1000 g', '2kg', '2 kg',
            'filament 1.75', 'filament 2.85', '3d filament', 'printer filament',
            'fdm filament', 'fff filament', '3d-printer filament',
        ],
        'medium': [
            # Material types
            'pla', 'petg', 'asa', 'tpu', 'nylon', 'pc filament',
            'hips', 'pva', 'pvb', 'peek', 'pei', 'ultem', 'polypropylene',
            'pctg', 'cpe', 'pa6', 'pa12', 'pa-cf', 'pa-gf',
            # Composite/specialty
            'wood fill', 'woodfill', 'carbon fiber', 'carbon fibre', 'cf filament',
            'glass fiber', 'glass fibre', 'gf filament', 'metal fill', 'metalfill',
            'silk pla', 'matte pla', 'pla+', 'pla pro', 'petg cf', 'abs+',
            'tpu 95a', 'tpu 85a', 'flexible filament', 'engineering filament',
            'high temp filament', 'high temperature filament', 'heat resistant filament',
            # Visual effects — specific compound forms only
            'glow in the dark', 'gitd', 'phosphorescent',
            # Brands - major filament specialists
            'prusament', 'polymaker', 'esun', 'sunlu', 'overture', 'hatchbox',
            'eryone', 'jayo',
            # Brands - European
            'fiberlogy', 'colorfabb', 'formfutura', 'fillamentum', 'extrudr',
            'das filament', '3djake', 'real filament', 'devil design',
            'rosa3d', 'add north', 'verbatim', 'innofil', 'innofil3d',
            'polyalkemi', 'nordic3d', '3dnet', 'gembird', 'basicfil',
            # Brands - specialty
            'primaselect', 'primavalue', 'matterhackers', 'atomic',
            'proto-pasta', 'protopasta', 'ninjatek', 'taulman', 'polymax',
            'polylite', 'polyterra', 'polywood', 'polyflex', 'polycast',
        ],
        'low': [
            '3d printer', '3d printing', 'fdm', 'fff', '3d print',
            '3d-print', '3dprint', 'additive', 'extrusion',
            # Ambiguous material abbreviations — too common outside 3D printing to score higher
            'abs', 'pp', 'pet',
            # Printer-first brands — sell far more printers than filament by SKU count;
            # only weak signal, require a strong filament/resin term to confirm
            'creality', 'elegoo', 'anycubic', 'prusa', 'bambu', 'bambulab', 'bambu lab',
            'geeetech', 'flashforge', 'qidi', 'mingda', 'longer', 'voxelab',
            'artillery', 'tronxy', 'two trees', 'biqu', 'kingroon',
            'prima', 'spectrum',
        ],
    }

    RESIN_KEYWORDS = {
        'high': [
            'uv resin', 'photopolymer', '405nm', '385nm', '365nm', 'sla resin', 'dlp resin',
            'msla resin', 'lcd resin', 'resin for 3d', '3d resin', 'printer resin',
            '3d printer resin', 'resin 405', 'uv curing resin', 'photocuring resin',
            'light curing resin', 'resin 500ml', 'resin 1000ml', 'resin 1l',
            'resin 500g', 'resin 1kg', 'resin 1000g', 'uv-harpiks', 'harpiks 405',
            'lysherdende harpiks', 'fotopolymer harpiks', 'resina uv', 'resina 405nm',
        ],
        'medium': [
            # Resin types
            'water-washable resin', 'water washable resin', 'waterwashable resin', 'vaskbar harpiks',
            'abs-like resin', 'abs like resin', 'abs-lignende', 'tough resin', 'hard resin',
            'flexible resin', 'elastic resin', 'rubber-like resin', 'gummiaktig harpiks',
            'castable resin', 'burnout resin', 'jewelry resin', 'smykkestøp harpiks',
            'dental resin', 'surgical resin', 'biocompatible resin',
            'engineering resin', 'functional resin', 'high temp resin', 'heat resistant resin',
            'standard resin', 'basic resin', 'regular resin', 'rapid resin', 'draft resin',
            'plant-based resin', 'plant based resin', 'bio resin', 'eco resin', 'soy resin',
            'low odor resin', 'odorless resin', 'low odour resin',
            'high detail resin', '4k resin', '8k resin', 'precision resin', 'high precision resin',
            'grey resin', 'gray resin', 'clear resin', 'transparent resin', 'translucent resin',
            'white resin', 'black resin', 'skin resin', 'ceramic resin', 'stone resin',
            'impact resistant resin', 'elastic like resin', 'silicone like resin',
            # Brands - major
            'anycubic resin', 'elegoo resin', 'phrozen resin', 'siraya tech',
            'siraya', 'creality resin', 'sunlu resin', 'esun resin', 'esun water washable',
            'nova3d', 'longer resin', 'voxelab resin', 'qidi resin', 'bambulab resin',
            'peopoly', 'monocure', 'monocure3d', 'liqcreate', 'formlabs',
            'prusa resin', 'prusament resin', 'asiga', 'nextdent', 'anycubic plant-based',
            'x1-uv resin', 'phrozen aqua', 'siraya fast', 'siraya blu',
            # Specialty
            'wax resin', 'model resin', 'fast resin',
            'high speed resin', 'speed resin', 'low shrinkage', 'nylon-like resin', 'pp-like resin',
            'bio-based resin', 'eco-friendly resin', 'soy-based resin',
        ],
        'low': [
            'resin', 'harpiks', 'harz', 'résine', 'resina', 'photosensitive', 'curing',
            'sla', 'dlp', 'msla', 'lcd printer', 'lysherdende', 'lyshærdende', 'fotopolymer',
        ],
    }

    FILAMENT_TYPES = {
        'pla': ['pla', 'pla+', 'pla pro', 'polylactic', 'pla-cf', 'pla cf', 'tough pla', 'htpla', 'ht-pla'],
        'petg': ['petg', 'pet-g', 'petg-cf', 'petg cf', 'cpetg', 'petg+'],
        'abs': ['abs', 'abs+', 'abs-cf', 'abs cf'],
        'asa': ['asa', 'asa+'],
        'tpu': ['tpu', 'tpe', 'tpu 95a', 'tpu 85a', 'tpu 70a', 'flexible'],
        'nylon': ['nylon', 'pa6', 'pa12', 'pa11', 'pa-cf', 'pa cf', 'pa-gf', 'polyamide'],
        'pc': ['polycarbonate', 'pc filament', 'pc-abs', 'pc abs', 'pc-cf', 'pc cf'],
        'pei': ['pei', 'ultem'],
        'peek': ['peek'],
        'pps': ['pps', 'ppsu'],
        'hips': ['hips'],
        'pva': ['pva', 'water soluble', 'bvoh'],
        'pvb': ['pvb', 'polysmooth'],
        'pp': ['polypropylene', 'pp filament'],
        'pet': ['pet filament', 'pctg', 'cpe'],
        'wood': ['wood', 'wood fill', 'woodfill', 'bamboo', 'cork'],
        'carbon': ['carbon', 'cf', 'carbon fiber', 'carbon fibre', 'cf-'],
        'glass': ['glass fiber', 'glass fibre', 'gf', 'gf-'],
        'metal': ['metal fill', 'metalfill', 'copper fill', 'copperfill', 'bronze fill', 'bronzefill', 'steel fill', 'iron fill', 'aluminum fill', 'aluminium fill'],
        'silk': ['silk', 'silky'],
        'matte': ['matte', 'matt'],
        'glow': ['glow', 'phosphorescent', 'gitd', 'glow in the dark', 'luminous'],
        'marble': ['marble', 'stone', 'granite'],
        'sparkle': ['sparkle', 'glitter', 'galaxy', 'starry', 'shimmer'],
        'gradient': ['rainbow', 'multicolor', 'gradient', 'dual color', 'tri color'],
    }

    FILAMENT_TYPE_PRIORITY = [
        'carbon', 'glass', 'metal', 'wood', 'silk', 'matte', 'glow', 'marble',
        'sparkle', 'gradient', 'nylon', 'tpu', 'asa', 'abs', 'petg', 'pla'
    ]

    RESIN_TYPES = {
        'standard': ['standard', 'basic', 'regular', 'general purpose', 'general-purpose'],
        'abs-like': ['abs-like', 'abs like', 'tough', 'hard', 'strong', 'durable', 'impact resistant'],
        'water-washable': ['water-washable', 'water washable', 'waterwashable', 'eco', 'plant-based', 'bio', 'soy-based'],
        'flexible': ['flexible', 'elastic', 'rubber-like', 'rubber like', 'soft', 'bendable', 'silicone-like'],
        'castable': ['castable', 'burnout', 'jewelry', 'wax', 'lost wax'],
        'dental': ['dental', 'surgical', 'biocompatible', 'medical', 'orthodontic'],
        'engineering': ['engineering', 'functional', 'high temp', 'heat resistant', 'industrial'],
        'clear': ['clear', 'transparent', 'translucent', 'crystal', 'glass-like'],
        'high-detail': ['high detail', 'high precision', '4k', '8k', 'precision', 'ultra detail', 'fine detail'],
        'rapid': ['rapid', 'fast', 'quick', 'high speed', 'draft', 'speed'],
        'nylon-like': ['nylon-like', 'nylon like', 'pa-like', 'pa like'],
        'ceramic': ['ceramic', 'porcelain', 'stone-like'],
        'skin': ['skin', 'flesh', 'skin tone'],
        'odorless': ['odorless', 'odourless', 'low odor', 'low odour', 'low smell', 'no odor'],
        'plant-based': ['plant-based', 'plant based', 'soy-based', 'bio-based', 'eco friendly', 'eco-friendly'],
    }

    EXCLUDE_KEYWORDS = [
        # Printers and machines
        '3d printer', 'printer kit', 'machine', 'print head',
        # Parts and accessories
        'nozzle', 'hotend', 'hot end', 'extruder', 'heater block',
        'thermistor', 'heat break', 'heatbreak', 'bowden', 'ptfe tube',
        'bed', 'glass bed', 'pei sheet', 'build plate', 'magnetic bed',
        'stepper', 'motor', 'driver', 'mainboard', 'motherboard',
        'power supply', 'psu', 'fan', 'blower', 'cooling',
        'belt', 'pulley', 'bearing', 'rod', 'rail', 'linear',
        'frame', 'profile', 'aluminum profile',
        # Tools
        'tool', 'scraper', 'spatula', 'glue', 'adhesive', 'tape',
        'wrench', 'hex key', 'allen', 'screwdriver', 'pliers',
        'tweezers', 'needle', 'cleaning needle', 'nozzle cleaner',
        # Storage and handling
        'enclosure', 'dryer', 'dry box', 'drybox', 'spool holder', 'rack',
        'filament sensor', 'runout sensor', 'humidity',
        # Upgrades
        'upgrade', 'mod', 'part', 'spare', 'replacement', 'kit',
        # Learning
        'book', 'guide', 'course', 'tutorial', 'manual',
        # Resin printer parts
        'vat', 'fep', 'fep film', 'screen', 'lcd panel', 'led array',
        'build platform', 'resin tank', 'z-axis',
        # Cleaning
        'ipa', 'isopropyl', 'alcohol', 'cleaner', 'wash station', 'cure station',
        'curing station', 'wash and cure', 'wash & cure', 'mercury',
        # Software
        'software', 'slicer', 'license',
        # Model kits and toys (not 3D printing materials)
        'italeri', 'airfix', 'revell', 'tamiya', 'hasegawa', 'trumpeter',
        'model kit', 'scale model', '1:72', '1:48', '1:32', '1:24', '1:12',
        'cockpit', 'aircraft', 'airplane', 'helicopter', 'tank', 'ship',
        'figurine', 'miniature', 'warhammer', 'diorama',
        # Drones and RC
        'drone', 'quadcopter', 'landing pad', 'propeller', 'gimbal',
        'remote control', 'rc car', 'rc plane', 'fpv',
        # Electronics unrelated to 3D printing
        'arduino', 'raspberry', 'sensor', 'camera', 'display', 'monitor',
        'cable', 'wire', 'connector', 'adapter', 'charger', 'battery pack',
        # Pen-based 3D drawing (not filament spools)
        '3doodler', '3d pen', '3d-pen', 'drawing pen',
        # Craft and art supplies
        'paint', 'brush', 'pigment', 'dye', 'spray', 'primer', 'varnish',
        'clay', 'sculpt', 'mold', 'casting',
        # Resin art / nail art — UV resin for non-3D-printing crafts
        'nail art', 'nail gel', 'nail resin', 'uv gel nail', 'gel polish', 'gel nails',
        'epoxy art', 'resin art', 'resin craft', 'resin jewelry', 'resin tray',
        'resin table', 'river table', 'wood filler', 'epoxy filler',
        # Clothing and accessories
        'shirt', 't-shirt', 'hoodie', 'cap', 'hat', 'bag', 'backpack',
        # Food and consumables
        'food', 'drink', 'snack', 'candy',
    ]

    # Products that should NEVER match unless they explicitly contain filament/resin keywords
    STRONG_EXCLUDE_PATTERNS = [
        r'italeri\s+\d+:\d+',  # Model kit scale patterns like "ITALERI 1:48"
        r'airfix\s+\d+:\d+',
        r'revell\s+\d+:\d+',
        r'\d+:\d+.*scale',  # Any scale model pattern
        r'landing\s+pad',
        r'for\s+drone',
        r'3doodler',
        # Printer accessory / compatibility patterns
        r'for\s+(?:ender|prusa\s+mk|bambu\s+(?:p1|x1|a1)|anycubic\s+\w+|elegoo\s+(?:mars|saturn|neptune))\b',
        r'compatible\s+with\s+\w[\w\s]{0,20}(?:printer|3d\s+printer)\b',
        r'replacement\s+(?:part|nozzle|bed|screen|fep|vat)\b',
        r'upgrade\s+kit\s+for\b',
        r'\bfits\b.{0,30}\bprinter\b',
        # Resin art / nail art — definitely not 3D printing
        r'nail\s+(?:art|gel|resin|polish)',
        r'resin\s+(?:art|craft|tray)',
        r'epoxy\s+(?:art|craft|table|river)',
        r'uv\s+gel\s+nail',
    ]

    STRONG_FILAMENT_TERMS = [
        'filament', '1.75', '1,75', '2.85', '2,85', 'spool', '1kg', '500g', '750g',
        '1000g', '250g', 'pla', 'petg', 'asa',
    ]

    STRONG_RESIN_TERMS = [
        'resin', 'harpiks', '405nm', 'photopolymer', 'uv resin',
        'sla resin', 'dlp resin', 'msla', 'water-washable', 'water washable',
        'abs-like', 'castable', 'dental', 'plant-based', 'odorless'
    ]

    _SPOOL_WEIGHTS_G: frozenset = frozenset({100, 200, 250, 330, 500, 750, 800, 1000, 1500, 2000, 2500, 3000, 5000})

    RAW_TEXT_KEYS = [
        'description', 'short_description', 'summary', 'meta_description', 'excerpt',
        'body', 'text', 'content', 'details', 'long_description'
    ]

    def __init__(self):
        self._compile_patterns()
        self._compile_strong_excludes()

    def _compile_strong_excludes(self):
        """Compile strong exclusion patterns."""
        self._strong_exclude_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.STRONG_EXCLUDE_PATTERNS
        ]

    def _compile_patterns(self):
        """Compile regex patterns for faster matching."""
        self._filament_patterns = {}
        for level, keywords in self.FILAMENT_KEYWORDS.items():
            patterns = [re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE) for kw in keywords]
            self._filament_patterns[level] = patterns

        self._resin_patterns = {}
        for level, keywords in self.RESIN_KEYWORDS.items():
            patterns = [re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE) for kw in keywords]
            self._resin_patterns[level] = patterns

        self._exclude_patterns = [
            re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
            for kw in self.EXCLUDE_KEYWORDS
        ]

    def _check_exclusions(self, text: str) -> bool:
        """Check if text contains exclusion keywords."""
        for pattern in self._exclude_patterns:
            if pattern.search(text):
                return True
        return False

    def _check_strong_exclusions(self, text: str) -> bool:
        """Check if text matches strong exclusion patterns that should never match."""
        for pattern in self._strong_exclude_patterns:
            if pattern.search(text):
                return True
        return False

    def _has_filament_context(self, text_lower: str) -> bool:
        """Check for structural filament context: diameter, spool terms, or canonical spool weights."""
        # Filament diameter — strongest structural signal
        if re.search(r'\bø?\s?(1[\.,]?75|2[\.,]?85|3\.0)\s?mm\b', text_lower):
            return True
        # Explicit spool/reel/roll terminology
        if any(term in text_lower for term in ['spool', 'reel', 'roll', 'coil']):
            return True
        # Weight — only accept canonical spool weights to avoid matching arbitrary
        # product weights (bike parts, hardware, electronics, food packaging, etc.)
        g_match = re.search(r'\b(\d+(?:[.,]\d+)?)\s?(?:g|grams?)\b', text_lower)
        if g_match:
            try:
                val = float(g_match.group(1).replace(',', '.'))
                if val in self._SPOOL_WEIGHTS_G:
                    return True
            except ValueError:
                pass
        kg_match = re.search(r'\b(\d+(?:[.,]\d+)?)\s?kg\b', text_lower)
        if kg_match:
            try:
                val = float(kg_match.group(1).replace(',', '.'))
                if 0.1 <= val <= 5.0:
                    return True
            except ValueError:
                pass
        # 1lb and 2lb are common US spool sizes
        if re.search(r'\b[12]\s?(?:lb|lbs|pound|pounds)\b', text_lower):
            return True
        return False

    def _has_resin_context(self, text_lower: str) -> bool:
        resin_terms_present = any(term in text_lower for term in ['resin', 'harpiks', 'photopolymer'])
        if not resin_terms_present:
            return False
        if re.search(r'\b\d+(?:[\.,]\d+)?\s?(ml|l|liter|litre)\b', text_lower):
            return True
        if re.search(r'\b\d+(?:[\.,]\d+)?\s?(g|grams?)\b', text_lower):
            return True
        if re.search(r'\b\d+(?:[\.,]\d+)?\s?(oz|ounce|ounces)\b', text_lower):
            return True
        if re.search(r'\b(365|385|395|405)\s?nm\b', text_lower) or 'uv' in text_lower:
            return True
        if any(term in text_lower for term in ['bottle', 'flask']):
            return True
        return False

    def _calculate_score(self, text: str, patterns: dict) -> Tuple[float, list[str]]:
        """Calculate match score with diminishing returns per tier.

        Each subsequent keyword match within the same tier contributes half the
        weight of the previous one, preventing long descriptions from accumulating
        high scores via keyword repetition or coincidental keyword density.
        """
        if not text:
            return 0.0, []

        score = 0.0
        matched = []
        weights = {'high': 0.5, 'medium': 0.3, 'low': 0.1}
        tier_match_counts: dict[str, int] = {'high': 0, 'medium': 0, 'low': 0}

        for level, level_patterns in patterns.items():
            base_weight = weights[level]
            for pattern in level_patterns:
                if pattern.search(text):
                    count = tier_match_counts[level]
                    # Diminishing returns: 1st match = full weight, 2nd = 50%, 3rd = 25%, ...
                    effective_weight = base_weight * (0.5 ** count)
                    score += effective_weight
                    tier_match_counts[level] += 1
                    matched.append(pattern.pattern.replace(r'\b', '').replace('\\', ''))

        return min(score, 1.0), matched

    def _detect_filament_type(self, text: str) -> Optional[str]:
        """Detect specific filament type."""
        text_lower = text.lower()
        handled: set[str] = set()
        for ftype in self.FILAMENT_TYPE_PRIORITY:
            if ftype not in self.FILAMENT_TYPES:
                continue
            for kw in self.FILAMENT_TYPES[ftype]:
                if kw in text_lower:
                    return ftype
            handled.add(ftype)
        for ftype, keywords in self.FILAMENT_TYPES.items():
            if ftype in handled:
                continue
            for kw in keywords:
                if kw in text_lower:
                    return ftype
        return None

    def _detect_resin_type(self, text: str) -> Optional[str]:
        """Detect specific resin type."""
        text_lower = text.lower()
        for rtype, keywords in self.RESIN_TYPES.items():
            for kw in keywords:
                if kw in text_lower:
                    return rtype
        return None

    def _strip_html(self, value: str) -> str:
        return re.sub(r'<[^>]+>', ' ', value)

    def _normalize_text(self, value: Optional[str]) -> str:
        if not value:
            return ''
        cleaned = self._strip_html(value)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _collect_raw_text_values(self, raw_data: dict) -> List[str]:
        values: List[str] = []
        if not isinstance(raw_data, dict):
            return values
        for key in self.RAW_TEXT_KEYS:
            val = raw_data.get(key)
            if isinstance(val, str):
                values.append(self._normalize_text(val))
        tags = raw_data.get('tags')
        if isinstance(tags, list):
            values.extend(self._normalize_text(tag) for tag in tags if isinstance(tag, str))
        attributes = raw_data.get('attributes')
        if isinstance(attributes, dict):
            for attr_val in attributes.values():
                if isinstance(attr_val, str):
                    values.append(self._normalize_text(attr_val))
                elif isinstance(attr_val, list):
                    values.extend(self._normalize_text(v) for v in attr_val if isinstance(v, str))
        return [val for val in values if val]

    def _build_search_text(self, product: ParsedProduct) -> str:
        parts = [
            self._normalize_text(product.name),
            self._normalize_text(product.brand),
            self._normalize_text(product.variant),
            self._normalize_text(product.color),
        ]
        raw_texts = self._collect_raw_text_values(product.raw_data or {})
        parts.extend(raw_texts)
        return ' '.join(part for part in parts if part)

    def match(self, product: ParsedProduct, source_url: str = '') -> MatchResult:
        """Match a product to filament/resin categories."""
        # --- Build text layers ---
        primary_parts = [
            self._normalize_text(product.name),
            self._normalize_text(product.variant),
            self._normalize_text(product.brand),
        ]
        primary_text = ' '.join(part for part in primary_parts if part)
        primary_text_lower = primary_text.lower()

        raw_text_values = self._collect_raw_text_values(product.raw_data or {})
        secondary_text = ' '.join(raw_text_values)

        color_text = self._normalize_text(product.color)
        text = ' '.join(p for p in [primary_text, color_text, secondary_text] if p)
        if not text:
            text = product.name or ''
        text_lower = text.lower()

        product_url_lower = product.url.lower() if product.url else ''

        # --- Hard exclusions (always reject, no override) ---
        if self._check_strong_exclusions(text):
            return MatchResult(
                is_match=False,
                category='excluded',
                product_type=None,
                confidence=0.0,
                matched_keywords=['strong_exclude'],
            )

        # --- URL hints ---
        url_hints_filament = any(kw in product_url_lower for kw in [
            'filament', 'pla', 'petg', 'abs', 'asa', 'tpu', 'nylon', 'hips', 'pva',
            '1-75mm', '1.75mm', '2-85mm', '2.85mm', 'spool', 'fdm', 'fff',
        ])
        url_hints_resin = any(kw in product_url_lower for kw in [
            'resin', 'resina', 'harpiks', 'sla', 'dlp', 'msla', 'lcd', '405nm',
            'photopolymer', 'uv-resin', 'uvharpiks', 'lysherdende',
        ])

        url_lower = source_url.lower()
        url_is_filament_related = any(kw in url_lower for kw in [
            'filament', 'pla', 'petg', 'abs', 'resin', 'material', 'consumable',
            'forbruksvarer', '3d-print',
        ])

        # --- Soft exclusions (allow through if explicit filament/resin keyword present) ---
        if self._check_exclusions(text):
            if 'filament' not in text_lower and 'resin' not in text_lower:
                return MatchResult(
                    is_match=False,
                    category='excluded',
                    product_type=None,
                    confidence=0.0,
                    matched_keywords=['excluded'],
                )

        # --- Scoring: primary text carries full weight, secondary carries half ---
        filament_score_p, filament_matched_p = self._calculate_score(primary_text, self._filament_patterns)
        filament_score_s, filament_matched_s = self._calculate_score(secondary_text, self._filament_patterns)
        resin_score_p, resin_matched_p = self._calculate_score(primary_text, self._resin_patterns)
        resin_score_s, resin_matched_s = self._calculate_score(secondary_text, self._resin_patterns)

        filament_score = min(filament_score_p + filament_score_s * 0.5, 1.0)
        resin_score = min(resin_score_p + resin_score_s * 0.5, 1.0)
        filament_matched = filament_matched_p + filament_matched_s
        resin_matched = resin_matched_p + resin_matched_s

        if 'harpiks' in text_lower:
            resin_score = min(resin_score + 0.1, 1.0)
            resin_matched.append('locale:harpiks')

        has_filament_context = self._has_filament_context(text_lower)
        has_resin_context = self._has_resin_context(text_lower)

        # --- URL hint boosts ---
        if url_hints_filament:
            filament_score = min(filament_score + 0.15, 1.0)
            filament_matched.append('url:filament-hint')
        if url_hints_resin:
            resin_score = min(resin_score + 0.15, 1.0)
            resin_matched.append('url:resin-hint')

        # --- Resin context boosts ---
        if has_resin_context:
            if re.search(r'\b\d{2,4}\s?(ml|g|gram|grams|g\b)\b', text_lower):
                resin_score = min(resin_score + 0.05, 1.0)
                if 'volume:ml' not in resin_matched:
                    resin_matched.append('volume:ml')
            if re.search(r'\b\d(\.\d+)?\s?l\b', text_lower):
                resin_score = min(resin_score + 0.05, 1.0)
                if 'volume:l' not in resin_matched:
                    resin_matched.append('volume:l')
            if re.search(r'\b3d\b', text_lower) or 'uv' in text_lower or '405' in text_lower:
                resin_score = min(resin_score + 0.05, 1.0)
                if 'context:uv' not in resin_matched:
                    resin_matched.append('context:uv')

        # --- Strong signal presence ---
        has_strong_filament_signal = any(kw in text_lower for kw in self.STRONG_FILAMENT_TERMS)
        has_strong_resin_signal = any(kw in text_lower for kw in self.STRONG_RESIN_TERMS)

        primary_filament_signal = any(kw in primary_text_lower for kw in self.STRONG_FILAMENT_TERMS)
        primary_resin_signal = any(kw in primary_text_lower for kw in self.STRONG_RESIN_TERMS)

        # --- Threshold calculation ---
        base_threshold = 0.25
        if url_is_filament_related:
            base_threshold -= 0.05
        if not has_strong_filament_signal and not has_strong_resin_signal:
            base_threshold += 0.15
        # Raise threshold when all signal is from description only (no title match)
        if filament_score_p == 0 and filament_score > 0:
            base_threshold += 0.10
        if resin_score_p == 0 and resin_score > 0:
            base_threshold += 0.10

        # --- Final decision ---
        if filament_score >= resin_score and filament_score >= base_threshold:
            if not (primary_filament_signal or has_filament_context):
                logger.debug(
                    'product_match_rejected_no_primary_signal',
                    name=product.name,
                    score=round(filament_score, 3),
                    matched=filament_matched[:5],
                )
                return MatchResult(
                    is_match=False,
                    category='unknown',
                    product_type=None,
                    confidence=filament_score,
                    matched_keywords=filament_matched + resin_matched,
                )
            result = MatchResult(
                is_match=True,
                category='filament',
                product_type=self._detect_filament_type(text),
                confidence=filament_score,
                matched_keywords=filament_matched,
            )
            if filament_score < 0.4:
                logger.debug(
                    'product_match_low_confidence_filament',
                    name=product.name,
                    score=round(filament_score, 3),
                    matched=filament_matched[:5],
                )
            return result

        elif resin_score >= filament_score and resin_score >= base_threshold:
            if not (primary_resin_signal or has_resin_context):
                logger.debug(
                    'product_match_rejected_no_primary_signal',
                    name=product.name,
                    score=round(resin_score, 3),
                    matched=resin_matched[:5],
                )
                return MatchResult(
                    is_match=False,
                    category='unknown',
                    product_type=None,
                    confidence=resin_score,
                    matched_keywords=filament_matched + resin_matched,
                )
            result = MatchResult(
                is_match=True,
                category='resin',
                product_type=self._detect_resin_type(text),
                confidence=resin_score,
                matched_keywords=resin_matched,
            )
            if resin_score < 0.4:
                logger.debug(
                    'product_match_low_confidence_resin',
                    name=product.name,
                    score=round(resin_score, 3),
                    matched=resin_matched[:5],
                )
            return result

        # Near-miss logging for threshold tuning
        best_score = max(filament_score, resin_score)
        if best_score > 0.15:
            logger.debug(
                'product_match_below_threshold',
                name=product.name,
                filament_score=round(filament_score, 3),
                resin_score=round(resin_score, 3),
                threshold=round(base_threshold, 3),
                filament_matched=filament_matched[:5],
                resin_matched=resin_matched[:5],
            )

        return MatchResult(
            is_match=False,
            category='unknown',
            product_type=None,
            confidence=best_score,
            matched_keywords=filament_matched + resin_matched,
        )

    def match_url(self, url: str) -> bool:
        """Check if URL likely contains filament/resin products."""
        url_lower = url.lower()

        # Filament-related URL keywords
        filament_keywords = [
            'filament', 'pla', 'petg', 'abs', 'asa', 'tpu', 'nylon', 'hips', 'pva',
            '1-75mm', '1.75mm', '2-85mm', '2.85mm', 'spool', 'fdm', 'fff',
            'prusament', 'polymaker', 'esun', 'sunlu', 'colorfabb', 'fiberlogy',
        ]

        # Resin-related URL keywords
        resin_keywords = [
            'resin', 'sla', 'dlp', 'msla', 'lcd-resin', '405nm', 'photopolymer',
            'uv-resin', 'water-washable', 'abs-like', 'elegoo-resin', 'anycubic-resin',
        ]

        # General 3D printing consumables — only 3D-printing-specific terms
        # (removed generic 'material', 'consumable', 'forbruksvarer' as too broad)
        general_keywords = [
            '3d-filament', '3d-resin', 'printer-tilbehor', '3d-printer-forbruksvarer',
        ]

        all_keywords = filament_keywords + resin_keywords + general_keywords

        for kw in all_keywords:
            if kw in url_lower:
                return True

        return False
