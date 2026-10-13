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
# yalnız qapalı (test) suallar – məs. DİM sinif testi (P013) üzrə KSQ, 13.10.2026: «sinif testindən 20 qapalı sual»
SLOT_PLAN_MCQ: list[tuple[str, str, float, int]] = [('mcq', 'asan', 3.0, 12), ('mcq', 'orta', 3.5, 12), ('mcq', 'çətin', 4.0, 6)]
LEVELS = ('asan', 'orta', 'çətin')
NEAR = {'asan': ('orta',), 'orta': ('asan', 'çətin'), 'çətin': ('orta',)}
CARD_MAX = 8
_NUM = r'-?\d+(?:[.,]\d+)?(?:/\d+)?'
_CARD = re.compile(rf'^{_NUM}(?:;{_NUM})*$')


N_MIN, N_MAX = 10, 30          # müəllim sual sayını seçir (kart: 9 test + 21 açıq xanaya qədər sığır)
RULES_V = 3                    # sual seçimi qaydalarının versiyası (3 – audit 13.10: dəqiq mövzu, zəif uyğunluq yox)
REUSE = 0.2                    # başqa siniflərin eyni imtahan variantları ilə təkrar – ən çox 20% (istifadəçi qaydası, 12.10.2026)


def slots(n: int = 30, mcq_only: bool = False) -> list[dict]:
    """n sual: slot planı mütənasib kiçilir (növ/çətinlik payı saxlanır), ballar cəmi 100 olacaq şəkildə 0,5-ə yuvarlanır.
    mcq_only – yalnız qapalı (test) suallar."""
    n = max(N_MIN, min(N_MAX, int(n)))
    plan_ = SLOT_PLAN_MCQ if mcq_only else SLOT_PLAN
    cnt = [max(1, round(c * n / 30)) for *_, c in plan_]
    while sum(cnt) != n:                                   # fərq – ən böyük qrupda (açıq orta)
        i = max(range(len(cnt)), key=lambda k: cnt[k])
        cnt[i] += 1 if sum(cnt) < n else -1
    raw = sum(p * c for (_, _, p, _), c in zip(plan_, cnt))
    out = []
    for (kind, level, pts, _), c in zip(plan_, cnt):
        out += [{'kind': kind, 'level': level, 'points': max(0.5, round(pts * 100 / raw * 2) / 2)} for _ in range(c)]
    diff = round((100 - sum(s['points'] for s in out)) * 2) / 2        # qalıq – ən çətin suallara 0,5-lik addımla
    k = len(out) - 1
    while abs(diff) >= 0.5:
        step = 0.5 if diff > 0 else -0.5
        if out[k]['points'] + step >= 0.5:
            out[k]['points'] += step
            diff -= step
        k = k - 1 if k > 0 else len(out) - 1
    for i, s in enumerate(out):
        s['slot'] = i + 1
    assert len(out) == n and abs(sum(s['points'] for s in out) - 100) < 1e-9
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
    topic: int                    # aralıqdakı mövzunun indeksi (-1 — şablon / seçilmiş test)
    q: dict
    topics: frozenset = frozenset()   # sualın aid olduğu BÜTÜN mövzular (ortaq fayl bir neçə mövzuya bağlana bilər)

    def on(self, ti: int) -> bool:
        return ti == self.topic or ti in self.topics


@dataclass
class Shortage(Exception):
    items: list[dict] = field(default_factory=list)

    def message(self) -> str:
        return '; '.join(f"{x['slot']}-ci sual ({'açıq' if x['kind'] == 'open' else 'test'}, {x['level']}): "
                         f"{x['missing']} şagird üçün sual çatmır" for x in self.items[:8])


