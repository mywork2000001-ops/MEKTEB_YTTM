"""Səviyyə qrupları (Zəif / Orta / Güclü) – fənn üzrə, sinif daxilində virtual qrup (ayrıca jurnal yaranmır).

Bölgü balı (0–100) komponentlərin çəkili ortasıdır; olmayan komponent çıxarılır, çəkilər yenidən normallaşdırılır:
- buraxilis  – IX sinif buraxılış balı (yalnız X–XI siniflər; fənnə uyğun: riyaziyyat / dil / xarici dil);
- sinaq      – sınaq imtahanlarının orta faizi (bu dərs üzrə);
- reytinq    – fənn reytinqi (analitika: formativ + KSQ + ev tapşırığı + davamiyyət);
- diaqnostik – ilin əvvəlindəki diaqnostik test (bankda «diaqnostik» fayllardan qurulmuş onlayn test).
İlin əvvəlində yalnız buraxılış balı olur – bölgü ona görə qurulur; nəticələr yığıldıqca çəkilər özü dəyişir.

Bölgü: sabit həddlər (≥70 güclü, 40–69,9 orta, <40 zəif – mövcud LEVEL_HIGH/LEVEL_MID) və ya «üçdəbir».
Sonrakı dəyişikliklər yalnız TƏKLİFDİR (histerezis: hədddən ən azı 5 bal o tərəfə keçəndə)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import LEVEL_HIGH, LEVEL_MID
from .models import BankFile, BankQuestion, LevelOverride, OnlineTask, TaskAttempt
from .services import PlanCtx, class_grade, ix_score, roster

LEVELS = ('Zəif', 'Orta', 'Güclü')
WEIGHTS = {'buraxilis': 30, 'sinaq': 40, 'reytinq': 30, 'diaqnostik': 30}
LABELS = {'buraxilis': 'IX buraxılış balı', 'sinaq': 'sınaq ortası', 'reytinq': 'fənn reytinqi', 'diaqnostik': 'diaqnostik test'}
HYSTERESIS = 5.0
MIN_GROUP = 3


def _task_pcts(db: Session, tasks: list[OnlineTask]) -> dict[int, list[float]]:
    out: dict[int, list[float]] = {}
    if not tasks:
        return out
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_([t.id for t in tasks]),
                                                  TaskAttempt.submitted_at.is_not(None))):
        if a.total:
            out.setdefault(a.student_id, []).append(a.correct * 100 / a.total)
    return out


def _diagnostic_tasks(db: Session, tasks: list[OnlineTask]) -> list[OnlineTask]:
    """Sualların əksəriyyəti bankın «diaqnostik» fayllarındandırsa – diaqnostik test."""
    ids = {q.get('bank_id') for t in tasks for q in t.questions if q.get('bank_id')}
    if not ids:
        return []
    diag = set(db.scalars(select(BankQuestion.id).join(BankFile).where(BankQuestion.id.in_(ids),
                                                                       BankFile.kind == 'diaqnostik')))
    return [t for t in tasks if sum(q.get('bank_id') in diag for q in t.questions) * 2 > len(t.questions)]


def components(db: Session, ctx: PlanCtx) -> dict[int, dict[str, float | None]]:
    from .analytics import Period, analyze
    studs = roster(db, ctx.ta)
    grade = class_grade(db, ctx.cls)
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ctx.ta.id)))
    sinaq = _task_pcts(db, [t for t in tasks if t.kind == 'sinaq'])
    diag = _task_pcts(db, _diagnostic_tasks(db, [t for t in tasks if t.kind != 'sinaq']))
    rating = {r['student_id']: r['rating'] for r in analyze(db, ctx, Period(ctx.year.start, ctx.year.end), links=False)['students']}
    out = {}
    for s in studs:
        avg = lambda v: round(sum(v) / len(v), 1) if v else None
        out[s.id] = {'buraxilis': ix_score(s, ctx.ta.subject, grade),
                     'sinaq': avg(sinaq.get(s.id)), 'reytinq': rating.get(s.id), 'diaqnostik': avg(diag.get(s.id))}
    return out


def blend(c: dict[str, float | None], w: dict[str, float]) -> float | None:
    got = [(c[k], w.get(k, 0)) for k in c if c[k] is not None and w.get(k, 0) > 0]
    tot = sum(x for _, x in got)
    return round(sum(v * x for v, x in got) / tot, 1) if tot else None


def by_threshold(score: float | None) -> str | None:
    if score is None:
        return None
    return 'Güclü' if score >= LEVEL_HIGH else 'Orta' if score >= LEVEL_MID else 'Zəif'


def by_tercile(scores: dict[int, float | None]) -> dict[int, str | None]:
    """Üçdəbir: balı olanlar sıralanır və üç bərabər hissəyə bölünür (hər qrupda ən azı MIN_GROUP – mümkündürsə)."""
    have = sorted([(v, k) for k, v in scores.items() if v is not None])
    n = len(have)
    out: dict[int, str | None] = {k: None for k in scores}
    if not n:
        return out
    if n < MIN_GROUP * 3:
        for v, k in have:
            out[k] = by_threshold(v)
        return out
    a, b = n // 3, n - n // 3
    for i, (_, k) in enumerate(have):
        out[k] = 'Zəif' if i < a else 'Orta' if i < b else 'Güclü'
    return out


def preview(db: Session, ctx: PlanCtx, mode: str = 'fixed', weights: dict[str, float] | None = None) -> dict:
    w = {**WEIGHTS, **(weights or {})}
    comps = components(db, ctx)
    scores = {sid: blend(c, w) for sid, c in comps.items()}
    proposed = by_tercile(scores) if mode == 'tercile' else {sid: by_threshold(v) for sid, v in scores.items()}
    cur = {o.student_id: o for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == ctx.ta.id))}
    rows = []
    for s in roster(db, ctx.ta):
        o = cur.get(s.id)
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'components': comps[s.id], 'score': scores[s.id],
                     'proposed': proposed[s.id], 'current': o.level if o else None,
                     'current_source': o.source if o else None, 'locked': bool(o and o.locked),
                     'change': bool(proposed[s.id]) and (o is None or o.level != proposed[s.id]) and not (o and o.locked)})
    used = {k: sum(1 for c in comps.values() if c[k] is not None) for k in WEIGHTS}
    return {'mode': mode, 'weights': w, 'labels': LABELS, 'used': used, 'rows': rows,
            'counts': {k: sum(r['proposed'] == k for r in rows) for k in LEVELS}}


def suggestions(db: Session, ctx: PlanCtx) -> list[dict]:
    """Köçürmə təklifləri – yalnız bölgüdən (kilidsiz) olanlar və hədddən ən azı HYSTERESIS bal o tərəfə keçəndə."""
    comps = components(db, ctx)
    names = {s.id: s.full_name for s in roster(db, ctx.ta)}
    out = []
    for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == ctx.ta.id)):
        if o.locked or o.student_id not in comps:
            continue
        sc = blend(comps[o.student_id], WEIGHTS)
        if sc is None:
            continue
        new = None
        if o.level != 'Güclü' and sc >= LEVEL_HIGH + HYSTERESIS:
            new = 'Güclü'
        elif o.level == 'Zəif' and sc >= LEVEL_MID + HYSTERESIS:
            new = 'Orta'
        elif o.level != 'Zəif' and sc < LEVEL_MID - HYSTERESIS:
            new = 'Zəif'
        elif o.level == 'Güclü' and sc < LEVEL_HIGH - HYSTERESIS:
            new = 'Orta'
        if new:
            out.append({'student_id': o.student_id, 'full_name': names[o.student_id], 'current': o.level, 'proposed': new,
                        'score': sc, 'old_score': o.score, 'components': comps[o.student_id]})
    return sorted(out, key=lambda x: x['full_name'])

