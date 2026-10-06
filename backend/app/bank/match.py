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


def p0010_files(db: Session) -> list[BankFile]:
    return list(db.scalars(select(BankFile).join(BankSource, BankSource.key == BankFile.source_key).where(
        BankFile.source_key == SOURCE, BankFile.active.is_(True), BankSource.enabled.is_(True), BankFile.question_count > 0,
        BankFile.kind == 'movzu').order_by(BankFile.lesson)))


def p0010_matches(db: Session, topic: str, section: str | None = None, limit: int = 6) -> list[tuple[BankFile, float]]:
    files = p0010_files(db)
    if not files:
        return []
    fst = {f.id: stems(f.label) for f in files}
    df: dict[str, int] = {}
    for st in fst.values():
        for w in st:
            df[w] = df.get(w, 0) + 1
    idf = lambda w: math.log((len(files) + 1) / (df.get(w, 0) + 1)) + 0.1     # noqa: E731
    t, sec = stems(topic), stems(re.sub(r'^\s*\d+\.\s*', '', section or '')) - stems(topic)
    scored = []
    for f in files:
        own = stems(f.label.split(' — ', 1)[-1])          # alt mövzu adı bölmə adından ağırdır
        w_of = lambda w: idf(w) * (1 if w in own else 0.5)  # noqa: E731
        s = 2 * sum(w_of(w) for w in t & fst[f.id]) + sum(w_of(w) for w in sec & fst[f.id])
        if s > 0:
            scored.append((f, round(s / (1 + 0.05 * len(fst[f.id])), 3)))
    scored.sort(key=lambda x: (-x[1], x[0].lesson))
    return scored[:limit]
