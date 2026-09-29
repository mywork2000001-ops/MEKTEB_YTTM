"""Gündəlik planlaşdırma (ARTİ): perspektiv plan üzrə hər dərs yuvası üçün süni intellektlə gündəlik plan.

Müəllim öz API açarını seçir (Gemini, OpenRouter, OpenAI, Anthropic, Groq, DeepSeek, OpenAI-uyğun).
Gün/həftə görünüşü, hazırlama (bir-bir – həftə üçün interfeys ardıcıl çağırır), redaktə, silmə, Word (.docx)."""
from __future__ import annotations

import datetime as dt
import io
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import ai
from ..db import get_db
from ..deps import staff
from ..domain import daily_plan as dp
from ..domain.plan import slot_at, view_range
from ..models import DailyPlan, JournalEntry, School, User
from ..security import secret_decrypt, secret_encrypt
from ..services import journal_entries, own_assignment, plan_ctx, roster, taught_lesson
from .common import audit, settings_unlocked
from .plan import WEEKDAYS, bell

router = APIRouter(prefix='/api', tags=['daily-plans'])
DAYS_FULL = ['Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə', 'Bazar']


# ---------------------------------------------------------------- müəllimin API açarı
def _ai_out(user: User) -> dict:
    s = user.ai_settings or {}
    key = secret_decrypt(s.get('key'))
    return {'provider': s.get('provider'), 'model': s.get('model'), 'base_url': s.get('base_url'),
            'has_key': bool(key), 'key_mask': ('••••' + key[-4:]) if key and len(key) > 8 else ('••••' if key else None),
            'providers': [{'id': k, 'label': v['label'], 'models': v['models'], 'key_url': v.get('key_url'),
                           'hint': v.get('hint'), 'custom': v['base'] is None} for k, v in ai.PROVIDERS.items()]}


def ai_config(user: User) -> dict:
    s = user.ai_settings or {}
    key = secret_decrypt(s.get('key'))
    if not s.get('provider') or not key or not s.get('model'):
        raise HTTPException(400, 'Süni intellekt qoşulmayıb: Tənzimləmələr → «Süni intellekt» bölməsində API açarınızı daxil edin')
    if s['provider'] not in ai.PROVIDERS:
        raise HTTPException(400, 'Provayder tanınmadı – tənzimləmələri yenidən saxlayın')
    return {'provider': s['provider'], 'model': s['model'], 'base_url': s.get('base_url'), 'api_key': key}


class AiIn(BaseModel):
    provider: str
    model: str = Field(min_length=2, max_length=120)
    api_key: str | None = Field(None, max_length=400)          # boş – köhnə açar qalır
    base_url: str | None = Field(None, max_length=300)


@router.get('/ai/settings')
def get_ai(user: User = Depends(staff)):
    return _ai_out(user)


