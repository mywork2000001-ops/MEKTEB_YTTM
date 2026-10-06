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
_STOP = {'ve', 'ile', 'onun', 'onlar', 'ucun', 'bezi', 'sinif', 'iki', 'hiss', 'mesel', 'anlay', 'esas', 'muxte', 'usull'}
_PREFIX = re.compile(r'^\s*[IVX]+\s+sinif\s*:\s*', re.I)


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


def p0010_files(db: Session) -> list[BankFile]:
    return list(db.scalars(select(BankFile).join(BankSource, BankSource.key == BankFile.source_key).where(
        BankFile.source_key == SOURCE, BankFile.active.is_(True), BankSource.enabled.is_(True), BankFile.question_count > 0,
        BankFile.kind == 'movzu').order_by(BankFile.lesson)))


class Matcher:
    """Bankdakı P0010 faylları bir dəfə oxunur (plan görünüşündə hər dərs üçün təkrar sorğu olmasın)."""

    def __init__(self, db: Session):
        self.files = p0010_files(db)
        self.fst = {f.id: stems(f.label) for f in self.files}
        self.own = {f.id: stems(f.label.split(' — ', 1)[-1]) for f in self.files}     # alt mövzu adı bölmədən ağırdır
        self.grp = {f.id: _raw(f.label.split(' — ', 1)[0]) for f in self.files}      # P0010 bölməsi
        df: dict[str, int] = {}
        for st in self.fst.values():
            for w in st:
                df[w] = df.get(w, 0) + 1
        n = len(self.files)
        self.idf = {w: math.log((n + 1) / (c + 1)) + 0.1 for w, c in df.items()}

    def matches(self, topic: str, section: str | None = None, limit: int = 6) -> list[tuple[BankFile, float]]:
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
        scored = [(f, v) for f, v, _ in scored]
        return scored[:limit]


def p0010_matches(db: Session, topic: str, section: str | None = None, limit: int = 6) -> list[tuple[BankFile, float]]:
    return Matcher(db).matches(topic, section, limit)
