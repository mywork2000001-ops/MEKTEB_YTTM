"""İnkişaf qrupu – ardıcıl proqram (rejim `chain`; docs/inkisaf-qrupu-ardicil-proqram-promtu.md §2, §5, §6).

Xətti zəncir: «Sinif testləri» (app/program_data/sinif_testleri.json) V → IX; hər məşğələyə bir mövzu, sinfin temposuna bağlı deyil.
Başlanğıc: {grade, semester}; hər sinfin sonunda illik test; «Təkrar» bölməsi çıxır; məşğələ yalnız end_date-dək.
Konfiqurasiya miqrasiyasız – `ExtraCourse.audience['chain']`. Mövzu testinin seçimi YALNIZ plan_tests.py-dədir (extra_choice).
Alt mövzular: V sinif mövzularına «Alt mövzular: …» + P001 dərsinə keçid; VI–VII mövzularına «5-ci sinifdən təkrar: …»
(app/program_data/inkisaf_v_prereq.json – uyğunluq yoxdursa boş).
Doldurma idempotentdir: keçirilmiş və əl ilə yazılmış mövzulara toxunulmur; cədvəl fərqlidirsə yalnız GƏLƏCƏK boş/avtomatik məşğələlər yenidən qurulur."""
from __future__ import annotations

import datetime as dt
import json
import re
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import plan_tests as PT
from .bank.match import GradeMatcher
from .extra_programs import _w, course_kind, course_tas, variants_for
from .models import ExtraCourse, ExtraSession, Holiday, PlanProgram
from .programs import ROMAN

DATA = Path(__file__).parent / 'program_data'
DEFAULT = {'enabled': True, 'grades': [5, 9], 'start': {'grade': 5, 'semester': 2}, 'end_date': '2027-01-26', 'weekdays': [2, 3, 4],
           'start_time': '21:00', 'end_time': '22:00', 'skip_repeat': True, 'annual': True, 'p001': True}
_SEC_NUM = re.compile(r'^\s*(\d+)\.')
_RE_TIME = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


@lru_cache(maxsize=1)
def _tests() -> dict:
    return json.loads((DATA / 'sinif_testleri.json').read_text(encoding='utf-8'))['grades']


@lru_cache(maxsize=1)
def _aux() -> dict:
    return json.loads((DATA / 'inkisaf_v_prereq.json').read_text(encoding='utf-8'))


# ---------------------------------------------------------------- konfiqurasiya
def get_cfg(c: ExtraCourse) -> dict | None:
    """Qrupun saxlanmış zəncir konfiqurasiyası (None – yoxdur; enabled=False – müəllim zənciri söndürüb)."""
    v = (c.audience or {}).get('chain')
    return v if isinstance(v, dict) else None


def normalize(raw: dict | None) -> dict:
    """Konfiqurasiya yoxlanır və DEFAULT ilə tamamlanır (yanlış dəyər 400-ə uyğun ValueError)."""
    cfg = {**DEFAULT, **{k: v for k, v in (raw or {}).items() if v is not None}}
    g0, g1 = (int(x) for x in cfg['grades'])
    if not (5 <= g0 <= g1 <= 11):
        raise ValueError('Siniflər 5–11 aralığında olmalıdır')
    st = {**DEFAULT['start'], **(cfg.get('start') or {})}
    st = {'grade': int(st['grade']), 'semester': int(st['semester'])}
    if not (g0 <= st['grade'] <= g1) or st['semester'] not in (1, 2):
        raise ValueError('Başlanğıc sinif zəncirin içində, yarımil 1 və ya 2 olmalıdır')
    wd = sorted({int(x) for x in cfg['weekdays']})
    if not wd or any(not 0 <= x <= 6 for x in wd):
        raise ValueError('Həftə günləri 0–6 olmalıdır')
    if not (_RE_TIME.match(cfg['start_time']) and _RE_TIME.match(cfg['end_time']) and cfg['start_time'] < cfg['end_time']):
        raise ValueError('Saat HH:MM, başlanğıc bitmədən əvvəl olmalıdır')
    end = cfg['end_date']
    end = end.isoformat() if isinstance(end, dt.date) else str(end)
    dt.date.fromisoformat(end)
    return {'enabled': bool(cfg.get('enabled', True)), 'grades': [g0, g1], 'start': st, 'end_date': end, 'weekdays': wd,
            'start_time': cfg['start_time'], 'end_time': cfg['end_time'], 'skip_repeat': bool(cfg['skip_repeat']),
            'annual': bool(cfg['annual']), 'p001': bool(cfg['p001'])}