@router.put('/ai/settings')
def put_ai(body: AiIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    if body.provider not in ai.PROVIDERS:
        raise HTTPException(400, 'Naməlum provayder')
    old = dict(user.ai_settings or {})
    base = None
    if ai.PROVIDERS[body.provider]['base'] is None:
        if not body.base_url:
            raise HTTPException(400, '«Başqa» provayder üçün ünvan (base URL) lazımdır')
        base = ai.check_base_url(body.base_url)
    key = (body.api_key or '').strip()
    if key and (len(key) < 12 or re.search(r'\s', key)):
        raise HTTPException(400, 'API açarı düzgün görünmür')
    if not key:
        if old.get('provider') != body.provider or not old.get('key'):
            raise HTTPException(400, 'API açarını daxil edin')
        enc = old['key']
    else:
        enc = secret_encrypt(key)
    user.ai_settings = {'provider': body.provider, 'model': body.model.strip(), 'base_url': base, 'key': enc}
    audit(db, user, 'update', 'ai_settings', user.id, provider=body.provider, model=body.model)
    db.commit()
    return _ai_out(user)


@router.delete('/ai/settings')
def del_ai(user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    user.ai_settings = None
    audit(db, user, 'delete', 'ai_settings', user.id)
    db.commit()
    return _ai_out(user)


@router.post('/ai/test')
def test_ai(user: User = Depends(staff)):
    cfg = ai_config(user)
    txt = ai.complete(cfg, 'Qısa cavab ver.', 'Yalnız bu sözü yaz: HAZIR', json_mode=False, max_tokens=400)
    return {'ok': True, 'reply': txt.strip()[:80], 'model': cfg['model']}


# ---------------------------------------------------------------- kontekst (perspektiv plan + jurnal)
def _slot(ctx, d: dt.date, period: int):
    s = slot_at(ctx.slots, d, period)
    if not s:
        raise HTTPException(404, 'Bu tarixdə və saatda sizin dərsiniz yoxdur')
    return s


def _context(db: Session, user: User, ctx, s, notes: str | None) -> tuple[dict, object]:
    entry = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ctx.ta.id, JournalEntry.date == s.date,
                                                 JournalEntry.period == s.period))
    pl = taught_lesson(ctx, s, entry)
    if pl is None:
        raise HTTPException(400, 'Bu dərs üçün perspektiv planda mövzu yoxdur (plan yüklənməyib və ya ilin sonuna sığmır)')
    i = next(k for k, x in enumerate(ctx.lessons) if x.id == pl.id)
    k = ctx.slots.index(s)
    prev_s = ctx.slots[k - 1] if k > 0 else None
    prev_pl = ctx.lessons[i - 1] if i > 0 else None
    nxt = ctx.lessons[i + 1] if i + 1 < len(ctx.lessons) else None
    prev_entry = db.scalar(select(JournalEntry).where(JournalEntry.assignment_id == ctx.ta.id, JournalEntry.homework.is_not(None),
                                                      (JournalEntry.date < s.date) | ((JournalEntry.date == s.date) & (JournalEntry.period < s.period)))
                           .order_by(JournalEntry.date.desc(), JournalEntry.period.desc()).limit(1))
    sec = [x for x in ctx.lessons if x.section == pl.section] if pl.section else []
    exam = None
    for j, x in enumerate(ctx.lessons[i + 1:], 1):
        if x.assessment_type in ('KSQ', 'BSQ'):
            exam = f"{x.assessment_type}{('-' + str(x.exam_no)) if x.exam_no else ''} – {j} dərs sonra"
            break
    hw_t = next((t for t in pl.tasks or [] if t.get('kind') == 'ev'), None)
    hw, hw_nums = None, []
    if hw_t:
        hw_nums = [str(hw_t.get('start'))] + ([str(hw_t['end'])] if hw_t.get('end') and hw_t.get('end') != hw_t.get('start') else [])
        hw = f"{pl.tt_pages + ', ' if pl.tt_pages else ''}№ {'–'.join(hw_nums)}"
    school = db.get(School, ctx.cls.school_id)
    c = {'school': school.name if school else '', 'teacher': user.full_name, 'subject': ctx.ta.subject,
         'class_name': ctx.cls.name, 'group': ctx.cls.kind == 'qrup', 'students': len(roster(db, ctx.ta)),
         'date': s.date.isoformat(), 'date_text': s.date.strftime('%d.%m.%Y'), 'weekday': DAYS_FULL[s.date.weekday()],
         'period': s.period, 'time': bell(db, ctx.cls, s.period), 'minutes': dp.LESSON_MIN,
         'semester': pl.semester, 'seq': pl.seq, 'total': len(ctx.lessons), 'section': pl.section,
         'section_pos': (sec.index(pl) + 1) if sec else None, 'section_len': len(sec) or None,
         'topic': pl.topic, 'standards': list(pl.standards or []), 'assessment_type': pl.assessment_type,
         'exam_no': pl.exam_no, 'assessment': pl.assessment, 'integration': pl.integration, 'resources': pl.resources,
         'tt_pages': pl.tt_pages, 'tasks': dp.tasks_text(pl.tasks),
         'continues_from': bool(prev_s and prev_s.held and prev_s.index == s.index),
         'continues_next': bool(s.held),
         'prev_topic': prev_pl.topic if prev_pl else None, 'prev_homework': prev_entry.homework if prev_entry else None,
         'next_topic': nxt.topic if nxt else None, 'next_exam': exam, 'notes': (notes or '').strip() or None,
         'homework_plan': hw, 'homework_nums': hw_nums}
    return c, pl


def _brief(p: DailyPlan | None) -> dict | None:
    return p and {'id': p.id, 'updated_at': p.updated_at, 'model': p.model, 'edited': p.edited, 'topic': p.topic}


def _full(p: DailyPlan, ctx) -> dict:
    return {**_brief(p), 'date': p.date, 'period': p.period, 'content': p.content, 'notes': p.notes,
            'provider': p.provider, 'class_name': ctx.cls.name, 'subject': ctx.ta.subject,
            'weekday': DAYS_FULL[p.date.weekday()], 'warnings': (p.content or {}).get('_warnings', []),
            'meta': (p.content or {}).get('_meta', {})}


