"""Əlavə məşğələ (əyani və onlayn): kurs → öz perspektiv planı (məşğələlər), davamiyyət, məşğələ testi, statistika.

Qaydalar (docs/plan-test-uygunlugu-promtu.md §3.15–3.20):
- dərs cədvəlindən və gündəlik plandan ayrıdır: jurnala qiymət yazmır, işçi planı sürüşdürmür, mövzunu «keçildi» etmir;
- tarixlər cədvəldən avtomatik qurulur, tətil/bayram günləri çıxılır; onlayn keçid yalnız https://;
- şagird və valideyn planı, öz iştirakını və öz nəticəsini görür (başqasınınkını və səviyyə etiketini yox);
- onlayn keçid şagirdə başlamazdan 10 dəqiqə əvvəl açılır;
- statistika yalnız «keçirildi» qeyd olunan məşğələlər üzrə; ləğv olunan iştiraka təsir etmir;
- məktəb cədvəli ilə toqquşma – xəbərdarlıq (qadağa deyil)."""
from __future__ import annotations

import copy
import datetime as dt
import re
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..models import (ExtraAttendance, ExtraCourse, ExtraSession, Holiday, LevelOverride, OnlineTask, PlanLesson,
                      SchoolClass, Student, TaskAttempt, TeachingAssignment, TestBatch, TopicProgress, User, now)
from ..services import SCHOOL_TZ, own_assignment, roster
from .common import audit, current_year, need_school
from .plan import bell
from .tasks import CustomQ, _snapshot, aware, custom_snapshot

router = APIRouter(prefix='/api/extra', tags=['extra'])
TZ = ZoneInfo(SCHOOL_TZ)
DAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.', 'Ş.', 'B.']
HM = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
JOIN_BEFORE = dt.timedelta(minutes=10)


def _https(v: str | None) -> str | None:
    v = (v or '').strip() or None
    if v and not v.lower().startswith('https://'):
        raise ValueError('keçid https:// ilə başlamalıdır')
    return v


class Slot(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start: str
    end: str
    room: str | None = Field(None, max_length=60)
    link: str | None = Field(None, max_length=500)

    @model_validator(mode='after')
    def _v(self):
        if not HM.match(self.start) or not HM.match(self.end) or self.end <= self.start:
            raise ValueError('vaxt: SS:DD, bitmə başlamadan sonra')
        self.link = _https(self.link)
        return self


class CourseIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    format: Literal['əyani', 'onlayn', 'qarışıq'] = 'əyani'
    ta_ids: list[int] = Field(min_length=1, max_length=20)
    levels: list[Literal['Zəif', 'Orta', 'Güclü']] | None = None
    student_ids: list[int] | None = None
    schedule: list[Slot] = Field(min_length=1, max_length=14)
    starts_on: dt.date
    ends_on: dt.date
    goal: str | None = Field(None, max_length=2000)

    @model_validator(mode='after')
    def _v(self):
        if self.ends_on < self.starts_on:
            raise ValueError('bitmə tarixi başlamadan sonra olmalıdır')
        if (self.ends_on - self.starts_on).days > 366:
            raise ValueError('kurs ən çoxu bir il')
        return self


# ---------------------------------------------------------------- köməkçilər
def _course(db: Session, user: User, cid: int) -> ExtraCourse:
    c = db.get(ExtraCourse, cid)
    if not c or c.owner_id != user.id:
        raise HTTPException(404, 'Kurs tapılmadı')
    return c


def members(db: Session, c: ExtraCourse) -> list[tuple[Student, int]]:
    """Kursun şagirdləri: (şagird, dərs bağlılığı) – sinif/qrup siyahısı, səviyyə və ya seçilmiş şagirdlər üzrə."""
    a = c.audience or {}
    levels, picked = a.get('levels'), set(a.get('student_ids') or [])
    out, seen = [], set()
    for ta_id in a.get('ta_ids') or []:
        ta = db.get(TeachingAssignment, ta_id)
        if not ta or ta.archived_at:
            continue
        lv = {o.student_id: o.level for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == ta.id))}
        for s in roster(db, ta):
            if s.id in seen or (levels and lv.get(s.id) not in levels) or (picked and s.id not in picked):
                continue
            seen.add(s.id)
            out.append((s, ta.id))
    return out


