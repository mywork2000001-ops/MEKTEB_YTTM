"""KSQ / BSQ: bal -> faiz -> qiymət (0–30→2, 31–60→3, 61–80→4, 81–100→5), tapşırıq üzrə ✓/✗,
tapşırıq və standart təhlili, yarımil qiyməti = (KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6."""
from __future__ import annotations

import copy
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import grade_from_points, semester_grade, year_grade
from ..models import BankQuestion, Exam, ExamAppeal, ExamScan, ExamScore, ExamVariant, OnlineTask, SchoolClass, TeachingAssignment, User, now
from ..appeals import freeze_refs, ref_of
from ..exam_logic import exam_label, exam_roster, final_grades, missed_ksq, recompute_score, scan_of
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
    extra_of: int | None = None                    # əlavə KSQ/BSQ: əsas imtahanın id-si
    extra_students: list[int] | None = None        # əlavə imtahan: yalnız bu şagirdlər (None – bütün sinif)
    send_on_scan: bool | None = None               # «skan olunan kimi şagirdə göndər» (None – dəyişmir / yeni imtahanda söndürülü)
    language: Literal['az', 'ru', 'az_ru'] | None = None   # imtahanın öz yazılı dili (istisna); None – sinfin qaydası

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
            'max_points': e.max_points, 'items': e.items, 'title': e.title,
            'extra_of': e.extra_of, 'extra_seq': e.extra_seq or 0, 'extra_students': e.extra_students, 'label': exam_label(e),
            'results_published_at': e.results_published_at, 'appeal_until': e.appeal_until,
            'online_task_id': e.online_task_id, 'batch_id': e.batch_id, 'to_journal': e.to_journal, 'variant_mode': e.variant_mode,
            'send_on_scan': bool(e.send_on_scan), 'language': e.language}


def _exam(db: Session, ta_id: int, exam_id: int) -> Exam:
    e = get_or_404(db, Exam, exam_id, 'İmtahan')
    if e.assignment_id != ta_id:
        raise HTTPException(404, 'İmtahan tapılmadı')
    return e


@router.get('/{ta_id}')
def list_exams(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    created = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind.in_(("KSQ", "BSQ")))
                              .order_by(Exam.semester, Exam.date, Exam.kind, Exam.extra_seq)))
    have = {(e.kind, e.semester, e.no) for e in created if not e.extra_seq}
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
    if body.extra_students is not None:
        if not body.extra_students:
            raise HTTPException(400, 'Əlavə imtahan üçün ən azı bir şagird seçin')
        if set(body.extra_students) - {s.id for s in roster(db, ta)}:
            raise HTTPException(400, 'Seçilən şagirdlərdən biri bu sinifdə deyil')
    if body.extra_of is not None:
        base = db.get(Exam, body.extra_of)
        if base is None or base.assignment_id != ta.id or base.extra_seq:
            raise HTTPException(404, 'Əsas imtahan tapılmadı')
        if (base.kind, base.semester, base.no) != (body.kind, body.semester, body.no):
            raise HTTPException(400, 'Əlavə imtahan əsasla eyni növ, nömrə və yarımildə olmalıdır')
        if body.date <= base.date:
            raise HTTPException(400, f'Əlavə imtahanın tarixi əsas imtahandan ({base.date:%d.%m.%Y}) sonra olmalıdır')
        return                                         # «yarımildə bir BSQ» qaydası yalnız əsas BSQ-yə aiddir
    if body.kind == 'BSQ':
        if body.no != body.semester:
            raise HTTPException(400, f'{body.semester}-ci yarımilin BSQ-si BSQ-{body.semester} olmalıdır')
        other = db.scalar(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind == 'BSQ', Exam.semester == body.semester,
                                             Exam.extra_seq == 0, Exam.id != (exam_id or 0)))
        if other:
            raise HTTPException(409, f'{body.semester}-ci yarımildə BSQ artıq var')


def _check_send_on_scan(db: Session, ta, body: ExamIn, e: Exam | None) -> None:
    """«Skan olunan kimi göndər» açılanda: eyni imtahan başqa sinifdə hələ keçirilməyibsə (tarixi gələcəkdədir) – 409."""
    if not body.send_on_scan:
        return
    from ..exam_cards import same_exam_elsewhere
    other = same_exam_elsewhere(db, ta, body.kind, body.no, body.semester, e.extra_seq if e else (1 if body.extra_of else 0), e.id if e else None)
    if other:
        raise HTTPException(409, f'«Skan olunan kimi göndər» bloklanıb: eyni imtahan «{other}» sinfində hələ keçirilməyib (suallar sızar). '
                                 'Həmin sinif yazandan sonra açın və ya «Nəticələri göndər» düyməsindən istifadə edin')


@router.post('/{ta_id}')
def create_exam(ta_id: int, body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    _check_exam(db, ta, body)
    if not ta.has_summative:
        raise HTTPException(400, 'Bu qrupda KSQ/BSQ keçirilmir (bütöv sinifdə keçirilir)')
    seq = 0
    _check_send_on_scan(db, ta, body, None)
    if body.extra_of is None:
        if body.extra_students is not None:
            raise HTTPException(400, 'Şagird seçimi yalnız əlavə imtahan üçündür')
        if db.scalar(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind == body.kind, Exam.extra_seq == 0,
                                        Exam.semester == body.semester, Exam.no == body.no)):
            raise HTTPException(409, f'{body.kind}-{body.no} ({body.semester}-ci yarımil) artıq var')
    else:                                              # əlavə: sıra nömrəsi max+1 (əlavə 1, 2, …)
        seq = 1 + (db.scalar(select(func.max(Exam.extra_seq)).where(
            Exam.assignment_id == ta.id, Exam.kind == body.kind, Exam.semester == body.semester, Exam.no == body.no)) or 0)
    e = Exam(extra_of=body.extra_of, extra_seq=seq, extra_students=sorted(set(body.extra_students)) if body.extra_students is not None else None,
             assignment_id=ta.id, kind=body.kind, no=body.no, semester=body.semester, date=body.date,
             max_points=body.max_points, items=[i.model_dump() for i in body.items] if body.items else None,
             title=body.title, send_on_scan=bool(body.send_on_scan), language=body.language)
    db.add(e)
    db.flush()
    audit(db, user, 'create', 'exam', e.id, kind=e.kind, no=e.no, extra_seq=seq)
    db.commit()
    return exam_out(e)