# ---------------------------------------------------------------- gündəlik planlar
@router.get('/daily-plans/{ta_id}')
def list_plans(ta_id: int, view: str = 'week', date: dt.date | None = None, user: User = Depends(staff),
               db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    ctx = plan_ctx(db, ta)
    from ..services import today
    d = date or today()
    if view not in ('day', 'week'):
        raise HTTPException(400, 'görünüş: day, week')
    a, b = view_range(view, d, ctx.year.sem1_end, ctx.year.sem2_start, ctx.year.start, ctx.year.end)
    saved = {(p.date, p.period): p for p in db.scalars(select(DailyPlan).where(
        DailyPlan.assignment_id == ta.id, DailyPlan.date >= a, DailyPlan.date <= b))}
    entries = journal_entries(db, ta.id, a, b)
    items = []
    for s in ctx.slots:
        if a <= s.date <= b:
            pl = taught_lesson(ctx, s, entries.get((s.date, s.period)))
            items.append({'date': s.date, 'weekday': WEEKDAYS[s.date.weekday()], 'period': s.period,
                          'time': bell(db, ctx.cls, s.period), 'held': s.held,
                          'lesson': pl and {'seq': pl.seq, 'topic': pl.topic, 'section': pl.section,
                                            'standards': pl.standards, 'assessment_type': pl.assessment_type,
                                            'exam_no': pl.exam_no, 'tt_pages': pl.tt_pages,
                                            'tasks': dp.tasks_text(pl.tasks)},
                          'plan': _brief(saved.get((s.date, s.period)))})
    s = user.ai_settings or {}
    return {'from': a, 'to': b, 'class_name': ctx.cls.name, 'subject': ta.subject, 'items': items,
            'ai': {'configured': bool(s.get('key')), 'provider': s.get('provider'), 'model': s.get('model')}}


class GenIn(BaseModel):
    date: dt.date
    period: int
    notes: str | None = Field(None, max_length=1500)


@router.post('/daily-plans/{ta_id}/prompt')
def prompt_preview(ta_id: int, body: GenIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Promtun özünü göstərir (şəffaflıq: müəllim hansı məlumatın göndərildiyini görür). Açar tələb olunmur."""
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    c, _ = _context(db, user, ctx, _slot(ctx, body.date, body.period), body.notes)
    return {'system': dp.system_prompt(c['minutes']), 'user': dp.user_prompt(c)}


@router.post('/daily-plans/{ta_id}/generate')
def generate(ta_id: int, body: GenIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    cfg = ai_config(user)
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    s = _slot(ctx, body.date, body.period)
    c, pl = _context(db, user, ctx, s, body.notes)
    raw = ai.complete_json(cfg, dp.system_prompt(c['minutes']), dp.user_prompt(c))
    content, warn = dp.normalize(raw, c)
    content['_warnings'] = warn
    content['_meta'] = {k: c[k] for k in ('school', 'teacher', 'subject', 'class_name', 'date_text', 'weekday', 'period',
                                          'time', 'minutes', 'semester', 'seq', 'total', 'section', 'topic',
                                          'assessment_type', 'exam_no', 'tt_pages', 'tasks', 'resources')}
    p = db.scalar(select(DailyPlan).where(DailyPlan.assignment_id == ctx.ta.id, DailyPlan.date == s.date,
                                          DailyPlan.period == s.period))
    if p is None:
        p = DailyPlan(assignment_id=ctx.ta.id, date=s.date, period=s.period, created_by=user.id)
        db.add(p)
    p.plan_lesson_id, p.topic, p.content, p.notes = pl.id, pl.topic, content, c['notes']
    p.provider, p.model, p.edited = cfg['provider'], cfg['model'], False
    db.flush()
    audit(db, user, 'create', 'daily_plan', p.id, date=str(s.date), period=s.period, model=cfg['model'])
    db.commit()
    return _full(p, ctx)


def _own_plan(db: Session, user: User, ta_id: int, pid: int):
    ctx = plan_ctx(db, own_assignment(db, user, ta_id))
    p = db.get(DailyPlan, pid)
    if not p or p.assignment_id != ctx.ta.id:
        raise HTTPException(404, 'Gündəlik plan tapılmadı')
    return p, ctx


@router.get('/daily-plans/{ta_id}/item/{pid}')
def get_plan(ta_id: int, pid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    p, ctx = _own_plan(db, user, ta_id, pid)
    return _full(p, ctx)


class EditIn(BaseModel):
    content: dict


@router.put('/daily-plans/{ta_id}/item/{pid}')
def edit_plan(ta_id: int, pid: int, body: EditIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    p, ctx = _own_plan(db, user, ta_id, pid)
    keep = {k: v for k, v in (p.content or {}).items() if k.startswith('_')}
    new = {k: v for k, v in body.content.items() if not k.startswith('_')}
    total = sum(int(m.get('vaxt') or 0) for m in new.get('merheleler') or [] if isinstance(m, dict))
    minutes = (keep.get('_meta') or {}).get('minutes', dp.LESSON_MIN)
    keep['_warnings'] = [] if total == minutes else [f'Mərhələlərin vaxtı cəmi {total} dəq (olmalı: {minutes}) – yoxlayın']
    p.content = {**new, **keep}
    p.edited = True
    audit(db, user, 'update', 'daily_plan', p.id)
    db.commit()
    return _full(p, ctx)


@router.delete('/daily-plans/{ta_id}/item/{pid}')
def delete_plan(ta_id: int, pid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    p, _ = _own_plan(db, user, ta_id, pid)
    db.delete(p)
    audit(db, user, 'delete', 'daily_plan', pid)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- Word (.docx)
@router.get('/daily-plans/{ta_id}/docx')
def docx_export(ta_id: int, ids: str, user: User = Depends(staff), db: Session = Depends(get_db)):
    want = [int(x) for x in ids.split(',') if x.strip().isdigit()][:40]
    ta = own_assignment(db, user, ta_id)
    plans = [p for p in db.scalars(select(DailyPlan).where(DailyPlan.assignment_id == ta.id, DailyPlan.id.in_(want))
                                   .order_by(DailyPlan.date, DailyPlan.period))]
    if not plans:
        raise HTTPException(404, 'Gündəlik plan tapılmadı')
    buf = io.BytesIO()
    build_docx(plans).save(buf)
    buf.seek(0)
    first = plans[0]
    name = f"Gundelik plan {ta.cls.name} {first.date:%d.%m}" + (f"-{plans[-1].date:%d.%m}" if len(plans) > 1 else '') + '.docx'
    from urllib.parse import quote
    return StreamingResponse(buf, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                             headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(name)}"})


def build_docx(plans: list[DailyPlan]):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    for side in ('left_margin', 'right_margin', 'top_margin', 'bottom_margin'):
        setattr(sec, side, Mm(15))
    st = doc.styles['Normal']
    st.font.name, st.font.size = 'Times New Roman', Pt(11)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
    st.paragraph_format.space_after = Pt(2)

    def shade(cell):
        tcPr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement('w:shd')
        sh.set(qn('w:val'), 'clear'); sh.set(qn('w:color'), 'auto'); sh.set(qn('w:fill'), 'D9D9D9')
        tcPr.append(sh)

    def para(text, bold=False, size=None, center=False, cell=None):
        p = cell.add_paragraph() if cell is not None else doc.add_paragraph()
        r = p.add_run(text)
        r.bold = bold
        if size:
            r.font.size = Pt(size)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return p

    def cell_text(cell, text, bold=False):
        cell.text = ''
        lines = str(text or '').split('\n')
        cell.paragraphs[0].add_run(lines[0]).bold = bold
        for ln in lines[1:]:
            cell.add_paragraph(ln)

    def joined(v):
        return '\n'.join(f'• {x}' for x in v) if isinstance(v, list) else str(v or '')

    for n, p in enumerate(plans):
        c, m = p.content or {}, (p.content or {}).get('_meta', {})
        if n:
            doc.add_page_break()
        para(m.get('school', ''), bold=True, center=True)
        para('GÜNDƏLİK DƏRS PLANI', bold=True, size=14, center=True)
        rows = [('Fənn', m.get('subject', '')), ('Sinif', m.get('class_name', '')),
                ('Tarix', f"{m.get('date_text', '')} ({m.get('weekday', '')}), {m.get('period', '')}-ci dərs"),
                ('Müəllim', m.get('teacher', '')),
                ('Bölmə', m.get('section') or ''), ('Mövzu', p.topic),
                ('Dərs №', f"{m.get('seq', '')} (perspektiv plan üzrə)"),
                ('Məzmun standartları', '\n'.join(f"{s['kod']}{(' – ' + s['metn']) if s.get('metn') else ''}" for s in c.get('standartlar', []))),
                ('Təlim nəticələri', joined(c.get('telim_neticeleri'))),
                ('Açar anlayışlar', ', '.join(c.get('acar_anlayislar', []))),
                ('İnteqrasiya', c.get('inteqrasiya', '')), ('İş formaları', ', '.join(c.get('is_formalari', []))),
                ('İş üsulları', ', '.join(c.get('is_usullari', []))), ('Resurslar', joined(c.get('resurslar'))),
                ('Tədqiqat sualı', c.get('tedqiqat_suali', ''))]
        t = doc.add_table(rows=0, cols=2)
        t.style = 'Table Grid'
        for k, v in rows:
            if not v:
                continue
            r = t.add_row().cells
            cell_text(r[0], k, bold=True); shade(r[0]); cell_text(r[1], v)
            r[0].width, r[1].width = Mm(45), Mm(135)
        para('Dərsin gedişi', bold=True, size=12).paragraph_format.space_before = Pt(8)
        t = doc.add_table(rows=1, cols=4)
        t.style = 'Table Grid'
        for cell, h in zip(t.rows[0].cells, ['Mərhələ', 'Vaxt', 'Müəllimin fəaliyyəti', 'Şagirdlərin fəaliyyəti']):
            cell_text(cell, h, bold=True); shade(cell)
        for s in c.get('merheleler', []):
            r = t.add_row().cells
            cell_text(r[0], s.get('ad'), bold=True)
            cell_text(r[1], f"{s.get('vaxt', '')} dəq")
            cell_text(r[2], s.get('muellim'))
            sag = s.get('sagird', '')
            if s.get('tapsiriqlar'):
                sag += '\nTapşırıqlar:\n' + '\n'.join(f"{i}) {x['metn']}{('  [Cavab: ' + x['cavab'] + ']') if x.get('cavab') else ''}"
                                                   for i, x in enumerate(s['tapsiriqlar'], 1))
            cell_text(r[3], sag)
        for row in t.rows:
            for cell, w in zip(row.cells, (Mm(35), Mm(15), Mm(65), Mm(65))):
                cell.width = w
        d = c.get('diferensial') or {}
        if d.get('destek') or d.get('inkisaf'):
            para('Diferensial yanaşma', bold=True, size=12).paragraph_format.space_before = Pt(8)
            if d.get('destek'):
                para(f"Dəstək: {d['destek']}")
            if d.get('inkisaf'):
                para(f"İnkişaf: {d['inkisaf']}")
        q = c.get('qiymetlendirme') or {}
        para('Qiymətləndirmə', bold=True, size=12).paragraph_format.space_before = Pt(8)
        if q.get('usul') or q.get('vasite'):
            para(f"Üsul: {q.get('usul', '')}.  Vasitə: {q.get('vasite', '')}")
        if q.get('rubrika'):
            t = doc.add_table(rows=1, cols=5)
            t.style = 'Table Grid'
            for cell, h in zip(t.rows[0].cells, ['Meyar', 'I səviyyə', 'II səviyyə', 'III səviyyə', 'IV səviyyə']):
                cell_text(cell, h, bold=True); shade(cell)
            for rb in q['rubrika']:
                r = t.add_row().cells
                for cell, k in zip(r, ('meyar', 'I', 'II', 'III', 'IV')):
                    cell_text(cell, rb.get(k, ''), bold=k == 'meyar')
        elif q.get('meyarlar'):
            para(joined(q['meyarlar']))
        if q.get('spesifikasiya'):
            t = doc.add_table(rows=1, cols=4)
            t.style = 'Table Grid'
            for cell, h in zip(t.rows[0].cells, ['Standart', 'Tapşırıq sayı', 'Çətinlik', 'Bal']):
                cell_text(cell, h, bold=True); shade(cell)
            for sp in q['spesifikasiya']:
                r = t.add_row().cells
                for cell, k in zip(r, ('standart', 'tapsiriq_sayi', 'seviyye', 'bal')):
                    cell_text(cell, sp.get(k, ''))
        if c.get('refleksiya'):
            para('Refleksiya', bold=True, size=12).paragraph_format.space_before = Pt(8)
            para(joined(c['refleksiya']))
        para('Ev tapşırığı', bold=True, size=12).paragraph_format.space_before = Pt(8)
        para(c.get('ev_tapsirigi') or '—')
        if c.get('muellim_ucun_qeyd'):
            para('Müəllim üçün qeyd', bold=True, size=12).paragraph_format.space_before = Pt(8)
            para(c['muellim_ucun_qeyd'])
    return doc
