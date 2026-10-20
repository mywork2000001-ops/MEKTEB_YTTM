"""Plan mövzusu → P0010 (viktorina-da «p003») test faylları: mövzu adına görə uyğunluq (docs/x-xi-p0010-testleri-promtu.md).

Söz kökü – normallaşdırılmış sözün ilk 5 hərfi; çox faylda təkrarlanan sözlərin çəkisi azdır (idf). Mövzu sözləri əsas,
bölmə adı əlavə çəki ilə."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import BankFile, BankSource

SOURCE = 'p003'
# sinif -> sıralı mənbə siyahısı (docs/sinfe-gore-testler-promtu.md §2.2): p001 – V, p011 – VI, p007 – DİM 9 toplusu, p003 – P0010 (V–XI),
# p013 – DİM «Sinif testləri» (V–XI). Bankda olmayan mənbə sadəcə boş keçilir. Konfiq yalnız burada.
SOURCE_ORDER = {5: ['p013', 'p001', 'p003'], 6: ['p013', 'p011', 'p003'], 7: ['p013', 'p003'], 8: ['p013', 'p003'],
                9: ['p007', 'p013', 'p003'], 10: ['p003', 'p013'], 11: ['p003', 'p013']}
GRADE_SOURCE = {9: 'p007', 10: 'p003', 11: 'p003'}     # kağız sınaqlar (KSQ/BSQ) üçün əsas mənbə: IX – DİM 9 test toplusu (P007), X–XI – P0010
MIN_COVER = 0.5                                         # mövzu köklərinin bu hissəsindən azı faylda yoxdursa – növbəti mənbəyə keçilir
# uyğunluq həddi (docs/mekteb-plan-movzu-testleri-promtu.md §2.2): örtük ≥ OK_COVER – ok; WEAK_COVER ≤ örtük < OK_COVER – şübhəli ⚠
# (qoşulur); aşağı – qoşulmur. Eyni mövzu nömrəsi olan fayl üçün ok həddi WEAK_COVER-dir; hədlər real bank adları ilə kalibrlənir.
OK_COVER = MIN_COVER
WEAK_COVER = 0.25
NO_BONUS = 1.5                                          # faylın nömrəsi dərsin mövzu nömrəsinə bərabərdirsə – bal bu qədər artır
PENDING_GRADES = {5, 6, 7, 8}                           # «Sinif testləri» sualları bankda hələ yoxdur, zamanla hazırlanacaq: tapılmayan mövzu – «gözlənilir» (pending); bank dolduqca siyahıdan çıxarılır


def source_for(grade: int | None) -> str | None:
    return GRADE_SOURCE.get(grade)


def sources_for(grade: int | None) -> list[str]:
    return list(SOURCE_ORDER.get(grade, []))


def file_grades(f: BankFile) -> list[int]:
    """Faylın sinifləri: bankdakı etiket (`grades`), yoxdursa mənbənin siniflər."""
    from .classify import SOURCE_GRADES
    return list(f.grades or SOURCE_GRADES.get(f.source_key, []))


def ta_source(db, ta) -> str | None:
    """Plan dərslərinin test linkləri üçün mənbə: sinfin ayarı (bank_source) üstündür; 'none' – link yoxdur."""
    if ta is not None and ta.bank_source:
        return None if ta.bank_source == 'none' else ta.bank_source
    from ..models import SchoolClass
    from ..services import class_grade
    return source_for(class_grade(db, db.get(SchoolClass, ta.class_id))) if ta is not None else None
_STOP = {'ve', 'ile', 'onun', 'onlar', 'ucun', 'bezi', 'sinif', 'iki', 'hiss', 'mesel', 'anlay', 'esas', 'muxte', 'usull'}
_PREFIX = re.compile(r'^\s*[IVX]+\s+sinif\s*:\s*', re.I)


# zəif qrup tempinin törəmə dərsləri (app/slow_plan.py; docs/zeif-plan-test-linkleri-promtu.md)
_BASE = ('Məşq və möhkəmləndirmə:', 'Təkrar və bərpa:')             # → əsas mövzunun testi
_MIXED = ('Bölmə təkrarı:', 'Spiral təkrar:', 'KSQ-yə hazırlıq:')       # qarışıq təkrar – tək fayl yoxdur
_GENERIC_SEC = {'Bazanın bərpası', 'Təkrar'}


def lesson_query(topic: str | None, section: str | None) -> tuple[str, str | None] | None:
    """Plan dərsi → uyğunluq üçün (mövzu, bölmə); None – bu dərsə mövzu testi verilmir."""
    t = (topic or '').strip()
    sec = None if (section or '').strip() in _GENERIC_SEC else section
    for p in _BASE:
        if t.startswith(p):
            return t[len(p):].strip(), sec
    if t.startswith(_MIXED) or (t.startswith('Təkrar:') and 'yekunlaşdırıcı' in t):
        return None
    return t, sec


def derived(topic: str | None) -> bool:
    """Törəmə dərs (məşq, bərpa, təkrar) – KSQ aralığında ayrıca mövzu sayılmır."""
    t = (topic or '').strip()
    return t.startswith(_BASE + _MIXED) or (t.startswith('Təkrar:') and 'yekunlaşdırıcı' in t)


def _norm(s: str) -> str:
    s = (s or '').lower().replace('ə', 'e').replace('i̇', 'i').replace('ı', 'i').replace('ö', 'o').replace('ü', 'u')
    s = s.replace('ğ', 'g').replace('ş', 's').replace('ç', 'c')
    return re.sub(r'[^\w\s]', ' ', s)


def stems(s: str) -> set[str]:
    out = {w[:5] for w in _norm(_PREFIX.sub('', s or '')).split() if len(w) >= 3 and not w.isdigit()}
    return out - _STOP


def _raw(s: str) -> set[str]:
    """Bölmə adları üçün köklər – köməkçi sözlər atılmır («Həndəsənin əsas anlayışları» bütöv tanınsın)."""
    s = re.sub(r'^\s*([ivxlc]+|\d+)\.?\s*', '', _norm(s or ''))
    return {w[:5] for w in s.split() if len(w) >= 3 and not w.isdigit()} - {'bolme', 'ile', 've'}


# ---------------------------------------------------------------- mövzu nömrəsi (docs/mekteb-plan-movzu-testleri-promtu.md §2.1)
# Plan dərsinin başlığındakı şablon əlavələri: «… (2/3). Məsələ həlli», «… . Sinif testi», «… . Nəzəri xülasə və nümunə məsələlər»
_TOPIC_TAIL = re.compile(r'\s*\(\d+/\d+\)\..*$|\.\s*(?:Ümumiləşdirmə\.\s*)?(?:Sinif testi(?: və təhlil)?|Test)\s*$'
                         r'|\.\s*Nəzəri xülasə və nümunə məsələlər\s*$')
_LEAD_NO = re.compile(r'^\s*(?:§\s*(\d{1,3})(?=\D|$)|(\d{1,2}(?:\.\d{1,2})+)(?=[.\s)\-–]|$))')
_SEC_NO = re.compile(r'^\s*(\d{1,2})\.\s')
_NOT_TOPIC = ('Sınaq', 'Aralıq sınaq', 'Yekun sınaq', 'Ümumi təkrar', 'KSQ-', 'BSQ-', 'Təkrar:', 'Diaqnostik', 'I yarımil', 'II yarımil')


def base_topic(topic: str | None) -> str:
    """Mövzunun əsas adı: sinif önəki və şablon əlavələri (saat nömrəsi, «Sinif testi») atılır."""
    return _TOPIC_TAIL.sub('', _PREFIX.sub('', (topic or '').strip())).strip()


def _get(x, k):
    return x.get(k) if isinstance(x, dict) else getattr(x, k, None)


def _tpl_topics(program) -> dict[str, list[str]]:
    """Proqram şablonunda bölmə adı → mövzu adlarının (normallaşmış) sırası."""
    tpl = ((program.data or {}).get('template') or {}) if program is not None else {}
    secs = list(tpl.get('sections') or [])
    for sem in tpl.get('semesters') or []:
        secs += list(sem or [])
    return {s.get('section'): [_norm(t).strip() for t in s.get('topics', [])] for s in secs if s.get('section')}


def topic_numbers(lessons: list, program=None) -> list[str | None]:
    """Hər plan dərsi üçün «bölmə.mövzu» nömrəsi (məs. «2.3») və ya None. (1) mövzu mətnindəki baş nömrə («3.4. …», «§12»);
    (2) bölmənin nömrəsi («2. Kvadrat tənliklər») + mövzunun bölmədəki sırası (proqram şablonu, yoxdursa planın özü);
    (3) yoxdursa None. Törəmə dərs (məşq, bərpa) əsas mövzunun nömrəsini alır. lessons – PlanLesson və ya dict, plan sırası ilə."""
    tpl = _tpl_topics(program)
    order: dict[str, list[str]] = {}                 # bölmə → planda mövzuların sırası (şablon yoxdursa)
    out: list[str | None] = [None] * len(lessons)
    by_base: dict[str, str] = {}
    pend: list[tuple[int, str]] = []

    def topic_of(l):
        typ, t = _get(l, 'assessment_type'), (_get(l, 'topic') or '').strip()
        if (typ and typ != 'formativ') or t.startswith(_NOT_TOPIC):
            return None
        return lesson_query(t, _get(l, 'section'))
    for i, l in enumerate(lessons):
        q = topic_of(l)
        if q is None:
            continue
        top, sec = q
        base = _norm(base_topic(top)).strip()
        m = _LEAD_NO.match(_PREFIX.sub('', top))
        if m:
            out[i] = m.group(1) or m.group(2)
        else:
            sm = _SEC_NO.match(sec or '')
            if sm and base:
                names = tpl.get(sec)
                if names and base in names:
                    out[i] = f'{int(sm.group(1))}.{names.index(base) + 1}'
                else:
                    lst = order.setdefault(sec, [])
                    if base not in lst:
                        lst.append(base)
                    out[i] = f'{int(sm.group(1))}.{lst.index(base) + 1}'
            elif base and (_get(l, 'topic') or '').strip() != top:
                pend.append((i, base))                 # törəmə dərs, öz bölməsi ümumidir – əsas mövzudan götürülür
        if out[i] and base:
            by_base.setdefault(base, out[i])
    for i, base in pend:
        out[i] = by_base.get(base)
    return out


def topic_no(lesson, program=None, lessons: list | None = None) -> str | None:
    """Bir dərsin mövzu nömrəsi (topic_numbers). lessons – bütün plan (sıra üçün); verilməyibsə yalnız dərsin özü."""
    if lessons:
        key = _get(lesson, 'id')
        for i, l in enumerate(lessons):
            if l is lesson or (key is not None and _get(l, 'id') == key):
                return topic_numbers(lessons, program)[i]
    return topic_numbers([lesson], program)[0]


_BANK_NO = re.compile(r'^\s*(\d{1,2}\.\d{1,2})(?=[.\s)\-–]|$)')


def bank_no(f: BankFile) -> str | None:
    """Faylın mövzu nömrəsi: etiketin (alt mövzu hissəsinin) başındakı «2.3 …» və ya yolda (`lesson`) «…/2.3/…»; yoxdursa None."""
    for part in ((f.label or '').split(' — ')[-1], f.label or ''):
        m = _BANK_NO.match(part)
        if m:
            return m.group(1)
    m = re.search(r'(?:^|/)(\d{1,2}\.\d{1,2})(?=\D|$)', f.lesson or '')
    return m.group(1) if m else None


def p0010_files(db: Session, source: str = SOURCE, any_kind: bool = False) -> list[BankFile]:
    """Mənbənin aktiv test faylları; any_kind – sınaq/yekun faylları da (əlavə qoşulan layihələr üçün)."""
    q = select(BankFile).join(BankSource, BankSource.key == BankFile.source_key).where(
        BankFile.source_key == source, BankFile.active.is_(True), BankSource.enabled.is_(True), BankFile.question_count > 0)
    if not any_kind:
        q = q.where(BankFile.kind == 'movzu')
    return list(db.scalars(q.order_by(BankFile.lesson)))


class Matcher:
    """Bankdakı P0010 faylları bir dəfə oxunur (plan görünüşündə hər dərs üçün təkrar sorğu olmasın)."""

    def __init__(self, db: Session, source: str = SOURCE, any_kind: bool = False, grade: int | None = None):
        self.files = p0010_files(db, source, any_kind)
        if grade is not None:                    # yalnız bu sinfin faylları (`grades`, boşdursa mənbənin sinifləri)
            self.files = [f for f in self.files if grade in file_grades(f)]
        self.fst = {f.id: stems(f.label) for f in self.files}
        self.own = {f.id: stems(f.label.split(' — ', 1)[-1]) for f in self.files}     # alt mövzu adı bölmədən ağırdır
        self.grp = {f.id: _raw(f.label.split(' — ', 1)[0]) for f in self.files}      # P0010 bölməsi
        self.fno = {f.id: bank_no(f) for f in self.files}                              # faylın mövzu nömrəsi (varsa)
        df: dict[str, int] = {}
        for st in self.fst.values():
            for w in st:
                df[w] = df.get(w, 0) + 1
        n = len(self.files)
        self.idf = {w: math.log((n + 1) / (c + 1)) + 0.1 for w, c in df.items()}

    def cover(self, f: BankFile, topic: str) -> float:
        """Mövzu köklərinin hansı hissəsi faylın adında var (0–1) – mənbələr arası müqayisə üçün (bal bankın ölçüsündən asılıdır)."""
        q = lesson_query(topic, None)
        t = stems(q[0]) if q else set()
        return len(t & self.fst.get(f.id, set())) / len(t) if t else 0.0

    def matches(self, topic: str, section: str | None = None, limit: int = 6, rel: float = 0.0,
                no: str | None = None) -> list[tuple[BankFile, float]]:
        """no – dərsin mövzu nömrəsi («2.3»): eyni nömrəli fayl (ad da qismən uyğundursa) NO_BONUS qədər irəli çıxır."""
        q = lesson_query(topic, section)
        if q is None:
            return []
        topic, section = q
        t = stems(topic)
        sec = stems(re.sub(r'^\s*\d+\.\s*', '', section or '')) - t
        sraw = _raw(section or '')
        scored = []
        for f in self.files:
            fs, own = self.fst[f.id], self.own[f.id]
            w = lambda x: self.idf.get(x, 0) * (1 if x in own else 0.5)      # noqa: E731
            s = 2 * sum(w(x) for x in t & fs) + sum(w(x) for x in sec & fs)
            if s > 0:
                if no and self.fno.get(f.id) == no:
                    s *= NO_BONUS
                g = self.grp[f.id]
                # dərsin bölməsi = P0010 bölməsi – öndə; tez-tez rast gələn sözlər («ədədlər») az çəkili (idf)
                gw = sum(self.idf.get(x, 1) for x in g)
                same = bool(g and sraw and sum(self.idf.get(x, 1) for x in sraw & g) / gw >= 0.6)
                scored.append((f, round(s / (1 + 0.05 * len(fs)), 3), same))
        scored.sort(key=lambda x: (not x[2], -x[1], x[0].lesson))
        if rel and any(x[2] for x in scored):                # KSQ: dərsin bölməsinə uyğun fayllar varsa – yalnız onlar
            scored = [x for x in scored if x[2]]
        scored = [(f, v) for f, v, _ in scored]
        if rel and scored:                                   # KSQ: yalnız mövzuya həqiqətən yaxın fayllar
            best = max(v for _, v in scored)
            scored = [(f, v) for f, v in scored if v >= best * rel]
        return scored[:limit]


@dataclass
class Found:
    """GradeMatcher.find_ex nəticəsi: fayllar, mənbə, status (ok | weak | none), mövzu köklərinin örtüyü (0–1)."""
    files: list
    source: str | None
    status: str
    cover: float


class GradeMatcher:
    """Plan dərsi üçün sinfə görə test faylı: sinfin sıralı mənbələri (SOURCE_ORDER) – əvvəl 1-ci, uyğunluq MIN_SCORE-dan aşağıdırsa növbəti.
    Hər (mənbə, sinif) üçün bir Matcher (keş). `explicit` – müəllimin ayarı (ta.bank_source): yalnız o mənbə, sinif süzgəci yoxdur."""

    def __init__(self, db: Session, explicit: str | None = None):
        self.db, self.explicit, self._cache = db, explicit, {}

    def sources(self, grade: int | None) -> list[str]:
        return [self.explicit] if self.explicit else sources_for(grade)

    def matcher(self, src: str, grade: int | None) -> Matcher:
        g = None if self.explicit else grade
        k = (src, g)
        if k not in self._cache:
            self._cache[k] = Matcher(self.db, src, any_kind=src not in GRADE_SOURCE.values(), grade=g)
        return self._cache[k]

    def find_ex(self, grade: int | None, topic: str, section: str | None = None, limit: int = 1, no: str | None = None) -> "Found":
        r = self._find(grade, topic, section, limit, no)
        if r.status == "none" and grade in PENDING_GRADES:          # bank hələ hazırlanır – «yoxdur» yox, «gözlənilir»
            r.status = "pending"
        return r

    def _find(self, grade, topic, section, limit, no) -> "Found":
        """Mənbələr sırası ilə: ilk həddi keçən (örtük ≥ OK_COVER, ya da eyni nömrə və örtük ≥ WEAK_COVER) – status 'ok'.
        Heç biri keçmirsə – 1-ci mənbənin ən yaxını: örtük ≥ WEAK_COVER – 'weak' (şübhəli ⚠), aşağı – 'none' (qoşulmur);
        mənbə/fayl yoxdursa 'none' və boş siyahı."""
        srcs = self.sources(grade)
        weak: Found | None = None
        for s in srcs:
            m = self.matcher(s, grade)
            found = m.matches(topic, section, limit, no=no)
            if not found:
                continue
            c = m.cover(found[0][0], topic)
            hit = bool(no and m.fno.get(found[0][0].id) == no)
            if c >= OK_COVER or (hit and c >= WEAK_COVER):
                return Found(found, s, 'ok', c)
            if weak is None:
                weak = Found(found, s, 'weak' if c >= WEAK_COVER else 'none', c)
        return weak or Found([], srcs[0] if srcs else None, 'none', 0.0)

    def find(self, grade: int | None, topic: str, section: str | None = None, limit: int = 1) -> tuple[list[tuple[BankFile, float]], str | None]:
        """(uyğun fayllar, mənbə). Heç bir mənbə həddi keçmirsə – 1-ci mənbənin ən yaxını (köhnə davranış); mənbə yoxdursa ([], None)."""
        r = self.find_ex(grade, topic, section, limit)
        return r.files, r.source


def p0010_matches(db: Session, topic: str, section: str | None = None, limit: int = 6, source: str = SOURCE) -> list[tuple[BankFile, float]]:
    return Matcher(db, source).matches(topic, section, limit)