def default_eligible(db: Session, c: ExtraCourse) -> bool:
    """İnkişaf qrupu, öz (əl ilə seçilmiş) proqramı yoxdur və zəncir söndürülməyib → defolt zəncir."""
    if course_kind(c) != 'inkisaf':
        return False
    cfg = get_cfg(c)
    if cfg is not None:
        return False                                        # ya artıq zəncirdir, ya da müəllim söndürüb
    if c.program_id:
        p = db.get(PlanProgram, c.program_id)
        own = p is not None and not p.archived_at and not ((p.key or '').startswith('dim-sinif-testleri-') and not c.program_sections)
        return not own                                      # köhnə avtomatik təyinat «öz proqram» sayılmır
    return True


def disable(c: ExtraCourse) -> None:
    c.audience = {**(c.audience or {}), 'chain': {'enabled': False}}


def follow_schedule(c: ExtraCourse) -> None:
    """Müəllim cədvəli əl ilə dəyişəndə zəncirin gün/saatı onu izləyir (əks halda zəncir cədvəli geri qaytarardı)."""
    cfg = get_cfg(c)
    if not cfg or not cfg.get('enabled', True) or not c.schedule:
        return
    s0 = c.schedule[0]
    c.audience = {**c.audience, 'chain': {**cfg, 'weekdays': sorted({int(s['weekday']) for s in c.schedule}),
                                          'start_time': s0['start'], 'end_time': s0['end']}}


# ---------------------------------------------------------------- zəncirin mövzuları
def _lessons(ids: list[int]) -> dict | None:
    L = _aux()['lessons']
    got = [L[str(i)] for i in ids if str(i) in L]
    if not got:
        return None
    return {k: '; '.join(x[k] for x in got) for k in ('az', 'ru', 'en')}


def _links(ids: list[int]) -> list[dict]:
    a = _aux()
    return [{'lesson': i, 'title': a['lessons'][str(i)], 'url': f'{a["base_url"]}Lesson-{i}.html'} for i in ids if str(i) in a['lessons']]


def build_entries(cfg: dict) -> list[dict]:
    """Zəncirin tam ardıcıllığı: [{ref, text, topic, section, no, grade, kind, sub, prereq, links}]."""
    aux, G = _aux(), _tests()
    g0, g1 = cfg['grades']
    out: list[dict] = []
    for g in range(g0, g1 + 1):
        gd = G.get(str(g))
        if not gd:
            continue
        sem0 = cfg['start']['semester'] if g == cfg['start']['grade'] else 1
        if g < cfg['start']['grade']:
            continue
        rom = ROMAN.get(g, g)
        si = 0
        for sem, secs in enumerate(gd['semesters'], 1):
            for sec in secs:
                si += 1
                if sem < sem0 or (cfg['skip_repeat'] and sec['section'].startswith('Təkrar')):
                    continue
                m = _SEC_NUM.match(sec['section'])
                for ti, topic in enumerate(sec['topics'], 1):
                    name = sec['section'] if topic.strip() == re.sub(r'^\s*[\d.]+\s*', '', sec['section']).strip() else f'{sec["section"]} – {topic}'
                    sub = prereq = None
                    ids: list[int] = []
                    if cfg['p001'] and g == 5:
                        ids = aux['v_topics'].get(topic, [])
                        sub = _lessons(ids)
                    elif cfg['p001'] and g in (6, 7):
                        pids = aux['prereq'].get(str(g), {}).get(topic, [])
                        prereq = _lessons(pids)
                        ids = pids
                    text = f'{rom} sinif · {name}'
                    if sub:
                        text += f' · Alt mövzular: {sub["az"]}'
                    if prereq:
                        text += f' · 5-ci sinifdən təkrar: {prereq["az"]}'
                    out.append({'ref': f'ch:{g}:{si}.{ti}', 'text': text, 'topic': topic, 'section': sec['section'],
                                'no': f'{int(m.group(1))}.{ti}' if m else None, 'grade': g, 'sub': sub, 'prereq': prereq,
                                'links': _links(ids)})
        if cfg['annual'] and gd.get('annual_test'):
            ids = aux['v_annual'] if g == 5 and cfg['p001'] else []
            out.append({'ref': f'ch:{g}:annual', 'text': f'{rom} sinif illik test', 'topic': None, 'section': None, 'no': None,
                        'grade': g, 'sub': None, 'prereq': None, 'links': _links(ids)})
    return out


# ---------------------------------------------------------------- tarixlər və məşğələlər
def _holidays(db: Session, c: ExtraCourse) -> set[dt.date]:
    from .api.common import current_year
    try:
        return {h.date for h in db.scalars(select(Holiday).where(Holiday.year_id == current_year(db, c.school_id).id))}
    except Exception:                                       # tədris ili yoxdur – bayram siyahısı boşdur
        return set()


