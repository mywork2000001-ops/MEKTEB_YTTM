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
from .timing import NOT_DONE, GIVEN, is_unlimited
from .models import (MissingNote, MissingRequest, Exam, ExamScan, ExamScore, ExamSeries, GroupMember, JournalEntry, Mark, OnlineTask, PlanLesson, Role,
                     SchoolClass, Student, TeachingAssignment, User)
from .services import class_grade, roster
from .test_stats import KINDS, _aware, _roots, avg, collect, local_date

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
        if r['status'] in GIVEN:
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
        if r['status'] in GIVEN:
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
MISSING_STATUSES = ('yazmayıb', 'gözlənilir', NOT_DONE)


def _cell(status: str, pct: float | None = None, published: bool = True) -> dict:
    return {'status': status, 'pct': pct, 'grade': summative_grade(pct) if pct is not None else None, 'published': published}


def class_matrix(db: Session, user: User, ta_id: int, kind: str = 'all', date_from: dt.date | None = None,
                 date_to: dt.date | None = None, period_by: str = 'open') -> dict:
    """Bir dərsin (sinif/qrup) «şagird × test» cədvəli: sütun – mövzu testləri (№), sınaqlar (adla), kağız KSQ/BSQ; xana – nəticə.
    Mənbə qaydaları `_build` ilə eyni: onlayn + kağız, eyni test bir dəfə (nəşr olunmuş kağız balı onlayn xananı əvəz edir).
    Yalnız öz dərsim (başqa müəllim – 404). Nəşr olunmamış skan balı `nəşr olunmayıb` (bal göstərilir, `published=False`)."""
    from .services import own_assignment, today
    if kind not in MATRIX_KINDS:
        raise HTTPException(400, 'kind: movzu, sinaq və ya all')
    ta = own_assignment(db, user, ta_id)
    cls = db.get(SchoolClass, ta.class_id)
    studs = list({s.id: s for s in roster(db, ta)}.values())      # bir şagird = bir sətir (student_id üzrə təkrarsız)
    nums = lesson_numbers(list(db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id))))
    cols: dict[str, dict] = {}
    cells: dict[str, dict[int, dict]] = {}
    unit_tasks: dict[str, set[int]] = {}

    # ---- onlayn
    for k in KINDS:
        if kind != 'all' and kind != k:
            continue
        data = collect(db, user, k, {ta.id}, date_from, date_to, period_by=period_by)
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
                           'date': _iso(t['date']), 'test_title': t['title']}
                cells[u] = {}
            unit_tasks.setdefault(u, set()).add(r['task_id'])
            st = r['status']
            cells[u][r['student_id']] = _cell('yazıb', r['pct']) if st == 'yazıb' else \
                _cell(st) if st in ('yazmayıb', NOT_DONE) else _cell('gözlənilir')
            if st == 'yazıb':
                cells[u][r['student_id']]['submitted_at'] = r.get('submitted_at')

    # ---- kağız / skan
    wanted = {'movzu': ('TEST',), 'sinaq': ('SINAQ',), 'all': ('KSQ', 'BSQ', 'TEST', 'SINAQ')}[kind]
    exams = [e for e in db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind.in_(wanted)).order_by(Exam.date, Exam.id))
             if _in_range(e.date, date_from, date_to)]
    smap = _series_map(db, {e.batch_id for e in exams if e.batch_id})
    scans = set(db.execute(select(ExamScan.exam_id, ExamScan.student_id).where(ExamScan.exam_id.in_([e.id for e in exams])))) if exams else set()   # exam_published üçün toplu
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
            pub = e.results_published_at is not None or (e.id, s.id) not in scans      # = exam_published
            if not pub and cells[key].get(s.id, {}).get('status') == 'yazıb':
                continue
            pct = round(sc.points * 100 / e.max_points, 1)
            cells[key][s.id] = _cell('yazıb' if pub else 'nəşr olunmayıb', pct, pub)

    # ---- plan günü / açılış (docs/islenmeyenler-hesabati-promtu.md §5.1)
    paper_date = {f'e{e.id}': e.date for e in exams}
    for key, c in cols.items():
        c['plan_date'] = c['opens'] = c['task_id'] = None
        ids = unit_tasks.get(key)
        if ids:
            ts = sorted((t for t in (db.get(OnlineTask, i) for i in ids) if t), key=lambda t: _aware(t.opens_at))
            if ts:
                first = ts[0]
                pl = next((db.get(PlanLesson, t.plan_lesson_id) for t in ts if t.plan_lesson_id), None)
                if pl:
                    pd = pl.date
                elif not is_unlimited(first):
                    pd = local_date(first.closes_at)
                else:
                    pd = local_date(first.opens_at) + dt.timedelta(days=7)
                c['plan_date'], c['opens'], c['task_id'] = _iso(pd), _iso(local_date(first.opens_at)), ts[-1].id
        elif key in paper_date:
            c['plan_date'] = _iso(paper_date[key])

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
            if x['status'] in _DONE or x['status'] in ('yazmayıb', NOT_DONE):
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


