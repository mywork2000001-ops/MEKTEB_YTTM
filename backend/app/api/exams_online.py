"""Əlavə sınaq imtahanları (onlayn): planla əlaqəsiz, bir neçə sinfə eyni anda; nəticə «Sınaq jurnalı»na və reytinqə.

Qaydalar (docs/plan-test-uygunlugu-promtu.md §3.9–3.10):
- formativ və KSQ/BSQ qiymətinə təsir etmir (jurnala köçürülmür, fənn analitikasına qarışmır);
- reytinq: bal (düz − səhv ÷ N, cərimə seçilibsə) → faiz; bərabər bal – eyni yer; sinifdə və ümumi yer;
- müəllimin cəhdi sıfırladığı şagird «təkrar» nişanı ilə göstərilir;
- adlar: admin və sınağı yaradan müəllim hamını görür, digər müəllim yalnız öz siniflərinin şagirdlərini
  (başqa siniflər – yalnız yer və bal, adsız); şagird/valideyn yalnız öz yerini və ümumi statistikanı görür.
- admin məktəbin istənilən sinfinə (həmin sinfin fənn müəlliminin dərsinə) sınaq göndərə bilər."""
from __future__ import annotations

import copy
import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..services import ws_cond
from ..db import get_db
from ..deps import staff
from ..domain.rules import rank, summative_grade
from ..models import (AuditLog, OnlineTask, Role, SchoolClass, Student, TaskAttempt, TeachingAssignment, TestBatch,
                      User, now)
from ..services import class_grade, roster
from .common import audit, need_school
from .tasks import CustomQ, _snapshot, aware, custom_snapshot, expire_due, is_ok, purge_tasks, score

router = APIRouter(prefix='/api/exams-online', tags=['exams-online'])


# ---------------------------------------------------------------- icazələr
def _can_target(db: Session, user: User, ta_id: int) -> tuple[TeachingAssignment, SchoolClass]:
    ta = db.get(TeachingAssignment, ta_id)
    cls = ta and db.get(SchoolClass, ta.class_id)
    # yalnız aktiv məkanın sinfi: məktəb və fərdi (repetitor) sinif bir sınaqda qarışmır
    ok = ta and not ta.archived_at and cls and not cls.archived_at and cls.school_id == user.school_id and (
        ta.teacher_id == user.id or user.role == Role.admin)
    if not ok:
        raise HTTPException(404, 'Dərs tapılmadı')
    return ta, cls


def _tasks(db: Session, b: TestBatch) -> list[OnlineTask]:
    return list(db.scalars(select(OnlineTask).where(OnlineTask.batch_id == b.id, OnlineTask.archived_at.is_(None))
                           .order_by(OnlineTask.id)))


def _school_of(db: Session, b: TestBatch) -> int | None:
    t = db.scalar(select(OnlineTask).where(OnlineTask.batch_id == b.id))
    if not t:
        return None
    return db.get(SchoolClass, db.get(TeachingAssignment, t.assignment_id).class_id).school_id


def _access(db: Session, user: User, b: TestBatch) -> str:
    """full – bütün adlar; own – yalnız öz siniflərinin adları. Görə bilmirsə 404."""
    if b.kind != 'sinaq':
        raise HTTPException(404, 'Sınaq tapılmadı')
    if _school_of(db, b) not in (None, user.school_id):          # başqa məkanın (məktəb / fərdi) sınağı
        raise HTTPException(404, 'Sınaq tapılmadı')
    if b.created_by == user.id or (user.role == Role.admin and _school_of(db, b) == user.school_id):
        return 'full'
    mine = db.scalar(select(OnlineTask.id).join(TeachingAssignment, TeachingAssignment.id == OnlineTask.assignment_id)
                     .where(OnlineTask.batch_id == b.id, TeachingAssignment.teacher_id == user.id, ws_cond(user)))
    if mine is None:
        raise HTTPException(404, 'Sınaq tapılmadı')
    return 'own'


def _batch(db: Session, user: User, batch_id: int) -> tuple[TestBatch, str]:
    b = db.get(TestBatch, batch_id)
    if not b:
        raise HTTPException(404, 'Sınaq tapılmadı')
    return b, _access(db, user, b)


# ---------------------------------------------------------------- hesab
def _points(correct: int, wrong: int, penalty: int) -> float:
    return round(correct - (wrong / penalty if penalty else 0), 2)