def _fillable(s: ExtraSession, today: dt.date, overwrite: bool) -> bool:
    auto = bool(s.topics) and all(t.get('ref') for t in s.topics)
    return s.status == 'planned' and s.date >= today and not s.batch_id and (not s.topics or auto or overwrite)


def _wanted_schedule(c: ExtraCourse, cfg: dict) -> list[dict]:
    first = (c.schedule or [{}])[0]
    return [{'weekday': w, 'start': cfg['start_time'], 'end': cfg['end_time'], 'room': first.get('room'), 'link': first.get('link')}
            for w in cfg['weekdays']]


def _same_schedule(c: ExtraCourse, cfg: dict) -> bool:
    have = {(int(s['weekday']), s['start'], s['end']) for s in c.schedule or []}
    return have == {(w, cfg['start_time'], cfg['end_time']) for w in cfg['weekdays']}


def _sync_sessions(db: Session, c: ExtraCourse, cfg: dict, today: dt.date, overwrite: bool) -> None:
    """Cədvəli və bitmə tarixini zəncirə uyğunlaşdırır: gələcək boş/avtomatik məşğələlər silinib yenidən qurulur."""
    from .api.extra import generate
    end = dt.date.fromisoformat(cfg['end_date'])
    if not _same_schedule(c, cfg):
        for s in list(db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id))):
            if _fillable(s, today, overwrite):
                db.delete(s)
        c.schedule = _wanted_schedule(c, cfg)
        db.flush()
    if c.ends_on < end:
        c.ends_on = end
    generate(db, c, today)
    db.flush()


def _virtual_slots(db: Session, c: ExtraCourse, cfg: dict, today: dt.date, sess: list[ExtraSession], overwrite: bool) -> list:
    """Önbaxış (dry): cədvəl fərqlidirsə DB-yə yazmadan yeni məşğələ yuvalarını hesablayır."""
    off, end = _holidays(db, c), dt.date.fromisoformat(cfg['end_date'])
    kept = {(s.date, s.start) for s in sess if not _fillable(s, today, overwrite)}
    out, d = [], today
    while d <= end:
        if d.weekday() in cfg['weekdays'] and d not in off and (d, cfg['start_time']) not in kept:
            out.append(SimpleNamespace(id=None, date=d, start=cfg['start_time'], end=cfg['end_time'], status='planned', topics=None,
                                       batch_id=None, topic_ref=None))
        d += dt.timedelta(days=1)
    return out


def _legacy_used(db: Session, c: ExtraCourse, g0: int, sess: list[ExtraSession]) -> set[str]:
    """Köhnə rejimdə (5.2 kimi ref) keçirilmiş V sinif mövzuları – zəncir onları təkrar qoymur."""
    if not c.program_id:
        return set()
    p = db.get(PlanProgram, c.program_id)
    if p is None or p.grade != g0:
        return set()
    return {s.topic_ref for s in sess if s.status == 'held' and s.topic_ref and not s.topic_ref.startswith('ch:')}


