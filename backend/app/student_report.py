"""Şagirdin fərdi hesabatı – vahid nəticə modeli (docs/sagird-ferdi-hesabat-promtu.md §2.1). Yalnız OXUYUR, miqrasiya yoxdur.

Mənbələr: onlayn mövzu testləri və sınaqlar (test_stats.collect), kağız/skan imtahanlar (Exam + ExamScore: KSQ, BSQ, TEST, SINAQ)
və jurnalın əl ilə test qiymətləri (Mark(kind='test', task_id=None)). Eyni test bir dəfə sayılır.
Məxfilik: nəşr olunmamış skan balı şagirdə görünmür (müəllimdə `published=False`); sinif ortası – ən azı 5 nəticə olanda."""
from __future__ import annotations

import datetime as dt
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.rules import rank, summative_grade
from .models import (Exam, ExamScan, ExamScore, ExamSeries, GroupMember, JournalEntry, Mark, OnlineTask, PlanLesson, Role,
                     SchoolClass, Student, TeachingAssignment, User)
from .services import class_grade, roster
from .test_stats import KINDS, avg, collect

MIN_PEERS = 5          # sinif ortası: bundan az nəticə varsa gizli (şəxsi nəticəni açar)
WEAK_PCT = 50.0        # zəif mövzu həddi (≤)


# ---------------------------------------------------------------- mövzu nömrəsi (saf funksiya)
_TOPIC_HEAD = re.compile(r'^\s*(\d+(?:\.\d+)+)\.?(?:\s|$)')
_SECTION_HEAD = re.compile(r'^\s*(\d+)\s*[.)]')


def topic_no(topic: str | None, section: str | None = None, pos: int | None = None) -> str | None:
    """Mövzunun nömrəsi: mövzu mətnindəki baş nömrə («3.4. Ad» → «3.4»); yoxdursa bölmənin nömrəsi («2. Tənliklər») +
    mövzunun bölmədəki sırası (pos, 1-dən) → «2.3»; tapılmırsa None."""
    m = _TOPIC_HEAD.match(topic or '')
    if m:
        return m.group(1)
    m = _SECTION_HEAD.match(section or '')
    if m and pos:
        return f'{int(m.group(1))}.{pos}'
    return None


def no_key(no: str | None) -> tuple:
    """Nömrəyə görə sıralama açarı: «2.10» > «2.3»; nömrəsizlər sonda."""
    if not no:
        return (1, ())
    return (0, tuple(int(x) for x in no.split('.') if x.isdigit()))


def lesson_numbers(lessons: list[PlanLesson]) -> dict[int, str | None]:
    """{plan_lesson_id: nömrə} – bir dərs bağlılığının planı üçün (bölmədəki sıra = bölmənin fərqli mövzularının sırası)."""
    seen: dict[str | None, list[str]] = {}
    out: dict[int, str | None] = {}
    for pl in sorted(lessons, key=lambda x: x.seq):
        lst = seen.setdefault(pl.section, [])
        if pl.topic not in lst:
            lst.append(pl.topic)
        out[pl.id] = topic_no(pl.topic, pl.section, lst.index(pl.topic) + 1)
    return out


# ---------------------------------------------------------------- sınaq adı
_TR = str.maketrans('ÜüİıÖöŞşÇçĞğƏə', 'UuIiOoSsCcGgEe')
_KNOWN = {'USI': 'ÜSİ', 'MSI': 'MSİ', 'BSI': 'BSİ', 'MS': 'MS'}
_NAME = re.compile(r'^\s*([A-Za-zÜüİıÖöŞşÇçĞğƏə]{2,4})\s*[-–—_ ]?\s*(\d{1,3})(?!\d)')


def parse_sinaq(raw: str | None) -> tuple[str, int] | None:
    """«usi 1», «ÜSİ-1 (yeni yer)», «MS2» → ('ÜSİ', 1) …; tanınmırsa None."""
    m = _NAME.match(raw or '')
    if not m:
        return None
    key = _KNOWN.get(m.group(1).translate(_TR).upper())
    return (key, int(m.group(2))) if key else None


