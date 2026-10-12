"""KSQ / BSQ: bal -> faiz -> qiymət (0–30→2, 31–60→3, 61–80→4, 81–100→5), tapşırıq üzrə ✓/✗,
tapşırıq və standart təhlili, yarımil qiyməti = (KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6."""
from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import grade_from_points, semester_grade
from ..models import BankQuestion, Exam, ExamScore, ExamVariant, OnlineTask, TeachingAssignment, User
from ..services import own_assignment, plan_ctx, roster, today
from .common import audit, get_or_404

router = APIRouter(prefix='/api/exams', tags=['exams'])


class ItemIn(BaseModel):
    n: int = Field(ge=1)
    points: float = Field(gt=0)
    standard: str | None = Field(None, max_length=20)


class ExamIn(BaseModel):
    kind: Literal['KSQ', 'BSQ']
    no: int = Field(ge=1, le=20)
    semester: Literal[1, 2]
    date: dt.date
    max_points: float | None = Field(None, gt=0, le=1000)
    items: list[ItemIn] | None = None
    title: str | None = Field(None, max_length=3000)

    @model_validator(mode='after')
    def _max(self):
        if self.items:
            total = round(sum(i.points for i in self.items), 2)
            if self.max_points is not None and abs(self.max_points - total) > 1e-6:
                raise ValueError(f'tapşırıqların balları cəmi ({total}) maksimal bala bərabər olmalıdır')
            self.max_points = total
        if self.max_points is None:
            raise ValueError('maksimal bal və ya tapşırıqlar lazımdır')
        return self


def exam_out(e: Exam) -> dict:
    return {'id': e.id, 'kind': e.kind, 'no': e.no, 'semester': e.semester, 'date': e.date,
            'max_points': e.max_points, 'items': e.items, 'title': e.title}


def _exam(db: Session, ta_id: int, exam_id: int) -> Exam:
    e = get_or_404(db, Exam, exam_id, 'İmtahan')
    if e.assignment_id != ta_id:
        raise HTTPException(404, 'İmtahan tapılmadı')
    return e


@router.get('/{ta_id}')
def list_exams(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    created = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id)
                              .order_by(Exam.semester, Exam.date, Exam.kind)))
    have = {(e.kind, e.semester, e.no) for e in created}
    planned = [{'kind': pl.assessment_type, 'no': pl.exam_no, 'semester': pl.semester, 'date': pl.date,
                'topic': pl.topic, 'created': (pl.assessment_type, pl.semester, pl.exam_no) in have}
               for pl in plan_ctx(db, ta).lessons if pl.assessment_type in ('KSQ', 'BSQ')]
    # BSQ-2 bir gündə iki saat ola bilər – bir imtahan kimi göstərilir
    seen, uniq = set(), []
    for p in planned:
        k = (p['kind'], p['semester'], p['no'])
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return {'has_summative': ta.has_summative, 'exams': [exam_out(e) for e in created], 'planned': uniq}


def _check_exam(db: Session, ta, body: ExamIn, exam_id: int | None = None):
    """Metodik qaydalar: tarix seçilən yarımilin içində; hər yarımildə bir BSQ (nömrəsi yarımilə bərabər)."""
    y = plan_ctx(db, ta).year
    a, b = (y.start, y.sem1_end) if body.semester == 1 else (y.sem2_start, y.end)
    if not a <= body.date <= b:
        raise HTTPException(400, f'{body.semester}-ci yarımil {a:%d.%m.%Y} – {b:%d.%m.%Y}: tarix bu aralıqda olmalıdır')
    if body.kind == 'BSQ':
        if body.no != body.semester:
            raise HTTPException(400, f'{body.semester}-ci yarımilin BSQ-si BSQ-{body.semester} olmalıdır')
        other = db.scalar(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind == 'BSQ', Exam.semester == body.semester,
                                             Exam.id != (exam_id or 0)))
        if other:
            raise HTTPException(409, f'{body.semester}-ci yarımildə BSQ artıq var')


@router.post('/{ta_id}')
def create_exam(ta_id: int, body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    _check_exam(db, ta, body)
    if not ta.has_summative:
        raise HTTPException(400, 'Bu qrupda KSQ/BSQ keçirilmir (bütöv sinifdə keçirilir)')
    if db.scalar(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind == body.kind,
                                    Exam.semester == body.semester, Exam.no == body.no)):
        raise HTTPException(409, f'{body.kind}-{body.no} ({body.semester}-ci yarımil) artıq var')
    e = Exam(assignment_id=ta.id, kind=body.kind, no=body.no, semester=body.semester, date=body.date,
             max_points=body.max_points, items=[i.model_dump() for i in body.items] if body.items else None,
             title=body.title)
    db.add(e)
    db.flush()
    audit(db, user, 'create', 'exam', e.id, kind=e.kind, no=e.no)
    db.commit()
    return exam_out(e)


@router.patch('/{ta_id}/{exam_id}')
def update_exam(ta_id: int, exam_id: int, body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    _check_exam(db, ta, body, e.id)
    has_scores = db.scalar(select(ExamScore).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None)))
    if has_scores and (body.max_points != e.max_points or (body.items and len(body.items) != len(e.items or []))):
        raise HTTPException(409, 'Nəticələr yazılıb – maksimal bal və tapşırıq sayı dəyişdirilə bilməz')
    e.kind, e.no, e.semester, e.date, e.title = body.kind, body.no, body.semester, body.date, body.title
    e.max_points = body.max_points
    e.items = [i.model_dump() for i in body.items] if body.items else None
    audit(db, user, 'update', 'exam', e.id)
    db.commit()
    return exam_out(e)