def _minutes(t: str) -> int:
    h, m = t.split(':')
    return int(h) * 60 + int(m)


def _overlap(a1: str, a2: str, bell_text: str | None) -> bool:
    if not bell_text:
        return False
    m = re.findall(r'(\d{1,2}):(\d{2})', bell_text)
    if len(m) < 2:
        return False
    b1, b2 = int(m[0][0]) * 60 + int(m[0][1]), int(m[1][0]) * 60 + int(m[1][1])
    return _minutes(a1) < b2 and b1 < _minutes(a2)


def conflicts(db: Session, user: User, ta_ids: list[int], schedule: list[dict]) -> list[str]:
    """Məktəb cədvəli ilə toqquşma: müəllimin öz dərsləri və kurs siniflərinin bütün dərsləri."""
    classes = {db.get(TeachingAssignment, i).class_id for i in ta_ids if db.get(TeachingAssignment, i)}
    tas = list(db.scalars(select(TeachingAssignment).where(TeachingAssignment.archived_at.is_(None),
                                                           (TeachingAssignment.teacher_id == user.id) |
                                                           (TeachingAssignment.class_id.in_(classes)))))
    out = []
    for sl in schedule:
        for t in tas:
            cls = db.get(SchoolClass, t.class_id)
            for p in (t.slots or {}).get(str(sl['weekday']), []):
                if _overlap(sl['start'], sl['end'], bell(db, cls, p)):
                    who = 'sizin dərsiniz' if t.teacher_id == user.id else f'{cls.name} sinfinin dərsi'
                    out.append(f'{DAYS[sl["weekday"]]} {sl["start"]}–{sl["end"]}: {who} ({cls.name}, {t.subject}, {p}-ci saat)')
    return list(dict.fromkeys(out))


def generate(db: Session, c: ExtraCourse, frm: dt.date | None = None) -> int:
    """Cədvəldən məşğələ tarixləri (tətil/bayram çıxılır); mövcud tarix+saat təkrar yaranmır."""
    off = {h.date for h in db.scalars(select(Holiday).where(Holiday.year_id == current_year(db, c.school_id).id))}
    have = {(x.date, x.start) for x in db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id))}
    d, n = max(c.starts_on, frm or c.starts_on), 0
    while d <= c.ends_on:
        for sl in c.schedule:
            if d.weekday() == sl['weekday'] and d not in off and (d, sl['start']) not in have:
                fmt = sl.get('format') or ('onlayn' if c.format == 'onlayn' or (c.format == 'qarışıq' and sl.get('link')) else 'əyani')
                db.add(ExtraSession(course_id=c.id, date=d, start=sl['start'], end=sl['end'], format=fmt,
                                    room=sl.get('room'), link=sl.get('link'), status='planned'))
                n += 1
        d += dt.timedelta(days=1)
    return n


def _sessions(db: Session, c: ExtraCourse) -> list[ExtraSession]:
    return list(db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id)
                           .order_by(ExtraSession.date, ExtraSession.start)))


def _when(s: ExtraSession) -> tuple[dt.datetime, dt.datetime]:
    a = dt.datetime.combine(s.date, dt.time.fromisoformat(s.start), tzinfo=TZ)
    b = dt.datetime.combine(s.date, dt.time.fromisoformat(s.end), tzinfo=TZ)
    return a, b


def _topics_text(db: Session, s: ExtraSession) -> list[dict]:
    out = []
    for t in s.topics or []:
        pl = db.get(PlanLesson, t['plan_lesson_id']) if t.get('plan_lesson_id') else None
        out.append({'plan_lesson_id': pl.id if pl else None, 'seq': pl.seq if pl else None,
                    'text': t.get('text') or (pl.topic if pl else '')})
    return out


def session_out(db: Session, s: ExtraSession, n_students: int | None = None) -> dict:
    att = list(db.scalars(select(ExtraAttendance).where(ExtraAttendance.session_id == s.id)))
    return {'id': s.id, 'date': s.date, 'weekday': DAYS[s.date.weekday()], 'start': s.start, 'end': s.end,
            'format': s.format, 'room': s.room, 'link': s.link, 'topics': _topics_text(db, s), 'goals': s.goals,
            'resources': s.resources, 'homework': s.homework, 'status': s.status, 'note': s.note,
            'recording_url': s.recording_url, 'batch_id': s.batch_id,
            'present': sum(a.status in ('var', 'gecikdi') for a in att), 'joined': sum(a.joined_at is not None for a in att),
            'students': n_students}