def run(db: Session, c: ExtraCourse, today: dt.date, cfg_in: dict | None = None, gm: GradeMatcher | None = None,
        overwrite: bool = False, dry: bool = False, rep: dict | None = None) -> dict:
    """Zəncir üzrə doldurma / önbaxış. Hesabat plan_fill ilə eyni açarları + `chain` bölməsi qaytarır."""
    cfg = normalize(cfg_in if cfg_in is not None else get_cfg(c))
    rep = rep if rep is not None else {'course_id': c.id, 'title': c.title, 'kind': 'inkisaf', 'warnings': [], 'skip': None}
    rep.update(kind='inkisaf', mode='chain', rows=[], warnings=rep.get('warnings', []), applicable=False, sessions=0, held=0, to_fill=0,
               kept_manual=0, topics=0, topics_left=0, program=None, tests={'ok': 0, 'pending': 0, 'none': 0}, skip=None)
    tas = course_tas(db, c)
    if not tas:
        rep['skip'] = 'Qrupun aktiv sinfi yoxdur'
        return rep
    grade0, ta0 = tas[0]
    rep['grade'] = grade0
    entries = build_entries(cfg)
    if not entries:
        rep['skip'] = 'Zəncir boşdur'
        return rep
    rep['applicable'] = True
    rep['topics'] = len(entries)
    end = dt.date.fromisoformat(cfg['end_date'])
    sync = not _same_schedule(c, cfg) or c.ends_on < end
    if sync and not dry:
        _sync_sessions(db, c, cfg, today, overwrite)
    sess = sorted((s for s in db.scalars(select(ExtraSession).where(ExtraSession.course_id == c.id)) if s.status != 'cancelled'),
                  key=lambda s: (s.date, s.start))
    fillable = [s for s in sess if _fillable(s, today, overwrite)]
    if sync and dry:
        fillable = _virtual_slots(db, c, cfg, today, sess, overwrite)
    fid = {id(s) for s in fillable}
    used = {t['ref'] for s in sess if id(s) not in fid for t in s.topics or [] if t.get('ref')}
    used |= {s.topic_ref for s in sess if id(s) not in fid and s.topic_ref}
    legacy = _legacy_used(db, c, cfg['grades'][0], sess)
    rep.update(sessions=len(sess), held=sum(s.status == 'held' for s in sess),
               kept_manual=sum(1 for s in sess if s.status == 'planned' and s.date >= today and id(s) not in fid))
    slots = [s for s in fillable if s.date <= end]
    left = [e for e in entries if e['ref'] not in used and not (e['grade'] == cfg['grades'][0] and e['no'] in legacy)]
    place = list(zip(slots, left))
    over = left[len(place):]
    rep['to_fill'], rep['topics_left'] = len(place), len(over)
    if over:
        rep['warnings'].append(_w('Zəncirdə {n} mövzu üçün {date} tarixinədək məşğələ çatmır – növbəti dövrə qalır', n=len(over),
                                  date=end.strftime('%d.%m.%Y')))
    explicit = ta0.bank_source if ta0.bank_source and ta0.bank_source != 'none' else None
    gm = GradeMatcher(db, explicit) if explicit or gm is None else gm
    ctx = PT.TaCtx(db, ta0, gm)
    by_grade: dict[int, int] = {}
    for s, e in place:
        by_grade[e['grade']] = by_grade.get(e['grade'], 0) + 1
        test = None
        if e['topic']:
            v = variants_for('inkisaf', e['grade'])
            ch = PT.extra_choice(db, ta0, e['grade'], e['topic'], e['section'], e['no'], PT.Opts(variants=v), ctx)
            st = 'ok' if ch.status in ('ok', 'manual') and ch.count else ch.status if ch.status in ('pending', 'weak') else 'none'
            test = {'status': st, 'file': ch.file.label if ch.file else None, 'questions': ch.count, 'source': ch.source}
            rep['tests']['ok' if st in ('ok', 'weak') else st] += 1
        e['_test'] = test
        rep['rows'].append({'session_id': s.id, 'date': s.date.isoformat(), 'start': s.start, 'end': s.end, 'ref': e['ref'], 'text': e['text'],
                            'grade': e['grade'], 'sub': e['sub'], 'prereq': e['prereq'], 'links': e['links'],
                            'variants': variants_for('inkisaf', e['grade']) if e['topic'] else None, 'test': test})
    rep['chain'] = {'config': cfg, 'sessions': len(place), 'first': rep['rows'][0]['date'] if place else None,
                    'last': rep['rows'][-1]['date'] if place else None,
                    'by_grade': [{'grade': g, 'n': n} for g, n in sorted(by_grade.items())],
                    'overflow': len(over), 'overflow_by_grade': _count([e['grade'] for e in over]),
                    'schedule_changed': sync, 'total_topics': len(entries)}
    if not dry:
        for s, e in place:
            s.topics = [{'plan_lesson_id': None, 'text': e['text'], 'ref': e['ref'], 'variants': variants_for('inkisaf', e['grade']) if e['topic'] else None,
                         'test': e.get('_test'), 'sub': e['sub'], 'prereq': e['prereq'], 'links': e['links']}]
            s.topic_ref = e['ref']
            if e['links'] and (not s.resources or s.resources.startswith('P001: ')):
                s.resources = 'P001: ' + '; '.join(f'{x["title"]["az"]} – {x["url"]}' for x in e['links'])
        placed = {id(s) for s, _ in place}
        for s in fillable:
            if id(s) not in placed and (not s.topics or all(t.get('ref') for t in s.topics)):
                s.topics, s.topic_ref = None, None
                if s.resources and s.resources.startswith('P001: '):
                    s.resources = None
        c.kind = c.kind or 'inkisaf'
        c.program_id = None
        c.audience = {**(c.audience or {}), 'chain': cfg}
    return rep


def _count(grades: list[int]) -> list[dict]:
    out: dict[int, int] = {}
    for g in grades:
        out[g] = out.get(g, 0) + 1
    return [{'grade': g, 'n': n} for g, n in sorted(out.items())]
