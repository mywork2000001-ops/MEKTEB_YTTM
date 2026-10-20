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
import re
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..services import ws_cond
from ..db import get_db
from ..deps import staff
from ..domain.rules import rank, summative_grade
from ..models import (AuditLog, BankFile, BankQuestion, OnlineTask, Role, SchoolClass, Student, TaskAttempt, TeachingAssignment, TestBatch,
                      User, now)
from ..services import class_grade, roster
from .common import audit, need_school
from ..timing import NOT_DONE, closes_or_none, fits_window, is_unlimited
from .tasks import CustomQ, TestMinutes, _snapshot, aware, custom_snapshot, exam_score, expire_due, is_ok, purge_tasks, score

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


# ---------------------------------------------------------------- təkrar sınaq (docs/sinaq-tekrar-qadagasi-promtu.md)
def _file_counts(db: Session, bank_ids) -> Counter:
    """Suallar hansı viktorina faylından və neçəsi (bank_id → BankQuestion.file_id)."""
    ids = {i for i in bank_ids if i}
    if not ids:
        return Counter()
    return Counter(f for _, f in db.execute(select(BankQuestion.id, BankQuestion.file_id).where(BankQuestion.id.in_(ids))))


def _norm_q(text) -> str:
    t = (text.get('az') or next(iter(text.values()), '')) if isinstance(text, dict) else (text or '')
    return re.sub(r'[\s$\\{}.,;:()]+', '', str(t)).lower()


def _text_index(db: Session) -> dict[str, int]:
    """Bankdakı sınaq suallarının mətni → fayl (fayl adını/yerini dəyişsə də, verilmiş sınaq tanınsın)."""
    idx: dict[str, int] = {}
    for qid, fid, text in db.execute(select(BankQuestion.id, BankQuestion.file_id, BankQuestion.text).join(BankFile)
                                     .where(BankQuestion.active.is_(True), BankFile.active.is_(True), BankFile.kind == 'sinaq')):
        k = _norm_q(text)
        if len(k) > 12:
            idx.setdefault(k, fid)
    return idx


def _task_counts(db: Session, qs: list, idx: dict[str, int]) -> Counter:
    """Tapşırığın sualları hansı fayldan: bank nömrəsi ilə VƏ mətnlə (hansı çoxdursa)."""
    by_id = _file_counts(db, [q.get('bank_id') for q in qs if isinstance(q, dict)])
    by_text = Counter(f for q in qs if isinstance(q, dict) and (f := idx.get(_norm_q(q.get('text')))))
    return Counter({f: max(by_id.get(f, 0), by_text.get(f, 0)) for f in set(by_id) | set(by_text)})


def _full(used: int, of: int) -> bool:
    """Faylın suallarının ən azı yarısı – «bu sınaq verilib» (azı – «qismən istifadə olunub»)."""
    return used * 2 >= max(1, of)


def given_files(db: Session, ta_ids: list[int]) -> dict[int, dict]:
    """Bu dərslərə verilmiş (arxivlənməmiş) sınaqların faylları: {file_id: {label, of, used, full, classes:[…]}}."""
    if not ta_ids:
        return {}
    tasks = list(db.scalars(select(OnlineTask).where(OnlineTask.assignment_id.in_(ta_ids), OnlineTask.kind == 'sinaq',
                                                     OnlineTask.archived_at.is_(None)).order_by(OnlineTask.opens_at)))
    idx = _text_index(db) if tasks else {}
    per = [(t, _task_counts(db, t.questions or [], idx)) for t in tasks]
    fids = {f for _, c in per for f in c}
    if not fids:
        return {}
    files = {f.id: f for f in db.scalars(select(BankFile).where(BankFile.id.in_(fids)))}
    names: dict[int, str] = {}
    out: dict[int, dict] = {}
    for t, cnt in per:
        if t.assignment_id not in names:
            names[t.assignment_id] = db.get(SchoolClass, db.get(TeachingAssignment, t.assignment_id).class_id).name
        for fid, n in cnt.items():
            f = files.get(fid)
            of = f.question_count if f and f.question_count else n
            e = out.setdefault(fid, {'label': f.label if f else '', 'of': of, 'used': 0, 'full': False, 'classes': []})
            e['used'] = max(e['used'], n)
            e['full'] = e['full'] or _full(n, of)
            e['classes'].append({'ta_id': t.assignment_id, 'class_name': names[t.assignment_id], 'title': t.title,
                                 'at': aware(t.opens_at), 'batch_id': t.batch_id, 'full': _full(n, of)})
    return out


