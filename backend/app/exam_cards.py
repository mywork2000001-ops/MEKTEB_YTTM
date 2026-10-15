"""KSQ/BSQ şagirdin cavab kartı (nəticə göndərildikdən sonra): hər sual üçün mətn, şagirdin cavabı, düzgün cavab, bal – onlayn və
kağız ayrıca, jurnala gedən yekun. Portal (öz kartı) və müəllimin çap səhifəsi eyni quruluşu işlədir."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import grade_from_points
from .models import BankQuestion, Exam, ExamScan, ExamScore, ExamVariant


def exam_card(db: Session, e: Exam, sid: int) -> dict | None:
    """{questions: [{slot, kind, text, options, key, points, explanation}], sources: {online|paper: {...}}, final: {...}}.
    Variantı yoxdursa – None. Mənbədə qiymətləndirilmiş skan yoxdursa o mənbə düşmür."""
    from .domain.ksq_card import key_value
    v = db.get(ExamVariant, (e.id, sid))
    if v is None:
        return None
    from .appeals import ref_of
    qs = sorted(v.questions, key=lambda q: q['slot'])
    expl = {b.id: b.explanation for b in db.scalars(select(BankQuestion).where(BankQuestion.id.in_([q['bank_id'] for q in qs if q.get('bank_id')] or [0])))}
    questions = [{'slot': q['slot'], 'kind': q['kind'], 'text': q.get('text'), 'options': q.get('options') if q['kind'] == 'mcq' else None,
                  'image': q.get('image'), 'key': key_value(q), 'points': q['points'], 'explanation': expl.get(q.get('bank_id')),
                  'ref': (ref_of(db, q) or {}).get('text')} for q in qs]
    annulled = {it['n'] for it in (e.items or []) if it.get('annulled')}
    sources = {}
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == sid, ExamScan.status == 'graded')):
        read = {int(r['slot']): r.get('value') for r in sc.reading or [] if r.get('slot') is not None}
        void = annulled | set(sc.lost or [])                         # «sayılmadı»: ləğv olunmuş və ya vərəqdə olmayan sual
        marks = sc.marks or [0] * len(qs)
        answers = {q['slot']: {'value': read.get(q['slot']) or '', 'ok': None if q['slot'] in void else bool(m), 'void': q['slot'] in void,
                               'earned': None if q['slot'] in void else (q['points'] if m else 0)} for q, m in zip(qs, marks)}
        sources[sc.source] = {'scan_id': sc.id, 'image': bool(sc.crop_key), 'points': sc.points,
                              'grade': grade_from_points(sc.points, e.max_points) if sc.points is not None else None, 'answers': answers}
    score = db.get(ExamScore, (e.id, sid))
    final = {'points': score.points if score and not score.absent else None, 'chosen': score.chosen if score else None,
             'grade': grade_from_points(score.points, e.max_points) if score and score.points is not None and not score.absent else None}
    return {'exam': {'id': e.id, 'kind': e.kind, 'no': e.no, 'extra_seq': e.extra_seq or 0, 'semester': e.semester, 'date': e.date,
                     'max_points': e.max_points}, 'code': v.code, 'questions': questions, 'sources': sources, 'final': final}
