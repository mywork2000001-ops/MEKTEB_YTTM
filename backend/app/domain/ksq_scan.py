"""KSQ/BSQ cavab kartının skanı (docs/ksq-bsq-kagiz-promtu.md §4, mərhələ 3).

1. Şəkil / PDF → QR-lar (zxing-cpp; bir şəkildə bir neçə kart ola bilər) → imza yoxlanılır (ksq_card.parse_qr).
2. QR-ın şəkildəki künclərinə görə kartın yalnız CAVAB ZONASI düzəldilib kəsilir (ad, sinif, məktəb – yox): kart ölçüləri
   frontend/src/ksqPrint.ts ilə eynidir (QR 22 mm, kartın sol kənarı QR-dan 10 mm solda, cavab zonası QR-ın üstündən 23–106 mm).
3. Oxunuş (Claude / idxal / müəllim) → serverdə qiymətləndirmə: test – hərf; açıq – «|» variantları, normallaşdırma, kəsr = onluq.
"""
from __future__ import annotations

import io
from fractions import Fraction

from .ksq_card import MCQ_LETTERS, parse_qr

QR_MM = 22.0                       # kartdakı QR-ın tərəfi (ksqPrint.ts: .ctop img 22mm)
ZONE = (-10.0, 23.0, 184.0, 112.0)  # QR-ın sol üst küncünə görə mm: x0, y0, x1, y1 (kartın eni 194 mm; QR-ın altından;
#                                    y1 106 → 112: çapda sətirlər bir az hündür olur, son sətir (28–30) kəsilirdi – 13.10.2026)
PX_MM = 8                          # kəsikdə 1 mm = 8 piksel (~200 dpi; 6 px əl yazısı rəqəmlər üçün az idi – 13.10.2026)
LOW = 0.85                         # bu etibardan aşağı xana – «yoxlanılmalı»


# ---------------------------------------------------------------- şəkillər
def images_from_upload(data: bytes, mime: str | None) -> list:
    """Yüklənmiş fayl → PIL şəkilləri (PDF-də hər səhifənin şəkilləri)."""
    from PIL import Image, ImageOps
    if (mime or '').endswith('pdf') or data[:5] == b'%PDF-':
        from pypdf import PdfReader
        out = []
        for page in PdfReader(io.BytesIO(data)).pages:
            for im in page.images:
                try:
                    out.append(_small(ImageOps.exif_transpose(Image.open(io.BytesIO(im.data))).convert('L')))
                except Exception:                       # noqa: BLE001 – oxunmayan şəkil atlanır
                    continue
        return out
    return [_small(ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('L'))]


MAX_SIDE = 2400                    # yaddaş (Render 512 MB): telefon şəkli 4000 px-dən çox ola bilər; QR və kəsik üçün 2400 kifayətdir


def _small(img):
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def _pt(p) -> tuple[float, float]:
    return float(p.x), float(p.y)


def find_cards(img) -> list[dict]:
    """Şəkildəki imzalı QR-lar → [{exam_id, student_id, code, crop(JPEG bytes)}]; imzasız/yad QR-lar atılır."""
    import zxingcpp
    out, seen = [], set()
    for b in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode):
        info = parse_qr(b.text)
        if not info or b.text in seen:
            continue
        seen.add(b.text)
        tl, tr, bl = _pt(b.position.top_left), _pt(b.position.top_right), _pt(b.position.bottom_left)
        if not zone_inside(img.size, tl, tr, bl):                 # kartın bir hissəsi kadrdan kənardadır
            out.append({**info, 'partial': True})
            continue
        out.append({**info, 'crop': crop_zone(img, tl, tr, bl)})
    return out


EDGE_MM = 2.0                      # zona şəkildən bu qədər (mm) kənara çıxa bilər – kənar xətlər; çoxu – «yenidən çək»


def zone_inside(size: tuple[int, int], tl, tr, bl) -> bool:
    """Cavab zonasının 4 küncü şəklin içindədirmi? Yoxsa crop_zone kənarı ağ doldurur və həmin suallar «boş» oxunur
    (şagirdə səhvən 0 bal) – belə kart qəbul edilmir (13.10.2026)."""
    ux, uy = (tr[0] - tl[0]) / QR_MM, (tr[1] - tl[1]) / QR_MM
    vx, vy = (bl[0] - tl[0]) / QR_MM, (bl[1] - tl[1]) / QR_MM
    w, h = size
    tol = EDGE_MM * max((ux * ux + uy * uy) ** 0.5, (vx * vx + vy * vy) ** 0.5)
    x0, y0, x1, y1 = ZONE
    for mx, my in ((x0 + EDGE_MM, y0), (x1 - EDGE_MM, y0), (x0 + EDGE_MM, y1), (x1 - EDGE_MM, y1)):
        px, py = tl[0] + ux * mx + vx * my, tl[1] + uy * mx + vy * my
        if px < -tol or py < -tol or px > w + tol or py > h + tol:
            return False
    return True


