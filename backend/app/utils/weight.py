import re
from typing import Optional

# (number)(optional space)(unit) patterns, evaluated in priority order.
# The 'g' pattern has a negative lookahead to reject filament diameters like "1.75mm".
_PATTERNS = [
    (re.compile(r'(\d+(?:[.,]\d+)?)\s*kg\b', re.IGNORECASE), 1000.0),
    (re.compile(r'(\d+(?:[.,]\d+)?)\s*lbs?\b', re.IGNORECASE), 453.592),
    (re.compile(r'(\d+(?:[.,]\d+)?)\s*g\b(?!\s*\d*\s*mm)', re.IGNORECASE), 1.0),
]

_MIN_GRAMS = 50.0
_MAX_GRAMS = 20000.0


def extract_weight_grams(text: str) -> Optional[float]:
    """
    Parse the first weight value found in `text` and return it in grams.

    Returns None if no weight is found, or if the result is outside
    the plausible spool range (50g - 20,000g).
    """
    if not text:
        return None

    lowered = text.lower()

    for pattern, multiplier in _PATTERNS:
        match = pattern.search(lowered)
        if match:
            raw = match.group(1).replace(',', '.')
            try:
                value = float(raw)
            except ValueError:
                continue
            grams = value * multiplier
            if _MIN_GRAMS <= grams <= _MAX_GRAMS:
                return grams

    return None