def results(db: Session, b: TestBatch) -> dict:
    """Sınaq jurnalı (adlarla – çağıran tərəf məxfiliyi özü tətbiq edir)."""
    tasks = _tasks(db, b)
    retakes = {(int(a.entity_id), (a.details or {}).get('student_id')) for a in db.scalars(
        select(AuditLog).where(AuditLog.entity == 'task_attempt', AuditLog.action == 'delete',
                               AuditLog.entity_id.in_([str(t.id) for t in tasks])))} if tasks else set()
    rows, t0 = [], now()
    q_ok: list[int] = []
    q_n = 0
    meta = []
    for t in tasks:
        expire_due(db, t)
        ta = db.get(TeachingAssignment, t.assignment_id)
        cls = db.get(SchoolClass, ta.class_id)
        meta.append({'task_id': t.id, 'ta_id': ta.id, 'class_name': cls.name, 'teacher_id': ta.teacher_id,
                     'opens_at': aware(t.opens_at), 'closes_at': aware(t.closes_at),
                     'state': 'gözlənilir' if t0 < aware(t.opens_at) else 'açıqdır' if t0 < aware(t.closes_at) else 'bitib'})
        atts = {a.student_id: a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == t.id))}
        if not q_ok:
            q_ok = [0] * len(t.questions)
        for s in roster(db, ta):
            if t.student_ids is not None and s.id not in t.student_ids:
                continue
            a = atts.get(s.id)
            row = {'student_id': s.id, 'full_name': s.full_name, 'class_name': cls.name, 'task_id': t.id,
                   'ta_id': ta.id, 'teacher_id': ta.teacher_id, 'status': 'yazmayıb', 'correct': None, 'wrong': None,
                   'blank': None, 'points': None, 'pct': None, 'grade': None, 'retake': (t.id, s.id) in retakes,
                   'submitted_at': None}
            if a and a.submitted_at and a.total:
                ok = [is_ok(t, a, i) for i in range(len(t.questions))]
                blank = sum(1 for i in range(len(t.questions)) if (a.answers or {}).get(str(i)) in (None, ''))
                c = sum(ok)
                wrong = len(ok) - c - blank
                pts = _points(c, wrong, b.penalty)
                pct = round(max(0.0, pts) * 100 / len(ok), 1)
                row.update(status='yazıb', correct=c, wrong=wrong, blank=blank, points=pts, pct=pct,
                           grade=summative_grade(pct), submitted_at=aware(a.submitted_at))
                for i, v in enumerate(ok):
                    q_ok[i] += v
                q_n += 1
            elif a:
                row['status'] = 'yazır'
            rows.append(row)
    wrote = [r for r in rows if r['status'] == 'yazıb']
    for k, _, place in rank([(str(i), r['points']) for i, r in enumerate(rows) if r['status'] == 'yazıb']):
        rows[int(k)]['place_all'] = place
    by_class: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        by_class.setdefault(r['task_id'], []).append(i)
    classes = []
    for m in meta:
        idx = by_class.get(m['task_id'], [])
        for k, _, place in rank([(str(i), rows[i]['points']) for i in idx if rows[i]['status'] == 'yazıb']):
            rows[int(k)]['place_class'] = place
        w = [rows[i]['pct'] for i in idx if rows[i]['status'] == 'yazıb']
        classes.append({**m, 'students': len(idx), 'wrote': len(w),
                        'avg_pct': round(sum(w) / len(w), 1) if w else None, 'max_pct': max(w) if w else None})
    for k, _, place in rank([(str(i), c['avg_pct']) for i, c in enumerate(classes)]):
        classes[int(k)]['place'] = place
    for r in rows:
        r.setdefault('place_all', None)
        r.setdefault('place_class', None)
    rows.sort(key=lambda r: (r['place_all'] is None, r['place_all'] or 0, r['full_name']))
    qs = tasks[0].questions if tasks else []
    questions = [{'index': i, 'text': q['text'], 'kind': q['kind'], 'correct': q_ok[i] if q_ok else 0, 'of': q_n,
                  'pct': round(q_ok[i] * 100 / q_n, 1) if q_n else None} for i, q in enumerate(qs)]
    pcts = [r['pct'] for r in wrote]
    return {'batch': {'id': b.id, 'title': b.title, 'subject': b.subject, 'grade': b.grade, 'penalty': b.penalty,
                      'questions': len(qs), 'created_at': aware(b.created_at) if b.created_at else None},
            'summary': {'students': len(rows), 'wrote': len(wrote), 'avg_pct': round(sum(pcts) / len(pcts), 1) if pcts else None,
                        'max_pct': max(pcts) if pcts else None, 'min_pct': min(pcts) if pcts else None},
            'classes': classes, 'rows': rows, 'questions': questions}


