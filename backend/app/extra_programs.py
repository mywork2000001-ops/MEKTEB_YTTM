"""Məşğələ qruplarına proqram (docs/meshgele-proqram-ve-video-beledci-promtu.md §A).

- tip: inkisaf (Zəif; V–IX «Sinif testləri» proqramı) | tereqqi (Güclü; sinfin planı 1–2 həftə irəli və ya «Güclü» proqram) | diger;
- ardıcıllıq (inkişaf): giriş diaqnostikası → əvvəlki sinfin «Təkrar» bölmələri (varsa) → proqram mövzuları (sinfin planı ilə
  paralel tempdə) → çıxış testi; tərəqqi: giriş → mövzular → çıxış;
- doldurma idempotentdir: keçirilmiş və müəllimin əl ilə yazdığı mövzulara toxunulmur, hər proqram mövzusu `ref` daşıyır
  (ExtraSession.topic_ref və topics[i]['ref']); cədvəl dəyişəndə yalnız proqramdan gələn gələcək məşğələlər yenidən hesablanır;
- mövzu testinin seçimi YALNIZ plan_tests.py-dədir (r_extra_program / extra_choice) – burada seçim məntiqi təkrarlanmır.
Bu modul api/extra.py-yə bağlı deyil (skript də istifadə edir): extra.py yalnız çağırır."""
from __future__ import annotations

import datetime as dt
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import plan_tests as PT
from .bank.match import PENDING_GRADES, GradeMatcher, _norm, base_topic
from .models import ExtraCourse, ExtraSession, PlanProgram, SchoolClass, TeachingAssignment, User
from .programs import ROMAN, grade_variants, topic_sequence, tpl_sections
from .services import class_grade

KINDS = ('inkisaf', 'tereqqi', 'diger')
INK_GRADES = range(5, 10)                      # inkişaf proqramı: V–IX
LEAD_DAYS = 7                                  # tərəqqi: sinifdən ~1 həftə irəli
THIS_WEEK = 6                                  # inkişaf: «bu həftə keçiləcək» mövzu da prioritetlidir
_INK = re.compile(r'inki[sş]af|z[əe]if', re.I)
_TER = re.compile(r't[əe]r[əe]qqi|g[üu]cl[üu]', re.I)
LEAK = re.compile(r'z[əe]if|g[üu]cl[üu]|inki[sş]af|t[əe]r[əe]qqi', re.I)          # şagirdə görünməməli sözlər


def leaks(text: str | None) -> bool:
    return bool(text and LEAK.search(text))


def detect_kind(c: ExtraCourse) -> str:
    """Tip: audience.levels (yalnız Zəif / yalnız Güclü), sonra ad və məqsəddəki söz; qalanı – diger."""
    lv = set((c.audience or {}).get('levels') or [])
    if 'Zəif' in lv and 'Güclü' not in lv:
        return 'inkisaf'
    if 'Güclü' in lv and 'Zəif' not in lv:
        return 'tereqqi'
    text = f'{c.title or ""} {c.goal or ""}'
    ink, ter = bool(_INK.search(text)), bool(_TER.search(text))
    return 'inkisaf' if ink and not ter else 'tereqqi' if ter and not ink else 'diger'


def course_kind(c: ExtraCourse) -> str:
    return c.kind if c.kind in KINDS else detect_kind(c)


def remember_kind(c: ExtraCourse) -> None:
    """Üzv əlavə/çıxarma səviyyə süzgəcini sıfırlamazdan əvvəl tipi yadda saxlayır (audit bug №1)."""
    if not c.kind:
        k = detect_kind(c)
        if k != 'diger':
            c.kind = k


def course_tas(db: Session, c: ExtraCourse) -> list[tuple[int, TeachingAssignment]]:
    """Kursun dərs bağlılıqları (sinif, ta) – sinfə görə artan."""
    out = []
    for i in (c.audience or {}).get('ta_ids') or []:
        ta = db.get(TeachingAssignment, i)
        if ta and not ta.archived_at:
            out.append((class_grade(db, db.get(SchoolClass, ta.class_id)) or 99, ta))
    return sorted(out, key=lambda x: x[0])


def _w(key: str, **params) -> dict:
    return {'key': key, 'params': params}


def variants_for(kind: str, grade: int) -> str:
    """İnkişaf – A+B, tərəqqi – B+C (sinfin variantlarına görə; olmayan hərf düşür)."""
    last = (grade_variants(grade) or 'A–D')[-1]
    got = [x for x in ('AB' if kind == 'inkisaf' else 'BC') if x <= last] or [last]
    return '+'.join(got)