def repeats(db: Session, ta_ids: list[int], cnt: Counter) -> list[dict]:
    """Yeni sınağın sualları bu dərslərdən hansına artıq verilmiş faylı təkrarlayır."""
    given = given_files(db, ta_ids)
    return [{'class_name': c['class_name'], 'ta_id': c['ta_id'], 'label': g['label'], 'title': c['title'],
             'at': c['at'].isoformat()}
            for fid, n in cnt.items() if (g := given.get(fid)) and _full(n, g['of'])
            for c in g['classes'] if c['full']]


def _nth(n: int | None) -> str:
    """Sinif sıra şəkilçisi: 9-cu, 10-cu, 11-ci, 6-cı, 3-cü."""
    return f"{n}-{_SUFFIX.get(n, 'ci')}" if n else '?'


_SUFFIX = {3: 'cü', 4: 'cü', 6: 'cı', 9: 'cu', 10: 'cu'}


def grade_fits(f: BankFile | None, grade: int | None) -> bool:
    """Sinfə avtomatik yalnız öz sinfinin sınağı: 11 → yalnız «11» işarəli fayl. Başqa sinfin və ya sinfi göstərilməmiş
    fayl – yalnız müəllimin təsdiqi ilə. Sinfin rəqəmi bilinmirsə yoxlanmır."""
    return f is None or grade is None or grade in (f.grades or [])


def grade_issues(db: Session, classes: list[tuple[str, int | None]], cnt: Counter) -> list[dict]:
    """Yeni sınağın faylları hansı sinfə uyğun deyil (sinif adı, sinif rəqəmi, fayl, faylın sinifləri)."""
    files = {f.id: f for f in db.scalars(select(BankFile).where(BankFile.id.in_(list(cnt) or [0])))}
    return [{'class_name': name, 'grade': g, 'label': f.label, 'grades': f.grades or []}
            for fid in cnt if (f := files.get(fid)) for name, g in classes if not grade_fits(f, g)]


# ---------------------------------------------------------------- hesab
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
    # sinif (dərs) üzrə: «Yenidən göndər» eyni paketə əlavə olunur – şagird bir dəfə, son təhvil verdiyi cəhdi ilə
    by_ta: dict[int, list[OnlineTask]] = {}
    for t in tasks:
        by_ta.setdefault(t.assignment_id, []).append(t)
    for ta_id, ts in by_ta.items():
        ts.sort(key=lambda x: (aware(x.opens_at), x.id))
        for t in ts:
            expire_due(db, t)
        ta = db.get(TeachingAssignment, ta_id)
        cls = db.get(SchoolClass, ta.class_id)
        o, c = min(aware(t.opens_at) for t in ts), max(aware(t.closes_at) for t in ts)
        meta.append({'task_id': ts[-1].id, 'task_ids': [t.id for t in ts], 'ta_id': ta.id, 'class_name': cls.name,
                     'teacher_id': ta.teacher_id, 'opens_at': o, 'closes_at': c,
                     'state': 'gözlənilir' if t0 < o else 'açıqdır' if t0 < c else 'bitib'})
        atts: dict[tuple[int, int], TaskAttempt] = {(a.task_id, a.student_id): a for a in db.scalars(
            select(TaskAttempt).where(TaskAttempt.task_id.in_([t.id for t in ts])))}
        if not q_ok:
            q_ok = [0] * len(ts[0].questions)
        for st in roster(db, ta):
            mine = [t for t in ts if t.student_ids is None or st.id in t.student_ids]
            if not mine:
                continue
            got = [(t, atts[(t.id, st.id)]) for t in mine if (t.id, st.id) in atts]
            done = sorted([(t, a) for t, a in got if a.submitted_at and a.total], key=lambda x: aware(x[1].submitted_at))
            t, a = done[-1] if done else (mine[-1], None)
            row = {'student_id': st.id, 'full_name': st.full_name, 'class_name': cls.name, 'task_id': t.id,
                   'ta_id': ta.id, 'teacher_id': ta.teacher_id, 'status': 'yazmayıb', 'correct': None, 'wrong': None,
                   'blank': None, 'points': None, 'pct': None, 'grade': None,
                   'retake': any((x.id, st.id) in retakes for x in mine), 'late': bool(done) and t.id != ts[0].id,
                   'submitted_at': None}
            if a:
                sc = exam_score(t, a, b.penalty)
                row.update(status='yazıb', **sc, grade=summative_grade(sc['pct']), submitted_at=aware(a.submitted_at))
                if len(t.questions) == len(q_ok):         # sual analizi – eyni suallı siniflər üzrə
                    for i in range(len(q_ok)):
                        q_ok[i] += is_ok(t, a, i)
                    q_n += 1
            elif any(not x.submitted_at for _, x in got):
                row['status'] = 'yazır'
                row['task_id'] = next(x for x, y in got if not y.submitted_at).id
            elif any(t0 < aware(x.closes_at) for x in mine):
                # vaxtı bitməyib – hələ yaza bilər; müddətsiz açıq test – «işlənməyib»
                row['status'] = NOT_DONE if any(is_unlimited(x) and t0 >= aware(x.opens_at) for x in mine) else 'gözlənilir'
            rows.append(row)
    wrote = [r for r in rows if r['status'] == 'yazıb']
    for k, _, place in rank([(str(i), r['points']) for i, r in enumerate(rows) if r['status'] == 'yazıb']):
        rows[int(k)]['place_all'] = place
    by_class: dict[int, list[int]] = {}
    for i, r in enumerate(rows):
        by_class.setdefault(r['ta_id'], []).append(i)
    classes = []
    for m in meta:
        idx = by_class.get(m['ta_id'], [])
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