def _private(res: dict, user: User, access: str) -> dict:
    """Başqa müəllimlərin siniflərindəki şagirdlərin adı gizlədilir (yer və bal qalır)."""
    if access == 'full':
        return res
    for r in res['rows']:
        if r['teacher_id'] != user.id:
            r['full_name'], r['student_id'] = None, None
    return res


# ---------------------------------------------------------------- API
@router.get('/targets')
def targets(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sınaq göndərilə bilən dərslər: müəllim – özününkülər; admin – məktəbin bütün dərsləri."""
    st = (select(TeachingAssignment, SchoolClass, User).select_from(TeachingAssignment)
          .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id).join(User, User.id == TeachingAssignment.teacher_id)
          .where(TeachingAssignment.archived_at.is_(None), SchoolClass.archived_at.is_(None)))
    st = st.where(SchoolClass.school_id == need_school(user)) if user.role == Role.admin else \
        st.where(TeachingAssignment.teacher_id == user.id, ws_cond(user))
    return [{'ta_id': ta.id, 'class_name': c.name, 'subject': ta.subject, 'grade': class_grade(db, c),
             'teacher': u.full_name, 'mine': ta.teacher_id == user.id, 'students': len(roster(db, ta))}
            for ta, c, u in db.execute(st.order_by(TeachingAssignment.subject, SchoolClass.name))]


@router.get('/targets/{ta_id}/students')
def target_students(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Kimə» seçicisi üçün: sinfin/qrupun şagirdləri və səviyyə qrupu (Jurnal → Səviyyə qrupları).
    Mövzu testi, sınaq, adi tapşırıq və yenidən göndərmə eyni siyahıdan istifadə edir."""
    from ..models import LevelOverride
    ta, _ = _can_target(db, user, ta_id)
    lv = {o.student_id: o.level for o in db.scalars(select(LevelOverride).where(LevelOverride.assignment_id == ta.id))}
    return [{'id': s.id, 'full_name': s.full_name, 'portal_code': s.portal_code, 'level': lv.get(s.id)}
            for s in sorted(roster(db, ta), key=lambda s: s.full_name)]


class ExamTarget(BaseModel):
    ta_id: int
    opens_at: dt.datetime
    closes_at: dt.datetime
    student_ids: list[int] | None = None


class ExamIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=2000)
    duration_min: int = Field(60, ge=1, le=300)
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)
    shuffle: bool = True
    show_answers: Literal['after_close', 'after_submit', 'never'] = 'after_close'
    penalty: Literal[0, 3, 4] = 0
    targets: list[ExamTarget] = Field(min_length=1, max_length=60)

    @model_validator(mode='after')
    def _v(self):
        if not self.bank_ids and not self.custom:
            raise ValueError('ən azı bir sual seçin')
        if len(self.bank_ids) + len(self.custom) > 100:
            raise ValueError('bir sınaqda ən çoxu 100 sual')
        if len({t.ta_id for t in self.targets}) != len(self.targets):
            raise ValueError('bir sinif iki dəfə seçilib')
        return self