@router.delete('/{ta_id}/{exam_id}')
def delete_exam(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """KSQ/BSQ-ni silir: nəticələr, kağız variantlar, kart skanları (şəkillər daxil) birlikdə. Plan sətri qalır («Hazırla»)."""
    from ..models import ExamScan
    from ..storage import DbStorage
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    n = {'scores': 0, 'variants': 0, 'scans': 0}
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id)):
        if sc.crop_key and sc.crop_key.startswith('db:'):
            DbStorage.remove(db, sc.crop_key)
        db.delete(sc)
        n['scans'] += 1
    for x in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)):
        db.delete(x)
        n['variants'] += 1
    for x in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id)):
        db.delete(x)
        n['scores'] += 1
    audit(db, user, 'delete', 'exam', e.id, kind=e.kind, no=e.no, **n)
    db.delete(e)
    db.commit()
    return {'ok': True, **n}


class ScoreIn(BaseModel):
    student_id: int
    points: float | None = Field(None, ge=0)
    item_marks: list[int] | None = None            # 1 = ✓, 0 = ✗
    absent: bool = False
    taken_on: dt.date | None = None                # üzrlü səbəbdən sonradan yazıb (tarix)


def _row(e: Exam, sc: ExamScore | None) -> dict:
    if not sc or sc.absent or sc.points is None:
        return {'points': None, 'pct': None, 'grade': None, 'absent': bool(sc and sc.absent),
                'item_marks': sc.item_marks if sc else None, 'taken_on': None}
    return {'points': sc.points, 'pct': round(sc.points * 100 / e.max_points, 1),
            'grade': grade_from_points(sc.points, e.max_points), 'absent': False, 'item_marks': sc.item_marks,
            'taken_on': sc.taken_on}


def _check_taken_on(db: Session, ta, e: Exam, s: ScoreIn, pts):
    """«Sonradan yazdı»: yalnız nəticə varsa; imtahan günündən sonra, bu gündən gec olmayaraq, həmin yarımil içində."""
    if s.taken_on is None:
        return
    if s.absent or pts is None:
        raise HTTPException(400, '«Sonradan yazdı» tarixi yalnız nəticə yazılanda qeyd olunur')
    y = plan_ctx(db, ta).year
    end = y.sem1_end if e.semester == 1 else y.end
    if not e.date < s.taken_on <= min(end, today()):
        raise HTTPException(400, f'Sonradan yazma tarixi {e.date:%d.%m.%Y}-dən sonra, yarımilin sonuna ({end:%d.%m.%Y}) '
                                 'və bu günə qədər olmalıdır')


@router.put('/{ta_id}/{exam_id}/scores')
def save_scores(ta_id: int, exam_id: int, body: list[ScoreIn], user: User = Depends(staff),
                db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    ids = {s.id for s in roster(db, ta)}
    for s in body:
        if s.student_id not in ids:
            raise HTTPException(400, f'Şagird {s.student_id} bu sinifdə deyil')
        pts = s.points
        if s.item_marks is not None:
            if not e.items or len(s.item_marks) != len(e.items) or any(m not in (0, 1) for m in s.item_marks):
                raise HTTPException(400, 'Tapşırıq üzrə qeydlər (0/1) tapşırıq sayına bərabər olmalıdır')
            pts = round(sum(it['points'] * m for it, m in zip(e.items, s.item_marks)), 2)
        if pts is not None and pts > e.max_points:
            raise HTTPException(400, f'Bal maksimal baldan ({e.max_points}) çox ola bilməz')
        _check_taken_on(db, ta, e, s, pts)
        sc = db.get(ExamScore, (e.id, s.student_id)) or ExamScore(exam_id=e.id, student_id=s.student_id)
        sc.points, sc.item_marks, sc.absent = (None if s.absent else pts), (None if s.absent else s.item_marks), s.absent
        sc.taken_on = s.taken_on
        db.merge(sc)
    audit(db, user, 'update', 'exam_scores', e.id, count=len(body))
    db.commit()
    return exam_result(ta_id, exam_id, user, db)


@router.get('/{ta_id}/{exam_id}')
def exam_result(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    scores = {sc.student_id: sc for sc in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id))}
    rows = [{'student_id': s.id, 'full_name': s.full_name, **_row(e, scores.get(s.id))} for s in roster(db, ta)]
    done = [r for r in rows if r['grade'] is not None]
    dist = {g: sum(r['grade'] == g for r in done) for g in (5, 4, 3, 2)}
    items, standards = [], {}
    if e.items:
        marked = [sc.item_marks for sc in scores.values() if sc.item_marks and not sc.absent]
        for i, it in enumerate(e.items):
            ok = sum(m[i] for m in marked)
            pct = round(ok * 100 / len(marked), 1) if marked else None
            items.append({**it, 'correct': ok, 'of': len(marked), 'pct': pct})
            if it.get('standard'):
                st = standards.setdefault(it['standard'], [0, 0])
                st[0] += ok
                st[1] += len(marked)
    return {'exam': exam_out(e), 'rows': rows,
            'summary': {'written': len(done), 'absent': sum(r['absent'] for r in rows),
                        'avg_pct': round(sum(r['pct'] for r in done) / len(done), 1) if done else None,
                        'distribution': dist},
            'items': items,
            'standards': [{'standard': k, 'pct': round(a * 100 / b, 1) if b else None}
                          for k, (a, b) in sorted(standards.items())]}


