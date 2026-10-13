"""Zəif qrup tempi (docs/x-e-zeif-qrup-tempi-promtu.md, 13.10.2026): sinfin perspektiv planı iki ilə yayılır.

1-ci il – I yarımilin bazası (V–IX sinif) bütün ilə: keçmiş dərslər toxunulmur, sonra «Bazanın bərpası», hər mövzudan sonra
«Məşq və möhkəmləndirmə», bölmə sonunda KSQ (yeni tempə görə), hər yarımilin sonunda təkrar + BSQ. 2-ci il – II yarımilin
materialı ayrıca proqram kimi saxlanır (tətbiq olunmur)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AcademicYear, PlanLesson, PlanProgram, SchoolClass, TeachingAssignment, User
from .programs import FIELDS, apply as apply_program, capacity
from .services import class_grade

RESTORE_MAX = 10           # «Bazanın bərpası» – ən çox neçə dərs
KSQ_PER_YEAR = 8           # yeni tempdə KSQ – ildə təxminən (yarımildə ~4), bölmə sonunda; ən azı 16 dərsdən bir
SPIRAL_EVERY = 10          # spiral təkrar – təxminən neçə mövzu/məşq dərsindən bir
PRACTICE = 'Məşq və möhkəmləndirmə'
SUMMATIVE = ('KSQ', 'BSQ')


def _les(sem: int, section: str, topic: str, typ: str = 'formativ', assessment: str | None = None,
         exam_no: int | None = None, resources: str | None = None) -> dict:
    return {'semester': sem, 'section': section, 'topic': topic, 'standards': [], 'integration': None,
            'resources': resources, 'assessment': assessment, 'assessment_type': typ, 'exam_no': exam_no,
            'tt_pages': None, 'tasks': []}


def _az_cap(t: str) -> str:
    """«TAM CƏBRİ İFADƏLƏR» → «Tam cəbri ifadələr» (Python lower() «İ»-ni «i̇» edir, «I»-ni «i»)."""
    low = t.replace('İ', 'i').replace('I', 'ı').lower()
    return ({'i': 'İ', 'ı': 'I'}.get(low[:1]) or low[:1].upper()) + low[1:] if low else low


def _content(l: dict) -> bool:
    return l['assessment_type'] not in SUMMATIVE and not (l.get('section') or '').startswith(('Təkrar', 'Diaqnostik'))


def build(db: Session, ta: TeachingAssignment, keep_until: dt.date) -> tuple[list[dict], list[dict], dict]:
    """→ (1-ci ilin tam dərs siyahısı – keçmiş + yeni, 2-ci il proqramının dərsləri, hesabat)."""
    rows = [{k: getattr(pl, k) for k in FIELDS} | {'date': pl.date}
            for pl in db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id).order_by(PlanLesson.seq))]
    cap = capacity(db, ta)
    slots = [d for d, _ in cap['slots']]
    sem1_end = db.get(AcademicYear, db.get(SchoolClass, ta.class_id).year_id).sem1_end
    past_n = sum(1 for d in slots if d <= keep_until)
    past = [{k: r[k] for k in FIELDS} for r in rows[:past_n]]
    rest = rows[past_n:]
    warnings: list[str] = []

    # 1-ci il: I yarımilin qalan mövzu dərsləri; 2-ci il: II yarımilin bütün dərsləri (ilkin KSQ/BSQ ilə)
    y1 = [r for r in rest if r['semester'] == 1 and _content(r)]
    y2 = [{k: r[k] for k in FIELDS} for r in rest if r['semester'] == 2]

    # bazanın bərpası: keçmiş mövzu dərsləri (KSQ-1-in yoxladığı) – mövzu başına bir dərs
    seen: list[str] = []
    for r in past:
        if _content(r) and r['topic'] not in seen:
            seen.append(r['topic'])
    restore = [_les(1, 'Bazanın bərpası', f'Təkrar və bərpa: {t}', 'formativ',
                    'Formativ: 10 dəqiqəlik mini-test (zəif qrup – asan tapşırıqlar), şifahi sorğu') for t in seen[:RESTORE_MAX]]

    free1 = sum(1 for d in slots[past_n:] if d <= sem1_end)
    free2 = len(slots) - past_n - free1
    # hər yarımilin sonu: «Təkrar» + BSQ (2 dərs)
    target = max(0, free1 - 2) + max(0, free2 - 2)

    # axın: mövzu → məşq; ~10 dərsdən bir spiral təkrar (əvvəlki bölmələr); bölmə sonu – bölmə təkrarı; KSQ-dən əvvəl hazırlıq
    ksq_no = max([r['exam_no'] or 0 for r in past if r['assessment_type'] == 'KSQ'] or [0])
    every = max(16, len(y1) * 2 // KSQ_PER_YEAR)
    short = lambda sec: _az_cap((sec or '').split(' – ', 1)[-1])               # noqa: E731

    def stream(keep: list[bool], spiral: int) -> list[dict]:
        out, since, since_sp, no, done_secs, covered = [], 0, 0, ksq_no, [], []
        for i, r in enumerate(y1):
            sec = r['section'] or ''
            out.append({k: r[k] for k in FIELDS})
            since += 1
            since_sp += 1
            if keep[i]:
                out.append(_les(1, sec, f'{PRACTICE}: {r["topic"]}', 'formativ',
                                'Formativ: mövzu testi (zəif qrup – asan/orta tapşırıqlar), müşahidə'))
                since += 1
                since_sp += 1
            if spiral and since_sp >= spiral and covered:
                out.append(_les(1, sec, 'Spiral təkrar: ' + ', '.join(short(x) for x in covered[-3:]), 'formativ',
                                'Formativ: 10 sual – əvvəlki bölmələrdən qarışıq test (unutmaya qarşı)'))
                since_sp = 0
            if i == len(y1) - 1 or y1[i + 1]['section'] != r['section']:
                out.append(_les(1, sec, f'Bölmə təkrarı: {short(sec)}', 'formativ', 'Formativ: ümumiləşdirici tapşırıqlar (zəif qrup)'))
                covered.append(sec)
                done_secs.append(sec)
                if since >= every:
                    no += 1
                    names = ', '.join(dict.fromkeys(short(x) for x in done_secs))
                    out.append(_les(1, sec, f'KSQ-yə hazırlıq: {names}', 'formativ', 'Formativ: sınaq testi (KSQ formatında)'))
                    out.append(_les(1, sec, f'KSQ-{no}: {names}', 'KSQ',
                                    'Kiçik summativ qiymətləndirmə (zəif qrup tempi – keçilmiş bölmələr)', exam_no=no))
                    since, done_secs = 0, []
        return out

    keep, spiral = [True] * len(y1), SPIRAL_EVERY
    seq = restore + stream(keep, spiral)
    if len(seq) > target:                                     # 1) məşq dərsləri bərabər paylanaraq azalır
        over = len(seq) - target
        if over >= len(y1):
            keep = [False] * len(y1)
        else:
            for j in range(over):
                keep[min(len(y1) - 1, int((j + 0.5) * len(y1) / over))] = False
        seq = restore + stream(keep, spiral)
        while len(seq) > target and spiral < 40:             # 2) spiral təkrar seyrəlir
            spiral += 5
            seq = restore + stream(keep, spiral)
        if len(seq) > target:
            seq = restore + stream(keep, 0)
        if len(seq) > target:                                 # 3) yenə çatmırsa – son dərslər 2-ci ilə
            over = len(seq) - target
            warnings.append(f'1-ci il üçün yuva çatmır: son {over} dərs 2-ci ilə keçirildi')
            y2 = [{k: v for k, v in l.items()} for l in seq[target:] if l['assessment_type'] != 'KSQ'] + y2
            seq = seq[:target]
    if len(seq) < target:                                     # artıq yuva – bərabər aralıqla əlavə spiral təkrar
        miss = target - len(seq)
        start = len(restore)
        body = seq[start:]
        step = max(1, len(body) // (miss + 1))
        for j in range(miss, 0, -1):
            pos = min(len(body), j * step)
            sec = body[pos - 1]['section'] if pos and body else 'Təkrar'
            body.insert(pos, _les(1, sec, 'Spiral təkrar: əvvəlki bölmələr', 'formativ',
                                  'Formativ: 10 sual – əvvəlki bölmələrdən qarışıq test (unutmaya qarşı)'))
        seq = seq[:start] + body
    # yarımillər: I yarımil yuvaları + təkrar + BSQ-1, sonra II yarımil + təkrar + BSQ-2
    n1 = max(0, free1 - 2)
    year = list(past)
    part1, part2 = seq[:n1], seq[n1:]
    for l in part1:
        l['semester'] = 1
    year += part1
    if free1 >= 2:
        year += [_les(1, 'Təkrar', 'Təkrar: I yarımil üzrə yekunlaşdırıcı tapşırıqlar (zəif qrup)', 'formativ', 'Formativ: yekunlaşdırıcı test'),
                 _les(1, 'Böyük summativ qiymətləndirmə', 'BSQ-1: I yarımil materialı', 'BSQ', 'Böyük summativ qiymətləndirmə', exam_no=1)]
    for l in part2:
        l['semester'] = 2
    year += part2
    if free2 >= 2:
        year += [_les(2, 'Təkrar', 'Təkrar: illik material üzrə yekunlaşdırıcı tapşırıqlar (zəif qrup)', 'formativ', 'Formativ: yekunlaşdırıcı test'),
                 _les(2, 'Böyük summativ qiymətləndirmə', 'BSQ-2: II yarımil materialı', 'BSQ', 'Böyük summativ qiymətləndirmə', exam_no=2)]
    # KSQ nömrələri ardıcıl (yarımil daxilində bölünmür – jurnal nömrəsi)
    no = 0
    for l in year:
        if l['assessment_type'] == 'KSQ':
            no += 1
            l['exam_no'] = no
            if l['topic'].startswith('KSQ-'):
                l['topic'] = f'KSQ-{no}:' + l['topic'].split(':', 1)[1]
    # 2-ci il: yarımillər yarı-yarıya, KSQ/BSQ yenidən nömrələnir
    half = len(y2) // 2
    kn = 0
    for i, l in enumerate(y2):
        l['semester'] = 1 if i < half else 2
        if l['assessment_type'] == 'KSQ':
            kn += 1
            l['exam_no'] = kn
        if l['assessment_type'] == 'BSQ':
            l['exam_no'] = l['semester']
    rep = {'slots': len(slots), 'kept_past': past_n, 'restore': len(restore), 'year1_topics': len(y1),
           'practice': sum(1 for l in year if l['topic'].startswith(PRACTICE)),
           'review': sum(1 for l in year[past_n:] if l['topic'].startswith('Təkrar:')),
           'section_review': sum(1 for l in year if l['topic'].startswith('Bölmə təkrarı')),
           'spiral': sum(1 for l in year if l['topic'].startswith('Spiral təkrar')),
           'ksq_prep': sum(1 for l in year if l['topic'].startswith('KSQ-yə hazırlıq')),
           'ksq': sum(1 for l in year if l['assessment_type'] == 'KSQ'), 'bsq': sum(1 for l in year if l['assessment_type'] == 'BSQ'),
           'lessons': len(year), 'year2_lessons': len(y2), 'warnings': warnings,
           'first_new': year[past_n]['topic'] if len(year) > past_n else None}
    return year, y2, rep


def make(db: Session, ta: TeachingAssignment, user: User, keep_until: dt.date) -> dict:
    """Proqramlar yaradılır (1-ci il – tətbiq olunur, 2-ci il – kitabxanada); əvvəlki plan kitabxanaya saxlanır (apply)."""
    year, y2, rep = build(db, ta, keep_until)
    cls = db.get(SchoolClass, ta.class_id)
    grade = class_grade(db, cls)
    common = dict(school_id=cls.school_id, owner_id=user.id, subject=ta.subject, kind='fixed', weekly_hours=ta.weekly_hours,
                  level='Zəif', source='Zəif qrup tempi (2 il)')
    p1 = PlanProgram(**common, grade=grade, title=f'{cls.name} – {ta.subject}: zəif qrup tempi, 1-ci il',
                     description=f'{len(year)} dərs · {keep_until:%d.%m.%Y}-dək keçilənlər saxlanılıb',
                     data={'lessons': year, 'from_ta': ta.id})
    p2 = PlanProgram(**common, grade=grade + 1 if grade else None, title=f'{cls.name} – {ta.subject}: zəif qrup tempi, 2-ci il',
                     description=f'{len(y2)} dərs · gələn tədris ili üçün', data={'lessons': y2, 'from_ta': ta.id})
    db.add_all([p1, p2])
    db.flush()
    res = apply_program(db, p1, ta, user)
    return {**rep, 'program_id': p1.id, 'year2_program_id': p2.id, 'previous_program_id': res.get('previous_program_id'),
            'frozen_topics': res.get('frozen_topics')}
