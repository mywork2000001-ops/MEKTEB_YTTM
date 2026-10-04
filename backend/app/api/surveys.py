"""Şagird sorğusu – müəllimin işi haqqında anonim rəy (docs/muellim-sorgusu-promtu.md).

- Müəllim sorğunu hazır şablondan yaradır, açıq link alır (ümumi və ya sinif/qrup üçün) – WhatsApp-da göndərir, QR çap edir.
- Şagird linki girişsiz açır (/s/{token}) və ya sorğunu öz tətbiqində (portal) görür.
- repeat=weekly: hər tədris həftəsində bir dəfə cavab (nəticələr həftələr üzrə, dinamika ilə).
- Anonimlik: cavabda şagird, IP, cihaz yoxdur; təkrar göndərmə yalnız ayrıca heşlə yoxlanır; nəticə ≥ min_group cavabda görünür."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import random
import secrets
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import ai
from ..config import settings
from ..db import get_db
from ..deps import require, staff
from ..domain import survey as SV
from ..models import (AiReview, GroupMember, Role, SchoolClass, Student, Survey, SurveyDedup, SurveyLink, SurveyQuestion,
                      SurveyResponse, TeachingAssignment, User, now)
from ..security import SESSION_COOKIE, read_session
from ..services import own_assignment
from .common import ConfirmIn, audit, check_confirm

router = APIRouter(prefix='/api', tags=['surveys'])
student_only = require(Role.student)
DEVICE_COOKIE = 'mk_sv'
BAKU = dt.timezone(dt.timedelta(hours=4))
_hits: dict[str, list[float]] = {}           # link üzrə sadə sürət limiti (IP saxlanmır)


# ---------------------------------------------------------------- köməkçilər
def aware(t: dt.datetime | None) -> dt.datetime | None:
    return t if t is None or t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def period_of(s: Survey, t: dt.datetime | None = None) -> str:
    """Həftəlik sorğuda ISO həftə (Bakı vaxtı ilə): «2026-W40»; birdəfəlik sorğuda «once»."""
    if s.repeat != 'weekly':
        return 'once'
    y, w, _ = (t or now()).astimezone(BAKU).isocalendar()
    return f'{y}-W{w:02d}'


def week_label(p: str) -> str:
    """«2026-W40» → «28.09–04.10.2026» (iş həftəsi bazar ertəsindən)."""
    try:
        y, w = int(p[:4]), int(p[6:])
        mon = dt.date.fromisocalendar(y, w, 1)
        sun = mon + dt.timedelta(days=6)
        return f'{mon:%d.%m}–{sun:%d.%m.%Y}'
    except (ValueError, IndexError):
        return p


def is_open(s: Survey) -> bool:
    t = now()
    return (s.status == 'open' and not s.archived_at and (not s.opens_at or aware(s.opens_at) <= t)
            and (not s.closes_at or aware(s.closes_at) > t))


def state(s: Survey) -> str:
    if s.archived_at:
        return 'archived'
    if s.status == 'open' and s.closes_at and aware(s.closes_at) <= now():
        return 'closed'
    if s.status == 'open' and s.opens_at and aware(s.opens_at) > now():
        return 'scheduled'
    return s.status


def own(db: Session, user: User, sid: int) -> Survey:
    """Yalnız öz sorğunuz və yalnız aktiv məkanda (məktəb və fərdi məkan qarışmır)."""
    s = db.get(Survey, sid)
    if not s or s.owner_id != user.id or s.school_id != user.school_id:
        raise HTTPException(404, 'Sorğu tapılmadı')
    return s


def questions(db: Session, sid: int) -> list[SurveyQuestion]:
    return list(db.scalars(select(SurveyQuestion).where(SurveyQuestion.survey_id == sid).order_by(SurveyQuestion.order)))


def q_dict(q: SurveyQuestion) -> dict:
    return {'id': q.id, 'key': q.key, 'section': q.section, 'kind': q.kind, 'text': q.text, 'options': q.options,
            'required': q.required, 'reverse': q.reverse}


def link_mode(s: Survey, l: SurveyLink | None) -> str:
    """full | short: linkin öz rejimi; «auto» – həftəlik qısa sorğuda short, qalan hallarda full."""
    if l is not None and l.mode in ('full', 'short'):
        return l.mode
    return 'short' if s.repeat == 'weekly' and s.pulse else 'full'


def served(db: Session, s: Survey, l: SurveyLink | None = None, variant: int | None = None) -> list[dict]:
    """Şagirdə verilən suallar. Qısa rejim: hər meyardan bir sual + ümumi bal (+ bir açıq sual) – həftəlik sorğuda
    həftəyə görə, birdəfəlik sorğuda variant nömrəsinə görə (hər şagird başqa dəst – birlikdə bütün anket əhatə olunur)."""
    qs = [q_dict(q) for q in questions(db, s.id)]
    if link_mode(s, l) == 'full':
        return qs
    return SV.pulse_pick(qs, period_of(s) if s.repeat == 'weekly' else (variant or 0))


def n_responses(db: Session, sid: int) -> int:
    return db.scalar(select(func.count()).select_from(SurveyResponse).where(SurveyResponse.survey_id == sid)) or 0


def _h(*parts) -> str:
    return hashlib.sha256('|'.join([settings().secret_key, *map(str, parts)]).encode()).hexdigest()


def student_hash(s: Survey, user_id: int, period: str) -> str:
    return _h('survey', s.id, 'u', user_id, period)


def teacher_classes(db: Session, owner_id: int, school_id: int | None) -> set[int]:
    return set(db.scalars(select(TeachingAssignment.class_id).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
                          .where(TeachingAssignment.teacher_id == owner_id, TeachingAssignment.archived_at.is_(None),
                                 SchoolClass.school_id == school_id, SchoolClass.archived_at.is_(None))))


def student_classes(db: Session, st: Student) -> set[int]:
    return set(db.scalars(select(GroupMember.group_id).where(GroupMember.student_id == st.id))) | {st.class_id}


# ---------------------------------------------------------------- müəllim: siyahı və yaratma
def survey_out(db: Session, s: Survey, full: bool = False) -> dict:
    links = list(db.scalars(select(SurveyLink).where(SurveyLink.survey_id == s.id).order_by(SurveyLink.id)))
    counts = dict(db.execute(select(SurveyResponse.link_id, func.count()).where(SurveyResponse.survey_id == s.id)
                             .group_by(SurveyResponse.link_id)).all())
    out = {'id': s.id, 'title': s.title, 'description': s.description, 'status': s.status, 'state': state(s),
           'opens_at': aware(s.opens_at), 'closes_at': aware(s.closes_at), 'min_group': s.min_group, 'repeat': s.repeat,
           'in_app': s.in_app, 'pulse': s.pulse, 'served': len(served(db, s)), 'wave': s.wave, 'root_id': s.root_id, 'created_at': aware(s.created_at),
           'archived_at': aware(s.archived_at), 'responses': sum(counts.values()), 'period': period_of(s),
           'links': [{'id': l.id, 'token': l.token, 'url': f'/s/{l.token}', 'label': l.label, 'class_id': l.class_id,
                      'active': l.active, 'responses': counts.get(l.id, 0), 'mode': l.mode, 'effective': link_mode(s, l),
                      'served': len(served(db, s, l))} for l in links]}
    if full:
        out['sections'] = s.sections
        out['questions'] = [q_dict(q) for q in questions(db, s.id)]
        out['locked'] = out['responses'] > 0
    return out


@router.get('/surveys')
def list_surveys(archived: bool = False, user: User = Depends(staff), db: Session = Depends(get_db)):
    st = select(Survey).where(Survey.owner_id == user.id, Survey.school_id == user.school_id)
    st = st.where(Survey.archived_at.is_not(None) if archived else Survey.archived_at.is_(None))
    return [survey_out(db, s) for s in db.scalars(st.order_by(Survey.id.desc()))]


@router.get('/surveys/template')
def template(user: User = Depends(staff)):
    return {'sections': SV.SECTIONS + [SV.DEMO_SECTION], 'questions': SV.TEMPLATE + SV.DEMO, 'likert': SV.LIKERT}


class CreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    include_demo: bool = False
    repeat: Literal['once', 'weekly'] = 'once'
    in_app: bool = True
    pulse: bool = True                       # həftəlik sorğuda qısa növbəli dəst (1–2 dəq.)
    open: bool = True                        # dərhal açıq (link işləsin); suallar ilk cavaba qədər dəyişdirilə bilər
    from_id: int | None = None              # təkrar sorğu (yeni dalğa) – sualları köçürür


def _add_questions(db: Session, sid: int, qs: list[dict]):
    for i, q in enumerate(qs):
        db.add(SurveyQuestion(survey_id=sid, key=q.get('key'), section=q['section'], order=i + 1, kind=q['kind'],
                              text=q['text'], options=q.get('options'), required=bool(q.get('required')),
                              reverse=bool(q.get('reverse'))))


@router.post('/surveys')
def create_survey(body: CreateIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    if body.from_id:
        src = own(db, user, body.from_id)
        qs, sections, tkey = [q_dict(q) for q in questions(db, src.id)], src.sections, src.template_key
        root = src.root_id or src.id
        wave = (db.scalar(select(func.max(Survey.wave)).where((Survey.root_id == root) | (Survey.id == root))) or 1) + 1
    else:
        qs = SV.TEMPLATE + (SV.DEMO if body.include_demo else [])
        sections = SV.SECTIONS + ([SV.DEMO_SECTION] if body.include_demo else [])
        tkey, root, wave = SV.TEMPLATE_KEY, None, 1
    s = Survey(owner_id=user.id, school_id=user.school_id, title=body.title.strip(), description=body.description,
               template_key=tkey, sections=sections, status='open' if body.open else 'draft', min_group=5, repeat=body.repeat, in_app=body.in_app,
               pulse=body.pulse,
               root_id=root, wave=wave, created_at=now())
    db.add(s)
    db.flush()
    _add_questions(db, s.id, qs)
    db.add(SurveyLink(survey_id=s.id, token=secrets.token_urlsafe(18), label='Ümumi link', created_at=now()))
    audit(db, user, 'create', 'survey', s.id, wave=wave)
    if body.open:
        audit(db, user, 'open', 'survey', s.id)
    db.commit()
    return survey_out(db, s, full=True)


@router.get('/surveys/{sid}')
def get_survey(sid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    return survey_out(db, own(db, user, sid), full=True)


class QIn(BaseModel):
    key: str | None = Field(None, max_length=20)
    section: str = Field(min_length=1, max_length=4)
    kind: Literal['likert5', 'scale10', 'single', 'multi', 'text']
    text: str = Field(min_length=3, max_length=500)
    options: dict | None = None
    required: bool = True
    reverse: bool = False


class SectionIn(BaseModel):
    key: str = Field(min_length=1, max_length=4)
    title: str = Field(min_length=1, max_length=120)


class UpdateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    opens_at: dt.datetime | None = None
    closes_at: dt.datetime | None = None
    min_group: int = Field(5, ge=3, le=30)
    repeat: Literal['once', 'weekly'] = 'once'
    in_app: bool = True
    pulse: bool = True
    sections: list[SectionIn] | None = None
    questions: list[QIn] | None = None       # yalnız hələ cavab yoxdursa


@router.put('/surveys/{sid}')
def update_survey(sid: int, body: UpdateIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    if body.opens_at and body.closes_at and body.closes_at <= body.opens_at:
        raise HTTPException(400, 'Bağlanma vaxtı açılma vaxtından sonra olmalıdır')
    has = n_responses(db, s.id) > 0
    if has and body.repeat != s.repeat:
        raise HTTPException(409, 'Cavab gəldikdən sonra sorğunun növünü (birdəfəlik / həftəlik) dəyişmək olmaz')
    s.title, s.description = body.title.strip(), body.description
    s.opens_at, s.closes_at, s.min_group, s.repeat, s.in_app = body.opens_at, body.closes_at, body.min_group, body.repeat, body.in_app
    s.pulse = body.pulse
    if body.questions is not None or body.sections is not None:
        if has:
            raise HTTPException(409, 'Sorğuya artıq cavab verilib – suallar dəyişdirilə bilməz (yeni dalğa yaradın)')
        sections = [x.model_dump() for x in body.sections] if body.sections is not None else s.sections
        keys = {x['key'] for x in sections}
        qs = body.questions if body.questions is not None else [QIn(**q_dict(q)) for q in questions(db, s.id)]
        if not qs:
            raise HTTPException(400, 'Sorğuda ən azı bir sual olmalıdır')
        for q in qs:
            if q.section not in keys:
                raise HTTPException(400, f'«{q.text[:40]}»: bölmə tapılmadı')
            if q.kind in ('single', 'multi') and len((q.options or {}).get('choices') or []) < 2:
                raise HTTPException(400, f'«{q.text[:40]}»: ən azı iki variant yazın')
            if q.kind == 'scale10':
                lo, hi = SV.scale_range(q.model_dump())
                if not 0 <= lo < hi <= 10:
                    raise HTTPException(400, f'«{q.text[:40]}»: şkala 0–10 aralığında olmalıdır')
        s.sections = sections
        for q in questions(db, s.id):
            db.delete(q)
        db.flush()
        _add_questions(db, s.id, [q.model_dump() for q in qs])
    db.commit()
    return survey_out(db, s, full=True)


class StatusIn(BaseModel):
    status: Literal['draft', 'open', 'closed']


@router.post('/surveys/{sid}/status')
def set_status(sid: int, body: StatusIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    if s.archived_at:
        raise HTTPException(409, 'Arxivdəki sorğu açıla bilməz')
    if body.status == 'draft' and n_responses(db, s.id):
        raise HTTPException(409, 'Cavab gəlmiş sorğu qaralamaya qaytarıla bilməz')
    if body.status == 'open' and s.closes_at and aware(s.closes_at) <= now():
        s.closes_at = None                   # yenidən açılır – köhnə bağlanma vaxtı silinir
    s.status = body.status
    audit(db, user, {'open': 'open', 'closed': 'close', 'draft': 'update'}[body.status], 'survey', s.id)
    db.commit()
    return survey_out(db, s)


class LinkIn(BaseModel):
    ta_id: int | None = None                 # None – ümumi link
    mode: Literal['auto', 'full', 'short'] = 'auto'


@router.post('/surveys/{sid}/links')
def add_link(sid: int, body: LinkIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    if body.ta_id:
        ta = own_assignment(db, user, body.ta_id)
        c = db.get(SchoolClass, ta.class_id)
        if c.school_id != user.school_id:
            raise HTTPException(404, 'Dərs tapılmadı')
        ex = db.scalar(select(SurveyLink).where(SurveyLink.survey_id == s.id, SurveyLink.class_id == c.id))
        if ex:
            ex.active, ex.mode = True, body.mode
            db.commit()
            return survey_out(db, s)
        db.add(SurveyLink(survey_id=s.id, token=secrets.token_urlsafe(18), class_id=c.id, label=c.name, mode=body.mode,
                          created_at=now()))
    else:
        label = {'full': 'Ümumi link (tam anket)', 'short': 'Ümumi link (qısa)'}.get(body.mode, 'Ümumi link')
        db.add(SurveyLink(survey_id=s.id, token=secrets.token_urlsafe(18), label=label, mode=body.mode, created_at=now()))
    db.commit()
    return survey_out(db, s)


class LinkUpd(BaseModel):
    active: bool | None = None
    mode: Literal['auto', 'full', 'short'] | None = None


@router.post('/surveys/{sid}/links/{lid}')
def toggle_link(sid: int, lid: int, body: LinkUpd, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    l = db.get(SurveyLink, lid)
    if not l or l.survey_id != s.id:
        raise HTTPException(404, 'Link tapılmadı')
    if body.active is not None:
        l.active = body.active
    if body.mode is not None:
        l.mode = body.mode
    db.commit()
    return survey_out(db, s)


@router.post('/surveys/{sid}/archive')
def archive(sid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    s.archived_at, s.status = now(), 'closed'
    audit(db, user, 'archive', 'survey', s.id)
    db.commit()
    return {'ok': True}


@router.post('/surveys/{sid}/restore')
def restore(sid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    s.archived_at = None
    db.commit()
    return {'ok': True}


@router.delete('/surveys/{sid}')
def delete_survey(sid: int, body: ConfirmIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    if not s.archived_at:
        raise HTTPException(409, 'Əvvəlcə sorğunu arxivə köçürün')
    check_confirm(s.title, body.confirm)
    for m in (SurveyDedup, SurveyResponse, SurveyLink, SurveyQuestion):
        for x in db.scalars(select(m).where(m.survey_id == s.id)):
            db.delete(x)
    for r in db.scalars(select(AiReview).where(AiReview.user_id == user.id, AiReview.key.like(f'survey:{s.id}:%'))):
        db.delete(r)
    db.delete(s)
    audit(db, user, 'delete', 'survey', sid)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- nəticələr
NO_CLASS = 0                                 # filtrdə: «sinif göstərilməyib»


def _responses(db: Session, s: Survey, link_id: int | None, period: str | None,
               class_id: int | None = None) -> list[SurveyResponse]:
    st = select(SurveyResponse).where(SurveyResponse.survey_id == s.id)
    if link_id:
        st = st.where(SurveyResponse.link_id == link_id)
    if class_id is not None:
        st = st.where(SurveyResponse.class_id.is_(None) if class_id == NO_CLASS else SurveyResponse.class_id == class_id)
    if period:
        st = st.where(SurveyResponse.period == period)
    return list(db.scalars(st.order_by(SurveyResponse.id)))


def _cls_ok(r: SurveyResponse, class_id: int | None) -> bool:
    return class_id is None or (r.class_id is None if class_id == NO_CLASS else r.class_id == class_id)


def class_names(db: Session, ids) -> dict[int, str]:
    ids = {i for i in ids if i}
    return dict(db.execute(select(SchoolClass.id, SchoolClass.name).where(SchoolClass.id.in_(ids))).all()) if ids else {}


def compute(db: Session, s: Survey, link_id: int | None = None, period: str | None = None,
            class_id: int | None = None) -> dict:
    qs = [q_dict(q) for q in questions(db, s.id)]
    all_rs = _responses(db, s, None, None)
    rs = [r for r in all_rs if (not link_id or r.link_id == link_id) and (not period or r.period == period)
          and _cls_ok(r, class_id)]
    names = class_names(db, {r.class_id for r in all_rs})
    cls_ids = sorted({r.class_id for r in all_rs if r.class_id}, key=lambda i: names.get(i, ''))
    links = list(db.scalars(select(SurveyLink).where(SurveyLink.survey_id == s.id).order_by(SurveyLink.id)))
    periods = sorted({r.period for r in all_rs if r.period != 'once'})
    out = {'survey': {'id': s.id, 'title': s.title, 'repeat': s.repeat, 'wave': s.wave, 'min_group': s.min_group},
           'n': len(rs), 'min_group': s.min_group, 'hidden': len(rs) < s.min_group, 'sections': s.sections,
           'links': [{'id': l.id, 'label': l.label, 'n': sum(r.link_id == l.id for r in all_rs)} for l in links],
           'periods': [{'period': p, 'label': week_label(p), 'n': sum(r.period == p for r in all_rs)} for p in periods],
           'classes': [{'id': i, 'name': names.get(i, '?'), 'n': sum(r.class_id == i for r in all_rs)} for i in cls_ids]
                      + ([{'id': NO_CLASS, 'name': 'Sinif göstərilməyib', 'n': sum(r.class_id is None for r in all_rs)}]
                         if any(r.class_id is None for r in all_rs) else []),
           'link_id': link_id, 'period': period, 'class_id': class_id}
    if out['hidden']:
        return out
    answers = [r.answers for r in rs]
    qstats = []
    for q in qs:
        if q['kind'] == 'text':
            continue
        vals = [a[str(q['id'])] for a in answers if a.get(str(q['id'])) is not None]
        qstats.append({**q, **SV.question_stats(q, vals)})
    sec = SV.section_index(qs, answers)
    out['questions'] = qstats
    out['section_index'] = [{'key': x['key'], 'title': x['title'], **sec[x['key']]} for x in s.sections if x['key'] in sec]
    out['summary'] = SV.summary(qs, answers)
    by_key = {q['key']: q for q in qstats}
    out['overall'] = by_key.get('overall')
    out['nps'] = (by_key.get('nps') or {}).get('nps')
    lk = sorted([q for q in qstats if q['kind'] == 'likert5' and q.get('adj_mean') is not None], key=lambda q: q['adj_mean'])
    pick = lambda q: {'id': q['id'], 'text': q['text'], 'section': q['section'], 'adj_mean': q['adj_mean'], 'agree_pct': q['agree_pct'],
                      'reverse': q['reverse'], 'n': q['n']}
    out['strengths'] = [pick(q) for q in lk[::-1][:3]]
    out['growth'] = [pick(q) for q in lk[:3] if q not in lk[::-1][:3]]
    rnd = random.Random(s.id)                # təsadüfi, amma sabit sıra – göndərilmə ardıcıllığı görünmür
    texts = []
    for q in qs:
        if q['kind'] != 'text':
            continue
        items = [{'rid': r.id, 'text': r.answers[str(q['id'])], 'hidden': q['id'] in (r.hidden or [])}
                 for r in rs if r.answers.get(str(q['id']))]
        rnd.shuffle(items)
        texts.append({'qid': q['id'], 'text': q['text'], 'items': items})
    out['texts'] = texts
    # siniflərin müqayisəsi və sinif üzrə təlim strategiyası (hər sinifdə ≥ min_group)
    titles = {x['key']: x['title'] for x in s.sections}
    cmp, strat = [], []
    for cid in cls_ids:
        cr = [r.answers for r in all_rs if r.class_id == cid and (not period or r.period == period)]
        if len(cr) < s.min_group:
            continue
        sm = SV.summary(qs, cr)
        cmp.append({'class_id': cid, 'label': names.get(cid, '?'), **sm})
        idx = sorted([(k, v) for k, v in sm['sections'].items() if v is not None and k in SV.STRATEGIES], key=lambda x: x[1])
        if idx:
            strat.append({'class_id': cid, 'label': names.get(cid, '?'), 'n': sm['n'], 'overall': sm['overall'], 'nps': sm['nps'],
                          'strong': {'key': idx[-1][0], 'title': titles.get(idx[-1][0], idx[-1][0]), 'index': idx[-1][1]},
                          'weak': [{'key': k, 'title': titles.get(k, k), 'index': v, 'tips': SV.STRATEGIES[k]}
                                   for k, v in idx[:2] if k != idx[-1][0]]})
    out['compare'] = cmp
    out['class_strategy'] = strat
    # həftələr üzrə dinamika (həftəlik sorğu)
    out['weeks'] = []
    for p in periods:
        pr = [r.answers for r in all_rs if r.period == p and (not link_id or r.link_id == link_id) and _cls_ok(r, class_id)]
        if len(pr) >= s.min_group:
            out['weeks'].append({'period': p, 'label': week_label(p), **SV.summary(qs, pr)})
    # dalğalar (təkrar sorğular) – eyni şablon açarları ilə
    root = s.root_id or s.id
    waves = []
    for w in db.scalars(select(Survey).where((Survey.root_id == root) | (Survey.id == root), Survey.owner_id == s.owner_id)
                        .order_by(Survey.wave)):
        wq = [q_dict(q) for q in questions(db, w.id)]
        wr = [r.answers for r in _responses(db, w, None, None)]
        if len(wr) >= w.min_group:
            waves.append({'survey_id': w.id, 'title': w.title, 'wave': w.wave, 'date': aware(w.created_at),
                          **SV.summary(wq, wr)})
    out['waves'] = waves if len(waves) > 1 else []
    return out


@router.get('/surveys/{sid}/results')
def results(sid: int, link_id: int | None = None, period: str | None = None, class_id: int | None = None,
            user: User = Depends(staff), db: Session = Depends(get_db)):
    return compute(db, own(db, user, sid), link_id, period, class_id)


class HideIn(BaseModel):
    qid: int
    hidden: bool


@router.post('/surveys/{sid}/responses/{rid}/hide')
def hide_text(sid: int, rid: int, body: HideIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    r = db.get(SurveyResponse, rid)
    if not r or r.survey_id != s.id:
        raise HTTPException(404, 'Cavab tapılmadı')
    h = set(r.hidden or [])
    h = h | {body.qid} if body.hidden else h - {body.qid}
    r.hidden = sorted(h) or None
    db.commit()
    return {'ok': True}


@router.get('/surveys/{sid}/export.csv')
def export_csv(sid: int, link_id: int | None = None, period: str | None = None, class_id: int | None = None,
               user: User = Depends(staff), db: Session = Depends(get_db)):
    s = own(db, user, sid)
    rs = _responses(db, s, link_id, period, class_id)
    names = class_names(db, {r.class_id for r in rs})
    if len(rs) < s.min_group:
        raise HTTPException(409, f'Cavab azdır ({len(rs)} < {s.min_group}) – anonimlik üçün nəticə gizlidir')
    qs = questions(db, s.id)
    labels = {l.id: l.label for l in db.scalars(select(SurveyLink).where(SurveyLink.survey_id == s.id))}

    def cell(q: SurveyQuestion, r: SurveyResponse):
        v = r.answers.get(str(q.id))
        if v is None or q.id in (r.hidden or []):
            return ''
        ch = (q.options or {}).get('choices') or []
        if q.kind == 'single':
            return ch[v] if 0 <= v < len(ch) else ''
        if q.kind == 'multi':
            return ', '.join(ch[x] for x in v if 0 <= x < len(ch))
        return v
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';')
    w.writerow(['№', 'Sinif', 'Link', 'Həftə' if s.repeat == 'weekly' else 'Dövr', 'Tarix'] +
               [f'{q.key or q.section} {q.text}' + (' (əks)' if q.reverse else '') for q in qs])
    rnd = random.Random(s.id)
    rs = rs[:]
    rnd.shuffle(rs)
    for i, r in enumerate(rs, 1):
        w.writerow([i, names.get(r.class_id, ''), labels.get(r.link_id, 'Tətbiq'), week_label(r.period) if r.period != 'once' else '',
                    f'{r.submitted_on:%d.%m.%Y}'] + [cell(q, r) for q in qs])
    name = f'sorgu-{s.id}.csv'
    return Response('﻿' + buf.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{name}"'})


# ---------------------------------------------------------------- süni intellektin rəyi
SYSTEM = """Sən Azərbaycan ümumtəhsil məktəbində təcrübəli metodist, pedaqoji psixoloq və müəllim inkişafı üzrə məsləhətçisən.
Müəllimə ŞAGİRDLƏRİN ANONİM SORĞUSUNUN nəticələrinə əsasən peşəkar inkişaf rəyi yazırsan.