def sinaq_name(raw: str | None) -> str:
    """Bank faylının etiketi vahid ada gətirilir: «usi 1», «ÜSİ 1», «ÜSİ-1 (yeni yer)» → «ÜSİ-1»; tanınmırsa sonundakı
    mötərizəsiz təmiz başlıq."""
    p = parse_sinaq(raw)
    if p:
        return f'{p[0]}-{p[1]}'
    t = re.sub(r'\s*\([^)]*\)\s*$', '', raw or '').strip()
    return t or (raw or '').strip()


def _series_map(db: Session, batch_ids: set[int]) -> dict[int, tuple[str, int]]:
    """{batch_id: (seriya adı, sıra №)} – ExamSeries.done siyahısından."""
    out: dict[int, tuple[str, int]] = {}
    if not batch_ids:
        return out
    for s in db.scalars(select(ExamSeries)):
        for i, d in enumerate(s.done or [], 1):
            if d.get('batch_id') in batch_ids:
                out[d['batch_id']] = (s.title, i)
    return out


def _mock_name(raw: str | None, batch_id: int | None, smap: dict) -> tuple[str, str | None, int | None]:
    """(ad, seriya, seriyada №): seriya adı + sıra → bank etiketi (ÜSİ-1) → başlıq."""
    if batch_id in smap:
        t, i = smap[batch_id]
        return f'{t} №{i}', t, i
    p = parse_sinaq(raw)
    return sinaq_name(raw), (p[0] if p else None), (p[1] if p else None)


# ---------------------------------------------------------------- köməkçilər
def _iso(d) -> str | None:
    return d.isoformat() if d else None


def _in_range(d: dt.date | None, a: dt.date | None, b: dt.date | None) -> bool:
    return d is not None and not ((a and d < a) or (b and d > b))


def student_assignments(db: Session, s: Student) -> list[TeachingAssignment]:
    """Şagirdin bütün aktiv dərs bağlılıqları (sinif + qrup üzvlüyü)."""
    gids = set(db.scalars(select(GroupMember.group_id).where(GroupMember.student_id == s.id)))
    return list(db.scalars(select(TeachingAssignment).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).where(
        TeachingAssignment.archived_at.is_(None), SchoolClass.archived_at.is_(None),
        SchoolClass.id.in_(gids | {s.class_id})).order_by(TeachingAssignment.id)))


def exam_published(db: Session, e: Exam, sid: int) -> bool:
    """Skanı olan imtahan nəticəsi yalnız müəllim «göstər» deyəndən sonra açıqdır (portal /results ilə eyni qayda);
    skansız (əl ilə yazılmış) bal həmişə açıqdır."""
    if e.results_published_at is not None:
        return True
    return db.scalar(select(ExamScan.id).where(ExamScan.exam_id == e.id, ExamScan.student_id == sid).limit(1)) is None


def _trend(pcts: list[float]) -> dict:
    last = pcts[-3:]
    if len(last) < 2:
        return {'dir': None, 'delta': None, 'last3': last}
    d = round(last[-1] - last[0], 1)
    return {'dir': 'up' if d > 3 else 'down' if d < -3 else 'flat', 'delta': d, 'last3': last}


