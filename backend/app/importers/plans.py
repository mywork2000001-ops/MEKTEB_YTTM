"""Rəsmi perspektiv planların (01 Aktual dərs proqramları 2026-2027) parseri.
Cədvəl: Sıra №-si | Məzmun standartları | Mövzu | İnteqrasiya | Resurslar | Qiymətləndirmə | Saat | Tarix.
Birləşdirilmiş sətirlər: «I YARIMİL» / «II YARIMİL» və «I BÖLMƏ – …». Plan heç vaxt dəyişdirilmir, yalnız oxunur."""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

HEADERS = ['sıra', 'məzmun', 'mövzu', 'inteqrasiya', 'resurs', 'qiymətləndirmə', 'saat', 'tarix']


@dataclass
class TaskRange:
    kind: str          # sinif | ev | mustaqil
    label: str         # altmövzu adı (bir neçə altmövzu olduqda) və ya ''
    start: int
    end: int


@dataclass
class PlanLesson:
    seq: int
    semester: int
    section: str
    standards: list[str]
    topic: str
    integration: str
    resources: str
    assessment: str
    assessment_type: str      # formativ | KSQ | BSQ | diaqnostik
    exam_no: int | None
    hours: int
    date: dt.date
    tt_pages: str = ''
    tasks: list[TaskRange] = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d['date'] = self.date.isoformat()
        return d


@dataclass
class ParsedPlan:
    file: str
    title: str
    sections: list[str]
    lessons: list[PlanLesson]
    warnings: list[str]


def _norm(s: str) -> str:
    return s.replace('İ', 'i').replace('I', 'ı').lower()


def _cell_texts(row) -> list[str]:
    # python-docx birləşdirilmiş xanaları təkrarlayır; _tc üzrə unikal xanalar götürülür
    seen, out = set(), []
    for c in row.cells:
        if id(c._tc) in seen:
            continue
        seen.add(id(c._tc))
        out.append(c.text.strip())
    return out


def _find_table(doc):
    for t in doc.tables:
        if not t.rows or len(t.columns) != 8:
            continue
        head = [_norm(x) for x in _cell_texts(t.rows[0])]
        if len(head) == 8 and all(h in head[i] for i, h in enumerate(HEADERS)):
            return t
    raise ValueError('8 sütunlu perspektiv plan cədvəli tapılmadı')


STD_RX = re.compile(r'\d+\.\d+\.\d+')
TASK_RX = re.compile(r'^(S|E|M)\s+(.+)$')
KIND = {'S': 'sinif', 'E': 'ev', 'M': 'mustaqil'}


def parse_resources(text: str) -> tuple[str, list[TaskRange]]:
    """«TT I, s.45–46; S 1–20; E 21–35; M 36–40» -> (səhifələr, tapşırıq aralıqları).
    Bir neçə altmövzu: «S Kəsrlər 1–10; Faiz 1–8». Tanınmayan hissələr atılmır – mətn tam saxlanılır."""
    pages, tasks = [], []
    for line in text.split('\n'):
        cur = None                                   # hər sətir yenidən başlayır: «QT …; D 5, 6» tapşırıq deyil
        for part in (p.strip() for p in line.split(';')):
            if not part:
                continue
            m = TASK_RX.match(part)
            if m:
                cur = KIND[m.group(1)]
                part = m.group(2)
            elif re.match(r'^(QT\b|D\b|P\d+:)', part):           # qiymətləndirmə tapşırıqları / dərslik / «P007: mövzu» (test bazası faylı) – nömrə aralığı deyil
                cur = None
                continue
            elif part.startswith('TT'):
                pages.append(part)
                cur = None
                continue
            elif part.startswith('s.') and pages:
                pages.append(part)
                continue
            if cur is None:
                continue
            r = re.match(r'^(.*?)\s*№?(\d+)(?:\s*[–-]\s*(\d+))?$', part)
            if r:
                a = int(r.group(2))
                b = int(r.group(3) or a)
                tasks.append(TaskRange(cur, r.group(1).strip(), a, b))
    return '; '.join(pages), tasks