def closed_results(db: Session, b: TestBatch) -> dict:
    """results() – bağlanmış paket üçün qısa keşlə (app/result_cache.py). Nəticə YALNIZ oxunur (dəyişdirmə)."""
    from .. import result_cache
    tasks = _tasks(db, b)
    if not tasks or now() < max(aware(t.closes_at) for t in tasks):
        return results(db, b)
    key = (b.id, str(b.created_at))
    res = result_cache.get(key)
    if res is None:
        res = results(db, b)
        result_cache.put(key, res)
    return res


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


@router.get('/given')
def given(ta_ids: str = '', user: User = Depends(staff), db: Session = Depends(get_db)):
    """Seçilmiş dərslərə artıq verilmiş sınaq faylları (BankPicker «verilib» nişanı)."""
    ok = []
    for x in {int(x) for x in ta_ids.split(',') if x.strip().isdigit()}:
        try:
            ok.append(_can_target(db, user, x)[0].id)
        except HTTPException:
            continue
    return {str(k): v for k, v in given_files(db, ok).items()}


class ExamTarget(BaseModel):
    ta_id: int
    opens_at: dt.datetime
    closes_at: dt.datetime | None = None        # boş – son tarix yoxdur
    student_ids: list[int] | None = None


class ExamIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(None, max_length=2000)
    duration_min: TestMinutes = 0               # 0 – taymer yoxdur
    bank_ids: list[int] = Field(default_factory=list)
    custom: list[CustomQ] = Field(default_factory=list)
    shuffle: bool = True
    show_answers: Literal['after_close', 'after_submit', 'never'] = 'after_close'
    penalty: Literal[0, 3, 4] = 0
    targets: list[ExamTarget] = Field(min_length=1, max_length=60)
    allow_repeat: bool = False                  # bilərəkdən təkrar – müəllim təsdiqləyib
    allow_other_grade: bool = False             # başqa sinfin / sinifsiz sınaq – müəllim təsdiqləyib

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
        o, c = aware(tg.opens_at), closes_or_none(tg.closes_at)
        if c <= o:
            raise HTTPException(400, f'{cls.name}: bitmə vaxtı başlamadan sonra olmalıdır')
        if c <= t0:
            raise HTTPException(400, f'{cls.name}: bitmə vaxtı keçmişdədir')
        if not fits_window(body.duration_min, o, c):
            raise HTTPException(400, f'{cls.name}: həll müddəti ({body.duration_min} dəq) açıq qalma aralığından uzundur')
        if tg.student_ids is not None and (not tg.student_ids or set(tg.student_ids) - {s.id for s in roster(db, ta)}):
            raise HTTPException(400, f'{cls.name}: şagirdlər bu sinifdən/qrupdan seçilməlidir')
        plan.append((ta, cls, o, c, tg.student_ids))
    if len(subjects) > 1:
        raise HTTPException(400, 'Bir sınaq yalnız bir fənn üzrə ola bilər')
    qs = _snapshot(db, body.bank_ids) + [custom_snapshot(q) for q in body.custom]
    title = body.title.strip()
    names = {p[0].id: p[1].name for p in plan}
    cnt = _task_counts(db, qs, _text_index(db))           # fayl nömrəsi və mətn üzrə (fayl yerini dəyişsə də)
    rep = repeats(db, list(names), cnt)
    bad = grade_issues(db, [(cls.name, class_grade(db, cls)) for _, cls, *_ in plan], cnt)
    if bad and not body.allow_other_grade:
        x = bad[0]
        whose = f"{', '.join(_nth(g) for g in x['grades'])} sinfin" if x['grades'] else 'sinfi göstərilməmiş'
        raise HTTPException(409, {'message': f'«{x["label"]}» {whose} sınağıdır, {x["class_name"]} isə {_nth(x["grade"])} sinifdir. '
                                             'Sinfə yalnız öz sinfinin sınağı verilir – başqasını vermək üçün təsdiq edin.',
                                  'grade': bad})
    # eyni dərsdə eyni adlı aktiv sınaq – siyahıda iki eyni sətir olardı
    same = [{'class_name': names[t.assignment_id], 'title': t.title, 'at': aware(t.opens_at).isoformat()}
            for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id.in_(list(names)), OnlineTask.kind == 'sinaq',
                                                         OnlineTask.archived_at.is_(None)))
            if t.title.strip().casefold() == title.casefold()]
    if (rep or same) and not body.allow_repeat:
        first = (rep or same)[0]
        what = f'«{first.get("label") or first["title"]}»' if rep else f'«{title}» adlı sınaq'
        raise HTTPException(409, {'message': f'{what} {first["class_name"]} sinfinə artıq verilib – təkrar sınaq qarışıqlıq '
                                             'yaradır. Başqa sınaq seçin və ya «Bilərəkdən təkrar» qutusunu işarələyin.',
                                  'repeat': rep, 'same_title': same})
    if (rep or same) and 'təkrar' not in title.casefold():
        title = f'{title[:190]} (təkrar)'
    b = TestBatch(kind='sinaq', title=title, subject=plan[0][0].subject, grade=class_grade(db, plan[0][1]),
                  penalty=body.penalty, created_by=user.id)
    db.add(b)
    db.flush()
    for ta, cls, o, c, sids in plan:
        t = OnlineTask(assignment_id=ta.id, title=title, description=body.description, opens_at=o, closes_at=c,
                       duration_min=body.duration_min, questions=copy.deepcopy(qs), shuffle=body.shuffle,
                       show_answers=body.show_answers, student_ids=sids, created_by=user.id, kind='sinaq', batch_id=b.id)
        db.add(t)
        db.flush()
        audit(db, user, 'create', 'task', t.id, kind='sinaq', batch=b.id, class_name=cls.name, questions=len(qs),
              repeat=bool(rep or same), other_grade=bool(bad))
    db.commit()
    return {'id': b.id, 'tasks': len(plan), 'questions': len(qs), 'title': title}