@router.get('/{ta_id}/semester/{sem}')
def semester(ta_id: int, sem: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if sem not in (1, 2):
        raise HTTPException(400, 'yarımil: 1 və ya 2')
    exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.semester == sem)
                            .order_by(Exam.kind.desc(), Exam.no)))
    scores = {(sc.exam_id, sc.student_id): sc for sc in db.scalars(
        select(ExamScore).where(ExamScore.exam_id.in_([e.id for e in exams])))}
    from ..services import plan_ctx
    from .exams_online import class_exams, exam_stats
    y = plan_ctx(db, ta).year
    exs = class_exams(db, ta, None if sem == 1 else y.sem2_start, y.sem1_end if sem == 1 else None)
    out = []
    for s in roster(db, ta):
        ksq = [(e.no, _row(e, scores.get((e.id, s.id)))['grade']) for e in exams if e.kind == 'KSQ']
        bsq = next((_row(e, scores.get((e.id, s.id)))['grade'] for e in exams if e.kind == 'BSQ'), None)
        ksq_grades = [g for _, g in ksq if g is not None]
        out.append({'student_id': s.id, 'full_name': s.full_name, 'ksq': ksq, 'bsq': bsq,
                    'ksq_avg': round(sum(ksq_grades) / len(ksq_grades), 2) if ksq_grades else None,
                    'semester_grade': semester_grade(ksq_grades, bsq), **exam_stats(exs, s.id)})
    return {'semester': sem, 'formula': '(KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6', 'students': out,
            'exams': len(exs)}


# ---------------------------------------------------------------- kağız variantları (docs/ksq-bsq-kagiz-promtu.md)
def _range_lessons(db: Session, ta, e: Exam) -> list:
    """İmtahanın aralığındakı plan dərsləri (mövzu təkrarlanmır) – _range_topics ilə eyni qayda."""
    lessons = [pl for pl in plan_ctx(db, ta).lessons if pl.semester == e.semester]
    lessons.sort(key=lambda pl: pl.seq)
    me = next((pl for pl in lessons if pl.assessment_type == e.kind and pl.exam_no == e.no), None)
    end = me.seq if me else max((pl.seq for pl in lessons if pl.date <= e.date), default=10 ** 9)
    start = max((pl.seq for pl in lessons if pl.assessment_type in ('KSQ', 'BSQ') and pl.seq < end), default=0) if e.kind == 'KSQ' else 0
    out, seen = [], set()
    for pl in lessons:
        if start < pl.seq < end and pl.assessment_type not in ('KSQ', 'BSQ') and pl.topic and pl.topic not in seen:
            seen.add(pl.topic)
            out.append(pl)
    return out


def _plan_files(db: Session, ta, e: Exam, source: str | list[str]) -> tuple[list, dict[int, list[int]]]:
    """Hər perspektiv plan dərsinin öz testləri: müəllimin planda seçdiyi fayl (LessonBankLink) üstündür, yoxdursa – mövzuya uyğun 4 fayl."""
    from ..bank.match import Matcher
    from ..models import LessonBankLink
    pls = _range_lessons(db, ta, e)
    links = {k.plan_lesson_id: k for k in db.scalars(select(LessonBankLink).where(LessonBankLink.plan_lesson_id.in_([p.id for p in pls] or [0])))}
    srcs = [source] if isinstance(source, str) else list(source)
    main = _source(db, ta)
    ms = [Matcher(db, s, any_kind=s != main) for s in srcs]           # əlavə layihələrdə sınaq faylları da (ad üzrə uyğunluq)
    files: dict[int, list[int]] = {}
    for i, pl in enumerate(pls):
        k = links.get(pl.id)
        own = ([k.file_id] if k.file_id else []) if k else []
        auto = [f.id for m in ms for f, _ in m.matches(pl.topic, pl.section, limit=4, rel=0.45)] if not k or main not in srcs or len(srcs) > 1 else []
        files[i] = list(dict.fromkeys(own + auto))
    return pls, files


def _source(db: Session, ta) -> str:
    from ..bank.match import source_for
    from ..models import SchoolClass
    from ..services import class_grade
    return source_for(class_grade(db, db.get(SchoolClass, ta.class_id))) or 'p003'


def _range_topics(db: Session, ta, e: Exam) -> list[tuple[str, str | None]]:
    """KSQ: əvvəlki KSQ/BSQ-dan bu imtahana qədər keçilmiş dərslərin mövzuları; BSQ: yarımilin bütün mövzuları (təkrarsız, ardıcıl)."""
    lessons = [pl for pl in plan_ctx(db, ta).lessons if pl.semester == e.semester]
    lessons.sort(key=lambda pl: pl.seq)
    me = next((pl for pl in lessons if pl.assessment_type == e.kind and pl.exam_no == e.no), None)
    end = me.seq if me else max((pl.seq for pl in lessons if pl.date <= e.date), default=10 ** 9)
    start = 0
    if e.kind == 'KSQ':
        start = max((pl.seq for pl in lessons if pl.assessment_type in ('KSQ', 'BSQ') and pl.seq < end), default=0)
    out, seen = [], set()
    for pl in lessons:
        if start < pl.seq < end and pl.assessment_type not in ('KSQ', 'BSQ') and pl.topic and pl.topic not in seen:
            seen.add(pl.topic)
            out.append((pl.topic, pl.section))
    return out


