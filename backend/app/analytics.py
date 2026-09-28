"""Analitika: şagird göstəriciləri, reytinq və irəliləyiş, cari səviyyə (güclü/orta/zəif – nəticələrə görə
avtomatik), risk (izahlı), davamiyyət xəritəsi və 25%+ xəbərdarlığı. Bir dərs bağlılığı (müəllim + sinif/qrup) üzrə."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import (ABSENCE_WARN_PCT, RiskInput, absence_warning, grade_from_points, level, rank,
                           rating_score, risk_score)
from .models import Attendance, Exam, ExamScore, HomeworkCheck, JournalEntry, Mark, TaskAttempt, OnlineTask
from .services import PlanCtx, roster

HW_W = {'etdi': 1.0, 'qismən': 0.5, 'etmədi': 0.0, 'köçürüb': 0.0}
LEVEL_NAMES = {'Yüksək': 'Güclü', 'Orta': 'Orta', 'Zəif': 'Zəif'}


@dataclass
class Period:
    a: dt.date
    b: dt.date


def _avg(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def _collect(db: Session, ta_id: int, p: Period):
    entries = {e.id: e for e in db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id == ta_id, JournalEntry.date >= p.a, JournalEntry.date <= p.b))}
    ids = list(entries)
    marks = list(db.scalars(select(Mark).where(Mark.entry_id.in_(ids))))
    att = list(db.scalars(select(Attendance).where(Attendance.entry_id.in_(ids))))
    hw = list(db.scalars(select(HomeworkCheck).where(HomeworkCheck.entry_id.in_(ids))))
    exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta_id, Exam.date >= p.a, Exam.date <= p.b)
                            .order_by(Exam.date)))
    scores = list(db.scalars(select(ExamScore).where(ExamScore.exam_id.in_([e.id for e in exams]))))
    tasks = [t.id for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta_id))]
    attempts = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_(tasks),
                                                                TaskAttempt.submitted_at.is_not(None)))
                if p.a <= a.submitted_at.date() <= p.b]
    return entries, marks, att, hw, exams, scores, attempts


def _metrics(sid: int, entries, marks, att, hw, exams, scores, attempts) -> dict:
    ex_by = {e.id: e for e in exams}
    my_marks = sorted((m for m in marks if m.student_id == sid), key=lambda m: (entries[m.entry_id].date,
                                                                                  entries[m.entry_id].period))
    grades = [m.grade for m in my_marks]
    tests = [m for m in my_marks if m.kind == 'test']
    a = [x.status for x in att if x.student_id == sid]
    missed = sum(s in ('yox', 'üzrlü') for s in a)
    h = [HW_W[x.status] for x in hw if x.student_id == sid]
    ksq = sorted(((ex_by[s.exam_id], s) for s in scores
                  if s.student_id == sid and ex_by[s.exam_id].kind == 'KSQ' and s.points is not None and not s.absent),
                 key=lambda x: x[0].date)
    ksq_pct = [round(s.points * 100 / e.max_points, 1) for e, s in ksq]
    online = [round(x.correct * 100 / x.total, 1) for x in attempts if x.student_id == sid and x.total]
    homework_pct = round(sum(h) * 100 / len(h), 1) if h else None
    attendance_pct = round((len(a) - missed) * 100 / len(a), 1) if a else None
    avg_grade = _avg(grades)
    return {
        'avg_grade': avg_grade, 'marks': len(grades), 'last_marks': grades[-5:],
        'test_pct': round(sum(m.test_correct for m in tests) * 100 / sum(m.test_total for m in tests), 1) if tests else None,
        'ksq_avg_pct': _avg(ksq_pct), 'last_ksq_pct': ksq_pct[-1] if ksq_pct else None,
        'ksq_grades': [grade_from_points(s.points, e.max_points) for e, s in ksq],
        'online_pct': _avg(online), 'online_count': len(online),
        'homework_pct': homework_pct, 'lessons': len(a), 'missed': missed, 'attendance_pct': attendance_pct,
        'absence_warning': absence_warning(missed, len(a)),
        'rating': rating_score(avg_grade, _avg(ksq_pct), homework_pct, attendance_pct),
    }


def analyze(db: Session, ctx: PlanCtx, p: Period) -> dict:
    studs = roster(db, ctx.ta)
    data = _collect(db, ctx.ta.id, p)
    mid = p.a + (p.b - p.a) / 2
    first = _collect(db, ctx.ta.id, Period(p.a, mid))
    second = _collect(db, ctx.ta.id, Period(mid + dt.timedelta(days=1), p.b))
    rows = []
    for s in studs:
        m = _metrics(s.id, *data)
        r1, r2 = _metrics(s.id, *first)['rating'], _metrics(s.id, *second)['rating']
        risk = risk_score(RiskInput(ix_math=s.score_math, last_formative=m['last_marks'], last_ksq_pct=m['last_ksq_pct'],
                                    attendance_pct=m['attendance_pct'], homework_pct=m['homework_pct']))
        base = level(s.score_math)
        cur = level(m['rating']) if m['rating'] is not None else base
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'portal_code': s.portal_code,
                     'ix_math': s.score_math, 'baseline_level': LEVEL_NAMES.get(base), 'level': LEVEL_NAMES.get(cur),
                     'level_source': 'nəticələr' if m['rating'] is not None else 'IX sinif balı',
                     'progress': round(r2 - r1, 1) if r1 is not None and r2 is not None else None,
                     'risk': {'score': risk.score, 'status': risk.status, 'factors': risk.factors}, **m})
    places = {k: pl for k, _, pl in rank([(r['student_id'], r['rating']) for r in rows])}
    prog = {k: pl for k, _, pl in rank([(r['student_id'], r['progress']) for r in rows])}
    for r in rows:
        r['place'], r['progress_place'] = places[r['student_id']], prog[r['student_id']]
    rows.sort(key=lambda r: (r['place'] is None, r['place'] or 0, r['full_name']))
    grades = [g for g in (m.grade for m in data[1])]
    return {
        'from': p.a, 'to': p.b, 'class_name': ctx.cls.name, 'subject': ctx.ta.subject,
        'lessons_written': len(data[0]), 'students': rows,
        'overview': {
            'students': len(rows), 'avg_grade': _avg(grades),
            'distribution': {g: grades.count(g) for g in (5, 4, 3, 2)},
            'avg_attendance': _avg([r['attendance_pct'] for r in rows]),
            'avg_homework': _avg([r['homework_pct'] for r in rows]),
            'avg_ksq_pct': _avg([r['ksq_avg_pct'] for r in rows]),
            'levels': {k: sum(r['level'] == k for r in rows) for k in ('Güclü', 'Orta', 'Zəif')},
            'risk': {k: sum(r['risk']['status'] == k for r in rows) for k in ('Qırmızı', 'Sarı', 'Yaşıl')},
            'absence_warnings': sum(r['absence_warning'] for r in rows), 'absence_limit_pct': ABSENCE_WARN_PCT,
        },
    }


def attendance_map(db: Session, ctx: PlanCtx, p: Period) -> dict:
    """İstilik xəritəsi: sətir – şagird, sütun – yazılmış dərs (tarix, saat)."""
    entries = list(db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id == ctx.ta.id, JournalEntry.date >= p.a, JournalEntry.date <= p.b)
        .order_by(JournalEntry.date, JournalEntry.period)))
    att = {(x.entry_id, x.student_id): x.status for x in db.scalars(
        select(Attendance).where(Attendance.entry_id.in_([e.id for e in entries])))}
    rows = []
    for s in roster(db, ctx.ta):
        cells = [att.get((e.id, s.id)) for e in entries]
        known = [c for c in cells if c]
        missed = sum(c in ('yox', 'üzrlü') for c in known)
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'cells': cells, 'missed': missed,
                     'unexcused': cells.count('yox'), 'late': cells.count('gecikdi'),
                     'missed_pct': round(missed * 100 / len(known), 1) if known else None,
                     'warning': absence_warning(missed, len(known))})
    return {'columns': [{'date': e.date, 'period': e.period} for e in entries], 'rows': rows,
            'limit_pct': ABSENCE_WARN_PCT}
