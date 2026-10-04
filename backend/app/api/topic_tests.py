"""Mövzu testi: perspektiv planın mövzusuna onlayn test təyin etmək – eyni mövzunu keçən digər siniflərə də eyni anda.

- «Eyni mövzu»: müəllimin öz dərsləri, eyni fənn, eyni sinif rəqəmi; mövzu normallaşdırılmış mətnə görə tapılır
  (kiçik hərf, durğu, «ə/e» fərqi nəzərə alınmır), tapılmırsa müəllim həmin sinfin planından əl ilə seçir.
- Default vaxt: həmin sinifdə mövzunun işçi plan üzrə dərsinin sonu → ertəsi gün 22:00 (Bakı vaxtı).
- Bütün siniflər bir tranzaksiyada yaradılır: biri səhvdirsə, heç biri yaranmır.
- Bağlananda nəticə formativ jurnala yazılır (app/task_journal.py)."""
from __future__ import annotations

import copy
import datetime as dt
import re
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..services import ws_cond
from ..db import get_db
from ..deps import staff
from ..models import (LevelOverride, OnlineTask, PlanLesson, SchoolClass, TaskAttempt, TeachingAssignment, TestBatch, User,
                      now)
from ..services import SCHOOL_TZ, class_grade, own_assignment, plan_ctx, roster
from .common import audit
from .plan import bell
from .tasks import CustomQ, _snapshot, aware, custom_snapshot, task_out

router = APIRouter(prefix='/api', tags=['topic-tests'])
TZ = ZoneInfo(SCHOOL_TZ)


