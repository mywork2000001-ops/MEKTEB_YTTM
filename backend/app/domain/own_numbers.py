"""«Hər şagirdə öz rəqəmləri»: eyni suallar, fərqli ədədlər (docs/yazili-testler-master-promtu.md, addım 5).

Nüvə: own_numbers_gen (generator) + own_numbers_auto (süni intellektsiz avtomatik şablon). DB-yə toxunmur, LLM yoxdur, sympy ilə.
Nəticə ExamVariant.questions-da DONUR (açar, skan, apelyasiya, çap – dəyişməz): hər şagirdin sualında dəyişən sahələr
(text, options, correct, answer) və bayraqlar: own_numbers (True/False), own_params, own_src (mənbə – retake üçün), own_reason (niyə dəyişmir).
Limit (Render free, 512 MB): bir sual ≤ 2 san., bütün sinif ≤ 30 san.; aşsa sual dəyişmir (hesabatda səbəb)."""
from __future__ import annotations

import copy
import re
import time

from . import own_numbers_auto as au
from . import own_numbers_gen as gen

PER_Q = 2.0
TOTAL = 30.0
SRC_KEYS = ('kind', 'text', 'options', 'correct', 'answer', 'image')
OWN_KEYS = ('own_numbers', 'own_params', 'own_src', 'own_reason')


def _bank_like(q: dict) -> dict:
    return {'kind': q.get('kind'), 'text': q.get('text'), 'options': q.get('options'), 'correct': q.get('correct'),
            'answer': q.get('answer'), 'points': q.get('points', 1), 'image': q.get('image')}


def _fixed(q: dict, reason: str) -> dict:
    out = copy.deepcopy(q)
    out['own_numbers'] = False
    out['own_reason'] = reason
    return out


def _all_fixed(src: list[dict], students: list, reason: str):
    res = {sid: [_fixed(q, reason) for q in src] for sid in students}
    rep = [{'no': i + 1, 'method': 'fixed', 'detail': reason} for i in range(len(src))]
    return res, _summary(src, rep)


def _summary(src: list[dict], rep: list[dict]) -> dict:
    items = [{'slot': q.get('slot', i + 1), 'changed': r['method'] != 'fixed',
              'reason': r['detail'] if r['method'] == 'fixed' else None} for i, (q, r) in enumerate(zip(src, rep))]
    n = sum(x['changed'] for x in items)
    return {'changed': n, 'fixed': len(items) - n, 'items': items}