def crop_zone(img, tl, tr, bl) -> bytes:
    """QR künclərindən afin çevirmə: kartın cavab zonası düz (fırlanma/miqyas düzəlir), boz JPEG."""
    from PIL import Image
    ux, uy = (tr[0] - tl[0]) / QR_MM, (tr[1] - tl[1]) / QR_MM        # 1 mm sağa – şəkildə
    vx, vy = (bl[0] - tl[0]) / QR_MM, (bl[1] - tl[1]) / QR_MM        # 1 mm aşağı – şəkildə
    x0, y0, x1, y1 = ZONE
    w, h = int((x1 - x0) * PX_MM), int((y1 - y0) * PX_MM)
    k = 1 / PX_MM
    data = (ux * k, vx * k, tl[0] + ux * x0 + vx * y0,
            uy * k, vy * k, tl[1] + uy * x0 + vy * y0)
    z = img.transform((w, h), Image.AFFINE, data, resample=Image.BICUBIC, fillcolor=255)
    buf = io.BytesIO()
    z.save(buf, 'JPEG', quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------- qiymətləndirmə
def _norm(v) -> str:
    return str(v or '').strip().replace(' ', '').replace('−', '-').replace('–', '-').replace('.', ',').upper()


def _num(t: str) -> Fraction | None:
    try:
        if '/' in t:
            a, b = t.split('/', 1)
            return Fraction(int(a), int(b))
        return Fraction(t.replace(',', '.'))
    except (ValueError, ZeroDivisionError):
        return None


def _same(given: str, expected: str) -> bool:
    g, e = _norm(given), _norm(expected)
    if not g or not e:
        return False
    if g == e:
        return True
    gs, es = g.split(';'), e.split(';')
    if len(gs) != len(es):
        return False
    gn, en = [_num(x) for x in gs], [_num(x) for x in es]
    if None in gn or None in en:
        return False
    return gn == en or (len(gn) > 1 and sorted(gn) == sorted(en))     # köklər cütü – sıra fərq etmir


SCORE_STEPS = (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(1))


def score_fraction(value) -> Fraction | None:
    """Müəllim balı dairəsi: «0», «1/4», «0,5», «3/4», «1» → Fraction; tanınmayan / boş → None (sarı xana)."""
    t = _norm(value)
    if not t:
        return None
    f = _num(t)
    return f if f in SCORE_STEPS else None


def correct(q: dict, value) -> bool:
    if q.get('kind') == 'mcq':
        v = _norm(value)
        return q.get('correct') is not None and len(v) == 1 and v in MCQ_LETTERS and MCQ_LETTERS.index(v) == int(q['correct'])
    return any(_same(value, a) for a in str(q.get('answer') or '').split('|'))


def grade(questions: list[dict], reading: list[dict], annulled: set[int] | None = None) -> dict:
    """Variant sualları + oxunuş → {marks (slot sırası ilə 1/0), points, flagged}. Boş və ya oxunmayan xana – 0 bal.
    annulled – müəllimin ləğv etdiyi slotlar (səhv sual): sayılmır, qalan ballar 100-ə miqyaslanır."""
    annulled = annulled or set()
    by = {int(r['slot']): r for r in reading or [] if r.get('slot') is not None}
    qs = sorted(questions, key=lambda q: q['slot'])
    marks, pts, flagged = [], 0.0, []
    total = sum(q['points'] for q in qs if q['slot'] not in annulled) or 1
    full = sum(q['points'] for q in qs) or 100
    for q in qs:
        if q['slot'] in annulled:
            marks.append(0)
            continue
        r = by.get(q['slot'])
        if q.get('kind') == 'score':                       # həlli yazılan sual: müəllim balı 0 · ¼ · ½ · ¾ · 1 (kartdakı dairələr)
            f = score_fraction(r.get('value')) if r else None
            marks.append(1 if f == 1 else 0.5 if f else 0)
            pts += q['points'] * (f or 0)
            if r is None or f is None or (r.get('confidence') is not None and float(r['confidence']) < LOW):
                flagged.append(q['slot'])
            continue
        ok = bool(r) and correct(q, r.get('value'))
        marks.append(1 if ok else 0)
        pts += q['points'] if ok else 0
        if r is None or (r.get('confidence') is not None and float(r['confidence']) < LOW):
            flagged.append(q['slot'])
    return {'marks': marks, 'points': round(pts * full / total, 2), 'flagged': flagged}


def crop_any_qr(img) -> bytes | None:
    """İmzası oxunmayan / tanınmayan QR da olsa – onun künclərinə görə cavab zonasını kəsir (əl ilə şagird seçimi üçün).
    QR heç tapılmırsa və ya kart kadra tam düşməyibsə – None."""
    import zxingcpp
    for b in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode):
        tl, tr, bl = _pt(b.position.top_left), _pt(b.position.top_right), _pt(b.position.bottom_left)
        if zone_inside(img.size, tl, tr, bl):
            return crop_zone(img, tl, tr, bl)
    return None