def bank_candidates(db, topics: list[tuple[str, str | None]], source: str = 'p003',
                    files: dict[int, list[int]] | None = None) -> list[Cand]:
    """Aralıqdakı plan mövzuları → sinfin test bazası (IX – DİM 9 P007, X–XI – P0010; Matcher, hər mövzuya 4 fayl) → yararlı suallar."""
    from sqlalchemy import select
    from ..models import BankQuestion
    from ..models import BankFile
    m = Matcher(db, source)
    out, seen = [], set()
    # files: {mövzu indeksi: [fayl id]} – perspektiv plandakı seçim və ya müəllimin seçdiyi testlər (-1 – istənilən mövzu)
    plan = files if files is not None else {ti: [f.id for f, _ in m.matches(t, sec, limit=4, rel=0.45)] for ti, (t, sec) in enumerate(topics)}
    # bir fayl bir neçə mövzuda ola bilər: sualları faylın ƏN UYĞUN mövzusuna yazılır – mövzu siyahısında birinci olduğu (və ya
    # ən yuxarıda durduğu), bərabərlikdə faylı az olan mövzu (məs. «Qalıqlı bölmə» → «Ədədin bölünəni», əvvəlki mövzuya yox)
    home: dict[int, int] = {}
    for ti, fids in plan.items():
        for rank, fid in enumerate(fids):
            cur = home.get(fid)
            key = (ti == -1, rank, len(fids))
            if cur is None or key < (cur == -1, plan[cur].index(fid), len(plan[cur])):
                home[fid] = ti
    of_file: dict[int, frozenset] = {}
    for ti, fids in plan.items():
        for fid in fids:
            if ti >= 0:
                of_file[fid] = of_file.get(fid, frozenset()) | {ti}
    for ti, fids in plan.items():
        for f in (db.get(BankFile, i) for i in fids if home.get(i) == ti):
            if f is None or not f.active:
                continue
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
                out.append(Cand(key, q.kind, level, ti, topics=of_file.get(f.id, frozenset()), q={
                    'bank_id': q.id, 'source': f.source_key, 'lesson': f.label, 'kind': q.kind, 'text': q.text,
                    'options': q.options, 'correct': q.correct, 'answer': q.answer, 'image': q.image,
                    'card_answer': card_answer(q.answer) if q.kind == 'open' else None}))
                # P0010-da sualların çoxu testdir (A–E), KSQ-də isə ~70 % açıq: düzgün variantı ƏDƏD olan test sualı
                # açıq sual kimi də verilə bilər (variantsız, cavab kart xanasına) – sual yenə P0010-dandır, şablon deyil
                if q.kind == 'mcq':
                    opt = q.options[q.correct]
                    ans = card_answer(opt.get('az') if isinstance(opt, dict) else str(opt))
                    if ans and not re.search(r'[a-zA-Zəğıöüşç]', (opt.get('az') if isinstance(opt, dict) else str(opt)) or ''):
                        out.append(Cand(key + ':o', 'open', 'orta' if level == 'asan' else level, ti, topics=of_file.get(f.id, frozenset()), q={
                            'bank_id': q.id, 'source': f.source_key, 'lesson': f.label, 'kind': 'open', 'text': q.text,
                            'options': None, 'correct': None, 'answer': ans, 'image': q.image, 'card_answer': ans, 'from_mcq': True}))
    return out


