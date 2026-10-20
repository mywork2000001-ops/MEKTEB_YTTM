"""Test nəticələri mərkəzi (docs/test-neticeleri-promtu.md): iki hissəli reytinq (mövzu testləri | sınaqlar),
yazmayanlar (yenidən göndər), şagird profili, sinif/qrup, ümumi və süni intellektin pedaqoji rəyi."""
from __future__ import annotations

import datetime as dt
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai
from ..db import get_db
from ..deps import staff
from ..domain.rules import summative_grade
from ..timing import GIVEN
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
    """Yazmayanlar (bağlanmış testlər) – TƏK mənbə `student_report.class_missing`: sinif hesabatı ilə eyni şagird/say/status.
    Cavab formatı köhnədir (ResultsCenter); əlavə `ta_ids`."""
    from ..student_report import class_missing
    from ..test_stats import CHRONIC_N, CHRONIC_SHARE
    tas = [own_assignment(db, user, ta_id)] if ta_id else _my_tas(db, user)
    tas = [t for t in tas if not subject or t.subject == subject]
    st: dict[int, dict] = {}
    tests: dict[str, dict] = {}
    for ta in tas:
        m = class_missing(db, user, ta.id, kind, date_from, date_to, all_students=True)
        ttask = {t['key']: t for t in m['tests']}
        for t in m['tests']:
            if t['done'] + t['missed']:
                x = tests.setdefault((ta.id, t['key']), {'unit': t['key'], 'kind': t['kind'], 'title': t['test_title'], 'date': t['date'],
                                                         'topic': None, 'given': 0, 'missed': 0})
                x['given'] += t['done'] + t['missed']
                x['missed'] += t['missed']
        for r in m['rows']:
            given = r['done'] + r['missed']
            p = st.setdefault(r['student_id'], {'student_id': r['student_id'], 'full_name': r['full_name'], 'class_name': m['class_name'],
                                                'given': 0, 'missed': 0, 'tests': []})
            p['given'] += given
            for i in r['items']:
                if i['status'] == 'yazmayıb':
                    p['missed'] += 1
                    p['tests'].append({'unit': i['key'], 'kind': i['kind'], 'title': ttask[i['key']]['test_title'], 'date': i['date'], 'topic': None,
                                       'task_id': ttask[i['key']]['task_id'], 'ta_id': ta.id})
    students = []
    for p in st.values():
        if not p['missed']:
            continue
        p['tests'].sort(key=lambda x: x['date'] or '')
        p['last_missed'] = p['tests'][-1]['date']
        p['chronic'] = bool(p['missed'] >= CHRONIC_N or (p['given'] >= 2 and p['missed'] / p['given'] >= CHRONIC_SHARE))
        students.append(p)
    students.sort(key=lambda p: (-p['missed'], p['class_name'], p['full_name']))
    db.commit()
    return {'students': students, 'tests': sorted([t for t in tests.values() if t['missed']], key=lambda t: (t['date'] or '', t['title']), reverse=True)}


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
    # kağız / skan nəticələr, adı ilə sınaqlar və nömrəli mövzu testləri (docs/sagird-ferdi-hesabat-promtu.md; geriyə uyğun əlavə)
    from ..student_report import student_results
    rep = student_results(db, user, sid, date_from, date_to)
    out.update(topic_tests=rep['topic_tests'], mocks=rep['mocks'], summatives=rep['summatives'])
    return out


@router.get('/student/{sid}')
def student_profile(sid: int, date_from: dt.date | None = None, date_to: dt.date | None = None,
                    user: User = Depends(staff), db: Session = Depends(get_db)):
    out = _student_data(db, user, sid, date_from, date_to)
    db.commit()
    return out


