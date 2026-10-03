"""Analitika: şagird göstəriciləri, reytinq və irəliləyiş, cari səviyyə (güclü/orta/zəif – nəticələrə görə
avtomatik), risk (izahlı), davamiyyət xəritəsi və 25%+ xəbərdarlığı. Bir dərs bağlılığı (müəllim + sinif/qrup) üzrə.

Əlaqələr: sınaq imtahanları (ayrıca blok, reytinqə qarışmır, riskdə amil), əlavə məşğələ (kursa yazılıb / davamiyyət),
bütün dərslər üzrə davamiyyət (sinif rəhbərinin birləşmiş qeydi – yalnız bütöv sinif şagirdləri üçün)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import (ABSENCE_WARN_PCT, RiskInput, absence_warning, grade_from_points, level, rank,
                           rating_score, risk_score)
from .models import (Attendance, Exam, ExamScore, HomeworkCheck, JournalEntry, LevelOverride, Mark, OnlineTask,
                     TaskAttempt)
from .services import IX_LABELS, SCHOOL_TZ, PlanCtx, class_grade, ix_kind, ix_score, roster, today

HW_W = {'etdi': 1.0, 'qismən': 0.5, 'etmədi': 0.0, 'köçürüb': 0.0}
LEVEL_NAMES = {'Yüksək': 'Güclü', 'Orta': 'Orta', 'Zəif': 'Zəif'}
MIN_PROGRESS_DAYS = 4          # irəliləyiş üçün dövrdə ən azı neçə nəticə günü olmalıdır (hər yarıda 2)


@dataclass
class Period:
    a: dt.date
    b: dt.date


def _avg(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def _local_date(t: dt.datetime) -> dt.date:
    """Bakı vaxtı ilə tarix (gecə 00:00–04:00 təhvil verilən test əvvəlki günə düşməsin)."""
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(ZoneInfo(SCHOOL_TZ)).date()


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
    tasks = [t.id for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta_id,   # sınaq – ayrıca blokda
                                                               (OnlineTask.kind.is_(None)) | (OnlineTask.kind != 'sinaq')))]
    attempts = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_(tasks),
                                                                TaskAttempt.submitted_at.is_not(None)))
                if p.a <= _local_date(a.submitted_at) <= p.b]
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


def _halves(data, p: Period) -> tuple[Period, Period] | None:
    """İrəliləyiş: dövrü TƏQVİM ortasından deyil, faktiki nəticə günlərinin ortasından böl (ilin əvvəlində də işləsin).
    Nəticə günü – qiymət yazılmış dərs və ya KSQ/BSQ günü; bu gündən sonrakı günlər nəzərə alınmır."""
    entries, marks, _att, _hw, exams, scores, _att2 = data
    end = min(p.b, today())
    marked = {m.entry_id for m in marks}
    days = sorted({e.date for e in entries.values() if e.id in marked and e.date <= end} |
                  {e.date for e in exams if e.date <= end and any(s.exam_id == e.id for s in scores)})
    if len(days) < MIN_PROGRESS_DAYS:
        return None
    mid = days[len(days) // 2 - 1]
    return Period(p.a, mid), Period(mid + dt.timedelta(days=1), end)


def _sub(data, p: Period):
    """Toplanmış məlumatdan alt dövr (təkrar sorğu yox)."""
    entries, marks, att, hw, exams, scores, attempts = data
    ent = {k: e for k, e in entries.items() if p.a <= e.date <= p.b}
    ex = [e for e in exams if p.a <= e.date <= p.b]
    exid = {e.id for e in ex}
    return (ent, [m for m in marks if m.entry_id in ent], [x for x in att if x.entry_id in ent],
            [x for x in hw if x.entry_id in ent], ex, [s for s in scores if s.exam_id in exid],
            [a for a in attempts if p.a <= _local_date(a.submitted_at) <= p.b])


def _extra(db: Session, ta_id: int, sids: set[int], p: Period) -> dict[int, dict]:
    """Əlavə məşğələ: bu dərsə bağlı kurslara yazılıb-yazılmadığı və keçirilən məşğələlərdə davamiyyət."""
    from .api.extra import members
    from .models import ExtraAttendance, ExtraCourse, ExtraSession
    out: dict[int, dict] = {}
    for c in db.scalars(select(ExtraCourse).where(ExtraCourse.archived_at.is_(None))):
        if ta_id not in ((c.audience or {}).get('ta_ids') or []):
            continue
        mem = {s.id for s, _ in members(db, c)} & sids
        if not mem:
            continue
        held = [s.id for s in db.scalars(select(ExtraSession).where(
            ExtraSession.course_id == c.id, ExtraSession.status == 'held', ExtraSession.date >= p.a, ExtraSession.date <= p.b))]
        att = {(x.session_id, x.student_id): x.status for x in db.scalars(
            select(ExtraAttendance).where(ExtraAttendance.session_id.in_(held)))} if held else {}
        for sid in mem:
            o = out.setdefault(sid, {'courses': [], 'held': 0, 'present': 0})
            o['courses'].append(c.title)
            o['held'] += len(held)
            o['present'] += sum(att.get((h, sid)) in ('var', 'gecikdi') for h in held)
    for o in out.values():
        o['attendance_pct'] = round(o['present'] * 100 / o['held'], 1) if o['held'] else None
    return out


def _all_lessons_attendance(db: Session, ctx: PlanCtx, studs, p: Period) -> dict[int, float | None]:
    """Bütün dərslər üzrə davamiyyət % (sinif rəhbərinin birləşmiş qeydi) – şagirdin öz sinfi üzrə."""
    from .api.homeroom_att import merged, student_stats
    from .models import SchoolClass
    out: dict[int, float | None] = {}
    by_cls: dict[int, list[int]] = {}
    for s in studs:
        by_cls.setdefault(s.class_id, []).append(s.id)
    for cid, sids in by_cls.items():
        c = db.get(SchoolClass, cid)
        if not c or c.kind == 'qrup':
            continue
        try:
            days, rec = merged(db, c, p.a, p.b)
        except Exception:                    # noqa: BLE001 – cədvəli olmayan sinif: göstərici yoxdur
            continue
        for sid in sids:
            st = student_stats(days, rec, sid)
            out[sid] = round(100 - st['missed_pct'], 1) if st['missed_pct'] is not None else None
    return out


def analyze(db: Session, ctx: PlanCtx, p: Period, links: bool = True) -> dict:
    """links=False – yalnız jurnal/KSQ/onlayn (səviyyə bölgüsü kimi daxili hesablamalar üçün, daha sürətli)."""
    from .api.exams_online import class_exams, exam_stats
    studs = roster(db, ctx.ta)
    data = _collect(db, ctx.ta.id, p)
    halves = _halves(data, p)
    first, second = (_sub(data, halves[0]), _sub(data, halves[1])) if halves else (None, None)
    ovr = {o.student_id: o for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == ctx.ta.id))}
    manual = {k: o.level for k, o in ovr.items()}
    grade = class_grade(db, ctx.cls)
    kind = ix_kind(ctx.ta.subject)
    ix_label = IX_LABELS.get(kind, 'IX sinif buraxılış balı')
    exs = class_exams(db, ctx.ta, p.a, p.b) if links else []
    extra = _extra(db, ctx.ta.id, {s.id for s in studs}, p) if links else {}
    all_att = _all_lessons_attendance(db, ctx, studs, p) if links else {}
    rows = []
    for s in studs:
        m = _metrics(s.id, *data)
        r1 = _metrics(s.id, *first)['rating'] if first else None
        r2 = _metrics(s.id, *second)['rating'] if second else None
        ix = ix_score(s, ctx.ta.subject, grade)
        sinaq = [x['rows'][s.id]['pct'] for x in exs if s.id in x['rows'] and x['rows'][s.id]['status'] == 'yazıb']
        risk = risk_score(RiskInput(ix_score=ix, ix_label=ix_label, last_formative=m['last_marks'],
                                    last_ksq_pct=m['last_ksq_pct'], attendance_pct=m['attendance_pct'],
                                    homework_pct=m['homework_pct'], sinaq_pcts=sinaq))
        base = level(ix)
        cur = level(m['rating']) if m['rating'] is not None else base
        auto_level = LEVEL_NAMES.get(cur)
        src = (('bölgü' if ovr[s.id].source == 'auto' else 'müəllim') if s.id in manual
               else 'nəticələr' if m['rating'] is not None else 'IX sinif balı' if ix is not None else None)
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'portal_code': s.portal_code,
                     'ix_math': s.score_math, 'ix_score': ix, 'baseline_level': LEVEL_NAMES.get(base),
                     'auto_level': auto_level, 'level': manual.get(s.id, auto_level), 'manual_level': manual.get(s.id),
                     'level_source': src, 'score_language': s.score_language, 'score_foreign': s.score_foreign,
                     'progress': round(r2 - r1, 1) if r1 is not None and r2 is not None else None,
                     'risk': {'score': risk.score, 'status': risk.status, 'factors': risk.factors},
                     **{f'sinaq_{k[5:]}': v for k, v in exam_stats(exs, s.id).items()},
                     'extra': extra.get(s.id), 'attendance_all_pct': all_att.get(s.id), **m})
    places = {k: pl for k, _, pl in rank([(r['student_id'], r['rating']) for r in rows])}
    prog = {k: pl for k, _, pl in rank([(r['student_id'], r['progress']) for r in rows])}
    for r in rows:
        r['place'], r['progress_place'] = places[r['student_id']], prog[r['student_id']]
    rows.sort(key=lambda r: (r['place'] is None, r['place'] or 0, r['full_name']))
    grades = [m.grade for m in data[1] if m.grade is not None]
    group = None
    if ctx.cls.kind == 'qrup':                        # çap başlığı üçün: qrupun növü və sinfi
        from .models import SchoolClass
        par = db.get(SchoolClass, ctx.cls.parent_id) if ctx.cls.parent_id else None
        group = {'kind': 'bölünmə qrupu' if par else 'tədris qrupu',
                 'classes': [par.name] if par else sorted({db.get(SchoolClass, s.class_id).name for s in studs})}
    return {
        'from': p.a, 'to': p.b, 'class_name': ctx.cls.name, 'subject': ctx.ta.subject, 'ix_label': ix_label, 'group': group,
        'lessons_written': sum(not e.auto for e in data[0].values()), 'students': rows,
        'progress_split': {'first': halves[0].b, 'second_from': halves[1].a, 'to': halves[1].b} if halves else None,
        'overview': {
            'students': len(rows), 'avg_grade': _avg(grades),
            'distribution': {g: grades.count(g) for g in (5, 4, 3, 2)},
            'avg_attendance': _avg([r['attendance_pct'] for r in rows]),
            'avg_homework': _avg([r['homework_pct'] for r in rows]),
            'avg_ksq_pct': _avg([r['ksq_avg_pct'] for r in rows]),
            'avg_online_pct': _avg([r['online_pct'] for r in rows]),
            'avg_sinaq_pct': _avg([r['sinaq_pct'] for r in rows]), 'sinaq_count': len(exs),
            'extra_students': sum(r['extra'] is not None for r in rows),
            'levels': {k: sum(r['level'] == k for r in rows) for k in ('Güclü', 'Orta', 'Zəif')},
            'risk': {k: sum(r['risk']['status'] == k for r in rows) for k in ('Qırmızı', 'Sarı', 'Yaşıl')},
            'absence_warnings': sum(r['absence_warning'] for r in rows), 'absence_limit_pct': ABSENCE_WARN_PCT,
        },
    }


def attendance_map(db: Session, ctx: PlanCtx, p: Period) -> dict:
    """İstilik xəritəsi: sətir – şagird, sütun – yazılmış dərs (tarix, saat). Yalnız onlayn test qiyməti olan
    (müəllimin saxlamadığı) dərslər sütun deyil – davamiyyəti yoxdur."""
    entries = list(db.scalars(select(JournalEntry).where(
        JournalEntry.assignment_id == ctx.ta.id, JournalEntry.date >= p.a, JournalEntry.date <= p.b,
        JournalEntry.auto.is_(False)).order_by(JournalEntry.date, JournalEntry.period)))
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
