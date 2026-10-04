"""Test nəticələri mərkəzi (docs/test-neticeleri-promtu.md): iki hissəli reytinq (mövzu testləri | sınaqlar),
yazmayanlar (yenidən göndər), şagird profili, sinif/qrup, ümumi və süni intellektin pedaqoji rəyi."""
from __future__ import annotations

import datetime as dt
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai
from ..db import get_db
from ..deps import staff
from ..domain.rules import summative_grade
from ..models import AiReview, LevelOverride, SchoolClass, Student, TeachingAssignment, User, now
from ..services import own_assignment, ws_cond
from ..test_stats import KINDS, avg, collect, missing, per_student, rating
from .common import audit, can_see_student

router = APIRouter(prefix='/api/results-center', tags=['results-center'])
Kind = Literal['movzu', 'sinaq']
LEVELS = ('Zəif', 'Orta', 'Güclü')


def _my_tas(db: Session, user: User, subject: str | None = None) -> list[TeachingAssignment]:
    st = (select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id, TeachingAssignment.archived_at.is_(None),
                                           ws_cond(user)).order_by(TeachingAssignment.id))
    return [t for t in db.scalars(st) if not subject or t.subject == subject]


def _tas_filter(db: Session, user: User, ta_id: int | None) -> set[int] | None:
    return {own_assignment(db, user, ta_id).id} if ta_id else None


