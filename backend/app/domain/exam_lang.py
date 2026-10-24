"""Yazılı imtahanın dili – TƏK mənbə (docs/tasks/sinif-sektoru-yazili-dil-2026-10-24.md).

Sıra: imtahanın öz dili (Exam.language) → sinfin yazılı dili (SchoolClass.exam_language; 'sector' → SchoolClass.sector) → 'az'.
Qrup sinfi (parent_id) öz dəyəri boşdursa ana sinifdən götürür. Şagirdin interfeys dili (User.language) vərəqə TƏSİR ETMİR.
Nəticə: 'az' | 'ru' | 'az_ru' (ikidilli: əsas mətn AZ, altında RU)."""
from __future__ import annotations

from typing import Any

EXAM_LANGS = ('az', 'ru', 'az_ru')
SECTORS = ('az', 'ru')
CLASS_EXAM_LANGS = ('sector', 'az', 'ru', 'az_ru')


def _class_value(db, cls, attr: str):
    """Sinfin sahəsi; boşdursa və qrupdursa – ana sinifdən."""
    seen = 0
    while cls is not None and seen < 3:
        v = getattr(cls, attr, None)
        if v:
            return v
        cls = db.get(type(cls), cls.parent_id) if getattr(cls, 'parent_id', None) else None
        seen += 1
    return None


def class_sector(db, cls) -> str:
    v = _class_value(db, cls, 'sector')
    return v if v in SECTORS else 'az'


def class_exam_language(db, cls) -> str:
    """Sinfin yazılı dili qaydası: 'sector' | 'az' | 'ru' | 'az_ru' (boş – 'sector')."""
    v = _class_value(db, cls, 'exam_language')
    return v if v in CLASS_EXAM_LANGS else 'sector'


def exam_lang(db, exam, cls=None) -> str:
    """İmtahanın yazılı dili: 'az' | 'ru' | 'az_ru'."""
    own = getattr(exam, 'language', None) if exam is not None else None
    if own in EXAM_LANGS:
        return own
    if cls is None and exam is not None and getattr(exam, 'assignment_id', None):
        from ..models import SchoolClass, TeachingAssignment
        ta = db.get(TeachingAssignment, exam.assignment_id)
        cls = db.get(SchoolClass, ta.class_id) if ta else None
    rule = class_exam_language(db, cls)
    if rule == 'sector':
        return class_sector(db, cls)
    return rule


def has_lang(x: Any, lang: str) -> bool:
    """Mətn bu dildə varmı (dict-də boş olmayan açar). Tək sətir (dilsiz) – həmişə «var»."""
    if isinstance(x, dict):
        return bool(x.get(lang))
    return True


def pick(x: Any, mode: str) -> tuple[str, str | None]:
    """(əsas, alt) – mode 'az'|'ru': alt None; 'az_ru': əsas AZ, alt RU (RU yoxdursa və ya AZ ilə eynidirsə None).
    Seçilən dildə mətn yoxdursa AZ-a (sonra istənilən mövcud mətnə) düşür."""
    if not isinstance(x, dict):
        return str(x or ''), None
    az = x.get('az') or ''
    if mode == 'ru':
        return (x.get('ru') or az or next((v for v in x.values() if v), '')), None
    main = az or next((v for v in x.values() if v), '')
    if mode == 'az_ru':
        ru = x.get('ru') or ''
        return main, (ru if ru and ru != main else None)
    return main, None


def render_question(q: dict, mode: str) -> dict:
    """Variant sualı → {text, options, text_sub, options_sub} (vərəq, paket, onlayn sual üçün). Sub yalnız ikidilli rejimdə."""
    text, text_sub = pick(q.get('text'), mode)
    opts, opts_sub = None, None
    if q.get('kind') == 'mcq' and q.get('options'):
        pairs = [pick(o, mode) for o in q['options']]
        opts = [a for a, _ in pairs]
        if mode == 'az_ru' and any(b for _, b in pairs):
            opts_sub = [b or '' for _, b in pairs]
    return {'text': text, 'options': opts, 'text_sub': text_sub, 'options_sub': opts_sub}


def missing_translations(questions: list[dict], mode: str) -> list[int]:
    """RU mətni olmayan sualların nömrələri (slot) – 'ru' və 'az_ru' rejimində müəllimə xəbərdarlıq üçün. 'az' – boş.
    Sual mətni və ya (test sualında) variantlardan biri RU-suzdursa, sual «çatışmır» sayılır."""
    if mode not in ('ru', 'az_ru'):
        return []
    out = []
    for q in questions:
        parts = [q.get('text')] + (list(q.get('options') or []) if q.get('kind') == 'mcq' else [])
        if any(not has_lang(p, 'ru') for p in parts if p not in (None, '')):
            out.append(q.get('slot') if q.get('slot') is not None else q.get('n'))
    return sorted(x for x in out if x is not None)


def join_pair(main: str, sub: str | None) -> str:
    """İkidilli mətn tək sətirdə (onlayn sual, paket): AZ, altında RU."""
    return f'{main}\n\n{sub}' if sub else main


def flatten_question(q: dict, mode: str) -> dict:
    """Sualın surəti: text/options imtahan dilində TƏK sətirlərdir ({az,ru,en} yox); az_ru – 'AZ\n\nRU'. Onlayn KSQ və paket üçün."""
    r = render_question(q, mode)
    out = dict(q)
    out['text'] = join_pair(r['text'], r['text_sub'])
    if r['options'] is not None:
        subs = r['options_sub'] or [None] * len(r['options'])
        out['options'] = [f'{a} / {b}' if b else a for a, b in zip(r['options'], subs)]
    return out


def default_ui_language(db, cls) -> str:
    """Yeni şagird hesabının interfeys dili: rus sektoru sinfində 'ru', qalanında 'az' (şagird sonra özü dəyişə bilər)."""
    return 'ru' if class_sector(db, cls) == 'ru' else 'az'