# ---------------------------------------------------------------- işlənməyənlər hesabatı (docs/islenmeyenler-hesabati-promtu.md)
MISSING_RISK = {'critical': 50, 'attention': 80, 'streak': 3}      # icra % hədləri; ardıcıl buraxma sayı
REASONS = ('excused', 'technical', 'no_device', 'forgot', 'refused', 'other')
ADVICE = {'contact': 'Valideynlə əlaqə + fərdi söhbət', 'remind': 'Xatırlatma, təkrar imkan', 'deadline': 'Son tarixi xatırlat'}
_PENDING = ('gözlənilir', NOT_DONE)
_RISK_ORDER = {'critical': 0, 'attention': 1, 'ok': 2}


def _pct(a: int, b: int) -> float | None:
    return round(a * 100 / b, 1) if b else None


def risk_of(rate: float | None, streak: int) -> str:
    """Şagird üzrə risk: kritik – icra < 50% və ya ardıcıl ≥ 3 buraxma; diqqət – < 80%; qalanı normal (məxrəc 0 → normal)."""
    if streak >= MISSING_RISK['streak'] or (rate is not None and rate < MISSING_RISK['critical']):
        return 'critical'
    if rate is not None and rate < MISSING_RISK['attention']:
        return 'attention'
    return 'ok'


def plan_state(status: str, col: dict, cell: dict, today_d: dt.date) -> tuple[str | None, int | None]:
    """Plan gününə görə vəziyyət: late_open / late_done / on_time / not_due (+ gecikmə günü). təyin olunmayıb → (None, None)."""
    if status == 'təyin olunmayıb':
        return None, None
    pd = dt.date.fromisoformat(col['plan_date']) if col.get('plan_date') else None
    if status in _DONE:
        sub = cell.get('submitted_at')
        if sub and pd:
            d = (local_date(dt.datetime.fromisoformat(sub)) - pd).days
            if d > 0:
                return 'late_done', d
        return 'on_time', None
    if status == 'yazmayıb':                           # test bağlanıb – plan günündən asılı olmayaraq borcdur
        return 'late_open', max(0, (today_d - pd).days) if pd else 0
    if pd and pd < today_d:
        return 'late_open', (today_d - pd).days
    return 'not_due', None


def unit_tasks(db: Session, ta_id: int, key: str) -> list[OnlineTask]:
    """Matris sütun açarına (b…/t…) aid onlayn tapşırıqlar (yenidən göndərmə surətləri daxil), açılış vaxtı ilə."""
    if key[:1] not in ('b', 't'):
        return []
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta_id)))
    root = _roots(db, tasks)
    out = []
    for t in tasks:
        r = db.get(OnlineTask, root[t.id]) or t
        if (f'b{r.batch_id}' if r.batch_id else f't{r.id}') == key:
            out.append(t)
    return sorted(out, key=lambda t: _aware(t.opens_at))


