"""Sinfin rəqəmi: «IX a» -> 9, «11 p» -> 11, «X b (riyaziyyat qrupu)» -> 10. Tanınmırsa None."""
from __future__ import annotations

import re

ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12}


# kiril/rəqəm-simvol oxşarları (rus sektoru: «IХ а», «VІ б», «Ⅸ»): latın rəqəm hərflərinə çevrilir
_HOMOGLYPHS = {ord(k): v for k, v in {"І": "I", "і": "i", "Х": "X", "х": "x", "Ӏ": "I", "Ѵ": "V", "ѵ": "v"}.items()}
_HOMOGLYPHS.update({0x2160 + i: r for i, r in enumerate(["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"])})


def _norm(name: str) -> str:
    return name.translate(_HOMOGLYPHS)


def grade_of(*names: str | None) -> int | None:
    """Birinci tanınan addan sinif rəqəmi (ad, sonra UTİS sinfi)."""
    for name in names:
        if not name:
            continue
        name = _norm(name)
        m = re.match(r'\s*(\d{1,2})', name)
        if m and 1 <= int(m.group(1)) <= 12:
            return int(m.group(1))
        m = re.match(r'\s*([IVXivx]{1,4})(?=$|[\s\-–.(])', name)
        if m and m.group(1).upper() in ROMAN:
            return ROMAN[m.group(1).upper()]
        # adın içində: «Buraxılış IX sinif», «Hazırlıq 9-cu sinif» (fərdi hazırlıq qrupları)
        m = re.search(r'\b(\d{1,2})\s*-?\s*(?:cu|ci|cü|cı)?\s+sinif', name, re.I)
        if m and 1 <= int(m.group(1)) <= 12:
            return int(m.group(1))
        m = re.search(r'\b([IVX]{1,4})\s+sinif', name)
        if m and m.group(1) in ROMAN:
            return ROMAN[m.group(1)]
    return None
