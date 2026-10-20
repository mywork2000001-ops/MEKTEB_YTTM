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


# ---------------------------------------------------------------- sinif matrisi: kim nəyi işləyib (docs/tasks/sinif-test-matrisi.md)
MATRIX_KINDS = ('movzu', 'sinaq', 'all')
_COL_ORDER = {'movzu': 0, 'sinaq': 1, 'ksq': 2, 'bsq': 3}
_DONE = ('yazıb', 'nəşr olunmayıb')
# «İşləməli» statuslar (işlənməyənlər siyahısı, Əsas səhifə sayı). Müddətsiz testlər üçün `işlənməyib` statusu əlavə olunanda YALNIZ bura yazılır.
MISSING_STATUSES = ('yazmayıb', 'gözlənilir')


def _cell(status: str, pct: float | None = None, published: bool = True) -> dict:
    return {'status': status, 'pct': pct, 'grade': summative_grade(pct) if pct is not None else None, 'published': published}


def class_matrix(db: Session, user: User, ta_id: int, kind: str = 'all', date_from: dt.date | None = None,
                 date_to: dt.date | None = None) -> dict:
    """Bir dərsin (sinif/qrup) «şagird × test» cədvəli: sütun – mövzu testləri (№), sınaqlar (adla), kağız KSQ/BSQ; xana – nəticə.
    Mənbə qaydaları `_build` ilə eyni: onlayn + kağız, eyni test bir dəfə (nəşr olunmuş kağız balı onlayn xananı əvəz edir).
    Yalnız öz dərsim (başqa müəllim – 404). Nəşr olunmamış skan balı `nəşr olunmayıb` (bal göstərilir, `published=False`)."""
    from .services import own_assignment, today
    if kind not in MATRIX_KINDS:
        raise HTTPException(400, 'kind: movzu, sinaq və ya all')
    ta = own_assignment(db, user, ta_id)
    cls = db.get(SchoolClass, ta.class_id)
    studs = roster(db, ta)
    nums = lesson_numbers(list(db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id))))
    cols: dict[str, dict] = {}
    cells: dict[str, dict[int, dict]] = {}

    # ---- onlayn
    for k in KINDS:
        if kind != 'all' and kind != k:
            continue
        data = collect(db, user, k, {ta.id}, date_from, date_to)
        by_unit = {t['unit']: t for t in data['tests']}
        for r in data['rows']:
            if r['ta_id'] != ta.id or not r['visible']:
                continue
            u = r['unit']
            if u not in cols:
                t = by_unit[u]
                no = None
                if k == 'movzu':
                    ot = db.get(OnlineTask, r['task_id'])
                    no = nums.get(ot.plan_lesson_id) if ot and ot.plan_lesson_id else None
                cols[u] = {'key': u, 'kind': k, 'no': no, 'title': (t['topic'] or t['title']) if k == 'movzu' else sinaq_name(t['title']),
                           'date': _iso(t['date'])}
                cells[u] = {}
            st = r['status']
            cells[u][r['student_id']] = _cell('yazıb', r['pct']) if st == 'yazıb' else \
                _cell('yazmayıb') if st == 'yazmayıb' else _cell('gözlənilir')

    # ---- kağız / skan
    wanted = {'movzu': ('TEST',), 'sinaq': ('SINAQ',), 'all': ('KSQ', 'BSQ', 'TEST', 'SINAQ')}[kind]
    exams = [e for e in db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind.in_(wanted)).order_by(Exam.date, Exam.id))
             if _in_range(e.date, date_from, date_to)]
    smap = _series_map(db, {e.batch_id for e in exams if e.batch_id})
    for e in exams:
        link = f'b{e.batch_id}' if e.batch_id else f't{e.online_task_id}' if e.online_task_id else None
        key = link if link in cols else f'e{e.id}'
        if key not in cols:
            if e.kind == 'SINAQ':
                title = _mock_name(e.title or f'Sınaq №{e.no}', e.batch_id, smap)[0]
            elif e.kind == 'TEST':
                title = e.title or f'Test №{e.no}'
            else:
                title = f"{e.kind}-{e.no}" + (f' (+{e.extra_seq})' if e.extra_seq else '')
            no = None
            if e.kind == 'TEST' and e.online_task_id:
                ot = db.get(OnlineTask, e.online_task_id)
                no = nums.get(ot.plan_lesson_id) if ot and ot.plan_lesson_id else None
            cols[key] = {'key': key, 'kind': 'movzu' if e.kind == 'TEST' else e.kind.lower(), 'no': no, 'title': title,
                         'date': _iso(e.date)}
            cells[key] = {}
        scores = {x.student_id: x for x in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id))}
        for s in studs:
            if e.extra_students is not None and s.id not in e.extra_students:
                continue
            sc = scores.get(s.id)
            if sc is None or sc.absent or sc.points is None or not e.max_points:
                if s.id not in cells[key]:                        # onlayn xana kağız boşluğu ilə əzilmir
                    cells[key][s.id] = _cell('gözlənilir' if e.date > today() else 'yazmayıb')
                continue
            pub = exam_published(db, e, s.id)
            if not pub and cells[key].get(s.id, {}).get('status') == 'yazıb':
                continue
            pct = round(sc.points * 100 / e.max_points, 1)
            cells[key][s.id] = _cell('yazıb' if pub else 'nəşr olunmayıb', pct, pub)

    # ---- sütunlar və sətirlər
    clist = sorted(cols.values(), key=lambda c: (_COL_ORDER[c['kind']], no_key(c['no']) if c['kind'] == 'movzu' else (0, ()),
                                                  c['date'] or '', c['title']))
    rows = []
    for s in studs:
        cs, pcts, wrote, given = {}, [], 0, 0
        for c in clist:
            x = cells[c['key']].get(s.id) or _cell('təyin olunmayıb')
            cs[c['key']] = x
            if x['status'] in _DONE:
                wrote += 1
            if x['status'] in _DONE or x['status'] == 'yazmayıb':
                given += 1
            if x['status'] == 'yazıb':
                pcts.append(x['pct'])
        rows.append({'student_id': s.id, 'full_name': s.full_name, 'cells': cs, 'wrote': wrote, 'given': given,
                     'avg_pct': avg(pcts)})
    for c in clist:
        xs = [cells[c['key']].get(s.id) for s in studs]
        xs = [x for x in xs if x and x['status'] != 'təyin olunmayıb']
        c['assigned_count'] = len(xs)
        c['wrote_count'] = sum(1 for x in xs if x['status'] in _DONE)
        c['avg_pct'] = avg([x['pct'] for x in xs if x['status'] == 'yazıb'])
    return {'ta_id': ta.id, 'class_name': cls.name, 'subject': ta.subject, 'kind': kind,
            'period': {'from': _iso(date_from), 'to': _iso(date_to)}, 'columns': clist, 'rows': rows}