def _history(db: Session, ta, e: Exam, student_ids: list[int]) -> dict[int, set[str]]:
    """Şagirdə əvvəl verilmiş suallar: bu dərsin onlayn testləri/sınaqları + digər KSQ/BSQ variantları."""
    hist: dict[int, set[str]] = {sid: set() for sid in student_ids}
    bank_keys: dict[int, str] = {}
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id)))
    ids = {q.get('bank_id') for t in tasks for q in (t.questions or []) if isinstance(q, dict) and q.get('bank_id')}
    if ids:
        bank_keys = {q.id: 'b:' + (q.content_hash or str(q.id)) for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_(ids)))}
    for t in tasks:
        keys = {bank_keys[q['bank_id']] for q in (t.questions or []) if isinstance(q, dict) and q.get('bank_id') in bank_keys}
        for sid in (t.student_ids or student_ids):
            if sid in hist:
                hist[sid] |= keys
    for v in db.scalars(select(ExamVariant).where(ExamVariant.student_id.in_(student_ids), ExamVariant.exam_id != e.id)):
        hist[v.student_id] |= {q.get('key') for q in v.questions if q.get('key')}
    return hist


def _variants_out(db: Session, ta, e: Exam) -> dict:
    from collections import Counter
    from ..domain.ksq_variants import RULES_V, fairness
    names = {s.id: s.full_name for s in roster(db, ta)}
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    vs.sort(key=lambda v: v.code)
    return {'exam': exam_out(e), 'variants': [{'student_id': v.student_id, 'full_name': names.get(v.student_id), 'code': v.code,
                                               'questions': v.questions} for v in vs],
            'report': fairness({v.student_id: v.questions for v in vs}) if vs else None,
            # köhnə qaydalarla yaradılıb (mövzudan kənar sual ola bilər) – müəllimə «Yenidən yarat» təklif olunur
            'stale': any(q.get('v', 0) < RULES_V or q.get('template') for v in vs for q in v.questions if not q.get('edited')),
            'share': max(Counter(q.get('key') for v in vs for q in v.questions).values(), default=0)}


@router.get('/{ta_id}/{exam_id}/variants')
def get_variants(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    return _variants_out(db, ta, _exam(db, ta_id, exam_id))


def _rescore(db: Session, e: Exam, student_ids: list[int] | None = None) -> int:
    """Skanı olan şagirdlərin balı yenidən hesablanır (sual düzəldiləndə / slot ləğv olunanda)."""
    from ..models import ExamScan
    from .exam_scans import apply
    q = select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.reading.is_not(None))
    if student_ids is not None:
        q = q.where(ExamScan.student_id.in_(student_ids or [0]))
    n = 0
    for sc in db.scalars(q):
        apply(db, e, sc)
        n += 1
    return n


def _variant(db: Session, e: Exam, sid: int, slot: int) -> tuple[ExamVariant, int]:
    v = db.get(ExamVariant, (e.id, sid))
    if v is None:
        raise HTTPException(404, 'Variant tapılmadı')
    i = next((k for k, q in enumerate(v.questions) if q['slot'] == slot), None)
    if i is None:
        raise HTTPException(404, 'Sual tapılmadı')
    return v, i


class ReplaceIn(BaseModel):
    hide_in_bank: bool = False                       # səhv bank sualı – bir daha heç bir varianta düşməsin


@router.post('/{ta_id}/{exam_id}/variants/{student_id}/{slot}/replace')
def replace_question(ta_id: int, exam_id: int, student_id: int, slot: int, body: ReplaceIn | None = None,
                     user: User = Depends(staff), db: Session = Depends(get_db)):
    """Tək sualı əvəz edir: eyni mövzu → aralığın başqa mövzusu, eyni növ və çətinlik; sinifdə təkrarsızlıq qorunur."""
    import random
    from ..domain.ksq_variants import norm_text, pick_one
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    v, i = _variant(db, e, student_id, slot)
    old = v.questions[i]
    if body and body.hide_in_bank and old.get('bank_id'):
        bq = db.get(BankQuestion, old['bank_id'])
        if bq:
            bq.active = False
    students, topics, cands, hist, others, _ = _prepare(db, ta, e, VariantsIn(n=len(v.questions)))
    taken = {q.get('key') for x in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)) for q in x.questions}
    hidden = {old.get('key')} | ({'b:' + bq.content_hash} if body and body.hide_in_bank and old.get('bank_id') and bq else set())
    cands = [c for c in cands if c.key not in taken and c.key not in hidden]
    texts = {norm_text(q.get('text')) for x in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)) for q in x.questions}
    got = pick_one(old, topics, cands, taken | hidden | texts | hist.get(student_id, set()), random.randrange(10 ** 9))
    if got is None:
        raise HTTPException(409, 'Bu slot üçün başqa uyğun sual tapılmadı (mövzular üzrə hovuz bitib)')
    new = {**got, 'slot': slot, 'kind': old['kind'], 'level': old['level'], 'topic': old.get('topic')}
    qs = list(v.questions)
    qs[i] = {**new, 'points': old['points'], 'replaced': True}
    v.questions = qs
    _rescore(db, e, [student_id])
    audit(db, user, 'update', 'exam_variant', e.id, student_id=student_id, slot=slot, op='replace')
    db.commit()
    return qs[i]


class ReplaceAllIn(BaseModel):
    file_ids: list[int] | None = Field(None, max_length=60)    # bu slot üçün başqa test(lər); boş – plan testləri