def _program(db: Session, c: ExtraCourse, kind: str, grade: int, rep: dict) -> tuple[PlanProgram | None, str | None]:
    """(proqram, rejim): 'program' – proqramın mövzuları; 'plan' – sinfin perspektiv planı (tərəqqi, «Güclü» proqram yoxdursa)."""
    if c.program_id:
        p = db.get(PlanProgram, c.program_id)
        if p and not p.archived_at:
            return p, 'program'
    if kind == 'inkisaf':
        if grade not in INK_GRADES:
            rep['warnings'].append(_w('İnkişaf proqramı yalnız V–IX siniflər üçündür'))
            return None, None
        p = db.scalar(select(PlanProgram).where(PlanProgram.key == f'dim-sinif-testleri-{grade}'))
        if p is None:
            rep['warnings'].append(_w('{grade} sinif üçün «Sinif testləri» proqramı tapılmadı', grade=ROMAN.get(grade, grade)))
        return p, 'program' if p else None
    p = db.scalar(select(PlanProgram).where(PlanProgram.level == 'Güclü', PlanProgram.grade == grade, PlanProgram.archived_at.is_(None),
                                            PlanProgram.subject == c.subject,
                                            (PlanProgram.school_id.is_(None)) | (PlanProgram.school_id == c.school_id))
                  .order_by(PlanProgram.id))
    return (p, 'program') if p else (None, 'plan')


def _entry(ref, text, topic=None, section=None, no=None, pl_id=None, cdate=None, grade=None) -> dict:
    return {'ref': ref, 'text': text, 'topic': topic, 'section': section, 'no': no, 'plan_lesson_id': pl_id, 'cdate': cdate,
            'grade': grade}


def _class_dates(db: Session, ta: TeachingAssignment) -> tuple[dict, dict, list]:
    """Sinfin əsas planı: mövzu nömrəsi → tarix, ad → tarix, mövzu siyahısı (plan_tests.plan_items – tək mühərrik)."""
    by_no, by_name, items = {}, {}, []
    try:
        for it in PT.plan_items(db, ta, None, None):
            if it.kind == 'topic' and it.date is not None:
                items.append(it)
                if it.no:
                    by_no.setdefault(it.no, it.date)
                by_name.setdefault(_norm(base_topic(it.pl.topic)).strip(), it.date)
    except Exception:                                  # planı olmayan sinif – tempo qaydası işləmir, ardıcıl gedir
        pass
    return by_no, by_name, items


def _sequence(db: Session, c: ExtraCourse, kind: str, grade: int, ta0: TeachingAssignment, program: PlanProgram | None,
              mode: str) -> tuple[list[dict], list[dict]]:
    """(əvvəlki sinfin təkrar mövzuları, əsas mövzular) – entry sözlükləri."""
    pre, main = [], []
    if mode == 'program' and program is not None:
        short = (program.data or {}).get('source_short')
        suffix = f' [{short} {ROMAN.get(program.grade, program.grade)}]' if short and program.grade else ''
        by_no, by_name, _ = _class_dates(db, ta0)
        for i, e in enumerate(topic_sequence(program, c.program_sections)):
            no = e['no']
            cdate = by_no.get(no) or by_name.get(_norm(base_topic(e['topic'])).strip())
            main.append(_entry(f'{no}' if no else f'p{program.id}:{i + 1}', f'{no} {e["topic"]}{suffix}' if no else f'{e["topic"]}{suffix}',
                               e['topic'], e['section'], no, None, cdate, program.grade or grade))
        if kind == 'inkisaf' and grade - 1 in INK_GRADES:
            prev = db.scalar(select(PlanProgram).where(PlanProgram.key == f'dim-sinif-testleri-{grade - 1}'))
            if prev is not None:
                rev = [s['section'] for s in tpl_sections(prev.data['template']) if s['section'].startswith('Təkrar')]
                for i, e in enumerate(topic_sequence(prev, rev)[:3]):
                    pre.append(_entry(f'pre:{grade - 1}:{i + 1}', f'{e["topic"]} [{ROMAN[grade - 1]} sinif – təkrar]', e['topic'],
                                      e['section'], None, None, None, grade - 1))
    else:
        _, _, items = _class_dates(db, ta0)
        for it in items:
            tp = base_topic(it.pl.topic) or it.pl.topic
            main.append(_entry(f'plan:{it.no or it.pl.seq}', f'{it.no} {tp}' if it.no else tp, tp, it.pl.section, it.no, it.pl.id,
                               it.date, grade))
    return pre, main


