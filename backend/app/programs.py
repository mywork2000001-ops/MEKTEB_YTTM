"""Perspektiv plan proqramları (docs/perspektiv-proqramlar-promtu.md).

Proqram sinfə bağlı deyil: müəllim sinif və ya qrup üçün kitabxanadan seçib tətbiq edir.
- fixed    – hazır dərs siyahısı (əvvəlki Word planları, sinifdən saxlanmış planlar);
- adaptive – bölmə/mövzu şablonu (DİM «Sinif testləri» V–XI), sinfin cədvəlinə görə dərslərə açılır:
  I yarımil: diaqnostik → bölmələr (mövzunun son dərsi – sinif testi) → bölmə sonunda KSQ → yarımil təkrarı → BSQ-1;
  II yarımil: bölmələr → KSQ → illik təkrar → BSQ-2. Yuva azdırsa əvvəl köməkçi dərslər çıxır, sonra mövzular 1 dərsə enir.
- adaptive + format «course» – repetitor/hazırlıq kursu (docs/repetitor-proqramlar-promtu.md): diaqnostik/KSQ/BSQ/yarımil yoxdur,
  kursun bütün yuvalarına mövzular → (istəyə görə) aralıq və bölmə sınaqları → yekun sınaq.
Tətbiq: əvvəlki plan kitabxanaya saxlanılır, jurnalda yazılmış dərslərin mövzusu dondurulur, plan_lesson id-ləri sıra № ilə qorunur."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain.calendar import lesson_slots
from .models import (Holiday, JournalEntry, PlanLesson, PlanProgram, SchoolClass, TeachingAssignment, User, now)
from .services import class_grade

DATA = Path(__file__).parent / 'program_data'
ROMAN = {5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI'}
STEPS = ('Məsələ həlli', 'Möhkəmləndirmə', 'Tətbiq məsələləri', 'Müstəqil iş')
FIELDS = ('semester', 'section', 'topic', 'standards', 'integration', 'resources', 'assessment', 'assessment_type',
          'exam_no', 'tt_pages', 'tasks')


# hazırlıq kursları – DİM «Sinif testləri» strukturundan ayrıca proqramlar (sinif planlarından köçürmə deyil)
PREP = (('hazirliq-buraxilis-9', 9, ['buraxilis9'], 'Buraxılış hazırlığı – IX sinif (V–IX mövzuları)'),
        ('hazirliq-buraxilis-11', 11, ['buraxilis11', 'qebul'], 'Buraxılış və qəbul (blok) hazırlığı – XI sinif (V–XI mövzuları)'))


def is_course(p: PlanProgram) -> bool:
    return p.kind == 'adaptive' and p.data.get('template', {}).get('format') == 'course'


def tpl_sections(tpl: dict) -> list[dict]:
    """Şablonun bölmələri ardıcıl (məktəb formatında – hər iki yarımil)."""
    return list(tpl['sections']) if tpl.get('format') == 'course' else [s for sem in tpl['semesters'] for s in sem]


def purposes(p: PlanProgram) -> list[str]:
    """Proqramın təyinatı (hazırlıq məqsədləri); DİM «Sinif testləri» – cari sinif dərsi."""
    if p.data.get('purposes'):
        return list(p.data['purposes'])
    return ['sinif'] if (p.key or '').startswith('dim-sinif-testleri') else []


def _prep_template(src: dict, upto: int) -> dict:
    sections = []
    for g in range(5, upto + 1):
        rom = ROMAN[g]
        for sem in src['grades'][str(g)]['semesters']:
            for sec in sem:
                if sec['section'].startswith('Təkrar'):
                    continue
                name = sec['section'].split(' ', 1)[-1] if sec['section'][:1].isdigit() else sec['section']
                sections.append({'section': f'{rom} sinif – {name}', 'part': sec.get('part'),
                                 'topics': [f'{rom} sinif: {t}' for t in sec['topics']]})
    return {'format': 'course', 'sections': sections, 'mock_after_section': False, 'final_mock': True,
            'mock_every': 8, 'resource': 'DİM «Riyaziyyat. Sinif testləri»'}


# ---------------------------------------------------------------- daxili proqramlar (kitabdan)
def ensure_builtin(db: Session) -> None:
    """DİM «Sinif testləri» – V–XI siniflər üçün ümumi (hamıya görünən) uyğunlaşan proqramlar və onların strukturundan
    buraxılış/qəbul hazırlığı kursları; idempotent."""
    src = json.loads((DATA / 'sinif_testleri.json').read_text(encoding='utf-8'))
    have = set(db.scalars(select(PlanProgram.key).where(PlanProgram.key.is_not(None))))
    for key, g, purp, title in PREP:
        if key in have:
            continue
        tpl = _prep_template(src, g)
        n = sum(len(x['topics']) for x in tpl['sections'])
        db.add(PlanProgram(
            key=key, school_id=None, owner_id=None, subject='Riyaziyyat', grade=g, kind='adaptive', title=title,
            source=src['source'],
            description=(f'{len(tpl["sections"])} bölmə, {n} mövzu – V–{ROMAN[g]} siniflərin materialı ardıcıl; hər mövzunun sonunda test, '
                         'hər 8 dərsdən bir aralıq sınaq, sonda yekun sınaq. Qrupun kurs müddətinə və cədvəlinə görə açılır; '
                         'yuva azdırsa lazım olan bölmələri seçin.'),
            data={'template': tpl, 'purposes': purp, 'source_short': 'DİM Sinif testləri'}))
    for g, tpl in src['grades'].items():
        key = f"{src['key']}-{g}"
        if key in have:
            continue
        n_topics = sum(len(s['topics']) for sem in tpl['semesters'] for s in sem)
        db.add(PlanProgram(
            key=key, school_id=None, owner_id=None, subject='Riyaziyyat', grade=int(g), kind='adaptive',
            title=f'Riyaziyyat – {ROMAN[int(g)]} sinif (DİM «Sinif testləri» əsasında)', source=src['source'],
            description=(f'{n_topics} mövzu, hər mövzuya sinif testi (variant {tpl["variants"]}); yarımil üzrə yekunlaşdırıcı testlər. '
                         'Sinfin həftəlik cədvəlinə görə dərslərə açılır.'),
            data={'template': tpl, 'source_short': 'DİM Sinif testləri'}))
    db.flush()


# ---------------------------------------------------------------- sinfin cari planı → proqram
def _lesson_dicts(db: Session, ta_id: int) -> list[dict]:
    rows = db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta_id).order_by(PlanLesson.seq))
    return [{k: getattr(pl, k) for k in FIELDS} for pl in rows]


def snapshot(db: Session, ta: TeachingAssignment, user: User | None, title: str | None = None) -> PlanProgram | None:
    """Sinfin hazırkı planını sabit proqram kimi saxlayır (dərs yoxdursa – None)."""
    lessons = _lesson_dicts(db, ta.id)
    if not lessons:
        return None
    cls = db.get(SchoolClass, ta.class_id)
    p = PlanProgram(school_id=cls.school_id, owner_id=user.id if user else ta.teacher_id, subject=ta.subject,
                    grade=class_grade(db, cls), kind='fixed', weekly_hours=ta.weekly_hours,
                    title=title or f'{cls.name} – {ta.subject}, {ta.weekly_hours} saat (cari plan)',
                    source='Sinifdən saxlanmış plan', description=f'{len(lessons)} dərs',
                    data={'lessons': lessons, 'from_ta': ta.id})
    db.add(p)
    db.flush()
    return p


def ensure_current(db: Session, user: User) -> None:
    """Müəllimin hər sinif/qrupunun mövcud planı kitabxanada proqram kimi olsun (əvvəlki planlar itməsin)."""
    for ta in db.scalars(select(TeachingAssignment).where(TeachingAssignment.teacher_id == user.id,
                                                          TeachingAssignment.archived_at.is_(None),
                                                          TeachingAssignment.program_id.is_(None))):
        p = snapshot(db, ta, user)
        if p:
            ta.program_id = p.id
    db.flush()


# ---------------------------------------------------------------- yuvalar
def capacity(db: Session, ta: TeachingAssignment) -> dict:
    """Sinfin cədvəlinə görə ildəki dərs yuvaları: I və II yarımil."""
    from .models import AcademicYear
    cls = db.get(SchoolClass, ta.class_id)
    y = db.get(AcademicYear, cls.year_id)
    off = {h.date: h.name for h in db.scalars(select(Holiday).where(Holiday.year_id == y.id))}
    from .services import ta_range
    slots = lesson_slots({int(k): v for k, v in (ta.slots or {}).items()}, off, *ta_range(ta, y))
    s1 = [s for s in slots if s[0] <= y.sem1_end]
    s2 = [s for s in slots if s[0] >= y.sem2_start]
    return {'slots': s1 + s2, 'sem1': len(s1), 'sem2': len(s2)}


# ---------------------------------------------------------------- uyğunlaşan proqramın açılması
def _share(total: int, n: int) -> list[int]:
    """total dərsi n mövzuya bərabər böl (ən böyük qalıq), hər birinə ən azı 1."""
    if n == 0:
        return []
    base, rest = divmod(total, n)
    return [base + (1 if i < rest else 0) for i in range(n)]


def expand(tpl: dict, grade: int, cap1: int, cap2: int, summative: bool) -> tuple[list[dict], list[str]]:
    """Şablonu dərs siyahısına açır: I yarımil – dəqiq cap1, II yarımil – dəqiq cap2 dərs (yuva çatırsa).
    Proqramlar qarışdırılmır: yalnız bu şablonun öz məzmunu (başqa proqramdan heç nə köçürülmür)."""
    rom = ROMAN.get(grade, str(grade))
    variants = tpl.get('variants', 'A–D')
    warnings: list[str] = []
    out: list[dict] = []
    ksq_no = 0

    def les(sem, section, topic, typ='formativ', assessment='', resources='', exam_no=None, standards=None):
        out.append({'semester': sem, 'section': section, 'topic': topic, 'standards': standards or [],
                    'integration': None, 'resources': resources or None, 'assessment': assessment or None,
                    'assessment_type': typ, 'exam_no': exam_no, 'tt_pages': None, 'tasks': []})

    for sem, cap in ((1, cap1), (2, cap2)):
        sections = tpl['semesters'][sem - 1]
        if not sections:                          # bölmə seçimində bu yarımildən heç nə qalmayıb
            continue
        topics = [(s, t) for s in sections for t in s['topics']]
        ksq_sections = [s for s in sections if not s['section'].startswith('Təkrar')]
        diag = sem == 1
        review = True
        ksq = summative
        final = 1                                                   # BSQ və ya (summativ yoxdursa) yekun təkrar
        def fixed():
            return int(diag) + (len(ksq_sections) if ksq else 0) + int(review) + final
        # yuva azdırsa: əvvəl diaqnostik, sonra təkrar, sonra KSQ-lar (bir yekun dərsi qalır)
        while cap - fixed() < len(topics) and (diag or review or ksq):
            if diag:
                diag = False
            elif review:
                review = False
            else:
                ksq = False
        free = cap - fixed()
        if free < len(topics):
            warnings.append(f'{sem}-ci yarımil: {cap} dərs yuvası {len(topics) + final} dərs üçün azdır – '
                            f'{len(topics) + final - max(cap, 0)} dərs sığmır')
            free = len(topics)
        if not ksq and summative and sections:
            warnings.append(f'{sem}-ci yarımil: yuva az olduğu üçün KSQ dərsləri plana salınmadı')
        per = _share(free, len(topics))
        if diag:
            prev = ROMAN.get(grade - 1)
            les(1, 'Diaqnostik qiymətləndirmə', f'{prev} sinif riyaziyyat kursunun təkrarı. Diaqnostik qiymətləndirmə' if prev
                else 'Diaqnostik qiymətləndirmə', 'diaqnostik', 'Diaqnostik qiymətləndirmə (məzmun standartlarının mənimsənilməsi)')
        k = 0
        for s in sections:
            for t in s['topics']:
                n = per[k]
                k += 1
                res = f'DİM «Riyaziyyat. Sinif testləri», {rom} sinif: «{t}» (variant {variants})'
                for j in range(n):
                    last = j == n - 1
                    if n == 1:
                        title = f'{t}. Sinif testi'
                    elif last:
                        title = f'{t} ({n}/{n}). Ümumiləşdirmə. Sinif testi'
                    elif j == 0:
                        title = f'{t} (1/{n}). Yeni material' if n > 2 else t
                    else:
                        title = f'{t} ({j + 1}/{n}). {STEPS[(j - 1) % len(STEPS)]}'
                    les(sem, s['section'], title, 'formativ',
                        f'Formativ: sinif testi, variant {variants} (10 tapşırıq)' if last else 'Formativ: şifahi sorğu, müşahidə, tapşırıq',
                        res if last else f'DİM «Riyaziyyat. Sinif testləri», {rom} sinif')
            if ksq and s in ksq_sections:
                ksq_no += 1
                les(sem, s['section'], f'KSQ-{ksq_no}: {s["section"].split(" ", 1)[-1]}', 'KSQ',
                    'Kiçik summativ qiymətləndirmə', exam_no=ksq_no)
        if review:
            what = 'İllik material üzrə yekunlaşdırıcı test tapşırıqları' if sem == 2 and tpl.get('annual_test') \
                else f'{"Birinci" if sem == 1 else "İkinci"} yarımil üzrə yekunlaşdırıcı test tapşırıqları'
            les(sem, 'Təkrar', f'Təkrar: {what}', 'formativ', f'Formativ: yekunlaşdırıcı test ({tpl.get("summative_variants", 8)} variant)',
                f'DİM «Riyaziyyat. Sinif testləri», {rom} sinif: {what}')
        if summative:
            les(sem, 'Böyük summativ qiymətləndirmə', f'BSQ-{sem}: {"I" if sem == 1 else "II"} yarımil materialı', 'BSQ',
                'Böyük summativ qiymətləndirmə', exam_no=sem)
        else:
            les(sem, 'Təkrar', f'{"I" if sem == 1 else "II"} yarımil materialının ümumiləşdirici təkrarı', 'formativ',
                'Formativ: yekun tapşırıqlar')
    for l in out:                                  # mövzunun qabağında sinif: «IX sinif: …» (başqa sinfin proqramı qoşulanda da aydın olsun)
        l['topic'] = f'{rom} sinif: {l["topic"]}'
    return out, warnings


def expand_course(tpl: dict, dates: list[dt.date], sem1_end: dt.date) -> tuple[list[dict], list[str]]:
    """Kurs (repetitor) şablonunu kursun yuvalarına açır: KSQ/BSQ/diaqnostik/yarımil yoxdur.
    Mövzular; hər `mock_every` mövzu dərsindən sonra aralıq sınaq; bölmə sonunda sınaq; sonda yekun sınaq (hamısı istəyə görə).
    Yuva azdırsa əvvəl aralıq sınaqlar, sonra bölmə sınaqları, sonra yekun sınaq çıxır, sonra mövzular 1 dərsə enir."""
    sections = [s for s in tpl['sections'] if s['topics']]
    n_topics = sum(len(s['topics']) for s in sections)
    cap = len(dates)
    every = int(tpl.get('mock_every') or 0)
    sec_mock = bool(tpl.get('mock_after_section')) and len(sections) > 1
    final = bool(tpl.get('final_mock'))
    warnings: list[str] = []

    def topic_room() -> int:
        """Mövzu dərsləri üçün ən çox yer (aralıq sınaqlar mövzu dərslərinin sayından asılıdır)."""
        room = cap - (len(sections) if sec_mock else 0) - int(final)
        if every:
            t = room
            while t > 0 and t + (t - 1) // every > room:
                t -= 1
            return t
        return room
    dropped = False
    while topic_room() < n_topics and (every or sec_mock or final):
        dropped = True
        if every:
            every = 0
        elif sec_mock:
            sec_mock = False
        else:
            final = False
    free = topic_room()
    if free < n_topics:
        warnings.append(f'Kursda {cap} dərs yuvası {n_topics} mövzu üçün azdır – {n_topics - max(cap, 0)} mövzu sığmır; '
                        'lazım olan bölmələri seçin və ya dərs sayını artırın')
        free = n_topics
    elif dropped:
        warnings.append('Yuva az olduğu üçün bəzi sınaq dərsləri plana salınmadı')
    per = _share(free, n_topics)
    res = tpl.get('resource')
    out: list[dict] = []

    def les(section, topic, assessment, resources=None):
        out.append({'semester': 0, 'section': section, 'topic': topic, 'standards': [], 'integration': None,
                    'resources': resources, 'assessment': assessment, 'assessment_type': 'formativ', 'exam_no': None,
                    'tt_pages': None, 'tasks': []})
    k = done = 0
    for s in sections:
        for t in s['topics']:
            n = per[k]
            k += 1
            for j in range(n):
                last = j == n - 1
                if n == 1:
                    title = f'{t}. Test'
                elif last:
                    title = f'{t} ({n}/{n}). Ümumiləşdirmə. Test'
                elif j == 0:
                    title = f'{t} (1/{n}). Yeni material' if n > 2 else t
                else:
                    title = f'{t} ({j + 1}/{n}). {STEPS[(j - 1) % len(STEPS)]}'
                les(s['section'], title, 'Formativ: test' if last else 'Formativ: şifahi sorğu, tapşırıq',
                    (f'{res}: «{t.split(": ", 1)[-1]}»' if last else res) if res else None)
                done += 1
                if every and done % every == 0 and done < free:
                    les(s['section'], f'Aralıq sınaq ({done // every})', 'Sınaq imtahanı (keçilən material üzrə)')
        if sec_mock:
            les(s['section'], f'Sınaq: {s["section"]}', 'Sınaq imtahanı (bölmə üzrə)')
    for i in range(cap - len(out) - int(final)):         # aralıq sınaqların bölgüsündən qalan yuva – ümumi təkrar
        les('Yekun', f'Ümumi təkrar ({i + 1})', 'Formativ: yekun tapşırıqlar')
    if final:
        les('Yekun', 'Yekun sınaq imtahanı', 'Sınaq imtahanı (bütün kurs üzrə)')
    for i, l in enumerate(out):                   # yarımil – dərsin düşdüyü tarixə görə
        l['semester'] = 1 if i < len(dates) and dates[i] <= sem1_end else 2
    return out, warnings


def section_names(program: PlanProgram) -> list[dict]:
    """Proqramın bölmələri (seçim üçün): ad, hissə (Cəbr/Həndəsə), mövzu və ya dərs sayı – ardıcıl, təkrarsız."""
    if program.kind == 'adaptive':
        return [{'name': s['section'], 'part': s.get('part'), 'count': len(s['topics'])} for s in tpl_sections(program.data['template'])]
    out: dict[str, dict] = {}
    for l in program.data.get('lessons', []):
        k = l.get('section') or 'Bölməsiz'
        out.setdefault(k, {'name': k, 'part': None, 'count': 0})['count'] += 1
    return list(out.values())


def check_sections(program: PlanProgram, sections: list[str] | None) -> list[str] | None:
    """Seçimi yoxlayır: None və ya hamısı – None; boş və ya naməlum bölmə – ValueError."""
    if sections is None:
        return None
    names = [s['name'] for s in section_names(program)]
    bad = [s for s in sections if s not in names]
    if bad:
        raise ValueError(f'Proqramda belə bölmə yoxdur: {bad[0]}')
    if not sections:
        raise ValueError('Ən azı bir bölmə seçin')
    return None if set(sections) == set(names) else [n for n in names if n in sections]


def lessons_for(db: Session, program: PlanProgram, ta: TeachingAssignment,
                sections: list[str] | None = None) -> tuple[list[dict], dict]:
    """Proqramın bu sinif/qrup üçün dərs siyahısı və hesabatı (önbaxış və tətbiq üçün).
    sections – proqramın yalnız seçilmiş bölmələri (eyni proqramın daxilində süzgəc; None – hamısı)."""
    from .models import AcademicYear
    cap = capacity(db, ta)
    cls = db.get(SchoolClass, ta.class_id)
    sem1_end = db.get(AcademicYear, cls.year_id).sem1_end
    grade = class_grade(db, cls) or program.grade
    keep = set(sections) if sections else None
    relabel = False
    if is_course(program):
        tpl = dict(program.data['template'])
        if keep:
            tpl['sections'] = [s for s in tpl['sections'] if s['section'] in keep]
        lessons, warnings = expand_course(tpl, [d for d, _ in cap['slots']], sem1_end)
    elif program.kind == 'adaptive':
        tpl = dict(program.data['template'])
        cap1, cap2 = cap['sem1'], cap['sem2']
        warnings = []
        if keep:
            tpl['semesters'] = [[s for s in sem if s['section'] in keep] for sem in tpl['semesters']]
            for i, other in ((0, 1), (1, 0)):
                if not tpl['semesters'][i] and tpl['semesters'][other]:
                    warnings.append(f'{"I" if i == 0 else "II"} yarımildən bölmə seçilməyib – onun dərs yuvaları '
                                    f'{"II" if i == 0 else "I"} yarımilin bölmələrinə verildi')
                    cap1, cap2 = (0, cap1 + cap2) if i == 0 else (cap1 + cap2, 0)
                    relabel = True
        les, w = expand(tpl, program.grade or grade, cap1, cap2, ta.has_summative)
        lessons, warnings = les, warnings + w
    else:
        lessons, warnings = [dict(l) for l in program.data.get('lessons', []) if not keep or (l.get('section') or 'Bölməsiz') in keep], []
        total = cap['sem1'] + cap['sem2']
        if len(lessons) > total:
            warnings.append(f'Proqramda {len(lessons)} dərs var, sinfin cədvəlində ildə {total} dərs yuvası – '
                            f'{len(lessons) - total} dərs sığmır')
        n1 = sum(1 for l in lessons if l.get('semester') == 1)
        if n1 > cap['sem1']:
            warnings.append(f'I yarımil dərsləri ({n1}) I yarımil yuvalarından ({cap["sem1"]}) çoxdur – bir hissəsi II yarımilə düşəcək')
    if relabel:                                   # bir yarımil boş qalıb – yarımil dərsin düşdüyü tarixə görə
        for i, l in enumerate(lessons):
            l['semester'] = 1 if i < len(cap['slots']) and cap['slots'][i][0] <= sem1_end else 2
    if program.grade and grade and program.grade != grade and not is_course(program):
        warnings.append(f'Proqram {ROMAN.get(program.grade, program.grade)} sinif üçündür, bu sinif – {ROMAN.get(grade, grade)}')
    from sqlalchemy import func
    n_written = db.scalar(select(func.count()).select_from(JournalEntry).where(
        JournalEntry.assignment_id == ta.id, JournalEntry.auto.is_(False))) or 0
    rep = {'lessons': len(lessons), 'sem1_slots': cap['sem1'], 'sem2_slots': cap['sem2'],
           'sem1_lessons': sum(1 for l in lessons if l['semester'] == 1),
           'sem2_lessons': sum(1 for l in lessons if l['semester'] == 2),
           'ksq': sum(l['assessment_type'] == 'KSQ' for l in lessons), 'bsq': sum(l['assessment_type'] == 'BSQ' for l in lessons),
           'written_lessons': n_written, 'warnings': warnings, 'sections': sections}
    return lessons, rep


def apply(db: Session, program: PlanProgram, ta: TeachingAssignment, user: User, sections: list[str] | None = None) -> dict:
    """Proqramı sinif/qrupa tətbiq edir. Əvvəlki plan kitabxanaya saxlanılır; jurnalda yazılmış dərslərin
    mövzusu dondurulur; dərslər sıra № ilə yenilənir (id-lər qorunur), «Tarix» – sinfin cədvəlinə görə."""
    from .services import plan_ctx, taught_lesson
    from .domain.plan import slot_at
    lessons, rep = lessons_for(db, program, ta, sections)
    prev = None
    cur = db.get(PlanProgram, ta.program_id) if ta.program_id else None
    cls = db.get(SchoolClass, ta.class_id)
    label = f'{cls.name} – {ta.subject}: əvvəlki plan ({dt.date.today():%d.%m.%Y})'
    if cur and cur.kind == 'fixed' and cur.data.get('lessons') == _lesson_dicts(db, ta.id):
        prev = cur                                       # cari plan kitabxanada artıq var – təkrar nüsxə yox
        if prev.title.endswith('(cari plan)'):
            prev.title = label
    elif _lesson_dicts(db, ta.id):
        prev = snapshot(db, ta, user, label)             # plan kitabxanada yoxdur (və ya dəyişib) – nüsxə saxlanılır
    # jurnalda yazılmış dərslərin mövzusu dondurulur (keçmiş dəyişməsin)
    ctx = plan_ctx(db, ta)
    frozen = 0
    for e in db.scalars(select(JournalEntry).where(JournalEntry.assignment_id == ta.id)):
        if not e.topic:
            pl = taught_lesson(ctx, slot_at(ctx.slots, e.date, e.period), e)
            if pl:
                e.topic = pl.topic
                frozen += 1
    cap = capacity(db, ta)
    dates = [d for d, _ in cap['slots']]
    existing = {pl.seq: pl for pl in db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id))}
    for i, l in enumerate(lessons, 1):
        vals = {k: l.get(k) for k in FIELDS}
        vals['date'] = dates[i - 1] if i - 1 < len(dates) else (dates[-1] if dates else dt.date.today())
        vals['tasks'] = vals['tasks'] or []
        pl = existing.get(i)
        if pl:
            for k, v in vals.items():
                setattr(pl, k, v)
        else:
            db.add(PlanLesson(assignment_id=ta.id, seq=i, **vals))
    removed = 0
    for s, pl in existing.items():
        if s > len(lessons):
            db.delete(pl)
            removed += 1
    ta.program_id = program.id
    ta.program_sections = sections
    db.flush()
    return {**rep, 'previous_program_id': prev.id if prev else None, 'frozen_topics': frozen, 'removed': removed,
            'applied_at': now()}


def dated(db: Session, program: PlanProgram, ta: TeachingAssignment, sections: list[str] | None = None) -> dict:
    """Əlavə proqramın dərs siyahısı bu sinfin cədvəlinə görə tarixlərlə – jurnala yazılmır (əsas proqramla qarışmır)."""
    lessons, rep = lessons_for(db, program, ta, sections)
    cap = capacity(db, ta)
    out = []
    for i, l in enumerate(lessons):
        d, p = cap['slots'][i] if i < len(cap['slots']) else (None, None)
        out.append({'seq': i + 1, 'date': d, 'period': p, 'semester': l['semester'], 'section': l.get('section'),
                    'topic': l['topic'], 'assessment_type': l['assessment_type'], 'resources': l.get('resources'),
                    'assessment': l.get('assessment'), 'standards': l.get('standards') or []})
    return {**rep, 'program': program.title, 'lessons_list': out}