Qaydalar:
- Yalnız Azərbaycan dilində, hörmətli, dəstəkləyici və konkret yaz; ümumi sözlər yox.
- Hər fikri verilən rəqəmlərlə əsaslandır (indeks 1–5, razılıq faizi, ümumi bal 1–10, NPS, həftə/dalğa dinamikası).
  Rəqəm uydurma. Açıq cavablardan sitat gətirəndə qısa və dəqiq götür.
- Meyarlar: A fənn bilgisi və izah, B dərsin təşkili, C qiymətləndirmə, D ünsiyyət, E motivasiya, F intizam.
- İndeks şərhi: ≥ 4,3 çox güclü; 3,8–4,3 güclü; 3,2–3,8 orta (inkişaf zonası); < 3,2 diqqət tələb edir.
- Şagirdləri tanımağa və ya kimin yazdığını təxmin etməyə ÇALIŞMA. Təhqiramiz cavabları ümumiləşdir, təkrarlama.
- Cavab sayı azdırsa (< 15), nəticənin ehtiyatla şərh edilməli olduğunu qeyd et.
- Tövsiyələr 2–6 həftəlik, ölçülə bilən və sinifdə real tətbiq olunan olsun.

Cavab YALNIZ JSON obyekti:
{"xulase": "3–5 cümlə", "guclu": ["..."], "inkisaf": ["..."],
 "movzular": [{"movzu": "açıq cavablardakı mövzu", "say": 0, "ton": "müsbət | neytral | mənfi"}],
 "tovsiyeler": [{"ne": "nə etməli", "muddet": "məs. 3 həftə", "olcu": "nəticəni necə yoxlamalı"}],
 "diqqet": ["ehtiyatla şərh edilməli məqamlar"]}"""


def _ai_key(sid: int, link_id: int | None, period: str | None, class_id: int | None = None) -> str:
    k = f'survey:{sid}:{link_id or "all"}:{period or "all"}'
    return k if class_id is None else f'{k}:c{class_id}'


def _review_out(r: AiReview | None) -> dict | None:
    return r and {'id': r.id, 'payload': r.payload, 'model': r.model, 'created_at': aware(r.created_at)}


@router.get('/surveys/{sid}/ai-review')
def last_review(sid: int, link_id: int | None = None, period: str | None = None, class_id: int | None = None,
                user: User = Depends(staff), db: Session = Depends(get_db)):
    own(db, user, sid)
    r = db.scalar(select(AiReview).where(AiReview.user_id == user.id, AiReview.key == _ai_key(sid, link_id, period, class_id))
                  .order_by(AiReview.id.desc()).limit(1))
    return {'review': _review_out(r)}


class AiIn(BaseModel):
    link_id: int | None = None
    period: str | None = None
    class_id: int | None = None


@router.post('/surveys/{sid}/ai-review')
def make_review(sid: int, body: AiIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    from .lessonplans import ai_config
    s = own(db, user, sid)
    d = compute(db, s, body.link_id, body.period, body.class_id)
    if d['hidden']:
        raise HTTPException(409, f'Cavab azdır ({d["n"]} < {s.min_group}) – rəy üçün kifayət deyil')
    cfg = ai_config(user)
    titles = {x['key']: x['title'] for x in s.sections}
    ctx = {'cavab sayı': d['n'], 'sorğu': s.title,
           'əhatə': (f"sinif {next((c['name'] for c in d['classes'] if c['id'] == body.class_id), '?')} – bu sinif üçün təlim strategiyasını dəyiş"
                     if body.class_id is not None else
                     next((l['label'] for l in d['links'] if l['id'] == body.link_id), 'bütün siniflər')) +
                    (f' · həftə {week_label(body.period)}' if body.period else ''),
           'meyarlar': [{'meyar': f"{x['key']} {x['title']}", 'indeks': x['index'], 'razılıq %': x['agree_pct']}
                        for x in d['section_index']],
           'ümumi bal (1–10)': (d['overall'] or {}).get('mean'), 'NPS': d['nps'],
           'suallar': [{'meyar': titles.get(q['section'], q['section']), 'sual': q['text'], 'əks': q['reverse'],
                        'orta (çevrilmiş)': q.get('adj_mean'), 'razılıq %': q.get('agree_pct')}
                       for q in d['questions'] if q['kind'] == 'likert5'],
           'siniflər': [{'sinif': c['label'], 'n': c['n'], 'meyarlar': c['sections'], 'ümumi': c['overall']} for c in d['compare']],
           'sinif üzrə zəif meyarlar': [{'sinif': c['label'], 'zəif': [w['title'] for w in c['weak']]} for c in d['class_strategy']],
           'həftələr': [{'həftə': w['label'], 'n': w['n'], 'meyarlar': w['sections'], 'ümumi': w['overall']} for w in d['weeks']],
           'dalğalar': [{'dalğa': w['wave'], 'n': w['n'], 'meyarlar': w['sections'], 'ümumi': w['overall']} for w in d['waves']],
           'açıq cavablar': [{'sual': t['text'], 'cavablar': [i['text'][:400] for i in t['items'] if not i['hidden']][:120]}
                             for t in d['texts']]}
    raw = ai.complete_json(cfg, SYSTEM, 'Anonim şagird sorğusunun nəticələri:\n' + json.dumps(ctx, ensure_ascii=False, default=str)
                           + '\n\nRəyi JSON kimi yaz.')
    lst = lambda v: [str(x) for x in v][:10] if isinstance(v, list) else ([str(v)] if v else [])
    themes = [{'movzu': str(x.get('movzu') or ''), 'say': x.get('say') if isinstance(x.get('say'), int) else None,
               'ton': str(x.get('ton') or '')} for x in raw.get('movzular') or [] if isinstance(x, dict)][:12]
    recs = []
    for x in raw.get('tovsiyeler') or []:
        if isinstance(x, dict):
            recs.append({'ne': str(x.get('ne') or ''), 'muddet': str(x.get('muddet') or ''), 'olcu': str(x.get('olcu') or '')})
        elif x:
            recs.append({'ne': str(x), 'muddet': '', 'olcu': ''})
    payload = {'title': ctx['əhatə'], 'n': d['n'], 'xulase': str(raw.get('xulase') or ''), 'guclu': lst(raw.get('guclu')),
               'inkisaf': lst(raw.get('inkisaf')), 'movzular': themes, 'tovsiyeler': recs[:10], 'diqqet': lst(raw.get('diqqet'))}
    if not payload['xulase'] and not payload['tovsiyeler']:
        raise HTTPException(502, 'Model boş rəy qaytardı – yenidən cəhd edin və ya başqa model seçin')
    r = AiReview(user_id=user.id, school_id=user.school_id, scope='survey', key=_ai_key(sid, body.link_id, body.period, body.class_id),
                 payload=payload, model=cfg['model'], created_at=now())
    db.add(r)
    audit(db, user, 'create', 'ai_review', None, scope='survey', key=r.key, model=cfg['model'])
    db.commit()
    return {'review': _review_out(r)}


# ---------------------------------------------------------------- şagird: cavab vermə (link və tətbiq)
def _teacher_name(db: Session, s: Survey) -> str:
    owner = db.get(User, s.owner_id)
    return owner.full_name if owner else ''


def public_out(db: Session, s: Survey, label: str | None, link: SurveyLink | None = None, variant: int | None = None,
               classes: list[dict] | None = None) -> dict:
    return {'id': s.id, 'title': s.title, 'description': s.description, 'teacher': _teacher_name(db, s),
            'label': label, 'repeat': s.repeat, 'period': period_of(s),
            'period_label': week_label(period_of(s)) if s.repeat == 'weekly' else None,
            'sections': s.sections, 'likert': SV.LIKERT,
            'mode': link_mode(s, link), 'variant': variant, 'classes': classes,
            'questions': [{k: v for k, v in q.items() if k != 'reverse'} for q in served(db, s, link, variant)]}


class SubmitIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answers: dict[str, int | str | list[int] | None]
    device: str | None = Field(None, min_length=8, max_length=64)
    variant: int | None = Field(None, ge=0, le=999)
    class_id: int | None = None              # ümumi linkdə şagirdin seçdiyi sinif


def _clean(db: Session, s: Survey, raw: dict, link: SurveyLink | None = None, variant: int | None = None) -> dict:
    out = {}
    for q in served(db, s, link, variant):
        try:
            v = SV.validate(q, raw.get(str(q['id'])))
        except ValueError:
            raise HTTPException(400, f'«{q["text"][:60]}»: cavab düzgün deyil')
        if v is None and q['required']:
            raise HTTPException(400, f'«{q["text"][:60]}» sualına cavab verin')
        if v is not None:
            out[str(q['id'])] = v
    if not out:
        raise HTTPException(400, 'Sorğu boşdur – suallara cavab verin')
    return out


def _save(db: Session, s: Survey, link_id: int | None, answers: dict, hashes: list[str], period: str,
          class_id: int | None = None):
    for h in hashes:
        if db.get(SurveyDedup, (s.id, h)):
            raise HTTPException(409, 'Siz bu sorğuya artıq cavab vermisiniz' + (' (bu həftə)' if s.repeat == 'weekly' else '')
                                + ' – təşəkkür edirik!')
    for h in set(hashes):
        db.add(SurveyDedup(survey_id=s.id, hash=h))
    db.add(SurveyResponse(survey_id=s.id, link_id=link_id, class_id=class_id, period=period,
                          submitted_on=now().astimezone(BAKU).date(), answers=answers))
    db.commit()


def _link(db: Session, token: str) -> tuple[SurveyLink, Survey]:
    l = db.scalar(select(SurveyLink).where(SurveyLink.token == token))
    s = l and db.get(Survey, l.survey_id)
    if not l or not s or not l.active or s.archived_at:
        raise HTTPException(404, 'Sorğu linki tapılmadı və ya deaktivdir')
    if not is_open(s):
        st = state(s)
        if st == 'scheduled':
            msg = f'Sorğu {aware(s.opens_at).astimezone(BAKU):%d.%m.%Y %H:%M}-da açılacaq – o vaxt yenidən daxil olun'
        elif st == 'draft':
            msg = 'Sorğu hələ başlamayıb – müəlliminiz onu açandan sonra bu link işləyəcək'
        else:
            msg = 'Sorğu bağlanıb – təşəkkür edirik! Sualınız varsa, müəlliminizə müraciət edin'
        raise HTTPException(410, msg)
    return l, s


def link_classes(db: Session, s: Survey) -> list[dict]:
    """Ümumi link: şagird öz sinfini seçir – müəllimin bu məkandakı sinif və qrupları."""
    names = class_names(db, teacher_classes(db, s.owner_id, s.school_id))
    return [{'id': i, 'name': n} for i, n in sorted(names.items(), key=lambda x: x[1])]


def student_class(db: Session, s: Survey, u: User | None) -> int | None:
    """Daxil olmuş şagirdin bu müəllimin dərs dediyi sinfi/qrupu (ümumi linkdə sinif soruşulmasın)."""
    if not u:
        return None
    st = db.scalar(select(Student).where(Student.user_id == u.id, Student.archived_at.is_(None)))
    cls = st and (teacher_classes(db, s.owner_id, s.school_id) & student_classes(db, st))
    return min(cls) if cls else None


def _session_student(db: Session, token: str | None) -> User | None:
    data = read_session(token)
    u = data and db.get(User, data.get('u'))
    return u if u and u.role == Role.student and not u.archived_at else None


@router.get('/public/surveys/{token}')
def public_get(token: str, v: int | None = None, db: Session = Depends(get_db),
               session: str | None = Cookie(None, alias=SESSION_COOKIE)):
    l, s = _link(db, token)
    variant = None
    if link_mode(s, l) == 'short' and s.repeat != 'weekly':
        variant = v if v is not None and 0 <= v <= 999 else secrets.randbelow(1000)   # brauzer variantı yadda saxlayır
    u = _session_student(db, session)
    known = l.class_id or student_class(db, s, u)
    out = public_out(db, s, l.label if l.class_id else None, l, variant, None if known else link_classes(db, s))
    out['done'] = bool(u and db.get(SurveyDedup, (s.id, student_hash(s, u.id, period_of(s)))))
    return out


@router.post('/public/surveys/{token}/responses')
def public_submit(token: str, body: SubmitIn, response: Response, db: Session = Depends(get_db),
                  session: str | None = Cookie(None, alias=SESSION_COOKIE),
                  device_cookie: str | None = Cookie(None, alias=DEVICE_COOKIE)):
    l, s = _link(db, token)
    t = now().timestamp()
    hits = [x for x in _hits.get(token, []) if t - x < 600]
    if len(hits) >= 300:
        raise HTTPException(429, 'Çox sayda göndərmə – bir neçə dəqiqədən sonra yenidən yoxlayın')
    _hits[token] = hits + [t]
    answers = _clean(db, s, body.answers, l, body.variant)
    u = _session_student(db, session)
    cid = l.class_id or student_class(db, s, u)
    if not cid:
        allowed = {c['id'] for c in link_classes(db, s)}
        if allowed and body.class_id not in allowed:
            raise HTTPException(400, 'Sinifinizi seçin')
        cid = body.class_id if body.class_id in allowed else None
    period = period_of(s)
    dev = device_cookie or secrets.token_urlsafe(18)
    hashes = [_h('survey', s.id, 'c', dev, period)]
    if body.device:
        hashes.append(_h('survey', s.id, 'd', body.device, period))
    if u:
        hashes.append(student_hash(s, u.id, period))
    _save(db, s, l.id, answers, hashes, period, cid)
    response.set_cookie(DEVICE_COOKIE, dev, max_age=60 * 60 * 24 * 400, httponly=True, samesite='lax',
                        secure=settings().cookie_secure)
    return {'ok': True}


def _student_surveys(db: Session, user: User) -> tuple[Student, list[tuple[Survey, int | None]]]:
    from .portal import me_student
    st = me_student(db, user)
    mine = student_classes(db, st)
    owners = dict(db.execute(select(TeachingAssignment.teacher_id, TeachingAssignment.class_id)
                             .where(TeachingAssignment.class_id.in_(mine), TeachingAssignment.archived_at.is_(None))).all())
    out = []
    for s in db.scalars(select(Survey).where(Survey.owner_id.in_(set(owners)), Survey.school_id == st.school_id,
                                             Survey.in_app.is_(True), Survey.archived_at.is_(None), Survey.status == 'open')
                        .order_by(Survey.id.desc())):
        if not is_open(s):
            continue
        cls = teacher_classes(db, s.owner_id, s.school_id) & mine
        out.append((s, min(cls) if cls else None))
    return st, out


@router.get('/portal/surveys')
def portal_surveys(user: User = Depends(student_only), db: Session = Depends(get_db)):
    _, lst = _student_surveys(db, user)
    return [{'id': s.id, 'title': s.title, 'teacher': _teacher_name(db, s),
             'repeat': s.repeat, 'period_label': week_label(period_of(s)) if s.repeat == 'weekly' else None,
             'period': period_of(s), 'questions': len(served(db, s)),
             'done': bool(db.get(SurveyDedup, (s.id, student_hash(s, user.id, period_of(s)))))} for s, _ in lst]


def _portal_one(db: Session, user: User, sid: int) -> tuple[Survey, int | None]:
    _, lst = _student_surveys(db, user)
    for s, cid in lst:
        if s.id == sid:
            return s, cid
    raise HTTPException(404, 'Sorğu tapılmadı və ya bağlıdır')


@router.get('/portal/surveys/{sid}')
def portal_survey(sid: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s, cid = _portal_one(db, user, sid)
    out = public_out(db, s, db.get(SchoolClass, cid).name if cid else None)
    out['done'] = bool(db.get(SurveyDedup, (s.id, student_hash(s, user.id, period_of(s)))))
    return out


@router.post('/portal/surveys/{sid}/responses')
def portal_submit(sid: int, body: SubmitIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s, cid = _portal_one(db, user, sid)
    answers = _clean(db, s, body.answers)
    link_id = None
    if cid:                                  # sinif linki – müqayisə üçün (yoxdursa yaradılır)
        l = db.scalar(select(SurveyLink).where(SurveyLink.survey_id == s.id, SurveyLink.class_id == cid))
        if not l:
            l = SurveyLink(survey_id=s.id, token=secrets.token_urlsafe(18), class_id=cid,
                           label=db.get(SchoolClass, cid).name, created_at=now())
            db.add(l)
            db.flush()
        link_id = l.id
    period = period_of(s)
    hashes = [student_hash(s, user.id, period)]
    if body.device:
        hashes.append(_h('survey', s.id, 'd', body.device, period))
    _save(db, s, link_id, answers, hashes, period, cid)
    return {'ok': True}