def norm_topic(s: str | None) -> str:
    s = (s or '').lower().replace('ə', 'e').replace('i̇', 'i')
    s = re.sub(r'[^\w\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _lesson_end(db: Session, cls: SchoolClass, d: dt.date, period: int, ta=None) -> dt.datetime:
    """Dərsin bitmə anı (fərdi qrupun vaxtı / sinfin / məktəbin zəngi); zəng yoxdursa – 15:00."""
    t = bell(db, cls, period, ta, d) or ''
    m = re.search(r'(\d{1,2}):(\d{2})\s*$', t.replace('–', '-'))
    h, mi = (int(m.group(1)), int(m.group(2))) if m else (15, 0)
    return dt.datetime(d.year, d.month, d.day, h, mi, tzinfo=TZ)


def _defaults(db: Session, ctx, pl_id: int) -> dict:
    """Mövzunun işçi plan üzrə (sonuncu) dərsi və default açılma/bağlanma vaxtı."""
    slots = [s for s in ctx.slots if (pl := ctx.lesson_for(s)) is not None and pl.id == pl_id]
    if not slots:
        return {'working_date': None, 'period': None, 'opens_at': None, 'closes_at': None}
    s = slots[-1]
    o = _lesson_end(db, ctx.cls, s.date, s.period, ctx.ta)
    c = dt.datetime.combine(s.date + dt.timedelta(days=1), dt.time(22, 0), tzinfo=TZ)
    return {'working_date': s.date, 'period': s.period, 'opens_at': o, 'closes_at': c}


def _has_test(db: Session, pl_id: int) -> bool:
    return db.scalar(select(OnlineTask.id).where(OnlineTask.plan_lesson_id == pl_id, OnlineTask.kind == 'movzu',
                                                 OnlineTask.archived_at.is_(None))) is not None


def _match(lessons: list[PlanLesson], src: PlanLesson) -> PlanLesson | None:
    key = norm_topic(src.topic)
    same = [l for l in lessons if norm_topic(l.topic) == key]
    return min(same, key=lambda l: abs(l.seq - src.seq)) if same else None


def _pl(db: Session, ta: TeachingAssignment, pl_id: int) -> PlanLesson:
    pl = db.get(PlanLesson, pl_id)
    if not pl or pl.assignment_id != ta.id:
        raise HTTPException(404, 'Mövzu bu dərsin planında yoxdur')
    return pl


@router.get('/plan/{ta_id}/topics/{pl_id}/peers')
def peers(ta_id: int, pl_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Cari sinif + eyni fənn və sinif rəqəmində müəllimin digər dərsləri, hər birində uyğun mövzu və default vaxt."""
    ta = own_assignment(db, user, ta_id)
    src = _pl(db, ta, pl_id)
    grade = class_grade(db, db.get(SchoolClass, ta.class_id))
    rows = db.execute(select(TeachingAssignment, SchoolClass).join(SchoolClass).where(
        TeachingAssignment.teacher_id == user.id, ws_cond(user), TeachingAssignment.archived_at.is_(None),
        TeachingAssignment.subject == ta.subject, SchoolClass.archived_at.is_(None)).order_by(SchoolClass.name)).all()
    out = []
    for t, c in rows:
        if t.id != ta.id and (grade is None or class_grade(db, c) != grade):
            continue
        ctx = plan_ctx(db, t)
        pl = src if t.id == ta.id else _match(ctx.lessons, src)
        item = {'ta_id': t.id, 'class_name': c.name, 'kind': c.kind, 'current': t.id == ta.id,
                'students': len(roster(db, t)),
                'plan_lesson': pl and {'id': pl.id, 'seq': pl.seq, 'topic': pl.topic},
                'already_has_test': bool(pl and _has_test(db, pl.id)),
                **(_defaults(db, ctx, pl.id) if pl else {'working_date': None, 'period': None,
                                                          'opens_at': None, 'closes_at': None})}
        if pl is None:                       # əl ilə seçmək üçün həmin sinfin planı
            item['lessons'] = [{'id': l.id, 'seq': l.seq, 'topic': l.topic} for l in ctx.lessons]
        out.append(item)
    out.sort(key=lambda x: (not x['current'], x['class_name']))
    return {'topic': {'id': src.id, 'seq': src.seq, 'topic': src.topic, 'section': src.section,
                      'assessment_type': src.assessment_type},
            'subject': ta.subject, 'grade': grade, 'classes': out}


class TopicTarget(BaseModel):
    ta_id: int
    plan_lesson_id: int
    opens_at: dt.datetime
    closes_at: dt.datetime
    student_ids: list[int] | None = None
    levels: list[Literal['Zəif', 'Orta', 'Güclü']] | None = None     # hədəf: yalnız bu səviyyə qrupları


class VariantQs(BaseModel):
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)


class TopicTestIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=2000)
    duration_min: int = Field(ge=1, le=300)
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)
    shuffle: bool = True
    show_answers: Literal['after_close', 'after_submit', 'never'] = 'after_close'
    journal_auto: bool = True
    targets: list[TopicTarget] = Field(min_length=1, max_length=30)
    # səviyyəyə görə variant: hər qrupa öz sualları (səviyyəsi və ya variantı olmayan şagird «Orta» variantı alır)
    variants: dict[Literal['Zəif', 'Orta', 'Güclü'], VariantQs] | None = None

    @model_validator(mode='after')
    def _v(self):
        sets = list(self.variants.values()) if self.variants else [self]
        if not sets or any(not v.bank_ids and not v.custom for v in sets):
            raise ValueError('ən azı bir sual seçin' + (' (hər variantda)' if self.variants else ''))
        if any(len(v.bank_ids) + len(v.custom) > 100 for v in sets):
            raise ValueError('bir testdə ən çoxu 100 sual')
        if self.variants and 'Orta' not in self.variants:
            raise ValueError('variantlı testdə «Orta» variantı məcburidir (səviyyəsi olmayanlar onu alır)')
        if len({t.ta_id for t in self.targets}) != len(self.targets):
            raise ValueError('bir sinif iki dəfə seçilib')
        return self


@router.post('/plan/{ta_id}/topics/{pl_id}/test')
def create_topic_test(ta_id: int, pl_id: int, body: TopicTestIn, user: User = Depends(staff),
                      db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    src = _pl(db, ta, pl_id)
    if src.assessment_type in ('KSQ', 'BSQ'):
        raise HTTPException(400, f'{src.assessment_type} dərsinə formativ mövzu testi təyin edilmir')
    t0 = now()
    plan = []
    for tg in body.targets:
        t = own_assignment(db, user, tg.ta_id)
        cls = db.get(SchoolClass, t.class_id)
        if t.subject != ta.subject:
            raise HTTPException(400, f'{cls.name}: fənn fərqlidir ({t.subject})')
        pl = _pl(db, t, tg.plan_lesson_id)
        o, c = (aware(x).astimezone(dt.timezone.utc) for x in (tg.opens_at, tg.closes_at))
        if c <= o:
            raise HTTPException(400, f'{cls.name}: bitmə vaxtı başlamadan sonra olmalıdır')
        if c <= t0:
            raise HTTPException(400, f'{cls.name}: bitmə vaxtı keçmişdədir')
        if body.duration_min > (c - o).total_seconds() / 60:
            raise HTTPException(400, f'{cls.name}: həll müddəti ({body.duration_min} dəq) açıq qalma aralığından uzundur')
        studs = [s.id for s in roster(db, t)]
        if tg.student_ids is not None:
            if not tg.student_ids or set(tg.student_ids) - set(studs):
                raise HTTPException(400, f'{cls.name}: şagirdlər bu sinifdən/qrupdan seçilməlidir')
            studs = list(tg.student_ids)
        lv = {o_.student_id: o_.level for o_ in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == t.id))}
        if tg.levels:
            studs = [x for x in studs if lv.get(x) in tg.levels]
            if not studs:
                raise HTTPException(400, f'{cls.name}: seçilən səviyyə qrupunda şagird yoxdur (Jurnal → Səviyyə qrupları)')
        if body.variants:                    # hər səviyyəyə öz tapşırığı (səviyyəsi və ya variantı olmayan – «Orta»)
            var_of = lambda x: lv.get(x) if lv.get(x) in body.variants else 'Orta'
            parts = [(k, [x for x in studs if var_of(x) == k]) for k in ('Zəif', 'Orta', 'Güclü') if k in body.variants]
            parts = [(k, ids) for k, ids in parts if ids]
        else:
            parts = [(None, None if tg.student_ids is None and not tg.levels else studs)]
        plan.append((t, pl, o, c, parts))
    if body.variants:
        qsets = {k: _snapshot(db, v.bank_ids) + [custom_snapshot(q) for q in v.custom] for k, v in body.variants.items()}
    else:
        qsets = {None: _snapshot(db, body.bank_ids) + [custom_snapshot(q) for q in body.custom]}
    batch = TestBatch(kind='movzu', title=body.title, subject=ta.subject,
                      grade=class_grade(db, db.get(SchoolClass, ta.class_id)), created_by=user.id)
    db.add(batch)
    db.flush()
    made = []
    for t, pl, o, c, parts in plan:
        for level, sids in parts:
            qs = qsets[level]
            task = OnlineTask(assignment_id=t.id, title=f'{body.title} · {level} variant' if level else body.title,
                              description=body.description, opens_at=o, closes_at=c,
                              duration_min=body.duration_min, questions=copy.deepcopy(qs), shuffle=body.shuffle,
                              show_answers=body.show_answers, student_ids=sids, created_by=user.id, kind='movzu',
                              batch_id=batch.id, plan_lesson_id=pl.id, journal_auto=body.journal_auto)
            db.add(task)
            db.flush()
            made.append(task)
            audit(db, user, 'create', 'task', task.id, kind='movzu', batch=batch.id, plan_seq=pl.seq, questions=len(qs),
                  variant=level)
    db.commit()
    return {'batch_id': batch.id, 'tasks': [{**task_out(x), 'ta_id': x.assignment_id} for x in made]}


def topic_tests(db: Session, ta: TeachingAssignment, pl_ids: set[int]) -> dict[int, list[dict]]:
    """Plan sətirləri üçün: mövzuya bağlı testlərin vəziyyəti."""
    if not pl_ids:
        return {}
    t0 = now()
    n_roster = None
    out: dict[int, list[dict]] = {}
    for task in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, OnlineTask.kind == 'movzu',
                                                    OnlineTask.plan_lesson_id.in_(pl_ids),
                                                    OnlineTask.archived_at.is_(None)).order_by(OnlineTask.opens_at)):
        done = db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == task.id,
                                                    TaskAttempt.submitted_at.is_not(None))).all()
        if task.student_ids is None and n_roster is None:
            n_roster = len(roster(db, ta))
        o, c = aware(task.opens_at), aware(task.closes_at)
        out.setdefault(task.plan_lesson_id, []).append({
            'task_id': task.id, 'title': task.title, 'opens_at': o, 'closes_at': c,
            'state': 'gözlənilir' if t0 < o else 'açıqdır' if t0 < c else 'bitib',
            'questions': len(task.questions), 'submitted': len(done),
            'total': len(task.student_ids) if task.student_ids is not None else n_roster,
            'avg_pct': round(sum(a.correct * 100 / a.total for a in done if a.total) / len(done), 1) if done else None,
            'journal': 'yazılıb' if task.journal_done_at else 'gözləyir' if task.journal_auto else 'yox'})
    return out


@router.post('/plan/{ta_id}/tests/{task_id}/journal')
def write_journal_now(ta_id: int, task_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«İndi jurnala yaz» – test bağlanmasını gözləmədən (təhvil verənlərin nəticəsi)."""
    from ..task_journal import write_topic_marks
    from .tasks import expire_due
    ta = own_assignment(db, user, ta_id)
    task = db.get(OnlineTask, task_id)
    if not task or task.assignment_id != ta.id or task.archived_at or task.kind != 'movzu':
        raise HTTPException(404, 'Mövzu testi tapılmadı')
    expire_due(db, task)
    r = write_topic_marks(db, task, by=user.id)
    if r['status'] == 'gözləyir':
        raise HTTPException(400, f'Mövzunun dərsi ({r["date"]:%d.%m.%Y}) hələ keçməyib – qiymət sonra yazılacaq')
    if r['status'] != 'yazıldı':
        raise HTTPException(400, {'mövzu yoxdur': 'Mövzu planda tapılmadı – testi başqa mövzuya bağlayın',
                                  'dərs yoxdur': 'Mövzunun dərsi cədvəldə tapılmadı',
                                  'summativ': 'KSQ/BSQ dərsinə formativ qiymət yazılmır'}[r['status']])
    db.commit()
    return r


@router.get('/plan/{ta_id}/topics/{pl_id}/previous')
def previous_tests(ta_id: int, pl_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bu mövzu üçün əvvəl istifadə etdiyiniz testlər (digər siniflər, keçən illər) – sualları yenidən götürmək üçün.
    Mövzu normallaşdırılmış mətnə və fənnə görə tanınır; yeni ilin planı yüklənəndə də işləyir."""
    ta = own_assignment(db, user, ta_id)
    key = norm_topic(_pl(db, ta, pl_id).topic)
    rows = db.execute(select(OnlineTask, PlanLesson, TeachingAssignment)
                      .join(PlanLesson, PlanLesson.id == OnlineTask.plan_lesson_id)
                      .join(TeachingAssignment, TeachingAssignment.id == OnlineTask.assignment_id)
                      .where(TeachingAssignment.teacher_id == user.id, ws_cond(user), TeachingAssignment.subject == ta.subject,
                             OnlineTask.kind == 'movzu').order_by(OnlineTask.id.desc())).all()
    out, seen = [], set()
    for t, pl, tta in rows:
        if norm_topic(pl.topic) != key:
            continue
        sig = (t.batch_id, t.title)                      # eyni paketin sinif surətləri bir dəfə
        if sig in seen:
            continue
        seen.add(sig)
        done = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id,
                                                                TaskAttempt.submitted_at.is_not(None))) if a.total]
        out.append({'task_id': t.id, 'title': t.title, 'class_name': db.get(SchoolClass, tta.class_id).name,
                    'opens_at': aware(t.opens_at), 'questions': t.questions, 'count': len(t.questions),
                    'avg_pct': round(sum(a.correct * 100 / a.total for a in done) / len(done), 1) if done else None})
        if len(out) >= 20:
            break
    return out