@router.patch('/{ta_id}/{exam_id}')
def update_exam(ta_id: int, exam_id: int, body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    if e.extra_seq:                                    # əlavə imtahan: növ/nömrə/yarımil əsasla bağlıdır, yalnız tarix, bal, şagirdlər
        if (body.kind, body.no, body.semester) != (e.kind, e.no, e.semester):
            raise HTTPException(400, 'Əlavə imtahanın növü, nömrəsi və yarımili dəyişdirilə bilməz')
        body.extra_of = e.extra_of
        if body.extra_students is None and e.extra_students is not None:
            body.extra_students = e.extra_students
    elif body.extra_of is not None or body.extra_students is not None:
        raise HTTPException(400, 'Əsas imtahan əlavəyə çevrilə bilməz')
    _check_exam(db, ta, body, e.id)
    _check_send_on_scan(db, ta, body, e)
    has_scores = db.scalar(select(ExamScore).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None)))
    if has_scores and (body.max_points != e.max_points or (body.items and len(body.items) != len(e.items or []))):
        raise HTTPException(409, 'Nəticələr yazılıb – maksimal bal və tapşırıq sayı dəyişdirilə bilməz')
    e.kind, e.no, e.semester, e.date, e.title = body.kind, body.no, body.semester, body.date, body.title
    e.max_points = body.max_points
    e.items = [i.model_dump() for i in body.items] if body.items else None
    if e.extra_seq:
        e.extra_students = sorted(set(body.extra_students)) if body.extra_students is not None else None
    if body.send_on_scan is not None:
        e.send_on_scan = body.send_on_scan
    if 'language' in body.model_fields_set:                # göndərilməyibsə – dəyişmir; null – «sinfin qaydası»
        e.language = body.language
    audit(db, user, 'update', 'exam', e.id)
    db.commit()
    return exam_out(e)