def class_missing(db: Session, user: User, ta_id: int, kind: str = 'all', date_from: dt.date | None = None,
                  date_to: dt.date | None = None, sid: int | None = None, *, all_students: bool = False,
                  only_missed: bool = False, plan: str = 'all', sort: str = 'name',
                  sids: list[int] | None = None, task_keys: list[str] | None = None) -> dict:
    """İşlənməyənlər hesabatı – TƏK mənbə (`class_matrix`-dən qurulur, təkrar məntiq yoxdur). Geriyə uyğun: köhnə sahələr qalır
    (`rows[].items`, `students`, `total`), yenilər əlavə olunur: göstəricilər (assigned/done/missed/pending, rate, rate_on_time),
    risk, streak, tövsiyə, plan günü vəziyyəti, səbəb qeydləri, tələb tarixçəsi; `summary` və test üzrə `tests`.
    Defolt – yalnız borcu olanlar (all_students=True – hamı); only_missed – gözlənilənlər çıxarılır; plan='late_open' – yalnız plan günü
    keçmiş borclar; sort='risk' – risk → icra % → ad. Üzrlü qeyd (excused) məxrəcdən çıxır. `lang` – şagirdin portal dili."""
    from .services import today
    if plan not in ('all', 'late_open'):
        raise HTTPException(400, 'plan: all və ya late_open')
    m = class_matrix(db, user, ta_id, kind, date_from, date_to, period_by='due')   # M3: dövr – plan günü/son tarixə görə
    td = today()
    keys = set(task_keys) if task_keys else None            # test süzgəci (məntiqi test açarı: b…/t…/e…; surətlər birləşib)
    sids = set(sids) if sids else None
    cols = {c['key']: c for c in m['columns']}
    by_date = sorted(m['columns'], key=lambda c: (c['date'] or '', c['title']))
    ids = [r['student_id'] for r in m['rows']]
    uid = {s.id: s.user_id for s in db.scalars(select(Student).where(Student.id.in_(ids)))} if ids else {}
    ulang = {u.id: u.language for u in db.scalars(select(User).where(User.id.in_([x for x in uid.values() if x])))} if uid else {}
    notes = {(n.task_key, n.student_id): n for n in db.scalars(select(MissingNote).where(MissingNote.ta_id == ta_id))}
    reqs: dict[int, list] = {}
    for q in db.scalars(select(MissingRequest).where(MissingRequest.ta_id == ta_id).order_by(MissingRequest.created_at)):
        reqs.setdefault(q.student_id, []).append(q)

    out, seen = [], set()
    tstat = {k: {'assigned': 0, 'done': 0, 'missed': 0, 'pending': 0} for k in cols}
    for r in m['rows']:
        if r['student_id'] in seen:                     # təkrarsızlıq: bir şagird = bir sətir
            continue
        seen.add(r['student_id'])
        items, late_done, excused = [], [], []
        n_done = n_missed = n_pending = n_on_time = n_late_done = n_late_open = n_not_due = 0
        late_days = 0
        for k, x in r['cells'].items():
            st = x['status']
            if st == 'təyin olunmayıb' or (keys is not None and k not in keys):
                continue
            c = cols[k]
            state, days = plan_state(st, c, x, td)
            note = notes.get((k, r['student_id']))
            if note and note.reason == 'excused' and st in MISSING_STATUSES:
                excused.append({'key': k, 'no': c['no'], 'title': c['title'], 'date': c['date'], 'reason': 'excused', 'note': note.note})
                continue
            if st in _PENDING and c.get('opens') and c['opens'] > td.isoformat():
                state = 'not_due'                       # hələ açılmayıb – məxrəcə düşmür
                continue
            ts = tstat[k]
            ts['assigned'] += 1
            if st in _DONE:
                n_done += 1
                ts['done'] += 1
                if state == 'late_done':
                    n_late_done += 1
                    late_done.append({'key': k, 'no': c['no'], 'title': c['title'], 'late_days': days})
                else:
                    n_on_time += 1
            else:
                if st == 'yazmayıb':
                    n_missed += 1
                    ts['missed'] += 1
                else:
                    n_pending += 1
                    ts['pending'] += 1
                if state == 'late_open':
                    n_late_open += 1
                    late_days = max(late_days, days or 0)
                else:
                    n_not_due += 1
                items.append({'key': k, 'kind': c['kind'], 'no': c['no'], 'title': c['title'], 'date': c['date'], 'status': st,
                              'state': state, 'plan_date': c.get('plan_date'), 'late_days': days if state == 'late_open' else None,
                              'reason': note.reason if note else None, 'note': note.note if note else None})
        assigned = n_done + n_missed + n_pending
        den_on_time = n_on_time + n_late_done + n_late_open
        rate, rate_on_time = _pct(n_done, assigned), _pct(n_on_time, den_on_time)
        streak = 0
        for c in reversed(by_date):                     # ardıcıl buraxma (ən son testlərdən geriyə)
            x = r['cells'].get(c['key'])
            if not x or x['status'] == 'təyin olunmayıb' or (keys is not None and c['key'] not in keys) or any(e['key'] == c['key'] for e in excused):
                continue
            if x['status'] in _DONE:
                break
            if x['status'] == 'yazmayıb' or plan_state(x['status'], c, x, td)[0] == 'late_open':
                streak += 1
            else:
                continue
        risk = risk_of(rate_on_time if rate_on_time is not None else rate, streak)
        advice = 'contact' if risk == 'critical' else 'remind' if risk == 'attention' else 'deadline' if n_pending else None
        shown = [i for i in items if not (only_missed and i['status'] in _PENDING) and (plan == 'all' or i['state'] == 'late_open')]
        rq = reqs.get(r['student_id'], [])
        reasons: dict[str, int] = {}
        for i in shown:
            if i['reason']:
                reasons[i['reason']] = reasons.get(i['reason'], 0) + 1
        out.append({'student_id': r['student_id'], 'full_name': r['full_name'], 'lang': 'ru' if ulang.get(uid.get(r['student_id'])) == 'ru' else 'az',
                    'ui_lang': ulang.get(uid.get(r['student_id'])) if ulang.get(uid.get(r['student_id'])) in ('ru', 'en') else 'az',
                    'items': shown, 'assigned': assigned, 'done': n_done, 'missed': n_missed, 'pending': n_pending,
                    'rate': rate, 'rate_on_time': rate_on_time, 'rate_total': rate, 'late_open': n_late_open, 'late_days': late_days,
                    'late_done': late_done, 'streak': streak, 'risk': risk, 'advice_key': advice, 'advice': ADVICE.get(advice),
                    'excused': excused, 'reasons': reasons,
                    'requests': {'count': len(rq), 'last': _iso(local_date(rq[-1].created_at)) if rq else None}})

    summary_rows = out
    rows = [x for x in out if (sid is None or x['student_id'] == sid) and (sids is None or x['student_id'] in sids)
            and (all_students or sid is not None or x['items'])]
    if sid is not None and not rows:
        raise HTTPException(404, 'Şagird bu sinifdə/qrupda deyil')
    rates = [x['rate'] for x in summary_rows if x['rate'] is not None]
    reason_sum: dict[str, int] = {}
    for x in rows:
        for q, n in x['reasons'].items():
            reason_sum[q] = reason_sum.get(q, 0) + n
    if sort == 'risk':
        rows.sort(key=lambda x: (_RISK_ORDER[x['risk']], x['rate'] if x['rate'] is not None else 101, x['full_name']))
    else:
        rows.sort(key=lambda x: x['full_name'])
    tests = []
    for c in (c for c in m['columns'] if keys is None or c['key'] in keys):
        ts = tstat[c['key']]
        tests.append({'key': c['key'], 'kind': c['kind'], 'no': c['no'], 'title': c['title'], 'date': c['date'], 'plan_date': c.get('plan_date'),
                      'task_id': c.get('task_id'), 'test_title': c.get('test_title') or c['title'], **ts, 'rate': _pct(ts['done'], ts['assigned'])})
    summary = {'students_total': len(summary_rows), 'tests': len(tests), 'avg_rate': avg(rates),
               'full': sum(1 for x in summary_rows if x['rate'] == 100.0),
               'critical': sum(1 for x in summary_rows if x['risk'] == 'critical'),
               'attention': sum(1 for x in summary_rows if x['risk'] == 'attention'), 'reasons': reason_sum}
    return {'ta_id': m['ta_id'], 'class_name': m['class_name'], 'subject': m['subject'], 'kind': m['kind'], 'period': m['period'],
            'plan': plan, 'students': len(rows), 'total': sum(len(r['items']) for r in rows), 'rows': rows, 'summary': summary,
            'tests': tests}


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
