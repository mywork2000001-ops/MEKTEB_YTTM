"""Test bazası faylının təsnifatı: növ (mövzu / sınaq / yekun / diaqnostik) və sinif(lər).

Viktorina-da bu məlumat yoxdur – mənbə açarı və faylın adından çıxarılır. Admin əl ilə düzəldirsə (`meta_locked`),
sinxronizasiya ona toxunmur."""
from __future__ import annotations

import re

from ..domain.classes import ROMAN

# mənbə -> sinif(lər); boş – addan
SOURCE_GRADES = {'p001': [5], 'p011': [6], 'p007': [9], 'p009': [11], 'p012': [11], 'p003': list(range(5, 12))}
SOURCE_KIND = {'p009': 'sinaq', 'p012': 'sinaq', 'p004': 'sinaq'}
_SINAQ = re.compile(r'sınaq|sınağ|\bBSİ\b|\bMSİ\b|\bÜSİ\b|^variant\s*\d|imtahan', re.I)
_YEKUN = re.compile(r'yekun', re.I)
_DIAG = re.compile(r'ilkin yoxlama|diaqnostik', re.I)
_ROMAN_RANGE = re.compile(r'\b([IVX]{1,4})(?:\s*[–-]\s*([IVX]{1,4}))?\s*sinif', re.I)
_ARABIC = re.compile(r'\b(\d{1,2})\s*(?:-?(?:cu|ci|cü|cı))?\s*sinif', re.I)


def grades_from_label(label: str) -> list[int]:
    out: set[int] = set()
    for a, b in _ROMAN_RANGE.findall(label):
        lo, hi = ROMAN.get(a.upper()), ROMAN.get((b or a).upper())
        if lo and hi:
            out.update(range(min(lo, hi), max(lo, hi) + 1))
    for n in _ARABIC.findall(label):
        if 1 <= int(n) <= 12:
            out.add(int(n))
    return sorted(out)


def classify(source_key: str, label: str) -> dict:
    """{'kind', 'grades', 'subject'} – fayl üçün avtomatik təsnifat."""
    if _DIAG.search(label):
        kind = 'diaqnostik'
    elif _YEKUN.search(label):
        kind = 'yekun'
    elif source_key in SOURCE_KIND or _SINAQ.search(label):
        kind = SOURCE_KIND.get(source_key, 'sinaq')
    else:
        kind = 'movzu'
    grades = grades_from_label(label) or SOURCE_GRADES.get(source_key, [])
    return {'kind': kind, 'grades': grades, 'subject': 'Riyaziyyat'}


def apply(f) -> bool:
    """BankFile-a təsnifatı yazır (kilidli deyilsə). Dəyişiklik oldusa True."""
    if f.meta_locked:
        return False
    c = classify(f.source_key, f.label or '')
    changed = (f.kind, f.grades, f.subject) != (c['kind'], c['grades'], c['subject'])
    f.kind, f.grades, f.subject = c['kind'], c['grades'], c['subject']
    return changed