@router.post('')
def create_exam(body: ExamIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    t0 = now()
    plan, subjects = [], set()
    for tg in body.targets:
        ta, cls = _can_target(db, user, tg.ta_id)
        subjects.add(ta.subject)
        o, c = (aware(x) for x in (tg.opens_at, tg.closes_at))
        if c <= o:
            raise HTTPException(400, f'{cls.name}: bitmə vaxtı başlamadan sonra olmalıdır')
        if c <= t0:
            raise HTTPException(400, f'{cls.name}: bitmə vaxtı keçmişdədir')
        if body.duration_min > (c - o).total_seconds() / 60:
            raise HTTPException(400, f'{cls.name}: həll müddəti ({body.duration_min} dəq) açıq qalma aralığından uzundur')
        if tg.student_ids is not None and (not tg.student_ids or set(tg.student_ids) - {s.id for s in roster(db, ta)}):
            raise HTTPException(400, f'{cls.name}: şagirdlər bu sinifdən/qrupdan seçilməlidir')
        plan.append((ta, cls, o, c, tg.student_ids))
    if len(subjects) > 1:
        raise HTTPException(400, 'Bir sınaq yalnız bir fənn üzrə ola bilər')
    qs = _snapshot(db, body.bank_ids) + [custom_snapshot(q) for q in body.custom]
    b = TestBatch(kind='sinaq', title=body.title, subject=plan[0][0].subject, grade=class_grade(db, plan[0][1]),
                  penalty=body.penalty, created_by=user.id)
    db.add(b)
    db.flush()
    for ta, cls, o, c, sids in plan:
        t = OnlineTask(assignment_id=ta.id, title=body.title, description=body.description, opens_at=o, closes_at=c,
                       duration_min=body.duration_min, questions=copy.deepcopy(qs), shuffle=body.shuffle,
                       show_answers=body.show_answers, student_ids=sids, created_by=user.id, kind='sinaq', batch_id=b.id)
        db.add(t)
        db.flush()
        audit(db, user, 'create', 'task', t.id, kind='sinaq', batch=b.id, class_name=cls.name, questions=len(qs))
    db.commit()
    return {'id': b.id, 'tasks': len(plan), 'questions': len(qs)}


@router.get('')
def list_exams(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Görə bildiyim sınaqlar: yaratdıqlarım, siniflərimə göndərilənlər, admin – məktəbin hamısı."""
    st = select(TestBatch).where(TestBatch.kind == 'sinaq').order_by(TestBatch.id.desc())
    out = []
    for b in db.scalars(st):
        try:
            _access(db, user, b)
        except HTTPException:
            continue
        all_tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.batch_id == b.id)))
        live = [t for t in all_tasks if t.archived_at is None]
        if not live:
            continue
        ts = live
        names = [db.get(SchoolClass, db.get(TeachingAssignment, t.assignment_id).class_id).name for t in ts]
        done = [a for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_([t.id for t in ts]),
                                                                TaskAttempt.submitted_at.is_not(None))) if a.total]
        t0 = now()
        o = min((aware(t.opens_at) for t in ts), default=None)
        c = max((aware(t.closes_at) for t in ts), default=None)
        out.append({'id': b.id, 'title': b.title, 'subject': b.subject, 'grade': b.grade, 'classes': names,
                    'opens_at': o, 'closes_at': c, 'questions': len(ts[0].questions) if ts else 0,
                    'mine': b.created_by == user.id, 'wrote': len(done),
                    'avg_pct': round(sum(a.correct * 100 / a.total for a in done) / len(done), 1) if done else None,
                    'state': 'gözlənilir' if o and t0 < o else 'açıqdır' if c and t0 < c else 'bitib'})
    return out


@router.get('/rating')
def rating(subject: str | None = None, grade: int | None = None, user: User = Depends(staff),
           db: Session = Depends(get_db)):
    """Kumulyativ reytinq: bütün sınaqlar üzrə orta faiz, iştirak, dinamika (son − əvvəlki), sinifdə və ümumi yer."""
    per: dict[int, dict] = {}
    batches = []
    for b in db.scalars(select(TestBatch).where(TestBatch.kind == 'sinaq').order_by(TestBatch.id)):
        if (subject and b.subject != subject) or (grade and b.grade != grade):
            continue
        try:
            access = _access(db, user, b)
        except HTTPException:
            continue
        if not _tasks(db, b):
            continue
        res = results(db, b)
        batches.append({'id': b.id, 'title': b.title, 'avg_pct': res['summary']['avg_pct']})
        for r in res['rows']:
            p = per.setdefault(r['student_id'], {'student_id': r['student_id'], 'full_name': r['full_name'],
                                                 'class_name': r['class_name'], 'visible': False, 'series': []})
            p['visible'] |= access == 'full' or r['teacher_id'] == user.id
            p['class_name'] = r['class_name']
            p['series'].append({'batch_id': b.id, 'pct': r['pct']})
    rows = []
    for p in per.values():
        got = [x['pct'] for x in p['series'] if x['pct'] is not None]
        p.update(count=len(got), avg_pct=round(sum(got) / len(got), 1) if got else None,
                 last_pct=got[-1] if got else None,
                 delta=round(got[-1] - got[-2], 1) if len(got) >= 2 else None)
        rows.append(p)
    for k, _, place in rank([(str(i), r['avg_pct']) for i, r in enumerate(rows)]):
        rows[int(k)]['place_all'] = place
    for cname in {r['class_name'] for r in rows}:
        idx = [i for i, r in enumerate(rows) if r['class_name'] == cname]
        for k, _, place in rank([(str(i), rows[i]['avg_pct']) for i in idx]):
            rows[int(k)]['place_class'] = place
    for r in rows:
        r.setdefault('place_all', None)
        r.setdefault('place_class', None)
        if not r.pop('visible'):
            r['full_name'], r['student_id'] = None, None
    rows.sort(key=lambda r: (r['place_all'] is None, r['place_all'] or 0, r['full_name'] or ''))
    improved = sorted([r for r in rows if r['delta'] is not None and r['delta'] > 0 and r['full_name']],
                      key=lambda r: -r['delta'])[:10]
    return {'batches': batches, 'rows': [r for r in rows if r['full_name']], 'total': len(rows), 'improved': improved}


@router.get('/{batch_id}')
def exam_results(batch_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    b, access = _batch(db, user, batch_id)
    res = _private(results(db, b), user, access)
    for c in res['classes']:                       # öz dərsim – testi idarə edə bilərəm (link, redaktə, yenidən göndər)
        ta = db.get(TeachingAssignment, db.get(OnlineTask, c['task_id']).assignment_id)
        c['ta_id'], c['own'] = ta.id, ta.teacher_id == user.id
    db.commit()                                    # expire_due avtomatik təhvilləri saxlasın
    return {**res, 'access': access}


@router.get('/{batch_id}/attempt/{task_id}/{student_id}')
def attempt_detail(batch_id: int, task_id: int, student_id: int, user: User = Depends(staff),
                   db: Session = Depends(get_db)):
    """Şagirdin cavabları (açıq sualları əl ilə yoxlamaq üçün) – yalnız öz sinfinin müəllimi və ya tam icazəli."""
    t, a = _editable_attempt(db, user, batch_id, task_id, student_id)
    return {'items': [{'index': i, 'kind': q['kind'], 'text': q['text'], 'options': q.get('options'),
                       'correct': q.get('correct'), 'answer': q.get('answer'), 'given': (a.answers or {}).get(str(i)),
                       'ok': is_ok(t, a, i), 'manual': (a.manual or {}).get(str(i))} for i, q in enumerate(t.questions)]}


def _editable_attempt(db: Session, user: User, batch_id: int, task_id: int, student_id: int):
    b, access = _batch(db, user, batch_id)
    t = db.get(OnlineTask, task_id)
    if not t or t.batch_id != b.id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    ta = db.get(TeachingAssignment, t.assignment_id)
    if access != 'full' and ta.teacher_id != user.id:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == student_id))
    if not a or not a.submitted_at:
        raise HTTPException(404, 'Şagird sınağı təhvil verməyib')
    return t, a


class ManualIn(BaseModel):
    index: int = Field(ge=0)
    ok: bool | None = None                   # None – düzəlişi götür (avtomatik yoxlama)


@router.put('/{batch_id}/attempt/{task_id}/{student_id}')
def set_manual(batch_id: int, task_id: int, student_id: int, body: ManualIn, user: User = Depends(staff),
               db: Session = Depends(get_db)):
    """Açıq sualın əl ilə yoxlanması (məs. «2,50» düz sayılmalıdır) – bal və reytinq yenidən hesablanır."""
    t, a = _editable_attempt(db, user, batch_id, task_id, student_id)
    if body.index >= len(t.questions):
        raise HTTPException(400, 'Belə sual yoxdur')
    if t.questions[body.index]['kind'] != 'open':
        raise HTTPException(400, 'Yalnız açıq sual əl ilə yoxlanılır')
    m = dict(a.manual or {})
    if body.ok is None:
        m.pop(str(body.index), None)
    else:
        m[str(body.index)] = body.ok
    a.manual = m or None
    score(t, a)
    audit(db, user, 'update', 'task_attempt', t.id, student_id=student_id, index=body.index, ok=body.ok)
    db.commit()
    return {'correct': a.correct, 'total': a.total}


@router.delete('/{batch_id}')
def delete_exam(batch_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sınaq sistemdən tam silinir (cəhdlər və nəticələr də – müəllim və şagird üçün). Tam icazəli – bütün siniflər üzrə;
    digər müəllim – yalnız öz siniflərindən."""
    b, access = _batch(db, user, batch_id)
    mine = [t for t in db.scalars(select(OnlineTask).where(OnlineTask.batch_id == b.id))
            if access == 'full' or db.get(TeachingAssignment, t.assignment_id).teacher_id == user.id]
    n = purge_tasks(db, mine)
    audit(db, user, 'delete', 'test_batch', batch_id, tasks=n)
    db.commit()
    return {'deleted': n}


# ---------------------------------------------------------------- formativ jurnal üçün (ayrıca sütun, ortaya daxil deyil)
def class_exams(db: Session, ta: TeachingAssignment, a: dt.date | None = None, b: dt.date | None = None) -> list[dict]:
    """Bu dərsin sınaqları keçirildiyi gün (açılma tarixi, məktəb vaxtı) üzrə: hər şagirdin faizi və qiyməti.
    Formativ jurnalda ayrıca «Sınaq» sütunu və yekunda ayrıca göstəricilər üçün – formativ ortaya qarışmır."""
    from zoneinfo import ZoneInfo
    from ..services import SCHOOL_TZ
    out, t0 = [], now()
    for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, OnlineTask.kind == 'sinaq',
                                                 OnlineTask.archived_at.is_(None)).order_by(OnlineTask.opens_at)):
        d = aware(t.opens_at).astimezone(ZoneInfo(SCHOOL_TZ)).date()
        bt = db.get(TestBatch, t.batch_id) if t.batch_id else None
        if not bt or (a and d < a) or (b and d > b):
            continue
        closed = t0 >= aware(t.closes_at)
        rows = {r['student_id']: {'status': r['status'] if r['status'] == 'yazıb' or not closed else 'yazmayıb',
                                  'pct': r['pct'], 'grade': r['grade']}
                for r in results(db, bt)['rows'] if r['task_id'] == t.id}
        out.append({'task_id': t.id, 'batch_id': bt.id, 'title': bt.title, 'date': d, 'closed': closed, 'rows': rows})
    return out