def plan_fill(db: Session, c: ExtraCourse, today: dt.date, gm: GradeMatcher | None = None, overwrite: bool = False,
              dry: bool = False, chain: dict | None = None, auto_default: bool = False) -> dict:
    """Qrupun gələcək planlaşdırılmış məşğələlərini proqramdan doldurur (dry=True – heç nə yazmır, hesabat). Təkrar çağırış eyni nəticə verir.
    Rejim `chain` (extra_chain.py): chain verilibsə və ya qrupda saxlanmış aktiv konfiqurasiya varsa; auto_default=True – öz proqramı olmayan
    inkişaf qrupu defolt zəncirlə (gündəlik tapşırıq)."""
    from . import extra_chain as XC
    if chain is None:
        saved = XC.get_cfg(c)
        if saved is not None and saved.get('enabled', True):
            chain = saved
        elif auto_default and XC.default_eligible(db, c):
            chain = XC.DEFAULT
    if chain is not None:
        return XC.run(db, c, today, chain, gm, overwrite, dry)
    kind = course_kind(c)
    rep: dict = {'course_id': c.id, 'title': c.title, 'kind': kind, 'kind_auto': c.kind not in KINDS, 'grade': None, 'program': None,
                 'mode': None, 'sessions': 0, 'held': 0, 'to_fill': 0, 'kept_manual': 0, 'topics': 0, 'topics_left': 0,
                 'rows': [], 'warnings': [], 'applicable': False, 'tests': {'ok': 0, 'pending': 0, 'none': 0}, 'skip': None}
    if kind == 'diger':
        rep['skip'] = 'Qrupun tipi tanınmadı – tipi seçin (inkişaf / tərəqqi)'
        return rep
    tas = course_tas(db, c)
    if not tas:
        rep['skip'] = 'Qrupun aktiv sinfi yoxdur'
        return rep
    grade, ta0 = tas[0]
    if len({g for g, _ in tas}) > 1:
        rep['warnings'].append(_w('Qrup bir neçə sinifdəndir – ən kiçik sinif ({grade}) götürüldü', grade=ROMAN.get(grade, grade)))
    if grade == 99:
        rep['skip'] = 'Sinfin nömrəsi bilinmir'
        return rep
    rep['grade'] = grade
    program, mode = _program(db, c, kind, grade, rep)
    if mode is None:
        rep['skip'] = 'Uyğun proqram tapılmadı'
        return rep
    pre, main = _sequence(db, c, kind, grade, ta0, program, mode)
    if mode == 'plan' and not main:
        rep['skip'] = 'Sinfin perspektiv planı boşdur'
        return rep
    rep['applicable'] = True
    rep['program'] = {'id': program.id, 'key': program.key, 'title': program.title} if program else {'id': None, 'key': None, 'title': None}
    rep['mode'] = mode
    sess = sorted((s for s in db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id)) if s.status != 'cancelled'),
                  key=lambda s: (s.date, s.start))
    auto = lambda s: bool(s.topics) and all(t.get('ref') for t in s.topics)                                     # noqa: E731
    R = [s for s in sess if s.status == 'planned' and s.date >= today and (not s.topics or auto(s) or overwrite)]
    rid = {s.id for s in R}
    used = {t['ref'] for s in sess if s.id not in rid for t in s.topics or [] if t.get('ref')}
    rep.update(sessions=len(sess), held=sum(s.status == 'held' for s in sess),
               kept_manual=sum(1 for s in sess if s.status == 'planned' and s.date >= today and s.id not in rid))
    v = variants_for(kind, grade)
    slots = list(R)
    place: list[tuple[ExtraSession, dict]] = []
    if sess and sess[0].id in rid and 'diag-in' not in used:
        place.append((sess[0], _entry('diag-in', 'Giriş diaqnostikası' + (' (öz sinfi və əvvəlki sinif mövzuları)' if kind == 'inkisaf' else ''))))
        slots.remove(sess[0])
    if len(sess) > 1 and sess[-1].id in rid and 'diag-out' not in used and sess[-1] in slots:
        place.append((sess[-1], _entry('diag-out', 'Çıxış testi')))
        slots.remove(sess[-1])
    left = [e for e in main if e['ref'] not in used]
    heads = [e for e in pre if e['ref'] not in used]
    rep['topics'] = len(main)
    for s in slots:
        if heads:
            place.append((s, heads.pop(0)))
        elif not left:
            break
        elif mode == 'plan':
            nxt = next((e for e in left if e['cdate'] and e['cdate'] >= s.date + dt.timedelta(days=LEAD_DAYS)), None)
            if nxt is None:
                continue
            left.remove(nxt)
            place.append((s, nxt))
        else:                                          # proqram: sinfdə keçilmiş / bu həftə keçiləcək mövzu prioritetlidir
            horizon = s.date + dt.timedelta(days=THIS_WEEK)
            nxt = next((e for e in left if kind == 'inkisaf' and e['cdate'] and e['cdate'] <= horizon), left[0])
            left.remove(nxt)
            place.append((s, nxt))
    place.sort(key=lambda x: (x[0].date, x[0].start))
    rep['to_fill'], rep['topics_left'] = len(place), len(left)
    if left:
        rep['warnings'].append(_w('Proqramda {n} mövzu üçün məşğələ çatmır (qrupun tarixlərini uzadın)', n=len(left)))
    if grade in PENDING_GRADES and kind == 'inkisaf':
        rep['warnings'].append(_w('{grade} sinif üçün test sualları hələ hazırlanır – mövzular yazılır, testlər «gözlənilir»',
                                  grade=ROMAN.get(grade, grade)))
    explicit = ta0.bank_source if ta0.bank_source and ta0.bank_source != 'none' else None
    gm = GradeMatcher(db, explicit) if explicit or gm is None else gm              # ortaq gm yalnız açıq mənbə ayarı olmayanda
    ctx = PT.TaCtx(db, ta0, gm)
    opts = PT.Opts(variants=v)
    for s, e in place:
        test = None
        if e['topic']:
            ch = PT.extra_choice(db, ta0, e['grade'] or grade, e['topic'], e['section'], e['no'], opts, ctx)
            st = 'ok' if ch.status in ('ok', 'manual') and ch.count else ch.status if ch.status in ('pending', 'weak') else 'none'
            test = {'status': st, 'file': ch.file.label if ch.file else None, 'questions': ch.count, 'source': ch.source}
            rep['tests']['ok' if st in ('ok', 'weak') else st] += 1
        rep['rows'].append({'session_id': s.id, 'date': s.date.isoformat(), 'ref': e['ref'], 'text': e['text'], 'variants': v if e['topic'] else None,
                            'test': test})
        e['_test'] = test
    if not dry:
        for s, e in place:
            s.topics = [{'plan_lesson_id': e['plan_lesson_id'], 'text': e['text'], 'ref': e['ref'], 'variants': v if e['topic'] else None,
                         'test': e.get('_test')}]
            s.topic_ref = e['ref']
        placed = {s.id for s, _ in place}
        for s in R:
            if s.id not in placed and auto(s):
                s.topics, s.topic_ref = None, None
        c.kind = c.kind or kind
        c.program_id = program.id if program is not None else None
    return rep