@router.get('/student/{sid}/report')
def student_report(sid: int, date_from: dt.date | None = Query(None, alias='from'), date_to: dt.date | None = Query(None, alias='to'),
                   format: Literal['json', 'pdf', 'docx'] = 'json', lang: Literal['az', 'ru', 'en'] = 'az', parent: bool = False,
                   user: User = Depends(staff), db: Session = Depends(get_db)):
    """Şagirdin fərdi hesabatı (onlayn + kağız + sınaqlar + KSQ/BSQ). pdf/docx: rəsmi çap AZ; parent=true – valideyn nüsxəsi (AZ|RU)."""
    from fastapi.responses import Response
    from ..student_report import student_results
    from ..student_report_print import report_docx, report_html
    rep = student_results(db, user, sid, date_from, date_to)
    db.commit()                                       # expire_due avtomatik təhvilləri saxlasın
    if format == 'json':
        return rep
    if not parent:
        lang = 'az'                                    # rəsmi sənəd yalnız Azərbaycan dilində
    name = f"hesabat-{sid}"
    audit(db, user, 'export', 'student_report', str(sid), format=format, parent=parent)
    db.commit()
    if format == 'docx':
        return Response(report_docx(rep, lang, parent), headers={'Content-Disposition': f'attachment; filename="{name}.docx"'},
                        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    return Response(_render_pdf(report_html(rep, lang, parent)), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{name}.pdf"'})


def _render_pdf(html: str) -> bytes:
    from .printing import _lock, render_pdf
    if not _lock.acquire(timeout=60):
        raise HTTPException(503, 'Server məşğuldur – bir az sonra yenidən yoxlayın')
    try:
        return render_pdf(html)
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(500, f'PDF hazırlanmadı: {str(e)[:120]}')
    finally:
        _lock.release()


MAX_BULK = 60


@router.get('/class/{ta_id}/reports')
def class_reports(ta_id: int, date_from: dt.date | None = Query(None, alias='from'), date_to: dt.date | None = Query(None, alias='to'),
                  format: Literal['pdf', 'html'] = 'pdf', lang: Literal['az', 'ru', 'en'] = 'az', parent: bool = False,
                  user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sinfin bütün şagirdlərinin hesabatı – hər şagird ayrıca səhifə (valideyn iclası üçün). Yalnız öz dərsimin sinfi;
    şagird adı ilə əlifba sırası. format=html – çap önbaxışı üçün hazır sənəd (testlər və brauzer)."""
    from fastapi.responses import HTMLResponse, Response
    from ..services import roster
    from ..student_report import student_results
    from ..student_report_print import report_html_many
    ta = own_assignment(db, user, ta_id)
    students = sorted(roster(db, ta), key=lambda s: s.full_name)
    if len(students) > MAX_BULK:
        raise HTTPException(400, f'Bir dəfəyə ən çox {MAX_BULK} şagird')
    reps = []
    for s in students:
        try:
            reps.append(student_results(db, user, s.id, date_from, date_to))
        except HTTPException:
            continue                                   # görünməyən şagird sənədə düşmür
    if not reps:
        raise HTTPException(404, 'Şagird tapılmadı')
    db.commit()
    if not parent:
        lang = 'az'
    audit(db, user, 'export', 'class_reports', str(ta_id), count=len(reps), parent=parent)
    db.commit()
    html = report_html_many(reps, lang, parent)
    if format == 'html':
        return HTMLResponse(html)
    return Response(_render_pdf(html), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="hesabatlar-{ta_id}.pdf"'})


@router.get('/class/{ta_id}/matrix')
def class_matrix_api(ta_id: int, kind: Literal['movzu', 'sinaq', 'all'] = 'all', date_from: dt.date | None = Query(None, alias='from'),
                     date_to: dt.date | None = Query(None, alias='to'), format: Literal['json', 'xlsx', 'pdf'] = 'json',
                     user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Kim nəyi işləyib»: şagird × test cədvəli (mövzu testləri, sınaqlar, kağız KSQ/BSQ). Yalnız öz dərsim.
    xlsx/pdf – rəsmi çap (AZ, A4 albom)."""
    from fastapi.responses import Response
    from ..class_matrix_print import matrix_html, matrix_xlsx
    from ..models import School
    from ..student_report import class_matrix
    m = class_matrix(db, user, ta_id, kind, date_from, date_to)
    db.commit()                                       # expire_due avtomatik təhvilləri saxlasın
    if format == 'json':
        return m
    from .lessonplans import SCHOOL_DEFAULT
    sc = db.get(School, user.school_id) if user.school_id else None
    school = sc.name if sc and sc.name else SCHOOL_DEFAULT
    audit(db, user, 'export', 'class_matrix', str(ta_id), format=format)
    db.commit()
    if format == 'xlsx':
        deputy = ((sc.doc_settings or {}) if sc else {}).get('deputy') or ''
        return Response(matrix_xlsx(m, school, user.full_name, deputy), headers={'Content-Disposition': f'attachment; filename="matris-{ta_id}.xlsx"'},
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return Response(_render_pdf(matrix_html(m, school, user.full_name)), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="matris-{ta_id}.pdf"'})


@router.get('/class/{ta_id}/missing-list')
def class_missing_api(ta_id: int, kind: Literal['movzu', 'sinaq', 'all'] = 'all', date_from: dt.date | None = Query(None, alias='from'),
                      date_to: dt.date | None = Query(None, alias='to'), format: Literal['json', 'xlsx', 'pdf'] = 'json',
                      per_student: int = Query(0, ge=0, le=1), sid: int | None = None,
                      only_missed: int = Query(0, ge=0, le=1), all_students: int = Query(0, ge=0, le=1, alias='all'),
                      plan: Literal['all', 'late_open'] = 'all', sort: Literal['name', 'risk'] | None = None,
                      user: User = Depends(staff), db: Session = Depends(get_db)):
    """İşlənməyənlər siyahısı (matrisdən): json; pdf/xlsx – sinif üzrə bir sənəd (rəsmi, AZ); per_student=1 – hər şagirdə ayrıca vərəqə
    (PDF; şagirdin dili ru isə AZ|RU), sid – tək şagird. Yalnız öz dərsim."""
    from fastapi.responses import Response
    from ..missing_list_print import class_html, class_xlsx, students_html
    from ..models import School
    from ..student_report import class_missing
    # sinif hesabatı (H1/Excel) – bütün şagirdlər (icra göstəriciləri üçün); şagird vərəqələri – yalnız borcu olanlar
    m = class_missing(db, user, ta_id, kind, date_from, date_to, sid, all_students=bool(all_students) or (format != 'json' and not per_student),
                      only_missed=bool(only_missed), plan=plan, sort=sort or ('name' if format == 'json' else 'risk'))
    db.commit()                                       # expire_due avtomatik təhvilləri saxlasın
    if format == 'json':
        return m
    if per_student:
        m = {**m, 'rows': [r for r in m['rows'] if r['items']]}
    if per_student and format == 'xlsx':
        raise HTTPException(400, 'Hər şagirdə ayrıca vərəqə yalnız PDF-dir')
    if per_student and not m['rows']:
        raise HTTPException(404, 'İşlənməyən test yoxdur')
    from .lessonplans import SCHOOL_DEFAULT
    sc = db.get(School, user.school_id) if user.school_id else None
    school = sc.name if sc and sc.name else SCHOOL_DEFAULT
    audit(db, user, 'export', 'missing_list', str(ta_id), format=format, per_student=per_student, sid=sid)
    db.commit()
    if format == 'xlsx':
        deputy = ((sc.doc_settings or {}) if sc else {}).get('deputy') or ''
        return Response(class_xlsx(m, school, user.full_name, deputy), headers={'Content-Disposition': f'attachment; filename="islenmeyenler-{ta_id}.xlsx"'},
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    html = students_html(m, school, user.full_name) if per_student else class_html(m, school, user.full_name)
    return Response(_render_pdf(html), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="islenmeyenler-{ta_id}{"-sagird" if per_student else ""}.pdf"'})


@router.get('/student/{sid}/missing-list')
def student_missing_api(sid: int, kind: Literal['movzu', 'sinaq', 'all'] = 'all', date_from: dt.date | None = Query(None, alias='from'),
                        date_to: dt.date | None = Query(None, alias='to'), user: User = Depends(staff), db: Session = Depends(get_db)):
    """Şagird hesabatından: «İşləməli olduğu testlər» vərəqəsi (PDF) – şagirdin mənim bütün dərslərim üzrə (hər dərs ayrıca vərəq)."""
    from fastapi.responses import Response
    from ..missing_list_print import students_html
    from ..models import School
    from ..student_report import class_missing
    rows, last = [], None
    for ta in _my_tas(db, user):
        try:
            m = class_missing(db, user, ta.id, kind, date_from, date_to, sid)
        except HTTPException:
            continue
        last = m
        for r in m['rows']:
            if r['items']:
                rows.append({**r, 'class_name': m['class_name'], 'subject': m['subject']})
    db.commit()
    if not rows or last is None:
        raise HTTPException(404, 'İşlənməyən test yoxdur')
    from .lessonplans import SCHOOL_DEFAULT
    sc = db.get(School, user.school_id) if user.school_id else None
    school = sc.name if sc and sc.name else SCHOOL_DEFAULT
    audit(db, user, 'export', 'missing_list_student', str(sid))
    db.commit()
    return Response(_render_pdf(students_html({**last, 'rows': rows}, school, user.full_name)), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="islenmeyenler-sagird-{sid}.pdf"'})


def _school_name(db: Session, user: User) -> str:
    from ..models import School
    from .lessonplans import SCHOOL_DEFAULT
    sc = db.get(School, user.school_id) if user.school_id else None
    return sc.name if sc and sc.name else SCHOOL_DEFAULT


@router.get('/class/{ta_id}/missing-share')
def class_missing_share(ta_id: int, lang: Literal['az', 'en', 'ru'] = 'az', names: Literal['full', 'short', 'none'] = 'short',
                        kind: Literal['movzu', 'sinaq', 'all'] = 'all', date_from: dt.date | None = Query(None, alias='from'),
                        date_to: dt.date | None = Query(None, alias='to'), only_missed: int = Query(0, ge=0, le=1),
                        plan: Literal['all', 'late_open'] = 'all', user: User = Depends(staff), db: Session = Depends(get_db)):
    """H4: qrupa göndəriləcək qısa mətn (seçilmiş dildə, ad rejimi: tam / ad + soyadın baş hərfi / adsız)."""
    from ..missing_list_print import share_text
    from ..student_report import class_missing
    m = class_missing(db, user, ta_id, kind, date_from, date_to, only_missed=bool(only_missed), plan=plan, sort='risk')
    db.commit()
    return {'text': share_text(m, lang, names)}


@router.get('/missing-all')
def missing_all_api(format: Literal['pdf', 'json'] = 'pdf', kind: Literal['movzu', 'sinaq', 'all'] = 'all',
                    date_from: dt.date | None = Query(None, alias='from'), date_to: dt.date | None = Query(None, alias='to'),
                    plan: Literal['all', 'late_open'] = 'all', user: User = Depends(staff), db: Session = Depends(get_db)):
    """H3: bütün öz siniflərim – xülasə + hər sinfin H1-i (PDF)."""
    from fastapi.responses import Response
    from ..class_matrix_print import _d
    from ..missing_list_print import all_classes_html
    from ..student_report import class_missing
    ms = [class_missing(db, user, ta.id, kind, date_from, date_to, all_students=True, plan=plan, sort='risk') for ta in _my_tas(db, user)]
    db.commit()
    if format == 'json':
        return {'classes': [{k: m[k] for k in ('ta_id', 'class_name', 'subject', 'summary')} for m in ms]}
    period = f'{_d(date_from.isoformat() if date_from else None)} – {_d(date_to.isoformat() if date_to else None)}' if date_from or date_to else 'bütün dövr'
    audit(db, user, 'export', 'missing_all', str(user.id))
    db.commit()
    return Response(_render_pdf(all_classes_html(ms, _school_name(db, user), user.full_name, period)), media_type='application/pdf',
                    headers={'Content-Disposition': 'attachment; filename="islenmeyenler-butun-siniflerim.pdf"'})


# ---------------------------------------------------------------- «Tələb et» və «Araşdır» (docs/islenmeyenler-hesabati-promtu.md §5.2–5.3)
class MissingRequestIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=200)
    task_keys: list[str] | None = None
    message: str | None = Field(None, max_length=2000)
    new_deadline: dt.datetime | None = None
    reopen: bool = False


def _local_text(t: dt.datetime) -> str:
    from zoneinfo import ZoneInfo
    from ..services import SCHOOL_TZ
    return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(ZoneInfo(SCHOOL_TZ)).strftime('%d.%m.%Y %H:%M')


@router.post('/class/{ta_id}/missing-request')
def missing_request(ta_id: int, body: MissingRequestIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Tələb et»: seçilmiş şagirdlərə işləməli testlərin siyahısı ilə mesaj (şagirdin dilində; daxili çat – şagirdin «Mesajlar»ı),
    istəyə görə yeni son tarix; reopen – bağlanmış testin surəti yalnız həmin şagirdlərə (copy_task). Tarixçə – missing_requests."""
    from ..missing_list_print import request_text
    from ..models import ChatMessage, MissingRequest
    from ..student_report import class_missing, unit_tasks
    from .chat import _ensure, can_dm
    from .tasks import CopyIn, copy_task, now as _tasks_now
    own_assignment(db, user, ta_id)
    if body.reopen and not body.new_deadline:
        raise HTTPException(400, 'Yenidən açmaq üçün yeni son tarix seçin')
    m = class_missing(db, user, ta_id, 'all', all_students=True)
    rows = {r['student_id']: r for r in m['rows']}
    keys = set(body.task_keys) if body.task_keys else None
    dl = _local_text(body.new_deadline) if body.new_deadline else None
    out = {'sent': 0, 'delivered': 0, 'no_account': 0, 'reopened': 0, 'errors': []}
    reopen_map: dict[str, list[int]] = {}
    for sid in dict.fromkeys(body.student_ids):
        r = rows.get(sid)
        if not r:
            out['errors'].append(f'{sid}: şagird bu sinifdə deyil')
            continue
        items = [i for i in r['items'] if keys is None or i['key'] in keys]
        if not items:
            out['errors'].append(f"{r['full_name']}: işləməli test yoxdur")
            continue
        s = db.get(Student, sid)
        su = db.get(User, s.user_id) if s and s.user_id else None
        mid = None
        if su and can_dm(db, user, su):
            a, b = sorted((user.id, su.id))
            room = _ensure(db, school_id=user.school_id, kind='dm', dm_key=f'dm:{a}:{b}')
            msg = ChatMessage(room_id=room.id, sender_id=user.id, text=request_text(r['ui_lang'], r['full_name'], items, dl, body.message))
            db.add(msg)
            db.flush()
            mid = msg.id
            out['delivered'] += 1
        else:
            out['no_account'] += 1
        if body.reopen:
            for i in items:
                if i['status'] == 'yazmayıb':
                    reopen_map.setdefault(i['key'], []).append(sid)
        db.add(MissingRequest(ta_id=ta_id, student_id=sid, task_keys=[i['key'] for i in items], message=(body.message or None),
                              new_deadline=body.new_deadline, reopened=bool(body.reopen), message_id=mid, teacher_id=user.id))
        out['sent'] += 1
    db.flush()
    if reopen_map:
        tid = {t['key']: t['task_id'] for t in m['tests']}
        for key, sids in reopen_map.items():
            src_id = tid.get(key) or next((t.id for t in reversed(unit_tasks(db, ta_id, key))), None)
            if not src_id:
                out['errors'].append(f'{key}: onlayn test deyil – yenidən açmaq mümkün deyil')
                continue
            try:
                copy_task(ta_id, src_id, CopyIn(target_ta_id=ta_id, opens_at=_tasks_now(), closes_at=body.new_deadline, student_ids=sids), user, db)
                out['reopened'] += 1
            except HTTPException as e:               # heç nə saxlanmır (mesajlar da) – müəllim tarixi düzəldib yenidən göndərsin
                db.rollback()
                raise HTTPException(400, str(e.detail))
    audit(db, user, 'create', 'missing_request', str(ta_id), students=out['sent'], reopen=body.reopen)
    db.commit()
    return out


class MissingNoteIn(BaseModel):
    task_key: str = Field(min_length=1, max_length=40)
    student_id: int
    reason: Literal['excused', 'technical', 'no_device', 'forgot', 'refused', 'other'] | None = None   # boş – qeyd silinir
    note: str | None = Field(None, max_length=500)


@router.put('/class/{ta_id}/missing-note')
def missing_note(ta_id: int, body: MissingNoteIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllimin «yazmayıb» səbəbi: bir test + bir şagird = bir qeyd; «excused» icra faizinin məxrəcindən çıxarır; reason boş – silinir."""
    from ..models import MissingNote
    from ..services import roster
    from ..student_report import class_matrix
    ta = own_assignment(db, user, ta_id)
    if body.student_id not in {s.id for s in roster(db, ta)}:
        raise HTTPException(404, 'Şagird bu sinifdə/qrupda deyil')
    if body.task_key not in {c['key'] for c in class_matrix(db, user, ta_id, 'all')['columns']}:
        raise HTTPException(404, 'Test tapılmadı')
    n = db.scalar(select(MissingNote).where(MissingNote.ta_id == ta_id, MissingNote.task_key == body.task_key,
                                             MissingNote.student_id == body.student_id))
    if body.reason is None:
        if n:
            db.delete(n)
    elif n:
        n.reason, n.note, n.teacher_id, n.updated_at = body.reason, (body.note or None), user.id, now()
    else:
        db.add(MissingNote(ta_id=ta_id, task_key=body.task_key, student_id=body.student_id, reason=body.reason,
                           note=body.note or None, teacher_id=user.id))
    audit(db, user, 'update', 'missing_note', str(ta_id), student=body.student_id, task=body.task_key, reason=body.reason)
    db.commit()
    return {'ok': True}


@router.get('/student/{sid}/missing-investigate')
def missing_investigate(sid: int, ta: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """«Araşdır»: şagirdin hər işlənməyən testi üzrə avtomatik faktlar (görünürdü, cəhd, bildiriş/tələb, plan günündə davamiyyət,
    oxşar testlər) + səbəb qeydləri. Son giriş tarixi sistemdə saxlanmır – `last_login` həmişə null."""
    from ..models import Attendance, ChatMember, ChatRoom, JournalEntry, MissingRequest, TaskAttempt
    from ..student_report import _DONE, class_matrix, class_missing, unit_tasks
    own_assignment(db, user, ta)
    m = class_missing(db, user, ta, 'all', sid=sid)
    r = m['rows'][0]
    mx = class_matrix(db, user, ta, 'all')
    kind_of = {c['key']: c['kind'] for c in mx['columns']}
    cells = next(x for x in mx['rows'] if x['student_id'] == sid)['cells']
    s = db.get(Student, sid)
    reqs = list(db.scalars(select(MissingRequest).where(MissingRequest.ta_id == ta, MissingRequest.student_id == sid).order_by(MissingRequest.created_at)))
    read: dict[int, bool] = {}
    if s and s.user_id:
        a, b = sorted((user.id, s.user_id))
        room = db.scalar(select(ChatRoom).where(ChatRoom.dm_key == f'dm:{a}:{b}'))
        cm = db.get(ChatMember, (room.id, s.user_id)) if room else None
        for q in reqs:
            if q.message_id:
                read[q.id] = bool(cm and cm.last_read_id >= q.message_id)
    excused = [{**e, 'status': 'excused', 'state': None, 'plan_date': None, 'late_days': None} for e in r['excused']]
    facts = []
    for it in r['items'] + excused:
        tasks = unit_tasks(db, ta, it['key'])
        att = [x for x in (db.scalar(select(TaskAttempt).where(TaskAttempt.task_id == t.id, TaskAttempt.student_id == sid)) for t in tasks) if x]
        att.sort(key=lambda x: x.started_at)
        rq = [q for q in reqs if not q.task_keys or it['key'] in q.task_keys]
        pd = it.get('plan_date')
        presence = None
        if pd:
            ents = list(db.scalars(select(JournalEntry).where(JournalEntry.assignment_id == ta, JournalEntry.date == dt.date.fromisoformat(pd))))
            sts = [x.status for x in (db.get(Attendance, (e.id, sid)) for e in ents) if x]
            presence = sts[0] if sts else None
        k = kind_of.get(it['key'])
        same = [c for kk, c in cells.items() if kind_of.get(kk) == k and c['status'] != 'təyin olunmayıb' and kk != it['key']]
        facts.append({**{f: it.get(f) for f in ('key', 'no', 'title', 'date', 'status', 'state', 'plan_date', 'late_days', 'reason', 'note')},
                      'facts': {'visible': bool(tasks) or it['key'][:1] == 'e', 'online': bool(tasks),
                                'attempt_started': bool(att), 'started_at': att[0].started_at.isoformat() if att else None,
                                'submitted_at': next((x.submitted_at.isoformat() for x in att if x.submitted_at), None),
                                'requests': {'count': len(rq), 'last': rq[-1].created_at.isoformat() if rq else None,
                                             'read': any(read.get(q.id) for q in rq)},
                                'attendance_on_plan_day': presence, 'last_login': None,
                                'similar_done': sum(1 for c in same if c['status'] in _DONE), 'similar_total': len(same)}})
    return {'student': {'id': sid, 'full_name': r['full_name']}, 'ta_id': ta, 'class_name': m['class_name'], 'subject': m['subject'],
            'rate': r['rate'], 'rate_on_time': r['rate_on_time'], 'risk': r['risk'], 'items': facts,
            'history': [{'at': q.created_at.isoformat(), 'keys': q.task_keys, 'reopened': q.reopened,
                         'read': read.get(q.id), 'delivered': q.message_id is not None} for q in reqs]}


@router.get('/missing-summary')
def missing_summary_api(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Əsas səhifə («Bu həftə diqqət»): öz dərslərim üzrə işlənməmiş test sayı – siyahı ilə eyni statuslar (class_missing)."""
    from ..student_report import missing_summary
    items = missing_summary(db, user, _my_tas(db, user))
    db.commit()
    return {'items': items}


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
            g = [r for r in rs if r['status'] in GIVEN]
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
        given = sum(1 for r in rows if r['status'] in GIVEN)
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
            g = sum(1 for r in rows if r['status'] in GIVEN)
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
    cfg = ai_config(user, 'review')                 # rəy – ayrıca açar (yoxdursa – plan açarı)
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