def generate(students: list[int], topics: list[tuple[str, str | None]], cands: list[Cand],
             history: dict[int, set[str]], seed: int, n: int = 30, others: set[str] | None = None,
             share: int = 1, templates: bool = False, mcq_only: bool = False) -> dict[int, list[dict]]:
    """students × n slot → {student_id: [sual surəti]}. others – başqa siniflərin eyni imtahanında işlənmiş suallar:
    əvvəl təzələri seçilir, çatmasa ən çox REUSE (20%) qədəri təkrar ola bilər. Çatışmazlıq olarsa Shortage."""
    rng = random.Random(seed)
    plan = slots(n, mcq_only)
    n = len(plan)
    others = others or set()
    # siniflərarası ≤ 20 % qaydası yalnız hamıya fərqli sual mümkün olanda; təkrar onsuz da lazımdırsa (share > 1) – limit yoxdur
    reuse_left = int(REUSE * n * len(students)) if share == 1 else 10 ** 9
    nt = max(1, len(topics))
    # slotlara mövzu: plan dərslərinin ardıcıllığı ilə dövri (saat payına mütənasib — eyni mövzu bir neçə dərsdirsə çox düşür)
    # slotlar yalnız SUALI OLAN mövzulara dövri paylanır (faylı qonşu mövzu ilə ortaq olan mövzu boş qalırdı – slot başqa yerə gedirdi)
    live = sorted({t for c in cands for t in ({c.topic} | set(c.topics)) if 0 <= t < nt}) or list(range(nt))
    for i, s in enumerate(plan):
        s['topic'] = live[i % len(live)]
    # şablonlar YALNIZ aralığın mövzularına uyğun (docs/ksq-movzu-dizayn-promtu.md B2) – ümumi ehtiyat yoxdur
    # şablonlar standart olaraq SÖNÜKDÜR: suallar yalnız layihənin (X–XI – P0010 Blok İmtahan) fayllarından (istifadəçi qaydası 13.10)
    tpl_topic = {ti: T.matching(stems(t) | stems(sec or '')) for ti, (t, sec) in enumerate(topics)} if templates else {}
    # share – bir sual sinifdə ən çox neçə şagirdə düşə bilər (standart 1 – hamıda fərqli; müəllim seçimi ilə 2)
    uses: dict[str, int] = {}
    text_uses: dict[str, int] = {}
    ntext: dict[str, str] = {}
    mine: dict[int, set[str]] = {sid: set() for sid in students}
    by = {}
    for c in cands:
        by.setdefault((c.kind, c.level), []).append(c)
    for lst in by.values():
        rng.shuffle(lst)
    res: dict[int, list[dict]] = {sid: [None] * n for sid in students}      # type: ignore[list-item]
    order = sorted(range(n), key=lambda i: (plan[i]['kind'] != 'open', plan[i]['level'] != 'çətin'))   # az olanlar əvvəl
    short: dict[int, int] = {}
    for i in order:
        s = plan[i]
        studs = students[:]
        rng.shuffle(studs)
        for sid in studs:
            hist = history.get(sid, set())

            def ok(c: Cand) -> bool:
                t = ntext.get(c.key) or ntext.setdefault(c.key, norm_text(c.q['text']))      # mətn bir dəfə normallaşdırılır
                return (uses.get(c.key, 0) < share and c.key not in hist and c.key not in mine[sid] and t not in mine[sid]
                        and text_uses.get(t, 0) < share)

            pick = None
            for lvl in (s['level'], *NEAR[s['level']]):
                pool = [c for c in by.get((s['kind'], lvl), []) if ok(c)]
                fresh = [c for c in pool if c.key not in others]          # başqa sinifdə işlənməyənlər əvvəl
                if not fresh and reuse_left <= 0:
                    continue
                pool = fresh or pool
                same = [c for c in pool if c.on(s['topic'])]
                if same or pool:
                    pick = (same or pool)[0]
                    break
            if pick is None:
                # bankda çatmır → slotun mövzusunun şablonu, sonra aralığın başqa mövzusunun şablonu (aralıqdan kənar – heç vaxt)
                tops = [s['topic'], *[k for k in tpl_topic if k != s['topic']]]
                for ti in tops:
                    for t in sorted(tpl_topic.get(ti, []), key=lambda t: (t.level != s['level'], rng.random())):
                        for _ in range(60):
                            q = T.instance(t, rng) if s['kind'] == 'open' else T.mcq_instance(t, rng)
                            if q and ok(Cand(q['key'], s['kind'], q['level'], ti, q)):
                                pick = Cand(q['key'], s['kind'], q['level'], ti, {**q, 'card_answer': q.get('answer')})
                                break
                        if pick:
                            break
                    if pick:
                        break
            if pick is None:
                short[i] = short.get(i, 0) + 1
                continue
            if pick.key in others:
                reuse_left -= 1
            uses[pick.key] = uses.get(pick.key, 0) + 1
            tn = norm_text(pick.q['text'])
            text_uses[tn] = text_uses.get(tn, 0) + 1
            mine[sid] |= {pick.key, tn}
            res[sid][i] = {**{k: v for k, v in pick.q.items() if k != 'key'}, 'key': pick.key, 'slot': s['slot'],
                           'kind': s['kind'], 'level': s['level'], 'level_actual': pick.level, 'points': s['points'], 'v': RULES_V,
                           'topic': topics[s['topic']][0] if topics else None,
                           'topic_actual': (topics[pick.topic][0] if 0 <= pick.topic < len(topics) else 'seçilmiş test') if topics else None}
    if short:
        raise Shortage([{'slot': plan[i]['slot'], 'kind': plan[i]['kind'], 'level': plan[i]['level'], 'missing': n}
                        for i, n in sorted(short.items())])
    return res