# ---------------------------------------------------------------- əsas
def _build(db: Session, s: Student, tas: list[TeachingAssignment], user: User | None, viewer: str,
           date_from: dt.date | None, date_to: dt.date | None) -> dict:
    """viewer: 'staff' (müəllim/admin – nəşr olunmayan «nəşr olunmayıb» kimi görünür) | 'student' (yalnız nəşr olunmuşlar)."""
    stu = viewer == 'student'
    ta_ids = {t.id for t in tas}
    tmap = {t.id: t for t in tas}
    cls_of = {t.id: db.get(SchoolClass, t.class_id) for t in tas}
    nums: dict[int, dict[int, str | None]] = {}
    lessons: dict[int, PlanLesson] = {}
    for ta in tas:
        ls = list(db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id)))
        nums[ta.id] = lesson_numbers(ls)
        lessons.update({pl.id: pl for pl in ls})

    def topic_info(pl_id: int | None, fallback_topic: str | None = None) -> dict:
        pl = lessons.get(pl_id) if pl_id else None
        if not pl:
            return {'no': None, 'section': None, 'topic': fallback_topic, 'plan_lesson_id': None}
        return {'no': nums[pl.assignment_id].get(pl.id), 'section': pl.section, 'topic': pl.topic, 'plan_lesson_id': pl.id}

    # ---- kağız / skan imtahanlar (əvvəl – təkrarın qarşısı üçün)
    exams = [e for e in db.scalars(select(Exam).where(Exam.assignment_id.in_(ta_ids or {-1}),
                                                      Exam.kind.in_(('KSQ', 'BSQ', 'TEST', 'SINAQ'))).order_by(Exam.date, Exam.id))
             if (e.extra_students is None or s.id in e.extra_students) and _in_range(e.date, date_from, date_to)]
    scores = {e.id: db.get(ExamScore, (e.id, s.id)) for e in exams}
    rosters: dict[int, list[int]] = {}
    paper: list[dict] = []
    covered_units: set[str] = set()                    # nəşr olunmuş kağız nəticəsi olan onlayn vahidlər – təkrar sayılmır
    smap_b = {e.batch_id for e in exams if e.batch_id}
    smap = _series_map(db, smap_b)
    for e in exams:
        sc = scores[e.id]
        if sc is None or sc.absent or sc.points is None or not e.max_points:
            continue
        pub = exam_published(db, e, s.id)
        if stu and not pub:
            continue
        ta = tmap[e.assignment_id]
        if e.id not in rosters:
            rosters[e.id] = [x.id for x in roster(db, ta)]
        peers = [p for p in (db.get(ExamScore, (e.id, i)) for i in rosters[e.id])
                 if p and not p.absent and p.points is not None]
        pcts = [p.points * 100 / e.max_points for p in peers]
        pct = round(sc.points * 100 / e.max_points, 1)
        ca = avg(pcts) if len(pcts) >= MIN_PEERS else None
        place = next((pl for k, _, pl in rank([(str(p.student_id), p.points) for p in peers]) if k == str(s.id)), None)
        if pub:
            if e.batch_id:
                covered_units.add(f'b{e.batch_id}')
            if e.online_task_id:
                covered_units.add(f't{e.online_task_id}')
        paper.append({'exam': e, 'ta': ta, 'score': sc, 'pct': pct, 'class_avg': ca, 'place': place, 'published': pub})

    # ---- onlayn
    online: dict[str, list[dict]] = {}
    closed: dict[str, bool] = {}
    for k in KINDS:
        if stu or (user and user.role == Role.admin):
            data = collect(db, None, k, ta_ids or {-1}, date_from, date_to)
        else:
            data = collect(db, user, k, ta_ids if k == 'movzu' else None, date_from, date_to)
        closed.update({t['unit']: t['closed'] for t in data['tests']})
        online[k] = [r for r in data['rows'] if r['student_id'] == s.id and r['visible'] and r['unit'] not in covered_units]
        # sinif ortası üçün həmin vahiddə həmin sinfin nəticələri
        by_unit: dict[tuple, list[float]] = {}
        for r in data['rows']:
            if r['status'] == 'yazıb':
                by_unit.setdefault((r['unit'], r['ta_id']), []).append(r['pct'])
        for r in online[k]:
            v = by_unit.get((r['unit'], r['ta_id']), [])
            r['_ca'] = avg(v) if len(v) >= MIN_PEERS else None

    topic_tests: list[dict] = []
    mocks: list[dict] = []
    summatives: list[dict] = []
    missed: list[dict] = []
    given = wrote = 0

    for r in online['movzu']:
        if r['status'] in ('yazıb', 'yazmayıb'):
            given += 1
        if r['status'] == 'yazmayıb':
            missed.append({'title': r['title'], 'date': _iso(r['date']), 'kind': 'movzu'})
        if r['status'] != 'yazıb':
            continue
        wrote += 1
        t = db.get(OnlineTask, r['task_id'])
        pl_id = t.plan_lesson_id if t else None
        ti = topic_info(pl_id, r['topic'])
        closed_u = closed.get(r['unit'], True)
        ca = r['_ca'] if (not stu or closed_u) else None
        topic_tests.append({**ti, 'grade': class_grade(db, cls_of[r['ta_id']]), 'title': r['title'], 'date': _iso(r['date']),
                            'pct': r['pct'], 'grade_5': r['grade'], 'class_avg': ca,
                            'diff': round(r['pct'] - ca, 1) if ca is not None else None, 'attempts': 1, 'source': 'onlayn',
                            'subject': tmap[r['ta_id']].subject, 'ta_id': r['ta_id'], 'published': True})
    # təkrar cəhd sayı: eyni mövzu üzrə yazılmış testlər
    cnt: dict[tuple, int] = {}
    for x in topic_tests:
        cnt[(x['ta_id'], x['plan_lesson_id'] or x['topic'])] = cnt.get((x['ta_id'], x['plan_lesson_id'] or x['topic']), 0) + 1
    for x in topic_tests:
        x['attempts'] = cnt[(x['ta_id'], x['plan_lesson_id'] or x['topic'])]

    batch_ids = {int(r['unit'][1:]) for r in online['sinaq'] if r['unit'].startswith('b')}
    smap.update(_series_map(db, batch_ids))
    for r in online['sinaq']:
        if r['status'] in ('yazıb', 'yazmayıb'):
            given += 1
        if r['status'] == 'yazmayıb':
            missed.append({'title': sinaq_name(r['title']), 'date': _iso(r['date']), 'kind': 'sinaq'})
        if r['status'] != 'yazıb':
            continue
        wrote += 1
        bid = int(r['unit'][1:]) if r['unit'].startswith('b') else None
        name, series, no = _mock_name(r['title'], bid, smap)
        done = closed.get(r['unit'], True)
        show = not stu or done                                   # yer və sinif ortası – sınaq bağlanandan sonra
        mocks.append({'name': name, 'series': series, 'no_in_series': no, 'date': _iso(r['date']), 'score': r['pct'], 'max': 100,
                      'pct': r['pct'], 'grade_5': r['grade'], 'place_class': r['place_class'] if show else None,
                      'place_all': r['place_all'] if show else None, 'class_avg': r['_ca'] if show else None,
                      'by_part': {}, 'source': 'onlayn', 'published': True, 'subject': tmap[r['ta_id']].subject,
                      'ta_id': r['ta_id']})

    for p in paper:
        e, sc = p['exam'], p['score']
        ta = p['ta']
        base = {'date': _iso(e.date), 'pct': p['pct'], 'class_avg': p['class_avg'], 'source': 'kağız',
                'published': p['published'], 'subject': ta.subject, 'ta_id': ta.id}
        g = summative_grade(sc.points * 100 / e.max_points)
        if e.kind in ('KSQ', 'BSQ'):
            summatives.append({**base, 'kind': e.kind, 'no': e.no, 'semester': e.semester, 'extra_seq': e.extra_seq or 0,
                               'points': sc.points, 'max': e.max_points, 'grade_5': g, 'exam_id': e.id,
                               'source': 'onlayn' if sc.chosen == 'online' else 'kağız'})
        elif e.kind == 'SINAQ':
            name, series, no = _mock_name(e.title or f'Sınaq №{e.no}', e.batch_id, smap)
            mocks.append({**base, 'name': name, 'series': series, 'no_in_series': no, 'score': sc.points, 'max': e.max_points,
                          'grade_5': g, 'place_class': p['place'], 'place_all': None, 'by_part': {}, 'exam_id': e.id})
        else:                                                   # TEST – kağız mövzu testi
            t = db.get(OnlineTask, e.online_task_id) if e.online_task_id else None
            ti = topic_info(t.plan_lesson_id if t else None)
            topic_tests.append({**ti, 'grade': class_grade(db, cls_of[ta.id]), 'title': e.title or f'Test №{e.no}', **base,
                                'grade_5': g, 'diff': round(p['pct'] - p['class_avg'], 1) if p['class_avg'] is not None else None,
                                'attempts': 1, 'exam_id': e.id})

    # jurnalın əl ilə test qiymətləri (onlayn testdən gələnlər artıq sayılıb)
    for m, je in db.execute(select(Mark, JournalEntry).join(JournalEntry, JournalEntry.id == Mark.entry_id).where(
            JournalEntry.assignment_id.in_(ta_ids or {-1}), Mark.student_id == s.id, Mark.kind == 'test',
            Mark.task_id.is_(None), Mark.test_total > 0)):
        if not _in_range(je.date, date_from, date_to):
            continue
        ti = topic_info(je.plan_lesson_id, je.topic)
        pct = round((m.test_correct or 0) * 100 / m.test_total, 1)
        topic_tests.append({**ti, 'grade': class_grade(db, cls_of[je.assignment_id]), 'title': je.topic or ti['topic'] or 'Test',
                            'date': _iso(je.date), 'pct': pct, 'grade_5': m.grade, 'class_avg': None, 'diff': None,
                            'attempts': 1, 'source': 'jurnal', 'subject': tmap[je.assignment_id].subject,
                            'ta_id': je.assignment_id, 'published': True})

    topic_tests.sort(key=lambda x: (no_key(x['no']), x['date'] or ''))
    mocks.sort(key=lambda x: (x['date'] or '', x['name']))
    summatives.sort(key=lambda x: (x['date'] or '', x['kind'], x['no']))

    # ---- yekun, zəif mövzular, tövsiyə (qayda əsaslı; nəşr olunmamış balı daxil deyil)
    shown = [x for x in topic_tests + mocks + summatives if x['published'] and x['pct'] is not None]
    series_pcts = [x['pct'] for x in sorted(shown, key=lambda y: y['date'] or '')]
    groups: dict[tuple, list[dict]] = {}
    for x in topic_tests:
        groups.setdefault((x['ta_id'], x['plan_lesson_id'] or x['topic']), []).append(x)
    weak = []
    for xs in groups.values():
        a = avg([x['pct'] for x in xs])
        if a is not None and a <= WEAK_PCT:
            weak.append({'no': xs[0]['no'], 'topic': xs[0]['topic'] or xs[0]['title'], 'pct': a, 'n': len(xs),
                         'ta_id': xs[0]['ta_id'], 'plan_lesson_id': xs[0]['plan_lesson_id']})
    weak.sort(key=lambda w: (w['pct'], no_key(w['no'])))
    part = round(wrote * 100 / given, 1) if given else None
    last_mock = next((m for m in reversed(mocks) if m['published'] and m['place_class']), None)
    summary = {'avg_pct': avg(series_pcts), 'last_pct': series_pcts[-1] if series_pcts else None, 'trend': _trend(series_pcts),
               'given': given, 'wrote': wrote, 'participation': part, 'missed': missed,
               'topic_avg': avg([x['pct'] for x in topic_tests if x['published']]),
               'mock_avg': avg([x['pct'] for x in mocks if x['published']]),
               'summative_avg': avg([x['pct'] for x in summatives if x['published']]),
               'place_class': last_mock['place_class'] if last_mock else None}
    recs = [{'code': 'repeat_topic', 'no': w['no'], 'topic': w['topic'], 'pct': w['pct'], 'ta_id': w['ta_id'],
             'plan_lesson_id': w['plan_lesson_id']} for w in weak[:3]]
    if part is not None and part < 60 and given >= 2:
        recs.append({'code': 'participation', 'pct': part})
    if summary['trend']['dir'] == 'down':
        recs.append({'code': 'trend_down', 'delta': summary['trend']['delta']})
    return {'student': {'id': s.id, 'full_name': s.full_name,
                        'class_name': db.get(SchoolClass, s.class_id).name if s.class_id else None},
            'period': {'from': _iso(date_from), 'to': _iso(date_to)}, 'viewer': viewer,
            'topic_tests': topic_tests, 'mocks': mocks, 'summatives': summatives,
            'weak_topics': weak, 'summary': summary, 'recommendations': recs}


def student_results(db: Session, user: User, sid: int, date_from: dt.date | None = None,
                    date_to: dt.date | None = None) -> dict:
    """Müəllim/admin üçün: yalnız şagirdi görməyə haqqı olanlar (`can_see_student`; fərdi məkan şagirdi başqa məkanda – 404)."""
    from .api.common import can_see_student
    s = db.get(Student, sid)
    if not s or not can_see_student(db, user, s):
        raise HTTPException(404, 'Şagird tapılmadı')
    tas = student_assignments(db, s)
    if user.role != Role.admin:                       # müəllim – yalnız öz dərsləri (mövcud şagird profili ilə eyni)
        tas = [t for t in tas if t.teacher_id == user.id]
    tas = [t for t in tas if db.get(SchoolClass, t.class_id).school_id == user.school_id]
    return _build(db, s, tas, user, 'staff', date_from, date_to)


def my_results(db: Session, s: Student, date_from: dt.date | None = None, date_to: dt.date | None = None) -> dict:
    """Şagirdin özü üçün: yalnız nəşr olunmuş nəticələr."""
    return _build(db, s, student_assignments(db, s), None, 'student', date_from, date_to)
