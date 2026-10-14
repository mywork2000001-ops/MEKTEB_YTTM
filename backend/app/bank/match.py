"""Plan mövzusu → P0010 (viktorina-da «p003») test faylları: mövzu adına görə uyğunluq (docs/x-xi-p0010-testleri-promtu.md).

Söz kökü – normallaşdırılmış sözün ilk 5 hərfi; çox faylda təkrarlanan sözlərin çəkisi azdır (idf). Mövzu sözləri əsas,
bölmə adı əlavə çəki ilə."""
from __future__ import annotations

import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BankFile, BankSource

SOURCE = 'p003'
GRADE_SOURCE = {9: 'p007', 10: 'p003', 11: 'p003'}     # IX – DİM 9 test toplusu (P007), X–XI – P0010


def source_for(grade: int | None) -> str | None:
    return GRADE_SOURCE.get(grade)


def ta_source(db, ta) -> str | None:
    """Plan dərslərinin test linkləri üçün mənbə: sinfin ayarı (bank_source) üstündür; 'none' – link yoxdur."""
    if ta is not None and ta.bank_source:
        return None if ta.bank_source == 'none' else ta.bank_source
    from ..models import SchoolClass
    from ..services import class_grade
    return source_for(class_grade(db, db.get(SchoolClass, ta.class_id))) if ta is not None else None
_STOP = {'ve', 'ile', 'onun', 'onlar', 'ucun', 'bezi', 'sinif', 'iki', 'hiss', 'mesel', 'anlay', 'esas', 'muxte', 'usull'}
_PREFIX = re.compile(r'^\s*[IVX]+\s+sinif\s*:\s*', re.I)


# zəif qrup tempinin törəmə dərsləri (app/slow_plan.py; docs/zeif-plan-test-linkleri-promtu.md)
_BASE = ('Məşq və möhkəmləndirmə:', 'Təkrar və bərpa:')             # → əsas mövzunun testi
_MIXED = ('Bölmə təkrarı:', 'Spiral təkrar:', 'KSQ-yə hazırlıq:')       # qarışıq təkrar – tək fayl yoxdur
_GENERIC_SEC = {'Bazanın bərpası', 'Təkrar'}


def lesson_query(topic: str | None, section: str | None) -> tuple[str, str | None] | None:
    """Plan dərsi → uyğunluq üçün (mövzu, bölmə); None – bu dərsə mövzu testi verilmir."""
    t = (topic or '').strip()
    sec = None if (section or '').strip() in _GENERIC_SEC else section
    for p in _BASE:
        if t.startswith(p):
            return t[len(p):].strip(), sec
    if t.startswith(_MIXED) or (t.startswith('Təkrar:') and 'yekunlaşdırıcı' in t):
        return None
    return t, sec


def derived(topic: str | None) -> bool:
    """Törəmə dərs (məşq, bərpa, təkrar) – KSQ aralığında ayrıca mövzu sayılmır."""
    t = (topic or '').strip()
    return t.startswith(_BASE + _MIXED) or (t.startswith('Təkrar:') and 'yekunlaşdırıcı' in t)


def _norm(s: str) -> str:
    s = (s or '').lower().replace('ə', 'e').replace('i̇', 'i').replace('ı', 'i').replace('ö', 'o').replace('ü', 'u')
    s = s.replace('ğ', 'g').replace('ş', 's').replace('ç', 'c')
    return re.sub(r'[^\w\s]', ' ', s)


def stems(s: str) -> set[str]:
    out = {w[:5] for w in _norm(_PREFIX.sub('', s or '')).split() if len(w) >= 3 and not w.isdigit()}
    return out - _STOP


def _raw(s: str) -> set[str]:
    """Bölmə adları üçün köklər – köməkçi sözlər atılmır («Həndəsənin əsas anlayışları» bütöv tanınsın)."""
    s = re.sub(r'^\s*([ivxlc]+|\d+)\.?\s*', '', _norm(s or ''))
    return {w[:5] for w in s.split() if len(w) >= 3 and not w.isdigit()} - {'bolme', 'ile', 've'}


def p0010_files(db: Session, source: str = SOURCE, any_kind: bool = False) -> list[BankFile]:
    """Mənbənin aktiv test faylları; any_kind – sınaq/yekun faylları da (əlavə qoşulan layihələr üçün)."""
    q = select(BankFile).join(BankSource, BankSource.key == BankFile.source_key).where(
        BankFile.source_key == source, BankFile.active.is_(True), BankSource.enabled.is_(True), BankFile.question_count > 0)
    if not any_kind:
        q = q.where(BankFile.kind == 'movzu')
    return list(db.scalars(q.order_by(BankFile.lesson)))


class Matcher:
    """Bankdakı P0010 faylları bir dəfə oxunur (plan görünüşündə hər dərs üçün təkrar sorğu olmasın)."""

    def __init__(self, db: Session, source: str = SOURCE, any_kind: bool = False):
        self.files = p0010_files(db, source, any_kind)
        self.fst = {f.id: stems(f.label) for f in self.files}
        self.own = {f.id: stems(f.label.split(' — ', 1)[-1]) for f in self.files}     # alt mövzu adı bölmədən ağırdır
        self.grp = {f.id: _raw(f.label.split(' — ', 1)[0]) for f in self.files}      # P0010 bölməsi
        df: dict[str, int] = {}
        for st in self.fst.values():
            for w in st:
                df[w] = df.get(w, 0) + 1
        n = len(self.files)
        self.idf = {w: math.log((n + 1) / (c + 1)) + 0.1 for w, c in df.items()}

    def matches(self, topic: str, section: str | None = None, limit: int = 6, rel: float = 0.0) -> list[tuple[BankFile, float]]:
        q = lesson_query(topic, section)
        if q is None:
            return []
        topic, section = q
        t = stems(topic)
        sec = stems(re.sub(r'^\s*\d+\.\s*', '', section or '')) - t
        sraw = _raw(section or '')
        scored = []
        for f in self.files:
            fs, own = self.fst[f.id], self.own[f.id]
            w = lambda x: self.idf.get(x, 0) * (1 if x in own else 0.5)      # noqa: E731
            s = 2 * sum(w(x) for x in t & fs) + sum(w(x) for x in sec & fs)
            if s > 0:
                g = self.grp[f.id]
                # dərsin bölməsi = P0010 bölməsi – öndə; tez-tez rast gələn sözlər («ədədlər») az çəkili (idf)
                gw = sum(self.idf.get(x, 1) for x in g)
                same = bool(g and sraw and sum(self.idf.get(x, 1) for x in sraw & g) / gw >= 0.6)
                scored.append((f, round(s / (1 + 0.05 * len(fs)), 3), same))
        scored.sort(key=lambda x: (not x[2], -x[1], x[0].lesson))
        if rel and any(x[2] for x in scored):                # KSQ: dərsin bölməsinə uyğun fayllar varsa – yalnız onlar
            scored = [x for x in scored if x[2]]
        scored = [(f, v) for f, v, _ in scored]
        if rel and scored:                                   # KSQ: yalnız mövzuya həqiqətən yaxın fayllar
            best = max(v for _, v in scored)
            scored = [(f, v) for f, v in scored if v >= best * rel]
        return scored[:limit]


def p0010_matches(db: Session, topic: str, section: str | None = None, limit: int = 6, source: str = SOURCE) -> list[tuple[BankFile, float]]:
    return Matcher(db, source).matches(topic, section, limit)