@router.post('/{ta_id}/{exam_id}/slots/{slot}/replace-all')
def replace_slot_all(ta_id: int, exam_id: int, slot: int, body: ReplaceAllIn | None = None, user: User = Depends(staff),
                     db: Session = Depends(get_db)):
    """Bir slotu BÜTÜN şagirdlərdə əvəz edir (məs. başqa test təyin etmək): hər şagirdə yeni, sinifdə təkrarsız sual."""
    import random
    from ..domain.ksq_variants import norm_text, pick_one
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    if not vs:
        raise HTTPException(404, 'Variant yoxdur')
    n = len(vs[0].questions)
    _, topics, cands, hist, _, _ = _prepare(db, ta, e, VariantsIn(n=n, file_ids=body.file_ids if body else None,
                                                                    only_mine=bool(body and body.file_ids)))
    olds = {q.get('key') for v in vs for q in v.questions if q['slot'] == slot}
    taken = {q.get('key') for v in vs for q in v.questions if q['slot'] != slot} | olds
    texts = {norm_text(q.get('text')) for v in vs for q in v.questions}
    rng = random.Random()
    done, failed = 0, 0
    for v in vs:
        i = next(k for k, q in enumerate(v.questions) if q['slot'] == slot)
        old = v.questions[i]
        got = pick_one(old, topics, cands, taken | texts | hist.get(v.student_id, set()), rng.randrange(10 ** 9))
        if got is None:
            failed += 1
            continue
        taken.add(got.get('key'))
        texts.add(norm_text(got.get('text')))
        qs = list(v.questions)
        qs[i] = {**got, 'slot': slot, 'kind': old['kind'], 'level': old['level'], 'topic': old.get('topic'),
                 'points': old['points'], 'replaced': True}
        v.questions = qs
        done += 1
    _rescore(db, e)
    audit(db, user, 'update', 'exam_variant', e.id, slot=slot, op='replace_all', done=done, failed=failed)
    db.commit()
    return {'ok': failed == 0, 'replaced': done, 'failed': failed}