@router.get('')
def list_exams(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Görə bildiyim sınaqlar: yaratdıqlarım, siniflərimə göndərilənlər, admin – məktəbin hamısı."""
    # toplu sorğular (əvvəl hər paket üçün 6–8 sorğu idi); icazə qaydası _access ilə eynidir
    batches = list(db.scalars(select(TestBatch).where(TestBatch.kind == 'sinaq').order_by(TestBatch.id.desc())))
    per: dict[int, list] = {}
    for t, ta, cls in db.execute(select(OnlineTask, TeachingAssignment, SchoolClass)
                                 .join(TeachingAssignment, TeachingAssignment.id == OnlineTask.assignment_id)
                                 .join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
                                 .where(OnlineTask.batch_id.in_([b.id for b in batches] or [-1])).order_by(OnlineTask.id)):
        per.setdefault(t.batch_id, []).append((t, ta, cls))
    seen = []
    for b in batches:
        rows = per.get(b.id, [])
        live = [r for r in rows if r[0].archived_at is None]
        if not live or rows[0][2].school_id != user.school_id:        # boş və ya başqa məkanın sınağı
            continue
        if not (b.created_by == user.id or user.role == Role.admin
                or any(ta.teacher_id == user.id for _, ta, _ in rows)):
            continue
        seen.append((b, live))
    done: dict[int, list] = {}
    for a in db.scalars(select(TaskAttempt).where(TaskAttempt.task_id.in_([t.id for _, live in seen for t, _, _ in live] or [-1]),
                                                  TaskAttempt.submitted_at.is_not(None))):
        if a.total:
            done.setdefault(a.task_id, []).append(a)
    t0, out = now(), []
    for b, live in seen:
        pcts = [exam_score(t, a, b.penalty)['pct'] for t, _, _ in live for a in done.get(t.id, [])]
        o = min(aware(t.opens_at) for t, _, _ in live)
        c = max(aware(t.closes_at) for t, _, _ in live)
        out.append({'id': b.id, 'title': b.title, 'subject': b.subject, 'grade': b.grade, 'classes': [cls.name for _, _, cls in live], 'ta_ids': sorted({ta.id for _, ta, _ in live}),
                    'opens_at': o, 'closes_at': c, 'questions': len(live[0][0].questions),
                    'mine': b.created_by == user.id, 'wrote': len(pcts),
                    'avg_pct': round(sum(pcts) / len(pcts), 1) if pcts else None,
                    'state': 'gözlənilir' if t0 < o else 'açıqdır' if t0 < c else 'bitib'})
    return out


@router.post('/{batch_id}/close')
def close_exam(batch_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Bağla»: sınaq öz siniflərimdə dərhal bağlanır (müddətsiz sınağı bitirmək üçün); yarımçıq cəhdlər təhvil verilir."""
    from .tasks import close_task
    b, access = _batch(db, user, batch_id)
    n = tasks_n = 0
    for t in _tasks(db, b):
        if access != 'full' and db.get(TeachingAssignment, t.assignment_id).teacher_id != user.id:
            continue
        if aware(t.closes_at) > now():
            n += close_task(db, t)
            tasks_n += 1
    audit(db, user, 'update', 'test_batch', batch_id, closed=tasks_n, auto_submitted=n)
    db.commit()
    return {'ok': True, 'closed': tasks_n, 'auto_submitted': n}


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
    from .. import result_cache
    t, a = _editable_attempt(db, user, batch_id, task_id, student_id)
    b = db.get(TestBatch, t.batch_id)
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
    result_cache.forget(b.id)
    audit(db, user, 'update', 'task_attempt', t.id, student_id=student_id, index=body.index, ok=body.ok)
    db.commit()
    return {'correct': a.correct, 'total': a.total}


class ExamRename(BaseModel):
    title: str = Field(max_length=200)

    @model_validator(mode='after')
    def _strip(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError('Sınağın adı boş ola bilməz')
        return self


@router.patch('/{batch_id}')
def rename_exam(batch_id: int, data: ExamRename, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sınağın adı bütün siniflərdə birdən dəyişir (paket + tapşırıqlar) – yalnız yaradan və ya admin
    (docs/test-sinaq-siyahi-promtu.md §2). Vaxt və suallar – hər sinif üçün tapşırıq redaktoru ilə."""
    b, access = _batch(db, user, batch_id)
    if access != 'full':
        raise HTTPException(403, 'Sınağın adını yalnız onu yaradan müəllim və ya admin dəyişə bilər')
    old = b.title
    b.title = data.title
    for t in db.scalars(select(OnlineTask).where(OnlineTask.batch_id == b.id)):
        t.title = data.title
    audit(db, user, 'update', 'test_batch', batch_id, title=[old, data.title])
    db.commit()
    return {'id': b.id, 'title': b.title}


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
    per: dict[int, list[OnlineTask]] = {}          # paket üzrə (yenidən göndərmə eyni sınaqdır – bir sütun)
    for t in db.scalars(select(OnlineTask).where(OnlineTask.assignment_id == ta.id, OnlineTask.kind == 'sinaq',
                                                 OnlineTask.archived_at.is_(None), OnlineTask.batch_id.is_not(None))
                        .order_by(OnlineTask.opens_at)):
        per.setdefault(t.batch_id, []).append(t)
    for bid, ts in per.items():
        d = aware(ts[0].opens_at).astimezone(ZoneInfo(SCHOOL_TZ)).date()
        bt = db.get(TestBatch, bid)
        if not bt or (a and d < a) or (b and d > b):
            continue
        closed = all(t0 >= aware(t.closes_at) for t in ts)
        rows = {r['student_id']: {'status': r['status'] if r['status'] == 'yazıb' or not closed else 'yazmayıb',
                                  'pct': r['pct'], 'grade': r['grade']}
                for r in closed_results(db, bt)['rows'] if r['ta_id'] == ta.id}
        out.append({'task_id': ts[0].id, 'batch_id': bt.id, 'title': bt.title, 'date': d, 'closed': closed, 'rows': rows})
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
    per: dict[int, list[OnlineTask]] = {}          # paket üzrə – yenidən göndərilən tapşırıq eyni sınaqdır
    for t in db.scalars(select(OnlineTask).where(OnlineTask.id.in_(task_ids), OnlineTask.kind == 'sinaq',
                                                 OnlineTask.batch_id.is_not(None)).order_by(OnlineTask.opens_at)):
        per.setdefault(t.batch_id, []).append(t)
    for bid, ts in per.items():
        t = ts[0]
        b = db.get(TestBatch, bid)
        closed = all(t0 >= aware(x.closes_at) for x in ts)
        item = {'batch_id': b.id, 'title': b.title, 'subject': b.subject, 'opens_at': aware(t.opens_at),
                'closes_at': max(aware(x.closes_at) for x in ts), 'closed': closed, 'questions': len(t.questions)}
        if closed:
            res = closed_results(db, b)
            me = next((r for r in res['rows'] if r['student_id'] == s.id), None)
            mine_cls = [r for r in res['rows'] if me and r['ta_id'] == me['ta_id'] and r['status'] == 'yazıb']
            item.update(
                status=me['status'] if me else 'yazmayıb', correct=me and me['correct'], wrong=me and me['wrong'],
                blank=me and me['blank'], points=me and me['points'], pct=me and me['pct'],
                place_class=me and me['place_class'], class_count=len(mine_cls),
                place_all=me and me['place_all'], all_count=res['summary']['wrote'],
                avg_pct=res['summary']['avg_pct'], max_pct=res['summary']['max_pct'],
                class_avg_pct=round(sum(r['pct'] for r in mine_cls) / len(mine_cls), 1) if mine_cls else None)
        else:                                    # hələ açıqdır: öz faizi görünür, yer – bağlananda
            done = [(x, a) for x in ts if (a := db.scalar(select(TaskAttempt).where(
                TaskAttempt.task_id == x.id, TaskAttempt.student_id == s.id))) and a.submitted_at and a.total]
            if done:
                x, a = max(done, key=lambda p: aware(p[1].submitted_at))
                item.update(my_pct=exam_score(x, a, b.penalty)['pct'], my_correct=a.correct, my_total=a.total)
        out.append(item)
    return out


# ---------------------------------------------------------------- köhnə təkrar paketlər (miqrasiya)
def merge_resend_batches(bind) -> int:
    """Miqrasiya e5a7c9d1f3b6: «Yenidən göndər» ilə yaranmış tək-tapşırıqlı sınaq paketlərini mənbə paketinə birləşdirir."""
    import json
    import sqlalchemy as sa
    merged = 0
    src_of = {}
    for eid, details in bind.execute(sa.text(
            "SELECT entity_id, details FROM audit_log WHERE entity = 'task' AND action = 'create'")).fetchall():
        d = json.loads(details) if isinstance(details, str) else (details or {})
        if d.get('copied_from') and str(eid).isdigit():
            src_of[int(eid)] = int(d['copied_from'])
    tasks = {r[0]: {'kind': r[1], 'batch': r[2]} for r in bind.execute(sa.text(
        'SELECT id, kind, batch_id FROM online_tasks')).fetchall()}
    for tid in sorted(src_of):
        t, s = tasks.get(tid), tasks.get(src_of[tid])
        if not t or not s or t['kind'] != 'sinaq' or s['kind'] != 'sinaq' or not s['batch'] or t['batch'] == s['batch']:
            continue
        if t['batch'] is not None:
            n = bind.execute(sa.text('SELECT COUNT(*) FROM online_tasks WHERE batch_id = :b'), {'b': t['batch']}).scalar()
            if n != 1:
                continue
        old = t['batch']
        bind.execute(sa.text('UPDATE online_tasks SET batch_id = :b WHERE id = :i'), {'b': s['batch'], 'i': tid})
        if old is not None:
            bind.execute(sa.text('DELETE FROM test_batches WHERE id = :b'), {'b': old})
        t['batch'] = s['batch']
        merged += 1
    return merged
