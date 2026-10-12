"""KSQ/BSQ kağız variantları — hər şagirdə tam fərqli 30 sual, cəmi 100 bal (docs/ksq-bsq-kagiz-promtu.md §1–§2, audit A1–A7).

Slot planı hamıda eynidir (növ + çətinlik + bal) → ədalət balla qorunur; suallar isə fərqli:
  1) sinifdə heç iki şagirddə eyni sual yoxdur (bank — content_hash, şablon — şablon+parametrlər);
  2) şagirdin öz variantında təkrar yoxdur;
  3) şagirdə əvvəl verilmiş suallar (onlayn test/sınaq, əvvəlki KSQ/BSQ variantları) seçilmir;
  4) seçim ardıcıllığı: slotun mövzusu → aralığın başqa mövzusu → qonşu çətinlik → parametrli şablon;
  5) yenə çatmırsa — Shortage istisnası (variantlar yaradılmır, müəllimə dəqiq siyahı). Səssiz təkrar yoxdur.
Açıq slota yalnız kart xanalarına yazıla bilən cavab düşür (card_answer)."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from ..bank.match import Matcher, stems
from . import templates as T

# (növ, çətinlik, bal) × say — cəmi 30 sual, 100 bal, 21 açıq (70%)
SLOT_PLAN: list[tuple[str, str, float, int]] = [
    ('mcq', 'asan', 1.5, 5), ('mcq', 'orta', 2.5, 4),
    ('open', 'asan', 2.5, 5), ('open', 'orta', 4.0, 10), ('open', 'çətin', 5.0, 6),
]
LEVELS = ('asan', 'orta', 'çətin')
NEAR = {'asan': ('orta',), 'orta': ('asan', 'çətin'), 'çətin': ('orta',)}
CARD_MAX = 8
_NUM = r'-?\d+(?:[.,]\d+)?(?:/\d+)?'
_CARD = re.compile(rf'^{_NUM}(?:;{_NUM})*$')


def slots() -> list[dict]:
    out = []
    for kind, level, pts, n in SLOT_PLAN:
        out += [{'kind': kind, 'level': level, 'points': pts} for _ in range(n)]
    for i, s in enumerate(out):
        s['slot'] = i + 1
    assert len(out) == 30 and abs(sum(s['points'] for s in out) - 100) < 1e-9
    return out


def card_answer(answer: str | None) -> str | None:
    """Kart xanalarına yazıla bilən ilk qəbul edilən cavab (≤ 8 simvol: rəqəm, «-», «,», «/», «;») — yoxdursa None."""
    for a in (answer or '').split('|'):
        a = a.strip().replace(' ', '').replace('−', '-').replace('.', ',')
        if a and len(a) <= CARD_MAX and _CARD.match(a):
            return a
    return None


def norm_text(t) -> str:
    s = t.get('az') if isinstance(t, dict) else str(t or '')
    return re.sub(r'[^\wəüöğışç]+', '', (s or '').lower())


@dataclass
class Cand:
    key: str
    kind: str
    level: str
    topic: int                    # aralıqdakı mövzunun indeksi (-1 — şablon)
    q: dict


@dataclass
class Shortage(Exception):
    items: list[dict] = field(default_factory=list)

    def message(self) -> str:
        return '; '.join(f"{x['slot']}-ci sual ({'açıq' if x['kind'] == 'open' else 'test'}, {x['level']}): "
                         f"{x['missing']} şagird üçün sual çatmır" for x in self.items[:8])


def bank_candidates(db, topics: list[tuple[str, str | None]]) -> list[Cand]:
    """Aralıqdakı plan mövzuları → P0010 faylları (Matcher, hər mövzuya 2 fayl) → yararlı bank sualları."""
    from sqlalchemy import select
    from ..models import BankQuestion
    m = Matcher(db)
    out, seen = [], set()
    for ti, (topic, section) in enumerate(topics):
        for f, _ in m.matches(topic, section, limit=2):
            for q in db.scalars(select(BankQuestion).where(BankQuestion.file_id == f.id, BankQuestion.active.is_(True))):
                key = 'b:' + (q.content_hash or str(q.id))
                if key in seen:
                    continue
                if q.kind == 'mcq':
                    if not q.options or not 2 <= len(q.options) <= 5 or q.correct is None:
                        continue
                    level = q.diff_auto or 'asan'
                elif q.kind == 'open':
                    if not card_answer(q.answer):
                        continue
                    level = q.diff_auto or 'orta'
                else:
                    continue
                seen.add(key)
                out.append(Cand(key, q.kind, level, ti, {
                    'bank_id': q.id, 'source': f.source_key, 'lesson': f.label, 'kind': q.kind, 'text': q.text,
                    'options': q.options, 'correct': q.correct, 'answer': q.answer, 'image': q.image,
                    'card_answer': card_answer(q.answer) if q.kind == 'open' else None}))
    return out


def generate(students: list[int], topics: list[tuple[str, str | None]], cands: list[Cand],
             history: dict[int, set[str]], seed: int) -> dict[int, list[dict]]:
    """students × 30 slot → {student_id: [sual surəti]}. Çatışmazlıq olarsa Shortage."""
    rng = random.Random(seed)
    plan = slots()
    nt = max(1, len(topics))
    # slotlara mövzu: plan dərslərinin ardıcıllığı ilə dövri (saat payına mütənasib — eyni mövzu bir neçə dərsdirsə çox düşür)
    for i, s in enumerate(plan):
        s['topic'] = i % nt
    tpls = T.matching(set().union(*(stems(t) | stems(sec or '') for t, sec in topics))) if topics else []
    used: set[str] = set()
    used_text: set[str] = set()
    by = {}
    for c in cands:
        by.setdefault((c.kind, c.level), []).append(c)
    for lst in by.values():
        rng.shuffle(lst)
    res: dict[int, list[dict]] = {sid: [None] * 30 for sid in students}      # type: ignore[list-item]
    order = sorted(range(30), key=lambda i: (plan[i]['kind'] != 'open', plan[i]['level'] != 'çətin'))   # az olanlar əvvəl
    short: dict[int, int] = {}
    for i in order:
        s = plan[i]
        studs = students[:]
        rng.shuffle(studs)
        for sid in studs:
            hist = history.get(sid, set())

            def ok(c: Cand) -> bool:
                return c.key not in used and c.key not in hist and norm_text(c.q['text']) not in used_text

            pick = None
            for lvl in (s['level'], *NEAR[s['level']]):
                pool = [c for c in by.get((s['kind'], lvl), []) if ok(c)]
                same = [c for c in pool if c.topic == s['topic']]
                if same or pool:
                    pick = (same or pool)[0]
                    break
            if pick is None and s['kind'] == 'open':
                for t in sorted(tpls, key=lambda t: (t.level != s['level'], rng.random())):
                    for _ in range(60):
                        q = T.instance(t, rng)
                        if q['key'] not in used and q['key'] not in hist and norm_text(q['text']) not in used_text:
                            pick = Cand(q['key'], 'open', q['level'], -1, {**q, 'card_answer': q['answer']})
                            break
                    if pick:
                        break
            if pick is None:
                short[i] = short.get(i, 0) + 1
                continue
            used.add(pick.key)
            used_text.add(norm_text(pick.q['text']))
            res[sid][i] = {**{k: v for k, v in pick.q.items() if k != 'key'}, 'key': pick.key, 'slot': s['slot'],
                           'kind': s['kind'], 'level': s['level'], 'level_actual': pick.level, 'points': s['points'],
                           'topic': topics[s['topic']][0] if topics else None,
                           'topic_actual': (topics[pick.topic][0] if 0 <= pick.topic < len(topics) else 'şablon') if topics else None}
    if short:
        raise Shortage([{'slot': plan[i]['slot'], 'kind': plan[i]['kind'], 'level': plan[i]['level'], 'missing': n}
                        for i, n in sorted(short.items())])
    return res


def fairness(variants: dict[int, list[dict]]) -> dict:
    """Ədalət hesabatı: slotun hədəf çətinliyinə dəqiq uyğun sualların payı, mövzu əvəzlənməsi, şablon sayı."""
    qs = [q for v in variants.values() for q in v]
    n = len(qs) or 1
    return {'questions': len(qs), 'unique': len({q['key'] for q in qs}),
            'exact_level_pct': round(100 * sum(q['level_actual'] == q['level'] for q in qs) / n, 1),
            'same_topic_pct': round(100 * sum(q.get('topic_actual') == q.get('topic') for q in qs) / n, 1),
            'templates': sum(q.get('template') is not None for q in qs),
            'open_pct': round(100 * sum(q['kind'] == 'open' for q in qs) / n, 1)}