def apply(questions: list[dict], students: list, exam_code: str, *, salt: str = '', pool: int | None = None,
          per_q: float = PER_Q, total: float = TOTAL) -> tuple[dict, dict]:
    """questions – ExamVariant.questions formatında ortaq sual siyahısı; students – şagird id-ləri.
    Qaytarır ({sid: suallar}, hesabat {changed, fixed, items:[{slot, changed, reason}]}).
    Seed = exam_code + salt + şagird + sual yeri (deterministik); sinifdə hər sualın ədəd dəsti təkrarsızdır.
    Uyğun olmayan (şəkilli, açar uyğunsuz, naməlum tipi, vaxt limiti) sual dəyişmir. Sual sırası və seçim sırası bəlli qalır
    (sabit suallar yerində, ədədi dəyişən test sualında variantların yeri şagirdə görə qarışır)."""
    src = [copy.deepcopy(q) for q in questions]
    students = list(students)
    if not src or not students:
        return {sid: copy.deepcopy(src) for sid in students}, _summary(src, [{'method': 'fixed', 'detail': ''}] * len(src))
    t_end = time.monotonic() + total
    n = max(len(students), pool or 0)
    code = f'{exam_code}{salt}'
    bank = [_bank_like(q) for q in src]
    tq, rep = [], []
    for i, (q, b) in enumerate(zip(src, bank), 1):
        t0 = time.monotonic()
        try:
            if time.monotonic() > t_end:
                raise au.Unsup('bütün sinif üçün vaxt limiti')
            if q.get('kind') not in ('mcq', 'open'):
                raise au.Unsup('əl ilə bal sualı')
            t, (meth, desc) = au.auto_question(b, n)
            if time.monotonic() - t0 > per_q:
                raise au.Unsup(f'hesab vaxtı limiti ({per_q:g} san)')
            tq.append(t)
            rep.append({'no': i, 'method': meth, 'detail': desc})
        except au.Unsup as e:
            tq.append(au.fixed_question(b))
            rep.append({'no': i, 'method': 'fixed', 'detail': str(e)})
        except Exception:                                   # sympy/təhlil gözlənilməz xətası – sual dəyişmir, iş dayanmır
            tq.append(au.fixed_question(b))
            rep.append({'no': i, 'method': 'fixed', 'detail': 'hesablama xətası'})
    if all(r['method'] == 'fixed' for r in rep):
        return _fixed_with_reasons(src, students, rep)
    tpl = {'code': code, 'title': {lg: code for lg in gen.LANGS}, 'questions': tq}
    try:
        built = au.clean_built(au.build_safe(bank, tpl, [(sid, '') for sid in students], code, rep,
                                             shuffle_fixed=False, per_q_limit=per_q, deadline=t_end))
    except gen.TimeLimit:
        return _all_fixed(src, students, 'bütün sinif üçün vaxt limiti (30 san) aşıldı')
    except gen.TemplateError as e:
        return _all_fixed(src, students, str(e))
    res = {}
    for st in built:
        out = []
        for q, r, it in zip(src, rep, st['questions']):
            if r['method'] == 'fixed':
                out.append(_fixed(q, r['detail']))
                continue
            x = copy.deepcopy(q)
            x['text'] = it['text']
            if q['kind'] == 'mcq':
                x['options'], x['correct'], x['answer'] = it['options'], it['correct'], None
            else:
                x['answer'] = it['answer']
            x.pop('explanation', None)
            x['own_numbers'] = True
            x['own_params'] = it.get('params') or {}
            x['own_src'] = {k: copy.deepcopy(q.get(k)) for k in SRC_KEYS}
            out.append(x)
        res[st['id']] = out
    return res, _summary(src, rep)


def _fixed_with_reasons(src, students, rep):
    res = {sid: [_fixed(q, r['detail']) for q, r in zip(src, rep)] for sid in students}
    return res, _summary(src, rep)


def report_of(questions: list[dict]) -> dict | None:
    """Donmuş variantdan hesabat (DB-də ayrıca saxlanmır). Rejim işləməyibsə – None."""
    if not any('own_numbers' in q for q in questions):
        return None
    items = [{'slot': q.get('slot'), 'changed': bool(q.get('own_numbers')), 'reason': None if q.get('own_numbers') else q.get('own_reason')}
             for q in sorted(questions, key=lambda q: q.get('slot') or 0)]
    n = sum(x['changed'] for x in items)
    return {'changed': n, 'fixed': len(items) - n, 'items': items}


def is_own_mode(questions: list[dict]) -> bool:
    return any('own_numbers' in q for q in questions)


def renew(question: dict, exam_code: str, student_id, avoid: set[str], *, start: int = 1, pool: int | None = None) -> dict | None:
    """Retake: ədədi dəyişən (own_numbers) sualın yeni ədədləri (seed-ə R1/R2… əlavə). avoid – sinifdə artıq olan own_params imzaları
    (sig_of). Yeni ədəd tapılmasa – None (sual dəyişmir)."""
    s = question.get('own_src')
    if not question.get('own_numbers') or not s:
        return None
    base = {k: copy.deepcopy(v) for k, v in question.items() if k not in OWN_KEYS and k not in SRC_KEYS}
    base.update(copy.deepcopy(s))
    for k in range(start, start + 8):
        res, _ = apply([base], [student_id], exam_code, salt=f'R{k}', pool=pool)
        new = res[student_id][0]
        if new.get('own_numbers') and sig_of(new) not in avoid:
            return new
    return None


def sig_of(q: dict) -> str:
    return repr(sorted((q.get('own_params') or {}).items()))


def next_salt(code: str) -> int:
    m = re.search(r'R(\d+)$', code or '')
    return int(m.group(1)) + 1 if m else 1
