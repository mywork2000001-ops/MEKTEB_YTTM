"""Test bazası faylının təsnifatı: növ (mövzu / sınaq / yekun / diaqnostik) və sinif(lər).

Viktorina-da bu məlumat yoxdur – mənbə açarı və faylın adından çıxarılır. Admin əl ilə düzəldirsə (`meta_locked`),
sinxronizasiya ona toxunmur."""
from __future__ import annotations

import datetime as dt
import re

from ..domain.classes import ROMAN

# mənbə -> sinif(lər); boş – addan
SOURCE_GRADES = {'p001': [5], 'p011': [6], 'p007': [9], 'p009': [11], 'p012': [11], 'p003': list(range(5, 12))}
# «Sınaqlar» qovluğu (viktorina `sinaqlar`) – yalnız 3-cü tərəf sınaqlarıdır, adında «sınaq» olmasa da (OBM mövzu sınaqları, RF MS1…)
SOURCE_KIND = {'p009': 'sinaq', 'p012': 'sinaq', 'p004': 'sinaq', 'sinaqlar': 'sinaq'}
_SINAQ = re.compile(r'sınaq|sınağ|\bBSİ\b|\bMSİ\b|\bÜSİ\b|\bMS\d|^variant\s*\d|imtahan', re.I)
# adda sinif yoxdursa: buraxılış sınağı – XI sinif (yalnız «Sınaqlar» mənbəyi; OBM kimi sinifsizlər boş qalır)
_BURAXILIS = re.compile(r'buraxılış', re.I)
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


_DAY = re.compile(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b')
_MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avqust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr']
_MONTH = re.compile(r'\b(' + '|'.join(_MONTHS) + r')\s+(\d{4})\b', re.I)
_YEAR = re.compile(r'\b(20\d{2})\b')


def held_from_label(label: str) -> tuple[dt.date | None, str | None]:
    """Sınağın keçirilmə tarixi etiketdən: «27.09.2026» → gün; «sentyabr 2026» → ay; «2026 · …» / «(…, 2026)» → il."""
    if m := _DAY.search(label):
        try:
            return dt.date(int(m[3]), int(m[2]), int(m[1])), 'day'
        except ValueError:
            pass
    if m := _MONTH.search(label):
        return dt.date(int(m[2]), _MONTHS.index(m[1].lower()) + 1, 1), 'month'
    if m := _YEAR.search(label):
        return dt.date(int(m[1]), 1, 1), 'year'
    return None, None


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
    if not grades and source_key == 'sinaqlar' and _BURAXILIS.search(label):
        grades = [11]
    return {'kind': kind, 'grades': grades, 'subject': 'Riyaziyyat'}


def apply(f) -> bool:
    """BankFile-a təsnifatı yazır (kilidli deyilsə). Dəyişiklik oldusa True."""
    f.held_on, f.held_prec = held_from_label(f.label or '')     # tarix – faktdır, admin kilidindən asılı deyil
    if f.meta_locked:
        return False
    c = classify(f.source_key, f.label or '')
    changed = (f.kind, f.grades, f.subject) != (c['kind'], c['grades'], c['subject'])
    f.kind, f.grades, f.subject = c['kind'], c['grades'], c['subject']
    return changed