def class_missing(db: Session, user: User, ta_id: int, kind: str = 'all', date_from: dt.date | None = None,
                  date_to: dt.date | None = None, sid: int | None = None) -> dict:
    """İşlənməyənlər siyahısı (docs/tasks/islenmeyenler-siyahisi.md): `class_matrix`-dən qurulur (təkrar məntiq yoxdur) –
    xananın statusu MISSING_STATUSES-dədir. Boş siyahılı şagirdlər çıxmır (sid verilibsə – həmin şagird boş olsa da qalır).
    Sıralama – ad. `lang` – şagirdin portal hesabının dili (hesab yoxdursa az)."""
    m = class_matrix(db, user, ta_id, kind, date_from, date_to)
    cols = {c['key']: c for c in m['columns']}
    ids = [r['student_id'] for r in m['rows']]
    uid = {s.id: s.user_id for s in db.scalars(select(Student).where(Student.id.in_(ids)))} if ids else {}
    ulang = {u.id: u.language for u in db.scalars(select(User).where(User.id.in_([x for x in uid.values() if x])))} if uid else {}
    rows = []
    for r in m['rows']:
        if sid is not None and r['student_id'] != sid:
            continue
        items = [{'key': k, 'kind': cols[k]['kind'], 'no': cols[k]['no'], 'title': cols[k]['title'], 'date': cols[k]['date'],
                  'status': x['status']} for k, x in r['cells'].items() if x['status'] in MISSING_STATUSES]
        if not items and sid is None:
            continue
        rows.append({'student_id': r['student_id'], 'full_name': r['full_name'],
                     'lang': 'ru' if ulang.get(uid.get(r['student_id'])) == 'ru' else 'az', 'items': items})
    if sid is not None and not rows:
        raise HTTPException(404, 'Şagird bu sinifdə/qrupda deyil')
    rows.sort(key=lambda r: r['full_name'])
    return {'ta_id': m['ta_id'], 'class_name': m['class_name'], 'subject': m['subject'], 'kind': m['kind'], 'period': m['period'],
            'students': len(rows), 'total': sum(len(r['items']) for r in rows), 'rows': rows}


def missing_summary(db: Session, user: User, tas: list) -> list[dict]:
    """Əsas səhifə: hər öz dərsim üçün {ta_id, class_name, subject, students, total} (yalnız total>0). Eyni `class_missing` – saylar siyahı ilə üst-üstə düşür."""
    out = []
    for ta in tas:
        try:
            x = class_missing(db, user, ta.id, 'all')
        except HTTPException:
            continue
        if x['total']:
            out.append({'ta_id': ta.id, 'class_name': x['class_name'], 'subject': x['subject'], 'students': x['students'], 'total': x['total']})
    return sorted(out, key=lambda z: z['class_name'])
