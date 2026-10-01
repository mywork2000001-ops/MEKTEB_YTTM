"""Telefon nömrələri: Azərbaycan formatına salma və Excel/CSV cədvəlindən oxuma.

Qəbul olunur: «050 123 45 67», «50-123-45-67», «994501234567», «+994 (50) 123 45 67», «0125551234» (stasionar).
Nəticə: «+994 50 123 45 67». Xarici nömrə «+» ilə başlayırsa, yalnız təmizlənir. Səhv nömrə – ValueError."""
from __future__ import annotations

import csv
import io
import re

AZ_CODES = {'10', '12', '50', '51', '55', '60', '70', '77', '99',              # mobil + Bakı
            '18', '20', '21', '22', '23', '24', '25', '26', '36'}             # regionlar (stasionar)


def norm_phone(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip()
    if s.endswith('.0'):                                   # Excel rəqəm kimi saxlayıb
        s = s[:-2]
    plus = s.startswith('+')
    d = re.sub(r'\D', '', s)
    if d.startswith('994'):
        d = d[3:]
    elif d.startswith('0') and len(d) == 10:
        d = d[1:]
    elif plus:                                             # xarici nömrə
        if not 8 <= len(d) <= 15:
            raise ValueError(f'Telefon nömrəsi səhvdir: {raw}')
        return '+' + d
    if len(d) != 9 or d[:2] not in AZ_CODES:
        raise ValueError(f'Telefon nömrəsi səhvdir: {raw}')
    return f'+994 {d[:2]} {d[2:5]} {d[5:7]} {d[7:]}'


def name_key(s: str) -> str:
    """Ad müqayisəsi: kiçik hərf, «oğlu/qızı» atılır, i/ı və boşluqlar bərabərləşdirilir."""
    s = s.casefold().replace('i̇', 'i').replace('ı', 'i')
    s = re.sub(r'\b(oğlu|oglu|qizi)\b', ' ', s)
    return ' '.join(re.sub(r'[^\w\s]', ' ', s).split())


# başlıq sözü -> sahə (ilk uyğun gələn)
HEADERS = [
    ('student_phone', ('şagirdin telefonu', 'şagird telefonu', 'şagird tel', 'öz telefonu')),
    ('mother_phone', ('ana telefonu', 'ananın telefonu', 'ana tel')),
    ('father_phone', ('ata telefonu', 'atanın telefonu', 'ata tel')),
    ('mother', ('ana', 'ananın adı')),
    ('father', ('ata', 'atanın adı')),
    ('student', ('şagird', 'soyad', 'ad, soyad', 'adı')),
]


def _field(h: str) -> str | None:
    h = ' '.join(str(h or '').casefold().replace('i̇', 'i').split())
    for f, words in HEADERS:
        if any(h == w or h.startswith(w + ' ') or h.startswith(w + ',') for w in words):
            return f
    return None


def read_table(data: bytes, filename: str) -> list[dict]:
    """Cədvəldən sətirlər: [{'row': 2, 'student': ..., 'student_phone': ..., 'mother': ..., ...}]."""
    if filename.lower().endswith('.csv'):
        text = data.decode('utf-8-sig', errors='replace')
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=',;\t') if text.strip() else csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    else:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        rows = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    head_i = next((i for i, r in enumerate(rows[:10]) if sum(_field(c) is not None for c in r) >= 2), None)
    if head_i is None:
        raise ValueError('Başlıq sətri tapılmadı: «Şagird», «Şagirdin telefonu», «Ana», «Ana telefonu», «Ata», «Ata telefonu»')
    cols = {}
    for j, h in enumerate(rows[head_i]):
        f = _field(h)
        if f and f not in cols:
            cols[f] = j
    if 'student' not in cols:
        raise ValueError('«Şagird» sütunu yoxdur')
    out = []
    for i, r in enumerate(rows[head_i + 1:], head_i + 2):
        get = lambda f: (str(r[cols[f]]).strip() if f in cols and cols[f] < len(r) and r[cols[f]] is not None else '')
        if not get('student'):
            continue
        out.append({'row': i, **{f: get(f) for f in cols}})
    return out