@router.post('/{ta_id}/{exam_id}/fix-offtopic')
def fix_offtopic(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Köhnə qaydalarla yaradılmış variantlarda MÖVZUDAN KƏNAR sualları tapıb əvəz edir (qalanlara toxunmur):
    şablon sualları (standart qadağandır) və planın fayllarından kənar bank sualları → P0010 sualları."""
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    r = _fix_offtopic(db, ta, e, user)
    db.commit()
    return r


def _fix_offtopic(db: Session, ta, e: Exam, user: User | None = None) -> dict:
    import random
    from ..domain.ksq_variants import RULES_V, norm_text, pick_one
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    if not vs:
        raise HTTPException(404, 'Variant yoxdur')
    _, topics, cands, hist, _, files = _prepare(db, ta, e, VariantsIn(n=len(vs[0].questions)))
    ok_tpl: set[str] = set()                      # şablonlar standart olaraq qadağandır – hamısı P0010 sualı ilə əvəz olunur
    ok_files = {f for lst in files.values() for f in lst}
    file_of = {q.id: q.file_id for q in db.scalars(select(BankQuestion).where(BankQuestion.id.in_(
        [x.get('bank_id') for v in vs for x in v.questions if x.get('bank_id')] or [0])))}
    bad = lambda q: (q.get('template') and q['template'] not in ok_tpl) or (q.get('bank_id') and file_of.get(q['bank_id']) not in ok_files)  # noqa: E731
    taken = {q.get('key') for v in vs for q in v.questions}
    texts = {norm_text(q.get('text')) for v in vs for q in v.questions}
    rng = random.Random()
    fixed, failed, touched = 0, 0, []
    for v in vs:
        qs, changed = list(v.questions), False
        for i, q in enumerate(qs):
            if q.get('edited') or not bad(q):
                continue
            got = pick_one(q, topics, cands, taken | texts | hist.get(v.student_id, set()), rng.randrange(10 ** 9))
            if got is None:                       # sinifdə boş P0010 sualı qalmayıb → başqa BİR şagirddə olan sual (≤ 2 nəfər)
                own = {x.get('key') for x in qs} | {norm_text(x.get('text')) for x in qs}
                many = {k for k in taken if k and sum(k == x.get('key') for w in vs for x in w.questions) >= 2}
                got = pick_one(q, topics, cands, own | many | hist.get(v.student_id, set()), rng.randrange(10 ** 9))
            if got is None:
                failed += 1
                continue
            taken.add(got.get('key'))
            texts.add(norm_text(got.get('text')))
            qs[i] = {**got, 'slot': q['slot'], 'kind': q['kind'], 'level': q['level'], 'topic': q.get('topic'), 'points': q['points'], 'replaced': True}
            changed = True
            fixed += 1
        # versiya yalnız uyğunsuz sual QALMAYANDA yenilənir (əks halda xəbərdarlıq qalır – müəllim görsün)
        new_ids = [x.get('bank_id') for x in qs if x.get('bank_id') and x['bank_id'] not in file_of]
        if new_ids:                                   # əvəz olunan sualların faylı – yoxlama üçün
            file_of.update({b.id: b.file_id for b in db.scalars(select(BankQuestion).where(BankQuestion.id.in_(new_ids)))})
        if not any(bad(x) and not x.get('edited') for x in qs):
            qs = [{**x, 'v': max(x.get('v', 0), RULES_V)} for x in qs]
        v.questions = qs
        if changed:
            touched.append(v.student_id)
    _rescore(db, e, touched)
    audit(db, user, 'update', 'exam_variant', e.id, op='fix_offtopic', fixed=fixed, failed=failed)
    return {'ok': failed == 0, 'fixed': fixed, 'failed': failed, 'students': len(touched)}


def fix_stale_all(db: Session) -> int:
    """Fon işi: köhnə qaydalarla yaradılmış, NƏTİCƏSİ HƏLƏ YAZILMAMIŞ bütün KSQ/BSQ variantları avtomatik təmizlənir
    (şablon və mövzudan kənar suallar → P0010). Nəticəli imtahanlara toxunulmur (müəllim düymə ilə)."""
    from ..domain.ksq_variants import RULES_V
    from ..models import TeachingAssignment
    n = 0
    for e in db.scalars(select(Exam).where(Exam.id.in_(select(ExamVariant.exam_id).distinct()))):
        if db.scalar(select(ExamScore.exam_id).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None)).limit(1)):
            continue
        vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
        if all(q.get('v', 0) >= RULES_V for v in vs for q in v.questions):
            continue
        ta = db.get(TeachingAssignment, e.assignment_id)
        if ta is None:
            continue
        r = _fix_offtopic(db, ta, e)
        db.commit()
        n += r['fixed']
    return n


class QuestionEditIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    options: list[str] | None = Field(None, max_length=5)
    correct: int | None = Field(None, ge=0, le=4)
    answer: str | None = Field(None, max_length=60)


@router.put('/{ta_id}/{exam_id}/variants/{student_id}/{slot}')
def edit_question(ta_id: int, exam_id: int, student_id: int, slot: int, body: QuestionEditIn,
                  user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sualın mətni / variantları / düzgün cavabı düzəldilir (yalnız bu variantda); skanı varsa bal yenidən hesablanır."""
    from ..domain.ksq_variants import card_answer
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    v, i = _variant(db, e, student_id, slot)
    q = dict(v.questions[i])
    lang = 'az'
    q['text'] = {**(q['text'] if isinstance(q.get('text'), dict) else {}), lang: body.text}
    if q['kind'] == 'mcq':
        if not body.options or len(body.options) < 2 or body.correct is None or body.correct >= len(body.options):
            raise HTTPException(400, 'Test sualı üçün ən azı 2 variant və düzgün cavab lazımdır')
        q['options'] = [{'az': o} for o in body.options]
        q['correct'] = body.correct
    else:
        if not card_answer(body.answer):
            raise HTTPException(400, 'Açıq cavab kartın xanalarına yazıla bilməlidir: rəqəm, «-», «,», «/», «;» (≤ 8 simvol)')
        q['answer'] = body.answer
    q['edited'] = True
    qs = list(v.questions)
    qs[i] = q
    v.questions = qs
    n = _rescore(db, e, [student_id])
    audit(db, user, 'update', 'exam_variant', e.id, student_id=student_id, slot=slot, op='edit')
    db.commit()
    return {**q, 'rescored': n}


class AnnulIn(BaseModel):
    annulled: bool = True


@router.post('/{ta_id}/{exam_id}/slots/{slot}/annul')
def annul_slot(ta_id: int, exam_id: int, slot: int, body: AnnulIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Slotu hamı üçün ləğv edir (səhv sual): bal hesablanmır, qalan ballar 100-ə miqyaslanır; geri qaytarmaq olar."""
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    if not e.items or not any(it['n'] == slot for it in e.items):
        raise HTTPException(404, 'Slot tapılmadı')
    if body.annulled and sum(1 for it in e.items if it.get('annulled') or it['n'] == slot) >= len(e.items):
        raise HTTPException(400, 'Bütün sualları ləğv etmək olmaz')
    e.items = [{**it, 'annulled': body.annulled} if it['n'] == slot else it for it in e.items]
    n = _rescore(db, e)
    audit(db, user, 'update', 'exam', e.id, slot=slot, annulled=body.annulled)
    db.commit()
    return {'ok': True, 'rescored': n, 'items': e.items}


@router.get('/{ta_id}/{exam_id}/variants/print')
def print_variants(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Çap üçün: hər şagirdə bir A4 (iki üz) – suallar şagirdin dilində (yoxdursa AZ), cavab kartı üçün imzalı QR; müəllim açarı.
    Düzgün cavablar yalnız açarda (vərəqdə yox)."""
    from ..domain.ksq_card import key_value, pick_lang, qr_payload
    from ..models import SchoolClass, Student
    from .lessonplans import header_school
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    if not vs:
        raise HTTPException(409, 'Əvvəl variantları yaradın')
    vs.sort(key=lambda v: v.code)
    studs = {s.id: s for s in db.scalars(select(Student).where(Student.id.in_([v.student_id for v in vs])))}
    langs = {u.id: u.language for u in db.scalars(select(User).where(User.id.in_([s.user_id for s in studs.values() if s.user_id] or [0])))}
    cls = db.get(SchoolClass, ta.class_id)
    sheets, key = [], []
    for v in vs:
        st = studs.get(v.student_id)
        lang = langs.get(st.user_id, 'az') if st and st.user_id else 'az'
        qs = sorted(v.questions, key=lambda q: q['slot'])
        sheets.append({'student_id': v.student_id, 'full_name': st.full_name if st else '—', 'code': v.code, 'lang': lang,
                       'qr': qr_payload(e.id, v.student_id, v.code),
                       'questions': [{'slot': q['slot'], 'kind': q['kind'], 'points': q['points'], 'text': pick_lang(q.get('text'), lang),
                                      'options': [pick_lang(o, lang) for o in q.get('options') or []] if q['kind'] == 'mcq' else None,
                                      'image': q.get('image'), 'topic': q.get('topic_actual') or q.get('topic')} for q in qs]})
        key.append({'code': v.code, 'full_name': st.full_name if st else '—',
                    'answers': [{'slot': q['slot'], 'value': key_value(q), 'points': q['points'], 'topic': q.get('topic_actual') or q.get('topic')} for q in qs]})
    return {'exam': {**exam_out(e), 'class_name': cls.name if cls else '', 'subject': ta.subject, 'school': header_school(user),
                     'teacher': user.full_name},
            'sheets': sheets, 'key': key}


class VariantsIn(BaseModel):
    n: int = Field(30, ge=10, le=30)                 # sual sayı – müəllim seçir
    file_ids: list[int] | None = Field(None, max_length=60)    # müəllimin seçdiyi testlər – plana ƏLAVƏ olunur
    only_mine: bool = False                                   # True – yalnız seçilən testlər (plan nəzərə alınmır)
    share: int = Field(1, ge=1, le=2)                          # bir sual sinifdə ən çox neçə şagirdə (çatışmazlıqda 2)
    sources: list[str] | None = Field(None, max_length=20)     # test layihələri (bank mənbələri); boş – sinfin əsas layihəsi


def _prepare(db: Session, ta, e: Exam, body: 'VariantsIn') -> tuple:
    """Generator üçün hər şey: şagirdlər, mövzular, namizədlər, tarixçə, başqa siniflərin sualları."""
    from ..domain.ksq_variants import bank_candidates
    students = [s.id for s in roster(db, ta)]
    topics = _range_topics(db, ta, e)
    src = _source(db, ta)
    _, files = _plan_files(db, ta, e, body.sources or [src])
    if body.file_ids:
        files = {-1: list(dict.fromkeys(body.file_ids))} if body.only_mine else {**files, -1: list(dict.fromkeys(body.file_ids))}
    same = select(Exam.id).join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id).where(
        TeachingAssignment.teacher_id == ta.teacher_id, Exam.kind == e.kind, Exam.no == e.no, Exam.semester == e.semester, Exam.id != e.id)
    others = {q.get('key') for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id.in_(same))) for q in v.questions if q.get('key')}
    return students, topics, bank_candidates(db, topics, src, files), _history(db, ta, e, students), others, files