def course_out(db: Session, c: ExtraCourse, full: bool = False) -> dict:
    ms = members(db, c)
    ss = _sessions(db, c)
    t = now().astimezone(TZ)
    nxt = next((s for s in ss if s.status == 'planned' and _when(s)[1] >= t), None)
    classes = []
    for i in (c.audience or {}).get('ta_ids') or []:
        ta = db.get(TeachingAssignment, i)
        if ta:
            classes.append(db.get(SchoolClass, ta.class_id).name)
    out = {'id': c.id, 'title': c.title, 'subject': c.subject, 'format': c.format, 'audience': c.audience,
           'classes': classes, 'schedule': c.schedule, 'starts_on': c.starts_on, 'ends_on': c.ends_on, 'goal': c.goal,
           'students': len(ms), 'sessions': len(ss), 'held': sum(s.status == 'held' for s in ss),
           'cancelled': sum(s.status == 'cancelled' for s in ss), 'archived': c.archived_at is not None,
           'next': nxt and session_out(db, nxt)}
    if full:
        out['session_list'] = [session_out(db, s, len(ms)) for s in ss]
        out['members'] = [{'student_id': s.id, 'full_name': s.full_name, 'ta_id': ta_id,
                           'class_name': db.get(SchoolClass, s.class_id).name} for s, ta_id in ms]
    return out


