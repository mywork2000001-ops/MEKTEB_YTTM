"""Sinfin rəqəmi: «IX a» -> 9, «11 p» -> 11, «X b (riyaziyyat qrupu)» -> 10. Tanınmırsa None."""
from __future__ import annotations

import re

ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12}


def grade_of(*names: str | None) -> int | None:
    """Birinci tanınan addan sinif rəqəmi (ad, sonra UTİS sinfi)."""
    for name in names:
        if not name:
            continue
        m = re.match(r'\s*(\d{1,2})', name)
        if m and 1 <= int(m.group(1)) <= 12:
            return int(m.group(1))
        m = re.match(r'\s*([IVXivx]{1,4})(?=$|[\s\-–.(])', name)
        if m and m.group(1).upper() in ROMAN:
            return ROMAN[m.group(1).upper()]
    return None