def fill_from_program(db: Session, c: ExtraCourse, today: dt.date, gm: GradeMatcher | None = None, overwrite: bool = False) -> dict:
    """Spesifikasiya adı: doldur (overwrite=False – keçirilmiş və əl ilə yazılmış mövzulara toxunmur)."""
    return plan_fill(db, c, today, gm, overwrite, dry=False)


def detach(db: Session, c: ExtraCourse, today: dt.date) -> int:
    """Proqramı ayır: gələcək planlaşdırılmış məşğələlərdəki proqram mövzuları silinir (əl ilə yazılanlar qalır)."""
    n = 0
    for s in db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id)):
        if s.status == 'planned' and s.date >= today and s.topics and all(t.get('ref') for t in s.topics):
            s.topics, s.topic_ref = None, None
            n += 1
    c.program_id, c.program_sections = None, None
    from . import extra_chain as XC
    XC.disable(c)                                  # müəllim proqramı ayırdı – gündəlik tapşırıq zənciri özü geri qaytarmasın
    return n


def has_program(db: Session, c: ExtraCourse) -> bool:
    chain = (c.audience or {}).get('chain')
    return bool(c.program_id) or bool(chain and chain.get('enabled', True)) or db.scalar(select(ExtraSession.id).where(ExtraSession.course_id == c.id,
                                                                         ExtraSession.topic_ref.is_not(None)).limit(1)) is not None


def assign_programs(db: Session, courses: list[ExtraCourse], today: dt.date, apply: bool = False) -> list[dict]:
    """Kütləvi təyinat (önbaxış apply=False – heç nə yazmır): hər qrup üçün tip, sinif, proqram, doldurulacaq məşğələ sayı, xəbərdarlıqlar."""
    gm = GradeMatcher(db)
    out = []
    for c in courses:
        r = plan_fill(db, c, today, gm, overwrite=False, dry=not apply, auto_default=True)
        r['owner'] = (db.get(User, c.owner_id).full_name if c.owner_id else None)
        r.pop('rows', None)
        out.append(r)
    return out