def exam_stats(exs: list[dict], student_id: int) -> dict:
    """Yekun üçün: yazdığı sınaq sayı, orta faiz, son faiz və dinamika (son − əvvəlki)."""
    got = [x['rows'][student_id]['pct'] for x in exs
           if student_id in x['rows'] and x['rows'][student_id]['status'] == 'yazıb']
    return {'exam_count': len(got), 'exam_pct': round(sum(got) / len(got), 1) if got else None,
            'exam_last': got[-1] if got else None,
            'exam_delta': round(got[-1] - got[-2], 1) if len(got) >= 2 else None}


# ---------------------------------------------------------------- şagird portalı üçün
def student_exams(db: Session, s: Student, task_ids: list[int]) -> list[dict]:
    """Şagirdin sınaqları: öz balı, sinifdə/ümumi yeri, orta və ən yüksək bal (başqasının adı yoxdur).
    Yer yalnız öz sinfinin testi bağlanandan sonra göstərilir (başqaları hələ yazır)."""
    t0, out = now(), []
    seen = set()
    for t in db.scalars(select(OnlineTask).where(OnlineTask.id.in_(task_ids), OnlineTask.kind == 'sinaq')
                        .order_by(OnlineTask.opens_at)):
        if t.batch_id in seen or t.batch_id is None:
            continue
        seen.add(t.batch_id)
        b = db.get(TestBatch, t.batch_id)
        closed = t0 >= aware(t.closes_at)
        item = {'batch_id': b.id, 'title': b.title, 'subject': b.subject, 'opens_at': aware(t.opens_at),
                'closes_at': aware(t.closes_at), 'closed': closed, 'questions': len(t.questions)}
        if closed:
            res = results(db, b)
            me = next((r for r in res['rows'] if r['student_id'] == s.id), None)
            mine_cls = [r for r in res['rows'] if r['task_id'] == t.id and r['status'] == 'yazıb']
            item.update(
                status=me['status'] if me else 'yazmayıb', correct=me and me['correct'], wrong=me and me['wrong'],
                blank=me and me['blank'], points=me and me['points'], pct=me and me['pct'],
                place_class=me and me['place_class'], class_count=len(mine_cls),
                place_all=me and me['place_all'], all_count=res['summary']['wrote'],
                avg_pct=res['summary']['avg_pct'], max_pct=res['summary']['max_pct'],
                class_avg_pct=round(sum(r['pct'] for r in mine_cls) / len(mine_cls), 1) if mine_cls else None)
        else:                                    # hələ açıqdır: öz faizi görünür, yer – bağlananda
            a = db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == s.id))
            if a and a.submitted_at and a.total:
                item.update(my_pct=round(a.correct * 100 / a.total, 1), my_correct=a.correct, my_total=a.total)
        out.append(item)
    return out