def assessment_type(topic: str, assessment: str) -> tuple[str, int | None]:
    t, a = _norm(topic), _norm(assessment)
    m = re.search(r'\b(ksq|bsq)\s*[-–№]?\s*(\d+)', t)
    if m:
        return m.group(1).upper(), int(m.group(2))
    m = re.search(r'(mövzu|ümumi) sınaq imtahanı\s*[-–№]?\s*(\d+)', t)   # köhnə adlandırma (X b bütöv sinif planı)
    if m:
        return ('KSQ' if m.group(1) == 'mövzu' else 'BSQ'), int(m.group(2))
    if 'hazırlıq' in t:                                  # «… qiymətləndirməyə hazırlıq» – adi dərsdir
        return ('diaqnostik' if a.startswith('diaqnostik') else 'formativ'), None
    if 'böyük summativ' in t or ('böyük summativ' in a and 'hazırlıq' not in t):
        return 'BSQ', None
    if 'kiçik summativ' in t or ('kiçik summativ' in a and 'hazırlıq' not in t):
        return 'KSQ', None
    if a.startswith('diaqnostik'):
        return 'diaqnostik', None
    return 'formativ', None


def _date(s: str) -> dt.date:
    return dt.datetime.strptime(s.strip(), '%d.%m.%Y').date()


def parse_plan(path: str | Path) -> ParsedPlan:
    import docx  # yalnız import zamanı lazımdır
    path = Path(path)
    doc = docx.Document(str(path))
    title = next((p.text.strip() for p in doc.paragraphs if 'perspektiv plan' in p.text), path.stem)
    table = _find_table(doc)
    lessons, sections, warnings = [], [], []
    semester, section = 1, ''
    for i, row in enumerate(table.rows[1:], 2):
        cells = _cell_texts(row)
        if len(cells) == 1 or len(set(cells)) == 1:
            text = cells[0]
            n = _norm(text)
            if 'yarımil' in n and 'bölmə' not in n:
                semester = 2 if n.startswith('ıı') else 1
            elif 'bölmə' in n:
                section = text
                if not text.endswith('(davamı)'):
                    sections.append(text)
            continue
        if len(cells) != 8:
            warnings.append(f'Sətir {i}: {len(cells)} xana (8 gözlənilirdi) – ötürüldü')
            continue
        no, std, topic, integ, res, asm, hrs, date = cells
        try:
            d = _date(date)
        except ValueError:
            warnings.append(f'Sətir {i}: tarix oxunmadı «{date}» – ötürüldü')
            continue
        if not no.isdigit():
            warnings.append(f'Sətir {i}: sıra № rəqəm deyil «{no}»')
        at, exam_no = assessment_type(topic, asm)
        pages, tasks = parse_resources(res)
        lessons.append(PlanLesson(
            seq=int(no) if no.isdigit() else len(lessons) + 1, semester=semester, section=section,
            standards=STD_RX.findall(std), topic=topic, integration=integ, resources=res, assessment=asm,
            assessment_type=at, exam_no=exam_no, hours=int(hrs) if hrs.isdigit() else 1, date=d,
            tt_pages=pages, tasks=tasks))
    # daxili yoxlamalar
    for a, b in zip(lessons, lessons[1:]):
        if b.seq != a.seq + 1:
            warnings.append(f'Sıra № ardıcıl deyil: {a.seq} → {b.seq}')
        if b.date < a.date:
            warnings.append(f'Tarix geri gedir: №{a.seq} {a.date:%d.%m.%Y} → №{b.seq} {b.date:%d.%m.%Y}')
    for l in lessons:
        if sum(t.end - t.start + 1 for t in l.tasks if t.kind == 'sinif') > 20:
            warnings.append(f'№{l.seq}: sinifdə 20-dən çox test tapşırığı')
    return ParsedPlan(path.name, title, sections, lessons, warnings)