@router.delete('/{ta_id}/{exam_id}')
def delete_exam(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """KSQ/BSQ-ni silir: nəticələr, kağız variantlar, kart skanları (şəkillər daxil) birlikdə. Plan sətri qalır («Hazırla»)."""
    from ..storage import DbStorage
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    if db.scalar(select(Exam.id).where(Exam.extra_of == e.id).limit(1)):
        raise HTTPException(409, 'Bu imtahanın əlavələri var – əvvəlcə əlavə imtahanları silin')
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
    ids = {s.id for s in exam_roster(db, ta, e)}
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
        new_pts = None if s.absent else pts
        same = (sc.points is None and new_pts is None) or (sc.points is not None and new_pts is not None and abs(sc.points - new_pts) < 1e-6)
        if sc.chosen != 'manual' and not (same and bool(sc.absent) == s.absent):
            sc.chosen = 'manual'                       # müəllim balı əl ilə dəyişdi – sonrakı skan/təhvil üstələmir
        sc.points, sc.item_marks, sc.absent = (None if s.absent else pts), (None if s.absent else s.item_marks), s.absent
        sc.taken_on = s.taken_on
        db.merge(sc)
    audit(db, user, 'update', 'exam_scores', e.id, count=len(body))
    db.commit()
    return exam_result(ta_id, exam_id, user, db)


def _sources(e: Exam, scans: dict, sid: int) -> dict:
    """Onlayn və yazılı (kağız) nəticə yanaşı + «⚠ fərq» (qiymət fərqi ≥ 1)."""
    out = {}
    for src in ('online', 'paper'):
        sc = scans.get((sid, src))
        ok = sc is not None and sc.status == 'graded' and sc.points is not None
        out[src] = {'points': sc.points, 'grade': grade_from_points(sc.points, e.max_points)} if ok else None
    a, b = out['online'], out['paper']
    out['differs'] = bool(a and b and abs(a['grade'] - b['grade']) >= 1)
    return out


class PublishIn(BaseModel):
    published: bool = True
    appeal_days: int = Field(3, ge=1, le=30)           # apelyasiya müddəti (göndərişdən gün); təkrar göndərmə müddəti yeniləyir


@router.put('/{ta_id}/{exam_id}/publish')
def publish_results(ta_id: int, exam_id: int, body: PublishIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«📤 Nəticələri şagirdlərə göndər» / geri al: şagird yalnız bundan sonra öz cavab kartını (sual, cavab, düz cavab, bal) görür."""
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    e.results_published_at = (e.results_published_at or now()) if body.published else None
    e.appeal_until = (now() + dt.timedelta(days=body.appeal_days)) if body.published else None
    sent = 0
    if body.published:                                  # nəticə paketi bütün yazan şagirdlərə açılır + bildiriş/çat (şagird üzrə bir dəfə)
        from ..exam_cards import deliver_published
        sent = deliver_published(db, e)
    audit(db, user, 'update', 'exam_publish', e.id, published=body.published, sent=sent)
    db.commit()
    return {**exam_out(e), 'sent': sent}


@router.get('/{ta_id}/{exam_id}/cards')
def exam_cards_print(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«🖨 Cavab kartlarını çap et»: hər şagird üçün cavab kartı (ad, variant, sual cədvəli, bal, qiymət) – müəllim üçün, nəşrdən asılı deyil."""
    from ..exam_cards import exam_card
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    out = []
    for s in exam_roster(db, ta, e):
        c = exam_card(db, e, s.id)
        if c is not None and (c['sources'] or c['final']['points'] is not None):
            out.append({'student_id': s.id, 'full_name': s.full_name, **c})
    cls = db.get(SchoolClass, ta.class_id)
    return {'exam': exam_out(e), 'class_name': cls.name if cls else '', 'subject': ta.subject, 'cards': out}


@router.get('/{ta_id}/{exam_id}/packages')
def exam_packages(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllim: bütün sinfin nəticə paketləri (çap/PDF üçün – hər şagird ayrıca səhifədən). Nəşrdən asılı deyil, tam məzmun."""
    from ..exam_cards import student_package
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    out = []
    for s in exam_roster(db, ta, e):
        p = student_package(db, e, s.id, None, True)
        if p is not None:
            out.append({'student_id': s.id, 'full_name': s.full_name, **p})
    cls = db.get(SchoolClass, ta.class_id)
    return {'exam': exam_out(e), 'class_name': cls.name if cls else '', 'subject': ta.subject, 'packages': out}


@router.get('/{ta_id}/{exam_id}/delivery')
def exam_delivery(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Hər şagird sətrində göndəriş statusu: göndərilməyib / göndərildi (tarix) / baxıb."""
    from ..exam_cards import delivery_status
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    return {str(k): v for k, v in delivery_status(db, e, [s.id for s in exam_roster(db, ta, e)]).items()}


class ChoiceIn(BaseModel):
    chosen: Literal['online', 'paper', 'max', 'manual']
    points: float | None = Field(None, ge=0)         # yalnız «manual» üçün: jurnala əl ilə yazılan bal


class ChoiceAllIn(BaseModel):
    chosen: Literal['online', 'paper', 'max']


@router.put('/{ta_id}/{exam_id}/choice/{student_id}')
def set_choice(ta_id: int, exam_id: int, student_id: int, body: ChoiceIn, user: User = Depends(staff),
               db: Session = Depends(get_db)):
    """Müəllim jurnala gedəcək nəticəni seçir: onlayn / yazılı / ən yüksək / əl ilə (bal). «Əl ilə» – sonrakı skan və təhvil üstələmir."""
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    if student_id not in {s.id for s in exam_roster(db, ta, e)}:
        raise HTTPException(400, f'Şagird {student_id} bu imtahana aid deyil')
    if body.points is not None and (body.chosen != 'manual' or body.points > e.max_points):
        raise HTTPException(400, 'Bal yalnız «əl ilə» seçimində və maksimal baldan çox olmayaraq yazılır')
    score = db.get(ExamScore, (e.id, student_id)) or ExamScore(exam_id=e.id, student_id=student_id)
    old = {'chosen': score.chosen or 'max', 'points': score.points}
    score.chosen = body.chosen
    if body.chosen == 'manual':
        if body.points is not None:
            score.points, score.item_marks, score.absent = body.points, None, False
    db.add(score)
    db.flush()
    recompute_score(db, e, student_id)
    audit(db, user, 'update', 'exam_choice', e.id, student_id=student_id, old=old, new={'chosen': score.chosen, 'points': score.points})
    db.commit()
    return exam_result(ta_id, exam_id, user, db)


@router.put('/{ta_id}/{exam_id}/choice')
def set_choice_all(ta_id: int, exam_id: int, body: ChoiceAllIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Hamı üçün birdən («hamıya: ən yüksək»). «Əl ilə» seçilmiş şagirdlərə toxunulmur."""
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    changed = skipped = 0
    for s in exam_roster(db, ta, e):
        score = db.get(ExamScore, (e.id, s.id))
        if score is None and not any(scan_of(db, e.id, s.id, src) for src in ('online', 'paper')):
            continue
        if score is not None and score.chosen == 'manual':
            skipped += 1
            continue
        score = score or ExamScore(exam_id=e.id, student_id=s.id)
        score.chosen = body.chosen
        db.add(score)
        db.flush()
        recompute_score(db, e, s.id)
        changed += 1
    audit(db, user, 'update', 'exam_choice', e.id, all=body.chosen, changed=changed, skipped_manual=skipped)
    db.commit()
    return {**exam_result(ta_id, exam_id, user, db), 'changed': changed, 'skipped_manual': skipped}


@router.get('/{ta_id}/{exam_id}/as-sinaq')
def as_sinaq(ta_id: int, exam_id: int, mode: Literal['analog', 'same'] = 'analog', user: User = Depends(staff),
             db: Session = Depends(get_db)):
    """«Bu KSQ əsasında sınaq»: onlayn sınaq pəncərəsini dolduran məlumat (göndərmə YOXDUR). Seçim məntiqi – plan_tests.analog_pick."""
    from .. import plan_tests
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    r = plan_tests.analog_pick(db, ta, e.id, mode)
    from .tasks import _snapshot
    snaps = []
    for i in r['bank_ids']:                          # söndürülmüş mənbədən sual düşməsin – tək-tək, səhv olan atılır
        try:
            snaps += _snapshot(db, [i])
        except HTTPException:
            r['missing'].append(None)
    ok = {s['bank_id'] for s in snaps}
    return {'title': f'{exam_label(e)} – sınaq', 'mode': mode, 'bank_ids': [i for i in r['bank_ids'] if i in ok], 'missing': r['missing'],
            'fallback': r['fallback'], 'total': r['total'], 'questions': snaps, 'targets': [{'ta_id': ta.id}]}


@router.get('/{ta_id}/{exam_id}')
def exam_result(ta_id: int, exam_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    scores = {sc.student_id: sc for sc in db.scalars(select(ExamScore).where(ExamScore.exam_id == e.id))}
    scans = {(x.student_id, x.source): x for x in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id))}
    rows = [{'student_id': s.id, 'full_name': s.full_name, **_row(e, scores.get(s.id)),
             'chosen': scores[s.id].chosen if s.id in scores else 'max', **_sources(e, scans, s.id)}
            for s in exam_roster(db, ta, e)]
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
            'appeals_open': db.scalar(select(func.count()).select_from(ExamAppeal).where(ExamAppeal.exam_id == e.id, ExamAppeal.status == 'open')) or 0,
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
    all_exams = list(db.scalars(select(Exam).where(Exam.assignment_id == ta.id, Exam.kind.in_(("KSQ", "BSQ")))
                                .order_by(Exam.kind.desc(), Exam.no)))
    scores = {(sc.exam_id, sc.student_id): sc for sc in db.scalars(
        select(ExamScore).where(ExamScore.exam_id.in_([e.id for e in all_exams])))}
    from ..services import plan_ctx
    from .exams_online import class_exams, exam_stats
    y = plan_ctx(db, ta).year
    exs = class_exams(db, ta, None if sem == 1 else y.sem2_start, y.sem1_end if sem == 1 else None)
    now_d = today()

    def calc(k: int, s):
        mine = [e for e in all_exams if e.semester == k and (e.extra_students is None or s.id in e.extra_students)]
        ksq, bsq = final_grades(mine, lambda e: _row(e, scores.get((e.id, s.id)))['grade'])
        grades = [g for _, g in ksq if g is not None]
        return ksq, bsq, grades, semester_grade(grades, bsq), missed_ksq(mine, ksq, now_d)
    out = []
    for s in roster(db, ta, since=y.start if sem == 1 else y.sem2_start):      # dövr ərzində çıxanlar da (rəsmi jurnal)
        ksq, bsq, ksq_grades, sg, missed = calc(sem, s)
        other = calc(2 if sem == 1 else 1, s)[3]
        out.append({'student_id': s.id, 'full_name': s.full_name, 'left_on': s.left_on if s.archived_at else None,
                    'ksq': ksq, 'bsq': bsq,
                    'ksq_avg': round(sum(ksq_grades) / len(ksq_grades), 2) if ksq_grades else None,
                    'semester_grade': sg,
                    # buraxılmış KSQ var – qiymət mövcud KSQ-lərə görə hesablanır, lakin «şərti» (⚠: əlavə KSQ təyin edin)
                    'conditional': bool(missed), 'missed_ksq': missed,
                    'year_grade': year_grade(*((sg, other) if sem == 1 else (other, sg))),
                    **exam_stats(exs, s.id)})
    return {'semester': sem, 'formula': '(KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6', 'students': out,
            'exams': len(exs)}


# ---------------------------------------------------------------- kağız variantları (docs/ksq-bsq-kagiz-promtu.md)
def _range_lessons(db: Session, ta, e: Exam) -> list:
    """İmtahanın aralığındakı plan dərsləri (mövzu təkrarlanmır) – _range_topics ilə eyni qayda."""
    from ..bank.match import derived                      # zəif tempin məşq/təkrar dərsləri ayrıca mövzu deyil
    lessons = [pl for pl in plan_ctx(db, ta).lessons if pl.semester == e.semester]
    lessons.sort(key=lambda pl: pl.seq)
    me = next((pl for pl in lessons if pl.assessment_type == e.kind and pl.exam_no == e.no), None)
    end = me.seq if me else max((pl.seq for pl in lessons if pl.date <= e.date), default=10 ** 9)
    start = max((pl.seq for pl in lessons if pl.assessment_type in ('KSQ', 'BSQ') and pl.seq < end), default=0) if e.kind == 'KSQ' else 0
    out, seen = [], set()
    for pl in lessons:
        if start < pl.seq < end and pl.assessment_type not in ('KSQ', 'BSQ') and pl.topic and pl.topic not in seen and not derived(pl.topic):
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
    if ta.ksq_source:
        return ta.ksq_source
    from ..bank.match import ta_source
    if ta.bank_source and ta.bank_source != 'none':
        return ta_source(db, ta)
    from ..bank.match import source_for
    from ..models import SchoolClass
    from ..services import class_grade
    return source_for(class_grade(db, db.get(SchoolClass, ta.class_id))) or 'p003'


def _range_topics(db: Session, ta, e: Exam) -> list[tuple[str, str | None]]:
    """KSQ: əvvəlki KSQ/BSQ-dan bu imtahana qədər keçilmiş dərslərin mövzuları; BSQ: yarımilin bütün mövzuları (təkrarsız, ardıcıl)."""
    from ..bank.match import derived                      # zəif tempin məşq/təkrar dərsləri ayrıca mövzu deyil
    lessons = [pl for pl in plan_ctx(db, ta).lessons if pl.semester == e.semester]
    lessons.sort(key=lambda pl: pl.seq)
    me = next((pl for pl in lessons if pl.assessment_type == e.kind and pl.exam_no == e.no), None)
    end = me.seq if me else max((pl.seq for pl in lessons if pl.date <= e.date), default=10 ** 9)
    start = 0
    if e.kind == 'KSQ':
        start = max((pl.seq for pl in lessons if pl.assessment_type in ('KSQ', 'BSQ') and pl.seq < end), default=0)
    out, seen = [], set()
    for pl in lessons:
        if start < pl.seq < end and pl.assessment_type not in ('KSQ', 'BSQ') and pl.topic and pl.topic not in seen and not derived(pl.topic):
            seen.add(pl.topic)
            out.append((pl.topic, pl.section))
    return out


def _history(db: Session, ta, e: Exam, student_ids: list[int]) -> dict[int, set[str]]:
    """Şagirdə əvvəl verilmiş suallar: bu dərsin onlayn testləri/sınaqları + digər KSQ/BSQ variantları."""
    hist: dict[int, set[str]] = {sid: set() for sid in student_ids}
    bank_keys: dict[int, str] = {}
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id,      # onlayn KSQ – variantın özüdür
                                                     (OnlineTask.kind.is_(None)) | (OnlineTask.kind != 'ksq'))))
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


def _base_info(db: Session, ta, e: Exam) -> dict | None:
    from ..domain import ksq_base
    b = ksq_base.get(db, ta, e)
    return b and {'topics': len(b.topics or []), 'files': len(b.files or []), 'edits': len(b.edits or {}), 'excluded': len(b.excluded or []),
                  'updated_at': b.updated_at}


def _variants_out(db: Session, ta, e: Exam) -> dict:
    from collections import Counter
    from ..domain import own_numbers
    from ..domain.ksq_variants import RULES_V, fairness
    names = {s.id: s.full_name for s in exam_roster(db, ta, e)}
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    vs.sort(key=lambda v: v.code)
    return {'exam': exam_out(e), 'variants': [{'student_id': v.student_id, 'full_name': names.get(v.student_id), 'code': v.code,
                                               'questions': [{**q, 'ref': ref_of(db, q)} for q in v.questions]} for v in vs],
            'report': fairness({v.student_id: v.questions for v in vs}) if vs else None,
            # köhnə qaydalarla yaradılıb (mövzudan kənar sual ola bilər) – müəllimə «Yenidən yarat» təklif olunur
            'stale': any(q.get('v', 0) < RULES_V or q.get('template') for v in vs for q in v.questions if not q.get('edited')),
            'own_numbers': own_numbers.report_of(vs[0].questions) if vs else None,
            'share': max(Counter(q.get('key') for v in vs for q in v.questions).values(), default=0),
            'base': _base_info(db, ta, e),
            'printed_at': max((v.printed_at for v in vs if v.printed_at), default=None),
            'suspects': _suspects(db, e, names)}


def _suspects(db: Session, e: Exam, names: dict[int, str]) -> list[dict]:
    """Köçürmə şübhəsi ilə yeni variant verilmiş şagirdlər (docs/kocurme-subhesi-hesabat-promtu.md): audit jurnalından
    silinmə tarixçəsi (kim, nə vaxt, kod, nə silindi) + yeni yazının icrası (çap, skan/onlayn, yeni bal)."""
    from ..models import AuditLog, ExamScan, now
    from .ksq_online import _attempt, _status, _tasks
    out: dict[int, dict] = {}
    who: dict[int, str] = {}
    for a in db.scalars(select(AuditLog).where(AuditLog.entity == 'exam_variant', AuditLog.entity_id == str(e.id)).order_by(AuditLog.at)):
        d = a.details or {}
        if d.get('op') != 'retake' or d.get('student_id') is None:
            continue
        sid = d['student_id']
        if a.user_id and a.user_id not in who:
            u = db.get(User, a.user_id)
            who[a.user_id] = u.full_name if u else ''
        x = out.setdefault(sid, {'student_id': sid, 'full_name': names.get(sid), 'times': 0, 'old_score': None, 'history': []})
        x['times'] += 1
        x['at'], x['code'], x['note'] = a.at, d.get('new_code'), d.get('note')
        if x['old_score'] is None:
            x['old_score'] = d.get('score')                    # ilk (şübhəli) yazının balı
        x['history'].insert(0, {'at': a.at, 'by': who.get(a.user_id), 'old_code': d.get('old_code'), 'new_code': d.get('new_code'),
                                'note': d.get('note'), 'deleted': {k: d.get(k) for k in ('scan_points', 'read_by', 'online', 'score')}})
    if out:
        tasks, at = _tasks(db, e), now()
        for sid, x in out.items():
            v = db.get(ExamVariant, (e.id, sid))
            sc = db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == sid).order_by(ExamScan.source.desc())).first()
            score = db.get(ExamScore, (e.id, sid))
            t = tasks.get(sid)
            online = _status(t, _attempt(db, t, sid) if t else None, at)
            x['printed_at'] = v.printed_at if v else None
            # icra: yazıb (bal) → kart oxunur → onlayn göndərilib → gözlənilir
            st = ('done' if score is not None and score.points is not None else 'reading' if sc is not None
                  else 'online' if online in ('waiting', 'open', 'doing') else 'missed' if online == 'missed' else 'waiting')
            x['now'] = {'status': st, 'points': score.points if score is not None else None,
                        'online': online, 'read_by': sc.read_by if sc is not None else None}
    return sorted(out.values(), key=lambda x: x['full_name'] or '')


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
    v.questions = freeze_refs(db, qs)
    from ..domain import ksq_base
    ksq_base.exclude(db, ta, e, old.get('key'))                  # gələn il bu sual seçilməsin
    _rescore(db, e, [student_id])
    audit(db, user, 'update', 'exam_variant', e.id, student_id=student_id, slot=slot, op='replace')
    db.commit()
    return qs[i]


class RetakeIn(BaseModel):
    note: str | None = Field(None, max_length=300)             # müəllimin qeydi (məs. «köçürmə şübhəsi») – audit jurnalına


@router.post('/{ta_id}/{exam_id}/variants/{student_id}/retake')
def retake(ta_id: int, exam_id: int, student_id: int, body: RetakeIn | None = None, user: User = Depends(staff),
           db: Session = Depends(get_db)):
    """Köçürmə şübhəsi (docs/kocurme-subhesi-yeni-variant-promtu.md): şagirdin cavabları (kağız skan, onlayn cəhd) və balı
    silinir, ona TAM YENİ variant verilir – hər slot eyni növ/çətinlik/bal, amma sinifdə və şagirdin tarixçəsində olmayan sual;
    kod dəyişir (KSQ1-05 → KSQ1-05R1), ona görə köhnə vərəqin kartı artıq qəbul olunmur. Vərəq yenidən çap olunmalıdır."""
    import random
    import re
    from ..domain.ksq_variants import norm_text, pick_one
    from ..models import ExamScan, TaskAttempt, now
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    v = db.get(ExamVariant, (e.id, student_id))
    if v is None:
        raise HTTPException(404, 'Variant tapılmadı')
    students, topics, cands, hist, others, _ = _prepare(db, ta, e, VariantsIn(n=len(v.questions)))
    all_vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    taken = {q.get('key') for x in all_vs for q in x.questions} | others
    used = taken | {norm_text(q.get('text')) for x in all_vs for q in x.questions} | hist.get(student_id, set())
    rnd = random.Random()
    qs, missing = [], []
    from ..domain import own_numbers
    own_mode = own_numbers.is_own_mode(v.questions)                  # «öz rəqəmləri» variantı: eyni suallar, yalnız ədədlər yenilənir
    for old in sorted(v.questions, key=lambda q: q['slot']):
        if own_mode:
            if old.get('own_numbers'):
                avoid = {own_numbers.sig_of(q) for x in all_vs for q in x.questions if q.get('slot') == old['slot']}
                got = own_numbers.renew(old, f'{e.kind}{e.no}-{e.id}', student_id, avoid, start=own_numbers.next_salt(v.code),
                                        pool=len(all_vs))
                if got is None:
                    missing.append(old['slot'])
                    continue
                qs.append(got)
            else:
                qs.append(copy.deepcopy(old))
            continue
        got = pick_one(old, topics, cands, used, rnd.randrange(10 ** 9))
        if got is None:
            missing.append(old['slot'])
            continue
        used |= {got.get('key'), norm_text(got.get('text'))}
        qs.append({**got, 'slot': old['slot'], 'kind': old['kind'], 'level': old['level'], 'topic': old.get('topic'), 'points': old['points']})
    if missing:
        raise HTTPException(409, f'Yeni variant üçün sual çatmır (slotlar: {", ".join(map(str, missing))}) – heç nə dəyişmədi')
    old_code = v.code
    base = re.sub(r'R\d+$', '', old_code)
    k = int(m.group(1)) + 1 if (m := re.search(r'R(\d+)$', old_code)) else 1
    codes = {x.code for x in all_vs}
    while f'{base}R{k}' in codes:
        k += 1
    v.code, v.questions, v.printed_at, v.unprinted, v.created_at = f'{base}R{k}', qs, None, None, now()
    # cavablar və bal silinir (kəsik şəkli storage-da qalır – sübut kimi; açarı audit jurnalında)
    gone = {}
    for sc in db.scalars(select(ExamScan).where(ExamScan.exam_id == e.id, ExamScan.student_id == student_id).order_by(ExamScan.source.desc())):
        if not gone:
            gone = {'scan_points': sc.points, 'read_by': sc.read_by, 'crop_key': sc.crop_key}
        db.delete(sc)
    score = db.get(ExamScore, (e.id, student_id))
    if score is not None:
        gone['score'] = score.points
        db.delete(score)
    for t in list(db.scalars(select(OnlineTask).where(OnlineTask.exam_id == e.id))):
        if student_id in (t.student_ids or []):
            for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id)):
                db.delete(a)
            db.delete(t)
            gone['online'] = True
    audit(db, user, 'update', 'exam_variant', e.id, student_id=student_id, op='retake', old_code=old_code, new_code=v.code,
          note=(body.note if body else None), **gone)
    db.commit()
    return {'student_id': student_id, 'code': v.code, 'old_code': old_code, 'questions': len(qs), 'deleted': gone}


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
        v.questions = freeze_refs(db, qs)
        done += 1
    from ..domain import ksq_base
    for k in olds:
        ksq_base.exclude(db, ta, e, k)
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
        v.questions = freeze_refs(db, qs)
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
    for e in db.scalars(select(Exam).where(Exam.kind.in_(("KSQ", "BSQ")), Exam.id.in_(select(ExamVariant.exam_id).distinct()))):
        if db.scalar(select(ExamScore.exam_id).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None)).limit(1)):
            continue
        if db.scalar(select(ExamVariant.exam_id).where(ExamVariant.exam_id == e.id, ExamVariant.printed_at.is_not(None)).limit(1)):
            continue                                          # çap olunub – kağızla uyğunluq pozulmasın
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
    text: str | None = Field(None, min_length=1, max_length=3000)     # None – mətn dəyişmir (skan ekranından yalnız açar)
    options: list[str] | None = Field(None, max_length=5)              # None – variantlar dəyişmir
    correct: int | None = Field(None, ge=0, le=4)
    answer: str | None = Field(None, max_length=60)
    all_same: bool = False                                             # eyni bank sualı olan bütün variantlarda açar


def _edit_q(q: dict, body: QuestionEditIn, key_only: bool) -> dict:
    """Bir sualın düzəlişi. Çapdan sonra açar dəyişsə də kağız dəyişmir – çap izi (variant_rev) ilk qiymətlə qalır."""
    from ..domain.ksq_variants import card_answer
    q = dict(q)
    if not key_only and body.text is not None:
        q['text'] = {**(q['text'] if isinstance(q.get('text'), dict) else {}), 'az': body.text}
    q.setdefault('rev_correct', q.get('correct'))
    q.setdefault('rev_answer', q.get('answer'))
    if q['kind'] == 'mcq':
        opts = [{'az': o} for o in body.options] if (body.options and not key_only) else (q.get('options') or [])
        if len(opts) < 2 or body.correct is None or body.correct >= len(opts):
            raise HTTPException(400, 'Test sualı üçün ən azı 2 variant və düzgün cavab lazımdır')
        q['options'], q['correct'] = opts, body.correct
    else:
        if not card_answer(body.answer):
            raise HTTPException(400, 'Açıq cavab kartın xanalarına yazıla bilməlidir: rəqəm, «-», «,», «/», «;» (≤ 8 simvol)')
        q['answer'] = body.answer
    q['edited'] = True
    return q


def apply_key_edit(db: Session, e: Exam, student_id: int, slot: int, body: QuestionEditIn) -> tuple[dict, list[int], int]:
    """Sualın düzəlişi (bir yerdə: PUT variants/... və apelyasiyadan düzəliş): variant(lar), baza qeydi, yenidən hesab. Commit/audit – çağıran."""
    v, i = _variant(db, e, student_id, slot)
    base = v.questions[i]
    q = _edit_q(base, body, key_only=False)
    qs = list(v.questions)
    qs[i] = q
    v.questions = freeze_refs(db, qs)
    students = [student_id]
    if body.all_same and base.get('key'):
        for o in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id, ExamVariant.student_id != student_id)):
            hit = [k for k, x in enumerate(o.questions) if x.get('key') == base['key']]
            if hit:
                oq = list(o.questions)
                for k in hit:
                    oq[k] = _edit_q(oq[k], body, key_only=True)
                o.questions = freeze_refs(db, oq)
                students.append(o.student_id)
    from ..domain import ksq_base
    ksq_base.note_edit(db, db.get(TeachingAssignment, e.assignment_id), e, q.get('key'),
                       {**({'text': body.text} if body.text is not None else {}),       # yalnız açar – mətn bazada dəyişmir
                        'options': q.get('options') if q['kind'] == 'mcq' else None, 'correct': body.correct, 'answer': body.answer})
    return q, students, _rescore(db, e, students)


@router.put('/{ta_id}/{exam_id}/variants/{student_id}/{slot}')
def edit_question(ta_id: int, exam_id: int, student_id: int, slot: int, body: QuestionEditIn,
                  user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sualın mətni / variantları / düzgün cavabı düzəldilir; all_same – eyni bank sualı olan bütün variantlarda açar
    (docs/skan-sayac-ve-donma-promtu.md). Skanı olanların balı yenidən hesablanır, jurnal yenilənir."""
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    q, students, n = apply_key_edit(db, e, student_id, slot, body)
    audit(db, user, 'update', 'exam_variant', e.id, student_id=student_id, slot=slot, op='edit', students=len(students))
    db.commit()
    return {**q, 'rescored': n, 'students': len(students)}


class AnnulIn(BaseModel):
    annulled: bool = True


def apply_annul(db: Session, e: Exam, slot: int, annulled: bool = True) -> int:
    """Slotu hamı üçün ləğv edir / geri qaytarır və balları yenidən hesablayır. Commit/audit – çağıran."""
    if not e.items or not any(it['n'] == slot for it in e.items):
        raise HTTPException(404, 'Slot tapılmadı')
    if annulled and sum(1 for it in e.items if it.get('annulled') or it['n'] == slot) >= len(e.items):
        raise HTTPException(400, 'Bütün sualları ləğv etmək olmaz')
    e.items = [{**it, 'annulled': annulled} if it['n'] == slot else it for it in e.items]
    return _rescore(db, e)


@router.post('/{ta_id}/{exam_id}/slots/{slot}/annul')
def annul_slot(ta_id: int, exam_id: int, slot: int, body: AnnulIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Slotu hamı üçün ləğv edir (səhv sual): bal hesablanmır, qalan ballar 100-ə miqyaslanır; geri qaytarmaq olar."""
    own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    n = apply_annul(db, e, slot, body.annulled)
    audit(db, user, 'update', 'exam', e.id, slot=slot, annulled=body.annulled)
    db.commit()
    return {'ok': True, 'rescored': n, 'items': e.items}


@router.get('/{ta_id}/{exam_id}/variants/print')
def print_variants(ta_id: int, exam_id: int, students: str | None = None, blank: bool = False, user: User = Depends(staff),
                   db: Session = Depends(get_db)):
    """Çap üçün: hər şagirdə bir A4 (iki üz) – suallar şagirdin dilində (yoxdursa AZ), cavab kartı üçün imzalı QR; müəllim açarı.
    Düzgün cavablar yalnız açarda (vərəqdə yox). students="5,7" – yalnız bu şagirdlərin vərəqi (məs. köçürmə şübhəsindən sonra)."""
    from ..domain.exam_lang import exam_lang, missing_translations, render_question
    from ..domain.ksq_card import key_value, qr_payload, variant_rev
    from ..models import now as _now
    from ..models import SchoolClass, Student
    from .lessonplans import header_school
    ta = own_assignment(db, user, ta_id)
    e = _exam(db, ta_id, exam_id)
    vs = list(db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)))
    if not vs:
        raise HTTPException(409, 'Əvvəl variantları yaradın')
    if students:
        only = {int(x) for x in students.split(',') if x.strip().isdigit()}
        vs = [v for v in vs if v.student_id in only]
        if not vs:
            raise HTTPException(404, 'Bu şagirdin variantı yoxdur')
    vs.sort(key=lambda v: v.code)
    if blank:                                      # boş forma: bütün variantlar eyni olanda (hamıya eyni suallar) – şagirdsiz bir vərəq
        sig = {variant_rev(v.questions) for v in vs}
        if len(sig) != 1:
            raise HTTPException(409, 'Boş forma yalnız «hamıya eyni suallar» olan işdə mümkündür')
        from ..domain.ksq_card import BLANK_CODE, blank_qr
        mode = exam_lang(db, e, db.get(SchoolClass, ta.class_id))
        ex = {**exam_out(e), 'class_name': (db.get(SchoolClass, ta.class_id).name if db.get(SchoolClass, ta.class_id) else ''),
              'subject': ta.subject, 'school': header_school(user), 'teacher': user.full_name, 'label': exam_label(e), 'lang': mode}
        qs = sorted(vs[0].questions, key=lambda q: q['slot'])
        miss = missing_translations(qs, mode)
        ex.update(missing_translations=len(miss), missing_detail=[{'full_name': '', 'code': BLANK_CODE, 'slots': miss}] if miss else [])
        return {'exam': ex, 'key': [], 'sheets': [{
            'student_id': 0, 'full_name': '', 'code': BLANK_CODE, 'lang': mode, 'qr': blank_qr(e.id),
            'questions': [_sheet_q(q, mode) for q in qs]}]}
    studs = {s.id: s for s in db.scalars(select(Student).where(Student.id.in_([v.student_id for v in vs])))}
    cls = db.get(SchoolClass, ta.class_id)
    mode = exam_lang(db, e, cls)           # dil sinfin/imtahanın qaydasından – şagirdin interfeys dili vərəqə təsir etmir
    sheets, key, miss_detail = [], [], []
    for v in vs:
        st = studs.get(v.student_id)
        qs = sorted(v.questions, key=lambda q: q['slot'])
        miss = missing_translations(qs, mode)
        if miss:
            miss_detail.append({'full_name': st.full_name if st else '—', 'code': v.code, 'slots': miss})
        sheets.append({'student_id': v.student_id, 'full_name': st.full_name if st else '—', 'code': v.code, 'lang': mode,
                       'qr': qr_payload(e.id, v.student_id, f'{v.code}~{variant_rev(v.questions)}'),   # kart variantın versiyasına bağlı
                       'questions': [_sheet_q(q, mode) for q in qs]})   # altmövzu şagird vərəqində yoxdur (açarda var)
        key.append({'code': v.code, 'full_name': st.full_name if st else '—',      # bank ünvanı (ref) yalnız müəllim açarında – şagird vərəqində yox
                    'answers': [{'slot': q['slot'], 'value': key_value(q), 'points': q['points'], 'topic': q.get('topic_actual') or q.get('topic'),
                                 'ref': (ref_of(db, q) or {}).get('text')} for q in qs]})
    for v in vs:
        v.printed_at = v.printed_at or _now()                 # çap olunub – fon işi bu variantlara toxunmur
    db.commit()
    return {'exam': {**exam_out(e), 'class_name': cls.name if cls else '', 'subject': ta.subject, 'school': header_school(user),
                     'teacher': user.full_name, 'label': exam_label(e), 'lang': mode,
                     'missing_translations': sum(len(m['slots']) for m in miss_detail), 'missing_detail': miss_detail},
            'sheets': sheets, 'key': key}


def _sheet_q(q: dict, mode: str) -> dict:
    """Vərəqdə sual: mətn/variantlar imtahan dilində (az_ru – text_sub/options_sub altda RU)."""
    from ..domain.exam_lang import render_question
    r = render_question(q, mode)
    return {'slot': q['slot'], 'kind': q['kind'], 'points': q['points'], 'text': r['text'], 'options': r['options'],
            'text_sub': r['text_sub'], 'options_sub': r['options_sub'], 'image': q.get('image')}


class VariantsIn(BaseModel):
    n: int = Field(30, ge=10, le=30)                 # sual sayı – müəllim seçir
    file_ids: list[int] | None = Field(None, max_length=60)    # müəllimin seçdiyi testlər – plana ƏLAVƏ olunur
    only_mine: bool = False                                   # True – yalnız seçilən testlər (plan nəzərə alınmır)
    share: int = Field(1, ge=1, le=2)                          # bir sual sinifdə ən çox neçə şagirdə (çatışmazlıqda 2)
    sources: list[str] | None = Field(None, max_length=20)     # test layihələri (bank mənbələri); boş – sinfin əsas layihəsi
    mcq_only: bool = False                                     # yalnız qapalı (test) suallar – məs. DİM sinif testi
    same_for_all: bool = False                                 # hamıya eyni variant, mövzu-mövzu (DİM sinif testi kimi)
    own_numbers: bool = False                                  # hamıya eyni suallar, hər şagirdə öz rəqəmləri (same_for_all-ı da işə salır)

    @model_validator(mode='after')
    def _own_implies_same(self):
        if self.own_numbers:
            self.same_for_all = True
        return self


def _prepare(db: Session, ta, e: Exam, body: 'VariantsIn') -> tuple:
    """Generator üçün hər şey: şagirdlər, mövzular, namizədlər, tarixçə, başqa siniflərin sualları."""
    from ..domain.ksq_variants import bank_candidates
    students = [s.id for s in exam_roster(db, ta, e)]
    topics = _range_topics(db, ta, e)
    src = _source(db, ta)
    _, files = _plan_files(db, ta, e, body.sources or [src])
    if body.file_ids:
        files = {-1: list(dict.fromkeys(body.file_ids))} if body.only_mine else {**files, -1: list(dict.fromkeys(body.file_ids))}
    same = select(Exam.id).join(TeachingAssignment, TeachingAssignment.id == Exam.assignment_id).where(
        TeachingAssignment.teacher_id == ta.teacher_id, Exam.kind == e.kind, Exam.no == e.no, Exam.semester == e.semester, Exam.id != e.id)
    others = {q.get('key') for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id.in_(same))) for q in v.questions if q.get('key')}
    from ..domain import ksq_base
    cands = ksq_base.apply(db, ta, e, bank_candidates(db, topics, src, files))      # gələcək illər: istisnalar və düzəlişlər
    return students, topics, cands, _history(db, ta, e, students), others, files


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
        mx = cap_n(cands, body.n, body.mcq_only)                          # generasiyasız – hovuzun ölçüsündən
        try:
            if body.same_for_all:                                         # hamıya eyni – bir variant kifayətdir
                from ..domain.ksq_variants import same_variant
                same_variant(cands, body.n, seed=e.id * 7919, mcq_only=body.mcq_only)
                share, mx = len(students), body.n
            else:
                _, share = generate_auto(students, topics, cands, hist, seed=e.id * 7919, n=body.n, others=others, mcq_only=body.mcq_only)
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


def _guard(db: Session, ta, e: Exam, res: dict, body: 'VariantsIn') -> None:
    """Məcburi yoxlama – variant bazaya yazılmazdan ƏVVƏL (şablon, layihədən/aralıqdan kənar sual, variantda təkrar)."""
    from ..domain import ksq_base
    _, files = _plan_files(db, ta, e, body.sources or [_source(db, ta)])
    allowed = {f for lst in files.values() for f in lst} | set(body.file_ids or [])
    ids = [q.get('bank_id') for qs in res.values() for q in qs if q.get('bank_id')]
    file_of = {b.id: b.file_id for b in db.scalars(select(BankQuestion).where(BankQuestion.id.in_(ids or [0])))}
    srcs = set(body.sources or [_source(db, ta)])
    if body.file_ids:
        from ..models import BankFile
        srcs |= {f.source_key for f in db.scalars(select(BankFile).where(BankFile.id.in_(body.file_ids)))}
    errs = ksq_base.validate(res, allowed, file_of, srcs)
    if errs:
        raise HTTPException(500, 'Variant yoxlamadan keçmədi (yazılmadı): ' + '; '.join(errs[:5]))


def _make(db: Session, user: User, ta, e: Exam, body: 'VariantsIn') -> None:
    """Bir sinif üçün variantlar (yaradılır və ya yenidən): nəticə yazılıbsa – 409, çatışmazlıq – 409 (mətnli)."""
    from ..domain.ksq_variants import Shortage, generate_auto, slots
    if db.scalar(select(ExamScore).where(ExamScore.exam_id == e.id, ExamScore.points.is_not(None))):
        raise HTTPException(409, 'Nəticələr yazılıb – variantları yenidən yaratmaq olmaz')
    students, topics, cands, hist, others, files = _prepare(db, ta, e, body)
    if not students:
        raise HTTPException(400, 'Sinifdə şagird yoxdur')
    if not topics:
        raise HTTPException(400, 'Perspektiv planda bu imtahanın aralığında mövzu tapılmadı')
    try:
        if body.same_for_all:                                             # hamıya eyni variant (DİM sinif testi kimi)
            import copy
            from ..domain.ksq_variants import same_variant
            one = same_variant(cands, body.n, seed=e.id * 7919, mcq_only=body.mcq_only)
            res, share = {sid: copy.deepcopy(one) for sid in students}, len(students)
            if body.own_numbers:                                          # eyni suallar, fərqli ədədlər (variantda donur)
                from ..domain import own_numbers
                res, _rep = own_numbers.apply(one, students, f'{e.kind}{e.no}-{e.id}')
        else:
            res, share = generate_auto(students, topics, cands, hist, seed=e.id * 7919, n=body.n, others=others, mcq_only=body.mcq_only)
        _guard(db, ta, e, res, body)
    except Shortage as sh:
        raise HTTPException(409, {'message': 'Bu mövzular üzrə layihədə (P0010) sual çatmır – sual sayını azaldın: ' + sh.message(),
                                  'shortage': sh.items, 'topics': [t for t, _ in topics]})
    for v in db.scalars(select(ExamVariant).where(ExamVariant.exam_id == e.id)):
        db.delete(v)
    db.flush()
    for i, sid in enumerate(students):
        db.add(ExamVariant(exam_id=e.id, student_id=sid, code=f'{e.kind}{e.no}-{i + 1:02d}', questions=freeze_refs(db, res[sid])))
    plan_ = next(iter(res.values())) if body.same_for_all else slots(body.n, body.mcq_only)
    e.items = [{'n': s['slot'], 'points': s['points'], 'standard': None, 'kind': s['kind'], 'level': s['level']} for s in plan_]
    e.max_points = 100
    e.variant_mode = 'numbers' if body.own_numbers else None
    from ..domain import ksq_base
    ksq_base.remember(db, ta, e, topics, files, user.id if user else None)
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