@router.post('/{ta_id}/{exam_id}/readiness')
def readiness(ta_id: int, exam_id: int, body: 'VariantsIn', user: User = Depends(staff), db: Session = Depends(get_db)):
    """Hazırlıq paneli: mövzular üzrə hovuz (bank test/açıq, şablon), seçilən n üçün sınaq generasiyası, maksimal mümkün n."""
    from ..domain.ksq_variants import N_MIN, Shortage
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    students, topics, cands, hist, others, files = _prepare(db, ta, e, body)
    rows = []
    for ti, (t, sec) in enumerate(topics):
        cs = [c for c in cands if c.on(ti)]                 # ortaq faylın sualları onun bütün mövzularında sayılır
        rows.append({'topic': t, 'files': len(files.get(ti, [])), 'mcq': sum(c.kind == 'mcq' for c in cs), 'open': sum(c.kind == 'open' for c in cs),
                     'templates': 0})
    extra = [c for c in cands if c.topic == -1]
    from ..domain.ksq_variants import generate_auto, max_n as cap_n
    short, share, mx = [{'missing': 1}], None, None
    if students and topics:
        mx = cap_n(cands, body.n)                          # generasiyasız – hovuzun ölçüsündən
        try:
            _, share = generate_auto(students, topics, cands, hist, seed=e.id * 7919, n=body.n, others=others)
            short = None
        except Shortage as sh:
            short = sh.items or [{'missing': 1}]
    max_n = body.n if not short else mx
    return {'students': len(students), 'n': body.n, 'need': len(students) * body.n, 'topics': rows,
            'selected': {'mcq': sum(c.kind == 'mcq' for c in extra), 'open': sum(c.kind == 'open' for c in extra)},
            'ok': not short, 'shortage': short or [], 'max_n': max_n, 'share': share}