# ---------------------------------------------------------------- kurslar
@router.get('')
def list_courses(archived: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    st = select(ExtraCourse).where(ExtraCourse.owner_id == user.id,
                                   ExtraCourse.archived_at.is_not(None) if archived else ExtraCourse.archived_at.is_(None))
    return [course_out(db, c) for c in db.scalars(st.order_by(ExtraCourse.starts_on.desc()))]


def _check_audience(db: Session, user: User, body) -> list[TeachingAssignment]:
    tas = [own_assignment(db, user, i) for i in dict.fromkeys(body.ta_ids)]
    if len({t.subject for t in tas}) > 1:
        raise HTTPException(400, 'Kursun dərsləri eyni fənn üzrə olmalıdır')
    if body.student_ids is not None:
        allowed = {s.id for t in tas for s in roster(db, t)}
        if not body.student_ids or set(body.student_ids) - allowed:
            raise HTTPException(400, 'Şagirdlər seçilən siniflərdən/qruplardan olmalıdır')
    return tas


@router.post('')
def create_course(body: CourseIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    tas = _check_audience(db, user, body)
    sched = [s.model_dump() for s in body.schedule]
    c = ExtraCourse(owner_id=user.id, school_id=need_school(user), title=body.title, subject=tas[0].subject,
                    format=body.format, audience={'ta_ids': [t.id for t in tas], 'levels': body.levels,
                                                  'student_ids': body.student_ids},
                    schedule=sched, starts_on=body.starts_on, ends_on=body.ends_on, goal=body.goal)
    db.add(c)
    db.flush()
    if not members(db, c):
        raise HTTPException(400, 'Seçimə uyğun şagird yoxdur (səviyyə qrupu boşdursa – əvvəl bölgü aparın)')
    n = generate(db, c)
    warn = conflicts(db, user, c.audience['ta_ids'], sched)
    audit(db, user, 'create', 'extra_course', c.id, title=c.title, sessions=n)
    db.commit()
    return {**course_out(db, c), 'warnings': warn}


@router.get('/{cid}')
def get_course(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    return {**course_out(db, c, full=True), 'warnings': conflicts(db, user, c.audience['ta_ids'], c.schedule)}


class CoursePatch(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    goal: str | None = Field(None, max_length=2000)
    ends_on: dt.date | None = None
    levels: list[Literal['Zəif', 'Orta', 'Güclü']] | None = None
    student_ids: list[int] | None = None
    all_students: bool = False


@router.patch('/{cid}')
def patch_course(cid: int, body: CoursePatch, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Ad, məqsəd, kimə; bitmə tarixi uzadılanda yeni məşğələlər qurulur."""
    c = _course(db, user, cid)
    data = body.model_dump(exclude_unset=True)
    if 'title' in data and body.title:
        c.title = body.title
    if 'goal' in data:
        c.goal = body.goal
    aud = dict(c.audience)
    if body.all_students:
        aud['levels'], aud['student_ids'] = None, None
    if 'levels' in data:
        aud['levels'] = body.levels or None
    if 'student_ids' in data and body.student_ids is not None:
        allowed = {s.id for i in aud['ta_ids'] for s in roster(db, own_assignment(db, user, i))}
        if not body.student_ids or set(body.student_ids) - allowed:
            raise HTTPException(400, 'Şagirdlər kursun siniflərindən olmalıdır')
        aud['student_ids'] = body.student_ids
    c.audience = aud
    added = 0
    if body.ends_on:
        if body.ends_on < c.starts_on:
            raise HTTPException(400, 'Bitmə tarixi başlamadan sonra olmalıdır')
        old = c.ends_on
        c.ends_on = body.ends_on
        if body.ends_on > old:
            added = generate(db, c, old + dt.timedelta(days=1))
        else:                                # qısaldılanda – keçirilməmiş artıq məşğələlər silinir
            for s in db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id, ExtraSession.date > body.ends_on,
                                                           ExtraSession.status != 'held')):
                db.delete(s)
    audit(db, user, 'update', 'extra_course', c.id, fields=sorted(data))
    db.commit()
    return {**course_out(db, c), 'added': added}


@router.post('/{cid}/archive')
def archive_course(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    c.archived_at = now()
    audit(db, user, 'archive', 'extra_course', c.id)
    db.commit()
    return {'ok': True}


@router.post('/{cid}/restore')
def restore_course(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    c.archived_at = None
    audit(db, user, 'restore', 'extra_course', c.id)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- məşğələlər (perspektiv plan)
class TopicRef(BaseModel):
    plan_lesson_id: int | None = None
    text: str | None = Field(None, max_length=300)


class SessionIn(BaseModel):
    date: dt.date | None = None
    start: str | None = None
    end: str | None = None
    format: Literal['əyani', 'onlayn'] | None = None
    room: str | None = Field(None, max_length=60)
    link: str | None = Field(None, max_length=500)
    topics: list[TopicRef] | None = Field(None, max_length=10)
    goals: str | None = Field(None, max_length=2000)
    resources: str | None = Field(None, max_length=4000)
    homework: str | None = Field(None, max_length=2000)
    status: Literal['planned', 'held', 'cancelled'] | None = None
    note: str | None = Field(None, max_length=300)
    recording_url: str | None = Field(None, max_length=500)

    @field_validator('link', 'recording_url')
    @classmethod
    def _l(cls, v):
        return _https(v)


def _plan_ids(db: Session, c: ExtraCourse) -> set[int]:
    return set(db.scalars(select(PlanLesson.id).where(PlanLesson.assignment_id.in_(c.audience['ta_ids']))))


def _apply_session(db: Session, c: ExtraCourse, s: ExtraSession, body: SessionIn):
    data = body.model_dump(exclude_unset=True)
    for k in ('start', 'end'):
        if k in data and (not data[k] or not HM.match(data[k])):
            raise HTTPException(400, 'Vaxt SS:DD formatında olmalıdır')
    if 'topics' in data and body.topics is not None:
        ok = _plan_ids(db, c)
        if any(t.plan_lesson_id and t.plan_lesson_id not in ok for t in body.topics):
            raise HTTPException(400, 'Mövzu kursun siniflərinin perspektiv planından olmalıdır')
        data['topics'] = [{'plan_lesson_id': t.plan_lesson_id, 'text': (t.text or '').strip() or None}
                          for t in body.topics if t.plan_lesson_id or (t.text or '').strip()]
    if data.get('status') == 'cancelled' and not (body.note or s.note):
        raise HTTPException(400, 'Ləğv səbəbini yazın')
    for k, v in data.items():
        setattr(s, k, v)
    if (s.end or '') <= (s.start or ''):
        raise HTTPException(400, 'Bitmə vaxtı başlamadan sonra olmalıdır')


@router.post('/{cid}/sessions')
def add_session(cid: int, body: SessionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Əlavə (cədvəldən kənar) məşğələ və ya köçürülən məşğələnin yeni tarixi."""
    c = _course(db, user, cid)
    if not (body.date and body.start and body.end):
        raise HTTPException(400, 'Tarix, başlama və bitmə vaxtı lazımdır')
    s = ExtraSession(course_id=c.id, date=body.date, start=body.start, end=body.end,
                     format=body.format or ('onlayn' if c.format == 'onlayn' else 'əyani'), status='planned')
    _apply_session(db, c, s, body)
    db.add(s)
    db.flush()
    audit(db, user, 'create', 'extra_session', s.id, course=c.id)
    db.commit()
    return session_out(db, s)


@router.put('/{cid}/sessions/{sid}')
def update_session(cid: int, sid: int, body: SessionIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    s = db.get(ExtraSession, sid)
    if not s or s.course_id != c.id:
        raise HTTPException(404, 'Məşğələ tapılmadı')
    _apply_session(db, c, s, body)
    audit(db, user, 'update', 'extra_session', s.id, fields=sorted(body.model_dump(exclude_unset=True)))
    db.commit()
    return session_out(db, s)


@router.delete('/{cid}/sessions/{sid}')
def delete_session(cid: int, sid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    s = db.get(ExtraSession, sid)
    if not s or s.course_id != c.id:
        raise HTTPException(404, 'Məşğələ tapılmadı')
    if s.status == 'held':
        raise HTTPException(409, 'Keçirilmiş məşğələ silinmir (davamiyyət və statistika itər)')
    db.delete(s)
    audit(db, user, 'delete', 'extra_session', sid, course=c.id)
    db.commit()
    return {'ok': True}


class HeldIn(BaseModel):
    attendance: dict[int, Literal['var', 'yox', 'üzrlü', 'gecikdi']] = Field(default_factory=dict)


@router.post('/{cid}/sessions/{sid}/held')
def mark_held(cid: int, sid: int, body: HeldIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Keçirildi» + davamiyyət. Onlayn qoşulanlar (joined_at) default «var» təklif olunur (interfeysdə)."""
    c = _course(db, user, cid)
    s = db.get(ExtraSession, sid)
    if not s or s.course_id != c.id:
        raise HTTPException(404, 'Məşğələ tapılmadı')
    if _when(s)[0] > now().astimezone(TZ) + dt.timedelta(minutes=30):
        raise HTTPException(400, 'Məşğələ hələ başlamayıb')
    ids = {m.id for m, _ in members(db, c)}
    if set(body.attendance) - ids:
        raise HTTPException(400, 'Şagird bu kursda deyil')
    for st, status in body.attendance.items():
        a = db.get(ExtraAttendance, (s.id, st)) or ExtraAttendance(session_id=s.id, student_id=st)
        a.status = status
        db.merge(a)
    s.status = 'held'
    audit(db, user, 'update', 'extra_session', s.id, held=True, present=sum(v in ('var', 'gecikdi') for v in body.attendance.values()))
    db.commit()
    return session_out(db, s, len(ids))


@router.get('/{cid}/sessions/{sid}/attendance')
def session_attendance(cid: int, sid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    s = db.get(ExtraSession, sid)
    if not s or s.course_id != c.id:
        raise HTTPException(404, 'Məşğələ tapılmadı')
    att = {a.student_id: a for a in db.scalars(select(ExtraAttendance).where(ExtraAttendance.session_id == s.id))}
    return [{'student_id': m.id, 'full_name': m.full_name, 'status': att[m.id].status if m.id in att else None,
             'joined_at': aware(att[m.id].joined_at) if m.id in att and att[m.id].joined_at else None}
            for m, _ in members(db, c)]


class BulkTopicsIn(BaseModel):
    plan_lesson_ids: list[int] = Field(min_length=1, max_length=100)
    per_session: int = Field(1, ge=1, le=5)


@router.post('/{cid}/topics/bulk')
def bulk_topics(cid: int, body: BulkTopicsIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«№12–№20 mövzularını ardıcıl paylaşdır»: mövzusu olmayan növbəti planlaşdırılmış məşğələlərə."""
    c = _course(db, user, cid)
    ok = _plan_ids(db, c)
    if set(body.plan_lesson_ids) - ok:
        raise HTTPException(400, 'Mövzu kursun siniflərinin perspektiv planından olmalıdır')
    today = now().astimezone(TZ).date()
    free = [s for s in _sessions(db, c) if s.status == 'planned' and s.date >= today and not s.topics]
    ids, n = list(body.plan_lesson_ids), 0
    for s in free:
        if not ids:
            break
        s.topics = [{'plan_lesson_id': i, 'text': None} for i in ids[:body.per_session]]
        ids = ids[body.per_session:]
        n += 1
    audit(db, user, 'update', 'extra_course', c.id, bulk_topics=n)
    db.commit()
    return {'sessions': n, 'left': len(ids)}


@router.get('/{cid}/suggest-topics')
def suggest_topics(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Mövzu təklifləri: «təkrar» statuslu və mövzu testi < 60 % olan mövzular (zəif qrup üçün);
    sınaqda ən çox səhv edilən suallar (güclü qrup üçün) – mətn kimi."""
    c = _course(db, user, cid)
    out = []
    for ta_id in c.audience['ta_ids']:
        for tp, pl in db.execute(select(TopicProgress, PlanLesson).join(PlanLesson, PlanLesson.id == TopicProgress.plan_lesson_id)
                                 .where(TopicProgress.assignment_id == ta_id, TopicProgress.status == 'təkrar')):
            out.append({'plan_lesson_id': pl.id, 'seq': pl.seq, 'topic': pl.topic, 'reason': 'təkrar statusu'})
        for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta_id, OnlineTask.kind == 'movzu',
                                                     OnlineTask.plan_lesson_id.is_not(None), OnlineTask.archived_at.is_(None))):
            done = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id,
                                                                    TaskAttempt.submitted_at.is_not(None))) if a.total]
            avg = sum(a.correct * 100 / a.total for a in done) / len(done) if done else None
            if avg is not None and avg < 60:
                pl = db.get(PlanLesson, t.plan_lesson_id)
                out.append({'plan_lesson_id': pl.id, 'seq': pl.seq, 'topic': pl.topic, 'reason': f'mövzu testi {avg:.0f}%'})
    seen, uniq = set(), []
    for x in out:
        if x['plan_lesson_id'] not in seen:
            seen.add(x['plan_lesson_id'])
            uniq.append(x)
    plan = [{'id': pl.id, 'seq': pl.seq, 'topic': pl.topic, 'section': pl.section}
            for pl in db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == c.audience['ta_ids'][0])
                                 .order_by(PlanLesson.seq))]
    return {'suggested': uniq, 'plan': plan}


class SessionTestIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    duration_min: int = Field(15, ge=1, le=300)
    opens_at: dt.datetime
    closes_at: dt.datetime
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)

    @model_validator(mode='after')
    def _v(self):
        if not self.bank_ids and not self.custom:
            raise ValueError('ən azı bir sual seçin')
        o, c = aware(self.opens_at), aware(self.closes_at)
        if c <= o or self.duration_min > (c - o).total_seconds() / 60:
            raise ValueError('vaxt aralığı və həll müddəti uyğun deyil')
        return self


@router.post('/{cid}/sessions/{sid}/test')
def session_test(cid: int, sid: int, body: SessionTestIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Məşğələ testi (5–8 sual məşğələnin effektini ölçür): yalnız kursun şagirdlərinə, jurnala yazılmır."""
    c = _course(db, user, cid)
    s = db.get(ExtraSession, sid)
    if not s or s.course_id != c.id:
        raise HTTPException(404, 'Məşğələ tapılmadı')
    if aware(body.closes_at) <= now():
        raise HTTPException(400, 'Bitmə vaxtı keçmişdədir')
    qs = _snapshot(db, body.bank_ids) + [custom_snapshot(q) for q in body.custom]
    b = TestBatch(kind='extra', title=body.title, subject=c.subject, created_by=user.id)
    db.add(b)
    db.flush()
    by_ta: dict[int, list[int]] = {}
    for m, ta_id in members(db, c):
        by_ta.setdefault(ta_id, []).append(m.id)
    for ta_id, sids in by_ta.items():
        db.add(OnlineTask(assignment_id=ta_id, title=body.title, opens_at=aware(body.opens_at), closes_at=aware(body.closes_at),
                          duration_min=body.duration_min, questions=copy.deepcopy(qs), shuffle=True,
                          show_answers='after_submit', student_ids=sids, created_by=user.id, kind='extra', batch_id=b.id))
    s.batch_id = b.id
    audit(db, user, 'create', 'extra_test', b.id, session=s.id, questions=len(qs))
    db.commit()
    return {'batch_id': b.id, 'tasks': len(by_ta)}


# ---------------------------------------------------------------- statistika
def _pcts(db: Session, task_ids: list[int]) -> dict[int, list[tuple[dt.datetime, float]]]:
    out: dict[int, list] = {}
    if not task_ids:
        return out
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_(task_ids), TaskAttempt.submitted_at.is_not(None))):
        if a.total:
            out.setdefault(a.student_id, []).append((aware(a.submitted_at), a.correct * 100 / a.total))
    return out


def _avg(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 1) if v else None


@router.get('/{cid}/stats')
def stats(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = _course(db, user, cid)
    ms = members(db, c)
    ss = _sessions(db, c)
    held = [s for s in ss if s.status == 'held']
    att = {(a.session_id, a.student_id): a.status for a in db.scalars(
        select(ExtraAttendance).where(ExtraAttendance.session_id.in_([s.id for s in held])))} if held else {}
    batches = [s.batch_id for s in ss if s.batch_id]
    extra_tasks = {t.id: t for t in db.scalars(select(OnlineTask).where(OnlineTask.batch_id.in_(batches)))} if batches else {}
    extra = _pcts(db, list(extra_tasks))
    start = dt.datetime.combine(c.starts_on, dt.time(0), tzinfo=TZ)
    # mövzu testləri + sınaqlar – kursdan əvvəl / sonra və iştirakçı ↔ iştirak etməyən müqayisəsi
    main_tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id.in_(c.audience['ta_ids']),
                                                          OnlineTask.kind.in_(('movzu', 'sinaq')))))
    main = _pcts(db, [t.id for t in main_tasks])

    sessions = []
    for s in held:
        here = [att.get((s.id, m.id)) for m, _ in ms]
        tids = [t for t in extra_tasks if s.batch_id and extra_tasks[t].batch_id == s.batch_id]
        test_p = _avg([p for lst in _pcts(db, tids).values() for _, p in lst]) if tids else None
        sessions.append({'id': s.id, 'date': s.date, 'format': s.format, 'topics': [t['text'] for t in _topics_text(db, s)],
                         'present': sum(x in ('var', 'gecikdi') for x in here), 'excused': sum(x == 'üzrlü' for x in here),
                         'students': len(ms), 'test_avg': test_p})
    students = []
    for m, ta_id in ms:
        st = [att.get((s.id, m.id)) for s in held]
        base = [x for x in st if x != 'üzrlü']
        present = sum(x in ('var', 'gecikdi') for x in st)
        pct = round(present * 100 / len(base), 1) if base else None
        last2 = st[-2:]
        before = _avg([p for t, p in main.get(m.id, []) if t < start])
        after = _avg([p for t, p in main.get(m.id, []) if t >= start])
        students.append({'student_id': m.id, 'full_name': m.full_name, 'class_name': db.get(SchoolClass, m.class_id).name,
                         'present': present, 'held': len(held), 'attendance_pct': pct,
                         'risk': len(last2) == 2 and all(x == 'yox' for x in last2),
                         'extra_test_avg': _avg([p for _, p in extra.get(m.id, [])]),
                         'before_pct': before, 'after_pct': after,
                         'delta': round(after - before, 1) if before is not None and after is not None else None})
    # iştirakçı (≥50 % iştirak) ↔ eyni siniflərdə qalan şagirdlər – kurs başlayandan sonrakı mövzu testi/sınaq ortası
    active = {s['student_id'] for s in students if (s['attendance_pct'] or 0) >= 50}
    others = {x.id for i in c.audience['ta_ids'] for x in roster(db, db.get(TeachingAssignment, i))} - active
    after_of = lambda ids: _avg([_avg([p for t, p in main.get(i, []) if t >= start]) for i in ids])
    by_format = {}
    for f in ('əyani', 'onlayn'):
        fs = [x for x in sessions if x['format'] == f]
        by_format[f] = {'held': len(fs), 'attendance_pct': _avg([x['present'] * 100 / x['students'] for x in fs if x['students']])}
    minutes = sum(_minutes(s.end) - _minutes(s.start) for s in held)
    return {
        'summary': {'sessions': len(ss), 'held': len(held), 'cancelled': sum(s.status == 'cancelled' for s in ss),
                    'planned_left': sum(s.status == 'planned' for s in ss), 'hours': round(minutes / 60, 1),
                    'students': len(ms), 'attendance_pct': _avg([s['attendance_pct'] for s in students]),
                    'extra_test_avg': _avg([s['extra_test_avg'] for s in students]),
                    'at_risk': sum(s['risk'] for s in students)},
        'compare': {'participants': len(active), 'participants_pct': after_of(active),
                    'others': len(others), 'others_pct': after_of(others)},
        'by_format': by_format, 'sessions': sessions, 'students': students,
    }


# ---------------------------------------------------------------- şagird portalı üçün
def student_courses(db: Session, s: Student) -> list[dict]:
    """Şagirdin kursları: plan (keçmiş və gələcək), öz iştirakı, məşğələ testlərinin nəticəsi.
    Onlayn keçid yalnız başlamazdan 10 dəqiqə əvvəldən bitənə qədər verilir."""
    t = now().astimezone(TZ)
    out = []
    for c in db.scalars(select(ExtraCourse).where(ExtraCourse.school_id == s.school_id, ExtraCourse.archived_at.is_(None))
                        .order_by(ExtraCourse.starts_on)):
        if s.id not in {m.id for m, _ in members(db, c)}:
            continue
        teacher = db.get(User, c.owner_id)
        rows, present, held = [], 0, 0
        for x in _sessions(db, c):
            a = db.get(ExtraAttendance, (x.id, s.id))
            beg, end = _when(x)
            live = x.status == 'planned' and beg - JOIN_BEFORE <= t <= end
            if x.status == 'held':
                held += a is None or a.status != 'üzrlü'
                present += bool(a and a.status in ('var', 'gecikdi'))
            test = None
            if x.batch_id:
                task = db.scalar(select(OnlineTask).where(OnlineTask.batch_id == x.batch_id))
                tids = [k.id for k in db.scalars(select(OnlineTask).where(OnlineTask.batch_id == x.batch_id))]
                at = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id.in_(tids), TaskAttempt.student_id == s.id,
                                                         TaskAttempt.submitted_at.is_not(None)))
                test = {'title': task.title if task else '', 'pct': round(at.correct * 100 / at.total, 1) if at and at.total else None}
            rows.append({'id': x.id, 'date': x.date, 'weekday': DAYS[x.date.weekday()], 'start': x.start, 'end': x.end,
                         'format': x.format, 'room': x.room, 'status': x.status, 'note': x.note,
                         'topics': [y['text'] for y in _topics_text(db, x)], 'goals': x.goals, 'resources': x.resources,
                         'homework': x.homework, 'recording_url': x.recording_url if x.status == 'held' else None,
                         'link': x.link if live and x.format == 'onlayn' else None, 'live': live,
                         'my_status': a.status if a else None, 'joined': bool(a and a.joined_at), 'test': test})
        out.append({'id': c.id, 'title': c.title, 'subject': c.subject, 'format': c.format, 'teacher': teacher.full_name,
                    'goal': c.goal, 'starts_on': c.starts_on, 'ends_on': c.ends_on, 'present': present, 'held': held,
                    'sessions': rows,
                    'next': next((r for r in rows if r['status'] == 'planned' and
                                  dt.datetime.combine(r['date'], dt.time.fromisoformat(r['end']), tzinfo=TZ) >= t), None)})
    return out


def join(db: Session, s: Student, sid: int) -> dict:
    x = db.get(ExtraSession, sid)
    c = x and db.get(ExtraCourse, x.course_id)
    if not c or c.archived_at or s.id not in {m.id for m, _ in members(db, c)}:
        raise HTTPException(404, 'Məşğələ tapılmadı')
    beg, end = _when(x)
    t = now().astimezone(TZ)
    if x.format != 'onlayn' or not x.link:
        raise HTTPException(400, 'Bu məşğələ əyanidir – otaq: ' + (x.room or 'müəllimdən soruşun'))
    if x.status != 'planned' or not (beg - JOIN_BEFORE <= t <= end):
        raise HTTPException(409, f'Keçid {beg - JOIN_BEFORE:%H:%M}-dan {end:%H:%M}-dək açıqdır')
    a = db.get(ExtraAttendance, (x.id, s.id)) or ExtraAttendance(session_id=x.id, student_id=s.id)
    a.joined_at = a.joined_at or now()
    db.merge(a)
    db.commit()
    return {'link': x.link}