# ---------------------------------------------------------------- reytinq (iki hissə)
@router.get('/rating')
def get_rating(kind: Kind, ta_id: int | None = None, subject: str | None = None, date_from: dt.date | None = None,
               date_to: dt.date | None = None, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Bir hissənin reytinqi: «Mövzu testləri» (kind=movzu) və ya «Sınaqlar» (kind=sinaq) – heç vaxt qarışmır."""
    out = rating(collect(db, user, kind, _tas_filter(db, user, ta_id), date_from, date_to, subject or None))
    db.commit()                                       # expire_due avtomatik təhvilləri saxlasın
    return {'kind': kind, **out}


# ---------------------------------------------------------------- yazmayanlar
@router.get('/missing')
def get_missing(kind: Literal['all', 'movzu', 'sinaq'] = 'all', ta_id: int | None = None, subject: str | None = None,
                date_from: dt.date | None = None, date_to: dt.date | None = None, user: User = Depends(staff),
                db: Session = Depends(get_db)):
    own = _tas_filter(db, user, ta_id) or {t.id for t in _my_tas(db, user)} or {-1}
    kinds = KINDS if kind == 'all' else (kind,)
    datas = [collect(db, user, k, own, date_from, date_to, subject or None) for k in kinds]
    out = missing(datas)
    db.commit()
    return out


class ResendItem(BaseModel):
    ta_id: int
    task_id: int
    student_ids: list[int] = Field(min_length=1)


class ResendIn(BaseModel):
    items: list[ResendItem] = Field(min_length=1, max_length=200)
    opens_at: dt.datetime
    closes_at: dt.datetime
    duration_min: int | None = Field(None, ge=1, le=300)


@router.post('/missing/resend')
def resend_missing(body: ResendIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Yazmayanlara yenidən göndər: hər test üçün surət (eyni suallar) yalnız seçilmiş şagirdlərə, yeni vaxtla.
    Surət kökün testinə aiddir – yazdıqdan sonra şagird «yazmayanlar»dan çıxır."""
    from .tasks import CopyIn, copy_task
    made, errors = 0, []
    for it in body.items:
        try:
            copy_task(it.ta_id, it.task_id, CopyIn(target_ta_id=it.ta_id, opens_at=body.opens_at, closes_at=body.closes_at,
                                                   duration_min=body.duration_min, student_ids=it.student_ids), user, db)
            made += 1
        except HTTPException as e:
            db.rollback()
            errors.append(str(e.detail))
    if not made and errors:
        raise HTTPException(400, errors[0])
    return {'tasks': made, 'errors': errors}


# ---------------------------------------------------------------- şagird profili
def _student_data(db: Session, user: User, sid: int, date_from=None, date_to=None) -> dict:
    s = db.get(Student, sid)
    if not s or not can_see_student(db, user, s):
        raise HTTPException(404, 'Şagird tapılmadı')
    own = {t.id for t in _my_tas(db, user)}
    out = {'student': {'id': s.id, 'full_name': s.full_name, 'class_name': db.get(SchoolClass, s.class_id).name if s.class_id else None},
           'parts': {}}
    for k in KINDS:
        data = collect(db, user, k, None if k == 'sinaq' else own, date_from, date_to)
        rt = rating(data)
        me = next((r for r in rt['rows'] if r['student_id'] == sid), None)
        mine = [r for r in data['rows'] if r['student_id'] == sid]
        items = []
        for r in mine:
            peers = [x['pct'] for x in data['rows'] if x['unit'] == r['unit'] and x['ta_id'] == r['ta_id'] and x['status'] == 'yazıb']
            ca = avg(peers)
            items.append({**{f: r[f] for f in ('unit', 'kind', 'title', 'date', 'topic', 'status', 'pct', 'grade',
                                               'place_class', 'place_all', 'class_name')},
                          'class_avg': ca, 'diff': round(r['pct'] - ca, 1) if r['pct'] is not None and ca is not None else None,
                          'class_count': len(peers)})
        items.sort(key=lambda x: (x['date'], x['title']))
        topics: dict[str, list] = {}
        for x in items:
            if x['topic'] and x['pct'] is not None:
                topics.setdefault(x['topic'], []).append(x['pct'])
        tl = sorted([{'topic': t, 'pct': avg(v), 'n': len(v)} for t, v in topics.items()], key=lambda x: x['pct'])
        out['parts'][k] = {'summary': me and {f: me[f] for f in ('avg_pct', 'last_pct', 'delta', 'given', 'wrote', 'missed',
                                                                  'participation', 'place_class', 'place_all', 'attention',
                                                                  'chronic', 'low_participation')},
                           'class_size': sum(1 for r in rt['rows'] if r['class_name'] == (me or {}).get('class_name')),
                           'items': items, 'weak_topics': tl[:5], 'strong_topics': tl[::-1][:5]}
    return out


@router.get('/student/{sid}')
def student_profile(sid: int, date_from: dt.date | None = None, date_to: dt.date | None = None,
                    user: User = Depends(staff), db: Session = Depends(get_db)):
    out = _student_data(db, user, sid, date_from, date_to)
    db.commit()
    return out


@router.get('/students')
def my_students(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Şagird seçimi üçün: öz dərslərimin şagirdləri (sinif adı ilə)."""
    from ..services import roster
    seen, out = set(), []
    for ta in _my_tas(db, user):
        cname = db.get(SchoolClass, ta.class_id).name
        for s in roster(db, ta):
            if s.id not in seen:
                seen.add(s.id)
                out.append({'id': s.id, 'full_name': s.full_name, 'class_name': cname})
    out.sort(key=lambda x: (x['class_name'], x['full_name']))
    return out


# ---------------------------------------------------------------- sinif / qrup
def _class_data(db: Session, user: User, ta_id: int | None, level: str | None, date_from=None, date_to=None) -> dict:
    """Bir dərs (sinif / qrup) və ya ta_id=None – «Hamısı»: bütün dərslərim. Səviyyə hər dərsin öz bölgüsündən."""
    tas = [own_assignment(db, user, ta_id)] if ta_id else _my_tas(db, user)
    raw = {(o.assignment_id, o.student_id): o.level for o in db.scalars(
        select(LevelOverride).where(LevelOverride.assignment_id.in_([t.id for t in tas] or [-1])))}
    if level and level not in LEVELS:
        raise HTTPException(400, 'Səviyyə: Zəif, Orta və ya Güclü')
    rlv = lambda r: raw.get((r['ta_id'], r['student_id']))
    if ta_id:
        name, subj = db.get(SchoolClass, tas[0].class_id).name, tas[0].subject
    else:
        name, subj = 'Bütün siniflərim', ', '.join(sorted({t.subject for t in tas})) or '—'
    out = {'ta_id': ta_id, 'class_name': name, 'subject': subj, 'level': level, 'parts': {}}
    for k in KINDS:
        data = collect(db, user, k, {t.id for t in tas} or {-1}, date_from, date_to)
        rows = [r for r in data['rows'] if r['visible'] and (not level or rlv(r) == level)]
        lv = {r['student_id']: rlv(r) for r in rows}
        ps = per_student(rows)
        tests = []
        for t in data['tests']:
            rs = [r for r in rows if r['unit'] == t['unit']]
            if not rs:
                continue
            w = [r['pct'] for r in rs if r['status'] == 'yazıb']
            g = [r for r in rs if r['status'] in ('yazıb', 'yazmayıb')]
            tests.append({'unit': t['unit'], 'title': t['title'], 'date': t['date'], 'topic': t['topic'],
                          'avg_pct': avg(w), 'wrote': len(w), 'given': len(g), 'max_pct': max(w) if w else None,
                          'min_pct': min(w) if w else None, 'missed': sum(1 for r in rs if r['status'] == 'yazmayıb')})
        dist = {g: 0 for g in (5, 4, 3, 2)}
        for r in rows:
            if r['status'] == 'yazıb':
                dist[summative_grade(r['pct']) or 2] += 1
        levels = {}
        for name in LEVELS:
            v = [r['pct'] for r in rows if r['status'] == 'yazıb' and rlv(r) == name]
            levels[name] = {'avg_pct': avg(v), 'students': len({r['student_id'] for r in rows if rlv(r) == name})}
        topics: dict[str, list] = {}
        for r in rows:
            if r['topic'] and r['status'] == 'yazıb':
                topics.setdefault(r['topic'], []).append(r['pct'])
        tl = sorted([{'topic': t, 'pct': avg(v), 'n': len(v)} for t, v in topics.items()], key=lambda x: x['pct'])
        studs = sorted([{f: p[f] for f in ('student_id', 'full_name', 'avg_pct', 'last_pct', 'delta', 'given', 'wrote',
                                            'missed', 'participation', 'attention', 'chronic')} | {'level': lv.get(p['student_id'])}
                        for p in ps.values()], key=lambda x: (x['avg_pct'] is None, -(x['avg_pct'] or 0), x['full_name']))
        allw = [r['pct'] for r in rows if r['status'] == 'yazıb']
        given = sum(1 for r in rows if r['status'] in ('yazıb', 'yazmayıb'))
        out['parts'][k] = {'summary': {'tests': len(tests), 'students': len(ps), 'avg_pct': avg(allw),
                                       'participation': round(len(allw) * 100 / given, 1) if given else None,
                                       'missed': sum(p['missed'] for p in ps.values()),
                                       'chronic': sum(1 for p in ps.values() if p['chronic']),
                                       'attention': sum(1 for p in ps.values() if p['attention'])},
                           'tests': tests, 'distribution': dist, 'levels': levels, 'weak_topics': tl[:5],
                           'strong_topics': tl[::-1][:5], 'students': studs}
    return out


@router.get('/class')
@router.get('/class/{ta_id}')
def class_report(ta_id: int | None = None, level: str | None = None, date_from: dt.date | None = None, date_to: dt.date | None = None,
                 user: User = Depends(staff), db: Session = Depends(get_db)):
    out = _class_data(db, user, ta_id, level, date_from, date_to)
    db.commit()
    return out


# ---------------------------------------------------------------- ümumi
def _overview_data(db: Session, user: User, date_from=None, date_to=None) -> dict:
    tas = _my_tas(db, user)
    out = {'classes': [], 'months': {}}
    datas = {k: collect(db, user, k, {t.id for t in tas} or {-1}, date_from, date_to) for k in KINDS}
    for ta in tas:
        c = {'ta_id': ta.id, 'class_name': db.get(SchoolClass, ta.class_id).name, 'subject': ta.subject}
        for k in KINDS:
            rows = [r for r in datas[k]['rows'] if r['ta_id'] == ta.id and r['visible']]
            w = [r['pct'] for r in rows if r['status'] == 'yazıb']
            g = sum(1 for r in rows if r['status'] in ('yazıb', 'yazmayıb'))
            ps = per_student(rows)
            c[k] = {'tests': len({r['unit'] for r in rows}), 'avg_pct': avg(w),
                    'participation': round(len(w) * 100 / g, 1) if g else None,
                    'chronic': sum(1 for p in ps.values() if p['chronic']),
                    'attention': sum(1 for p in ps.values() if p['attention'])}
        if c['movzu']['tests'] or c['sinaq']['tests']:
            out['classes'].append(c)
    for k in KINDS:
        m: dict[str, list] = {}
        for r in datas[k]['rows']:
            if r['status'] == 'yazıb' and r['visible']:
                m.setdefault(r['date'].strftime('%Y-%m'), []).append(r['pct'])
        out['months'][k] = [{'month': x, 'avg_pct': avg(v), 'n': len(v)} for x, v in sorted(m.items())]
    allp = {k: [r['pct'] for r in datas[k]['rows'] if r['status'] == 'yazıb' and r['visible']] for k in KINDS}
    out['summary'] = {k: {'avg_pct': avg(allp[k]), 'tests': len(datas[k]['tests']), 'results': len(allp[k])} for k in KINDS}
    return out


@router.get('/overview')
def overview(date_from: dt.date | None = None, date_to: dt.date | None = None, user: User = Depends(staff),
             db: Session = Depends(get_db)):
    out = _overview_data(db, user, date_from, date_to)
    db.commit()
    return out


# ---------------------------------------------------------------- süni intellektin pedaqoji rəyi
SYSTEM = """Sən Azərbaycan ümumtəhsil məktəbində təcrübəli metodist və pedaqoji məsləhətçisən. Müəllimə onlayn mövzu testləri
(formativ qiymətləndirmə – perspektiv planın mövzuları üzrə) və sınaq imtahanlarının (ümumi hazırlıq, formativ qiymətə təsir
etmir) nəticələrinə əsasən PEDAQOJİ RƏY yazırsan.

Qaydalar:
- Yalnız Azərbaycan dilində, rəsmi-pedaqoji, səmimi və konkret yaz; ümumi sözlər yox.
- Hər fikri verilən rəqəmlərlə əsaslandır (faiz, dinamika, iştirak, mövzu adı). Rəqəm uydurma.
- Şagirdləri yalnız verilən kodlarla (Ş-1, Ş-2 …) xatırla; ad uydurma. Etiketləmə («tənbəl», «qabiliyyətsiz») QADAĞANDIR.
- Səbəbləri ehtimal kimi yaz («ola bilər», «ehtimal ki»), qəti hökm vermə.
- Tövsiyələr 2–4 həftəlik, ölçülə bilən, sinifdə real tətbiq olunan olsun (diferensial tapşırıq, cüt iş, əks-əlaqə, təkrar
  mövzu testi, əlavə məşğələ, valideynlə əməkdaşlıq və s.).
- Testi yazmamaq ayrıca problemdir – iştirakı artırmaq üçün də tövsiyə ver.
- Mövzu testi ilə sınaq nəticələrini qarışdırma: hər birini öz adı ilə təhlil et, fərq varsa izah et.

Cavab YALNIZ JSON obyekti:
{"xulase": "3–5 cümlə", "guclu": ["..."], "zeif": ["..."], "sebebler": ["..."],
 "tovsiyeler": [{"ne": "nə etməli", "kim": "müəllim | şagird | valideyn | sinif rəhbəri", "muddet": "məs. 2 həftə"}],
 "valideyne": "valideynə 2–4 cümləlik müraciət (yalnız şagird rəyində; başqa hallarda boş sətir)",
 "diqqet": ["diqqət tələb edən şagirdlər/hallar (kodlarla)"]}"""


class ReviewIn(BaseModel):
    scope: Literal['student', 'class', 'group', 'overall']
    ta_id: int | None = None
    student_id: int | None = None
    level: str | None = None
    kind: Kind | None = None                 # None – «Hamısı»: iki hissə ayrıca
    date_from: dt.date | None = None
    date_to: dt.date | None = None


def _key(b: ReviewIn) -> str:
    ta = b.ta_id or 'all'
    k = {'student': f'student:{b.student_id}', 'class': f'class:{ta}', 'group': f'class:{ta}:{b.level}',
         'overall': 'overall'}[b.scope]
    return f'{k}:{b.kind}' if b.kind else k


class Coder:
    """Adları provayderə göndərmirik: «Ş-1»… kodları, cavabda adlar geri qoyulur."""
    def __init__(self):
        self.map: dict[str, str] = {}

    def __call__(self, name: str | None) -> str | None:
        if not name:
            return name
        for k, v in self.map.items():
            if v == name:
                return k
        k = f'Ş-{len(self.map) + 1}'
        self.map[k] = name
        return k

    def back(self, v):
        if isinstance(v, str):
            for k in sorted(self.map, key=len, reverse=True):
                v = v.replace(k, self.map[k])
            return v
        if isinstance(v, list):
            return [self.back(x) for x in v]
        if isinstance(v, dict):
            return {k: self.back(x) for k, x in v.items()}
        return v


def _context(db: Session, user: User, b: ReviewIn, code: Coder) -> tuple[str, str]:
    """(başlıq, kontekst mətni) – yalnız rəqəmlər, adlar kodla."""
    period = f"Dövr: {b.date_from or 'əvvəldən'} – {b.date_to or 'bu günə'}"
    pick = lambda d, fs: {f: d.get(f) for f in fs}
    if b.scope == 'student':
        if not b.student_id:
            raise HTTPException(400, 'Şagird seçin')
        d = _student_data(db, user, b.student_id, b.date_from, b.date_to)
        code(d['student']['full_name'])
        ctx = {'növ': 'şagird', 'şagird': 'Ş-1', 'sinif': d['student']['class_name'], 'hissələr': {
            {'movzu': 'mövzu testləri', 'sinaq': 'sınaqlar'}[k]: {
                'yekun': p['summary'], 'sinifdə şagird sayı': p['class_size'],
                'testlər': [pick(x, ('date', 'title', 'topic', 'status', 'pct', 'class_avg', 'diff', 'place_class')) for x in p['items']][-25:],
                'zəif mövzular': p['weak_topics'], 'güclü mövzular': p['strong_topics']} for k, p in d['parts'].items()
            if not b.kind or k == b.kind}}
        title = f"Şagird: {d['student']['full_name']}"
    elif b.scope in ('class', 'group'):
        d = _class_data(db, user, b.ta_id, b.level if b.scope == 'group' else None, b.date_from, b.date_to)
        ctx = {'növ': 'səviyyə qrupu' if b.scope == 'group' else 'sinif', 'sinif': d['class_name'], 'fənn': d['subject'],
               'səviyyə': d['level'], 'hissələr': {
                   {'movzu': 'mövzu testləri', 'sinaq': 'sınaqlar'}[k]: {
                       'yekun': p['summary'], 'qiymət paylanması': p['distribution'], 'səviyyələr': p['levels'],
                       'testlər': [pick(x, ('date', 'title', 'topic', 'avg_pct', 'wrote', 'given', 'missed')) for x in p['tests']][-25:],
                       'zəif mövzular': p['weak_topics'], 'güclü mövzular': p['strong_topics'],
                       'şagirdlər': [{**pick(x, ('avg_pct', 'delta', 'participation', 'missed', 'level', 'attention', 'chronic')),
                                      'kod': code(x['full_name'])} for x in p['students']]}
                   for k, p in d['parts'].items() if not b.kind or k == b.kind}}
        title = f"{'Səviyyə qrupu' if b.scope == 'group' else 'Sinif'}: {d['class_name']} · {d['subject']}" + (f' · {b.level}' if b.level and b.scope == 'group' else '')
    else:
        d = _overview_data(db, user, b.date_from, b.date_to)
        if b.kind:
            d = {'summary': {b.kind: d['summary'][b.kind]}, 'months': {b.kind: d['months'][b.kind]},
                 'classes': [{f: c[f] for f in ('class_name', 'subject', b.kind)} for c in d['classes']]}
        ctx = {'növ': 'ümumi (müəllimin bütün sinifləri)', 'yekun': d['summary'], 'siniflər': d['classes'], 'aylar': d['months']}
        title = 'Ümumi: bütün siniflərim'
    if b.kind:
        title += ' · ' + {'movzu': 'mövzu testləri', 'sinaq': 'sınaqlar'}[b.kind]
    return title, period + '\n' + json.dumps(ctx, ensure_ascii=False, default=str)


def _review_out(r: AiReview | None) -> dict | None:
    return r and {'id': r.id, 'scope': r.scope, 'key': r.key, 'payload': r.payload, 'model': r.model,
                  'created_at': r.created_at}


@router.get('/ai-review')
def last_review(scope: Literal['student', 'class', 'group', 'overall'], ta_id: int | None = None,
                student_id: int | None = None, level: str | None = None, kind: Kind | None = None,
                user: User = Depends(staff), db: Session = Depends(get_db)):
    key = _key(ReviewIn(scope=scope, ta_id=ta_id, student_id=student_id, level=level, kind=kind))
    r = db.scalar(select(AiReview).where(AiReview.user_id == user.id, AiReview.school_id == user.school_id,
                                         AiReview.key == key).order_by(AiReview.id.desc()).limit(1))
    return {'review': _review_out(r)}


@router.post('/ai-review')
def make_review(body: ReviewIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    from .lessonplans import ai_config
    if body.scope == 'group' and body.level not in LEVELS:
        raise HTTPException(400, 'Səviyyə qrupunu seçin (Zəif, Orta, Güclü)')
    cfg = ai_config(user)
    code = Coder()
    title, ctx = _context(db, user, body, code)
    db.commit()
    raw = ai.complete_json(cfg, SYSTEM, f'{title.split(":")[0]} üzrə nəticələr (adlar kodlanıb):\n{ctx}\n\nPedaqoji rəyi JSON kimi yaz.')
    lst = lambda v: [str(x) for x in v][:10] if isinstance(v, list) else ([str(v)] if v else [])
    recs = []
    for x in raw.get('tovsiyeler') or []:
        if isinstance(x, dict):
            recs.append({'ne': str(x.get('ne') or ''), 'kim': str(x.get('kim') or ''), 'muddet': str(x.get('muddet') or '')})
        elif x:
            recs.append({'ne': str(x), 'kim': '', 'muddet': ''})
    payload = code.back({'title': title, 'xulase': str(raw.get('xulase') or ''), 'guclu': lst(raw.get('guclu')),
                         'zeif': lst(raw.get('zeif')), 'sebebler': lst(raw.get('sebebler')), 'tovsiyeler': recs[:10],
                         'valideyne': str(raw.get('valideyne') or '') if body.scope == 'student' else '',
                         'diqqet': lst(raw.get('diqqet'))})
    if not payload['xulase'] and not payload['tovsiyeler']:
        raise HTTPException(502, 'Model boş rəy qaytardı – yenidən cəhd edin və ya başqa model seçin')
    r = AiReview(user_id=user.id, school_id=user.school_id, scope=body.scope, key=_key(body), payload=payload,
                 model=cfg['model'], created_at=now())
    db.add(r)
    audit(db, user, 'create', 'ai_review', None, scope=body.scope, key=r.key, model=cfg['model'])
    db.commit()
    return {'review': _review_out(r)}
