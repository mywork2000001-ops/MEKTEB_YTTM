"""Perspektiv planın Word (.docx) ixracı – rəsmi forma, yalnız Azərbaycan dilində (CLAUDE.md: rəsmi sənədlər AZ).

Düzüm müəllimin «01 Aktual dərs proqramları 2026-2027» sənədləri kimidir: məktəb, başlıq, proqram/saat, aylar üzrə saatlar,
məlumat cədvəli (müəllim, dərs cədvəli, tədris ili, əsas, resurslar), 8 sütunlu plan cədvəli (yarımil və bölmə sətirləri ilə),
aylar üzrə saat cədvəli. Məşq / bərpa / təkrar dərsləri standart və resursu əsas mövzudan götürür (zəif qrup tempi)."""
from __future__ import annotations

import datetime as dt
import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, RGBColor
from sqlalchemy.orm import Session

from .models import PlanProgram, TeachingAssignment, User
from .services import plan_ctx

FONT = 'Times New Roman'
MONTHS = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avqust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr']
DAYS = ['Bazar ertəsi', 'Çərşənbə axşamı', 'Çərşənbə', 'Cümə axşamı', 'Cümə', 'Şənbə', 'Bazar']
DERIVED = ('Məşq və möhkəmləndirmə: ', 'Təkrar və bərpa: ')
HEAD = ['Sıra\n№-si', 'Məzmun\nstandartları', 'Mövzu', 'İnteqrasiya', 'Resurslar', 'Qiymətləndirmə', 'Saat', 'Tarix']
WIDTHS = [0.45, 0.85, 2.4, 1.15, 1.1, 1.35, 0.4, 0.75]           # düym – A4 portret, 1 sm kənar


def _run(p, text: str, size: float = 10, bold: bool = False, italic: bool = False):
    r = p.add_run(text)
    r.font.name, r.font.size, r.bold, r.italic = FONT, Pt(size), bold, italic
    r._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)
    return r


def _para(doc, text: str = '', size: float = 11, bold: bool = False, center: bool = False, italic: bool = False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if text:
        _run(p, text, size, bold, italic)
    return p


def _cell(c, text: str, size: float = 9, bold: bool = False, center: bool = False, shade: str | None = None):
    c.text = ''
    lines = (text or '').split('\n')
    p = c.paragraphs[0]
    for i, line in enumerate(lines):
        if i:
            p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        if center:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, line, size, bold)
    if shade:
        tc = c._element.get_or_add_tcPr()
        sh = OxmlElement('w:shd')
        sh.set(qn('w:val'), 'clear')
        sh.set(qn('w:color'), 'auto')
        sh.set(qn('w:fill'), shade)
        tc.append(sh)


def _merged_row(t, text: str, shade: str, size: float = 9.5):
    row = t.add_row()
    c = row.cells[0].merge(row.cells[-1])
    _cell(c, text, size, bold=True, center=True, shade=shade)


def _date(d: dt.date | None) -> str:
    return f'{d:%d.%m.%Y}' if d else '—'


def _long(d: dt.date) -> str:
    return f'{d.day} {MONTHS[d.month - 1]} {d.year}'