def pick_one(slot: dict, topics: list[tuple[str, str | None]], cands: list[Cand], exclude: set[str], seed: int,
             templates: bool = False) -> dict | None:
    """Bir slot üçün yeni sual (əvəzetmə): eyni növ; çətinlik – eyni, sonra qonşu; mövzu – slotunku, sonra aralığın başqası;
    bankda yoxdursa – həmin mövzuların şablonu. exclude – sinifdə işlənmiş açarlar və mətnlər."""
    rng = random.Random(seed)
    ti = next((k for k, (t, _) in enumerate(topics) if t == slot.get('topic')), 0)
    ok = lambda c: c.key not in exclude and norm_text(c.q['text']) not in exclude      # noqa: E731
    for lvl in (slot['level'], *NEAR[slot['level']]):
        pool = [c for c in cands if c.kind == slot['kind'] and c.level == lvl and ok(c)]
        rng.shuffle(pool)
        pool.sort(key=lambda c: c.topic != ti)
        if pool:
            c = pool[0]
            return {**{k: v for k, v in c.q.items() if k != 'key'}, 'key': c.key, 'level_actual': c.level, 'v': RULES_V,
                    'topic_actual': topics[c.topic][0] if 0 <= c.topic < len(topics) else 'seçilmiş test'}
    for k in ([ti, *[x for x in range(len(topics)) if x != ti]] if templates else []):
        t_, sec = topics[k]
        for t in sorted(T.matching(stems(t_) | stems(sec or '')), key=lambda t: (t.level != slot['level'], rng.random())):
            for _ in range(60):
                q = T.instance(t, rng) if slot['kind'] == 'open' else T.mcq_instance(t, rng)
                if q and q['key'] not in exclude and norm_text(q['text']) not in exclude:
                    return {**q, 'card_answer': q.get('answer'), 'level_actual': q['level'], 'topic_actual': t_, 'v': RULES_V}
    return None


def capacity(cands: list[Cand], n: int, mcq_only: bool = False) -> tuple[bool, dict]:
    """Bir şagirdin variantı ümumiyyətlə dolurmu (növ üzrə fərqli sual sayı ≥ slot sayı)? Tez yoxlama – generasiyasız."""
    plan = slots(n, mcq_only)
    need = {k: sum(s['kind'] == k for s in plan) for k in ('mcq', 'open')}
    have = {k: len({c.key for c in cands if c.kind == k}) for k in ('mcq', 'open')}
    return all(have[k] >= need[k] for k in need), {'need': need, 'have': have}


def max_n(cands: list[Cand], upto: int, mcq_only: bool = False) -> int | None:
    """Hovuzun imkan verdiyi ən böyük sual sayı (generasiyasız)."""
    return next((k for k in range(min(upto, N_MAX), N_MIN - 1, -1) if capacity(cands, k, mcq_only)[0]), None)


def generate_auto(students: list[int], topics, cands, history, seed: int, n: int = 30, others: set[str] | None = None,
                  max_share: int | None = None, mcq_only: bool = False) -> tuple[dict[int, list[dict]], int]:
    """Ən az təkrarla variantlar (istifadəçi qaydası 13.10): əvvəl hər şagirdə fərqli; bank çatmırsa sistem özü
    «bir sual ən çox k şagirdə» həddini seçir (ən kiçik mümkün k). Şagirdin öz variantında təkrar heç vaxt yoxdur.
    Şablon sualı yoxdur. k hovuzun ölçüsündən hesablanır, sonra cəmi bir neçə generasiya (pulsuz server zəifdir)."""
    import math
    fits, info = capacity(cands, n, mcq_only)
    if not fits:
        raise Shortage([{'slot': 0, 'kind': k, 'level': '—', 'missing': info['need'][k] - info['have'][k]}
                        for k in info['need'] if info['have'][k] < info['need'][k]])
    k0 = max(1, *(math.ceil(len(students) * info['need'][k] / max(1, info['have'][k])) for k in info['need']))
    top = max(1, max_share or len(students))
    lo, hi, best, last = min(k0, top), top, None, None
    # ən kiçik işləyən k – ikili axtarış (hər generasiya ~0,1 s)
    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            best = (generate(students, topics, cands, history, seed=seed, n=n, others=others, share=mid, mcq_only=mcq_only), mid)
            hi = mid - 1
        except Shortage as sh:
            last = sh
            lo = mid + 1
    if best:
        return best
    raise last or Shortage([])


def fairness(variants: dict[int, list[dict]]) -> dict:
    """Ədalət hesabatı: slotun hədəf çətinliyinə dəqiq uyğun sualların payı, mövzu əvəzlənməsi, şablon sayı."""
    qs = [q for v in variants.values() for q in v]
    n = len(qs) or 1
    return {'questions': len(qs), 'unique': len({q.get('key') or id(q) for q in qs}),
            'exact_level_pct': round(100 * sum(q.get('level_actual', q.get('level')) == q.get('level') for q in qs) / n, 1),
            'same_topic_pct': round(100 * sum(q.get('topic_actual') == q.get('topic') for q in qs) / n, 1),
            'templates': sum(q.get('template') is not None for q in qs),
            'open_pct': round(100 * sum(q['kind'] == 'open' for q in qs) / n, 1)}
