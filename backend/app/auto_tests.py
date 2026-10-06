"""Hər plan dərsinə avtomatik mövzu testi (sinif/qrupda «auto_tests» açıqdırsa).

Dərs günü (işçi plana görə) həmin dərsin mövzusuna test yaradılır – müəllimin əl ilə açdığı «🧪 Test» ilə eyni:
açılır dərsin sonunda, bağlanır ertəsi gün 22:00, 20 dəqiqə, sualların sırası qarışıq, cavablar bağlanandan sonra,
nəticə formativ jurnala. Suallar: «Test toplusu» dərsi – P007 (dərsin S/E/M aralığı), X–XI – P0010 (müəllimin seçdiyi
və ya mövzuya ən uyğun fayl, ən çoxu 15 sual). Sualı olmayan, KSQ/BSQ və artıq testi olan dərsə yaradılmır."""
from __future__ import annotations

import datetime as dt
import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OnlineTask, SchoolClass, TeachingAssignment, TestBatch, User, now
from .services import class_grade, plan_ctx, today

log = logging.getLogger('auto_tests')


def _questions(db: Session, ta: TeachingAssignment, teacher: User, pl) -> tuple[list[dict], str] | None:
    from .api.programs import _toplu_src, toplu_lesson, toplu_questions
    from .api.topic_tests import p0010_for_topic
    try:
        if toplu_lesson(pl, _toplu_src()):
            r = toplu_questions(lesson_id=pl.id, scope='lesson', n=15, user=teacher, db=db)
        elif class_grade(db, db.get(SchoolClass, ta.class_id)) in (10, 11):
            r = p0010_for_topic(ta_id=ta.id, pl_id=pl.id, file_id=None, n=15, user=teacher, db=db)
        else:
            return None
    except HTTPException:
        return None
    qs = [{k: v for k, v in q.items() if k != 'qid'} for q in r.get('questions') or []]
    return (qs, r.get('title') or f'№{pl.seq} {pl.topic} – mövzu testi') if qs else None


def run(db: Session, day: dt.date | None = None) -> int:
    from .api.topic_tests import TZ, _has_test, _lesson_end
    from .api.common import audit
    d = day or today()
    made = 0
    for ta in db.scalars(select(TeachingAssignment).where(TeachingAssignment.auto_tests.is_(True),
                                                          TeachingAssignment.archived_at.is_(None))):
        teacher = db.get(User, ta.teacher_id)
        ctx = plan_ctx(db, ta)
        for s in [x for x in ctx.slots if x.date == d]:
            pl = ctx.lesson_for(s)
            if pl is None or pl.assessment_type in ('KSQ', 'BSQ') or _has_test(db, pl.id):
                continue
            got = _questions(db, ta, teacher, pl)
            if not got:
                continue
            qs, title = got
            o = _lesson_end(db, ctx.cls, s.date, s.period, ta).astimezone(dt.timezone.utc)
            c = dt.datetime.combine(s.date + dt.timedelta(days=1), dt.time(22, 0), tzinfo=TZ)
            batch = TestBatch(kind='movzu', title=title[:200], subject=ta.subject, grade=class_grade(db, ctx.cls),
                              created_by=teacher.id)
            db.add(batch)
            db.flush()
            t = OnlineTask(assignment_id=ta.id, title=title[:200], description='Avtomatik mövzu testi (perspektiv plan)',
                           opens_at=o, closes_at=c.astimezone(dt.timezone.utc), duration_min=20, questions=qs, shuffle=True,
                           show_answers='after_close', student_ids=None, created_by=teacher.id, kind='movzu',
                           batch_id=batch.id, plan_lesson_id=pl.id, journal_auto=True)
            db.add(t)
            db.flush()
            audit(db, teacher, 'create', 'task', t.id, kind='movzu', auto=True, plan_seq=pl.seq, questions=len(qs))
            made += 1
        db.commit()
    return made