@router.get('/{ta_id}/{exam_id}/sources')
def variant_sources(ta_id: int, exam_id: int, sources: str | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Variantlar üçün testlər: perspektiv plan dərsləri üzrə (avtomatik) və sinfin bütün test faylları (özü seçmək üçün)."""
    from ..bank.match import p0010_files
    from ..models import BankFile
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    src = _source(db, ta)
    from sqlalchemy import func
    from ..models import BankSource
    chosen = [x for x in (sources or '').split(',') if x] or [src]
    pls, files = _plan_files(db, ta, e, chosen)
    projects = [{'key': s.key, 'label': s.label, 'default': s.key == src,
                 'files': db.scalar(select(func.count()).select_from(BankFile).where(BankFile.source_key == s.key, BankFile.active.is_(True), BankFile.question_count > 0)) or 0}
                for s in db.scalars(select(BankSource).where(BankSource.enabled.is_(True)).order_by(BankSource.key))]
    lab = lambda i: (lambda f: {'file_id': f.id, 'label': f.label, 'questions': f.question_count} if f else None)(db.get(BankFile, i))  # noqa: E731
    return {'source': src, 'plan': [{'seq': pl.seq, 'topic': pl.topic, 'files': [x for x in map(lab, files[i]) if x]} for i, pl in enumerate(pls)],
            'projects': [p for p in projects if p['files']],
            'all': [{'file_id': f.id, 'label': f.label, 'questions': f.question_count, 'source': f.source_key}
                    for s in chosen for f in p0010_files(db, s, any_kind=s != src)]}


def _make(db: Session, user: User, ta, e: Exam, body: 'VariantsIn') -> None:
    """Bir sinif üçün variantlar (yaradılır və ya yenidən): nəticə yazılıbsa – 409, çatışmazlıq – 409 (mətnli)."""
    from ..domain.ksq_variants import Shortage, generate_auto, slots
    if db.scalar(select(ExamScore).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None))):
        raise HTTPException(409, 'Nəticələr yazılıb – variantları yenidən yaratmaq olmaz')
    students, topics, cands, hist, others, _ = _prepare(db, ta, e, body)
    if not students:
        raise HTTPException(400, 'Sinifdə şagird yoxdur')
    if not topics:
        raise HTTPException(400, 'Perspektiv planda bu imtahanın aralığında mövzu tapılmadı')
    try:
        res, share = generate_auto(students, topics, cands, hist, seed=e.id * 7919, n=body.n, others=others)
    except Shortage as sh:
        raise HTTPException(409, {'message': 'Bu mövzular üzrə layihədə (P0010) sual çatmır – sual sayını azaldın: ' + sh.message(),
                                  'shortage': sh.items, 'topics': [t for t, _ in topics]})
    for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)):
        db.delete(v)
    db.flush()
    for i, sid in enumerate(students):
        db.add(ExamVariant(exam_id=e.id, student_id=sid, code=f'{e.kind}{e.no}-{i + 1:02d}', questions=res[sid]))
    e.items = [{'n': s['slot'], 'points': s['points'], 'standard': None, 'kind': s['kind'], 'level': s['level']} for s in slots(body.n)]
    e.max_points = 100
    audit(db, user, 'create', 'exam_variants', e.id, students=len(students), topics=len(topics), share=share)


@router.post('/{ta_id}/{exam_id}/variants')
def make_variants(ta_id: int, exam_id: int, body: VariantsIn | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """n sual (10–30) / 100 bal; sinifdə hər şagirdə tam fərqli suallar; başqa siniflərin eyni imtahanı ilə ≤ 20% təkrar."""
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    _make(db, user, ta, e, body or VariantsIn())
    db.commit()
    return _variants_out(db, ta, e)


def _siblings(db: Session, user: User, ta) -> list:
    """Müəllimin eyni proqramlı (və eyni fənli) başqa sinifləri – KSQ/BSQ bir dəfəyə hazırlana bilər."""
    if not ta.program_id:
        return []
    return list(db.scalars(select(TeachingAssignment).where(TeachingAssignment.teacher_id == ta.teacher_id, TeachingAssignment.id != ta.id,
                                                            TeachingAssignment.program_id == ta.program_id, TeachingAssignment.subject == ta.subject)))


@router.get('/{ta_id}/{exam_id}/siblings')
def siblings(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    from ..models import SchoolClass
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    out = []
    for t in _siblings(db, user, ta):
        x = db.scalar(select(Exam).where(Exam.assignment_id == t.id, Exam.kind == e.kind, Exam.no == e.no, Exam.semester == e.semester))
        has_scores = bool(x and db.scalar(select(ExamScore).where(ExamScore.exam_id == x.id, ExamScore.points.is_not(None))))
        cls = db.get(SchoolClass, t.class_id)
        out.append({'ta_id': t.id, 'class_name': cls.name if cls else '', 'exam_id': x.id if x else None, 'date': x.date if x else None,
                    'variants': bool(x and db.scalar(select(ExamVariant.exam_id).where(ExamVariant.exam_id == x.id).limit(1))), 'locked': has_scores})
    return out


class MultiIn(VariantsIn):
    ta_ids: list[int] = Field(min_length=1, max_length=20)


@router.post('/{ta_id}/{exam_id}/variants-multi')
def make_variants_multi(ta_id: int, exam_id: int, body: MultiIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Eyni proqramlı bir neçə sinif üçün eyni ayarlarla variantlar (imtahan yoxdursa – eyni tarixlə yaradılır).
    Siniflərarası ≤ 20 % təkrar qaydası avtomatik işləyir; hər sinfin nəticəsi ayrıca qaytarılır."""
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    allowed = {t.id: t for t in _siblings(db, user, ta)} | {ta.id: ta}
    out = []
    for tid in dict.fromkeys(body.ta_ids):
        t = allowed.get(tid)
        if t is None:
            out.append({'ta_id': tid, 'ok': False, 'error': 'Bu sinfin proqramı fərqlidir'})
            continue
        x = db.scalar(select(Exam).where(Exam.assignment_id == t.id, Exam.kind == e.kind, Exam.no == e.no, Exam.semester == e.semester))
        if x is None:
            x = Exam(assignment_id=t.id, kind=e.kind, no=e.no, semester=e.semester, date=e.date, max_points=100, title=e.title)
            db.add(x)
            db.flush()
        try:
            with db.begin_nested():
                _make(db, user, t, x, body)
            out.append({'ta_id': tid, 'exam_id': x.id, 'ok': True})
        except HTTPException as ex:
            d = ex.detail
            out.append({'ta_id': tid, 'exam_id': x.id, 'ok': False, 'error': d.get('message') if isinstance(d, dict) else d})
    db.commit()
    return out