def build(db: Session, ta: TeachingAssignment, user: User, school: str) -> tuple[bytes, str]:
    """→ (.docx baytları, fayl adı)."""
    ctx = plan_ctx(db, ta)
    cls, year, lessons = ctx.cls, ctx.year, ctx.lessons
    when: dict[int, dt.date] = {}
    for s in ctx.slots:
        if s.index is not None:
            when.setdefault(s.index, s.date)
    prog = db.get(PlanProgram, ta.program_id) if ta.program_id else None
    base = {pl.topic: pl for pl in lessons}

    def src(pl):                                            # məşq / bərpa – əsas mövzunun standartı və resursu
        for pre in DERIVED:
            if pl.topic.startswith(pre):
                return base.get(pl.topic[len(pre):])
        return None

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Emu(7560310), Emu(10692130)
    sec.left_margin = sec.right_margin = Emu(360045)
    sec.top_margin = sec.bottom_margin = Emu(431800)
    st = doc.styles['Normal']
    st.font.name, st.font.size = FONT, Pt(10)

    _para(doc, school.replace('i', 'İ').replace('ı', 'I').upper(), 11, bold=True, center=True)   # az: i → İ
    _para(doc, f'{cls.name} sinfi “{ta.subject}” fənni üzrə {year.name}-ci tədris ili üçün perspektiv plan', 14, bold=True, center=True)
    sub = (prog.title.split(': ', 1)[-1] if prog else ta.subject)
    if prog and prog.level == 'Zəif':
        sub = 'Zəif qrup tempi – iki illik proqram, 1-ci il (baza: bərpa, məşq, bölmə və spiral təkrar)'
    _para(doc, f'{sub}, həftədə {ta.weekly_hours} saat', 11, center=True)
    _para(doc)

    info = doc.add_table(rows=0, cols=2)
    days: list[str] = []
    for k, periods in sorted(((int(k), v) for k, v in (ta.slots or {}).items())):
        if periods:
            days.append(f'{DAYS[k]} – {", ".join(str(p) for p in sorted(periods))}-ci saat')
    rows = [('Müəllim:', user.full_name or '—'), ('Dərs cədvəli:', '; '.join(days) or '—'),
            ('Tədris ili:', f'{_long(year.start)} – {_long(year.end)}; şənbə və bazar istirahət günləridir'),
            ('Əsas:', (prog.title if prog else 'Sinfin perspektiv planı') + (f' ({prog.source})' if prog and prog.source else '')),
            ('Resurslar:', 'DİM “Riyaziyyat. Test toplusu”, DİM “Riyaziyyat. Sinif testləri”; planda göstərilən dərslik səhifələri')]
    for a, b in rows:
        r = info.add_row().cells
        _cell(r[0], a, 10, bold=True)
        _cell(r[1], b, 10)
    _para(doc)

    t = doc.add_table(rows=1, cols=8)
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in zip(t.rows[0].cells, HEAD):
        _cell(c, h, 9, bold=True, center=True, shade='D9E2F3')
    cur_sem, cur_sec = None, None
    for i, pl in enumerate(lessons):
        if pl.semester != cur_sem:
            cur_sem, cur_sec = pl.semester, None
            _merged_row(t, 'I YARIMİL' if pl.semester == 1 else 'II YARIMİL', 'BDD7EE', 10)
        if (pl.section or '') != (cur_sec or ''):
            cur_sec = pl.section or ''
            if cur_sec:
                _merged_row(t, cur_sec, 'EDEDED')
        s = src(pl)
        stds = pl.standards or (s.standards if s else None) or []
        res = pl.resources or (s.resources if s else None)
        integ = pl.integration or (s.integration if s else None)
        r = t.add_row().cells
        bold = pl.assessment_type in ('KSQ', 'BSQ')
        vals = [str(pl.seq), ', '.join(stds) or '—', pl.topic, integ or '—', res or '—', pl.assessment or pl.assessment_type or '—',
                '1', _date(when.get(i) or pl.date)]
        for k, (c, v) in enumerate(zip(r, vals)):
            _cell(c, v, 9, bold=bold and k == 2, center=k in (0, 6, 7))
    for row in t.rows:
        for c, w in zip(row.cells, WIDTHS):
            c.width = Emu(int(w * 914400))

    _para(doc)
    _para(doc, 'Aylar üzrə dərs saatlarının bölgüsü', 11, bold=True, center=True)
    n1 = sum(1 for pl in lessons if pl.semester == 1)
    _para(doc, f'I yarımil: {n1} saat   ·   II yarımil: {len(lessons) - n1} saat   ·   İl üzrə: {len(lessons)} saat', 10, bold=True, center=True)
    months: dict[tuple[int, int], int] = {}
    for i, pl in enumerate(lessons):
        d = when.get(i) or pl.date
        if d:
            months[(d.year, d.month)] = months.get((d.year, d.month), 0) + 1
    keys = sorted(months)
    mt = doc.add_table(rows=2, cols=len(keys) + 1)
    mt.style = 'Table Grid'
    for k, (y_, m_) in enumerate(keys):
        _cell(mt.rows[0].cells[k], MONTHS[m_ - 1].capitalize(), 9, bold=True, center=True)
        _cell(mt.rows[1].cells[k], str(months[(y_, m_)]), 9, center=True)
    _cell(mt.rows[0].cells[-1], 'CƏMİ', 9, bold=True, center=True)
    _cell(mt.rows[1].cells[-1], str(sum(months.values())), 9, bold=True, center=True)
    p = _para(doc, 'Qeyd: Bayram və tətil günləri Nazirlər Kabinetinin və Elm və Təhsil Nazirliyinin rəsmi qərarlarına uyğun '
                   'dəqiqləşdirilməlidir.', 9, italic=True)
    p.runs[0].font.color.rgb = RGBColor(0x40, 0x40, 0x40)
    buf = io.BytesIO()
    doc.save(buf)
    name = f'{cls.name.replace(" ", "-")} sinif – {ta.subject} perspektiv plan {year.name.replace("–", "-")}.docx'
    return buf.getvalue(), name
