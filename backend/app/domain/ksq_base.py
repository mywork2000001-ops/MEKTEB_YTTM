"""KSQ/BSQ bazası (istifadəçi tələbi 13.10.2026: «gələcək illər üçün KSQ bazası formalaşsın, səhvlər birdə yaranmasın»).

Bir dəfə hazırlanan KSQ (fənn · sinif səviyyəsi · KSQ/BSQ nömrəsi · yarımil) üzrə yadda saxlanır:
  - mövzular və P0010 faylları (perspektiv plandan);
  - müəllimin düzəlişləri (redaktə olunmuş sualın mətni / variantları / cavabı) – gələn il eyni sual düzəldilmiş gəlir;
  - istisnalar (ləğv edilmiş slotun sualı, «bankda gizlət») – gələn il bu suallar seçilmir.
Növbəti dəfə (və ya gələn tədris ili) eyni KSQ hazırlananda baza avtomatik tətbiq olunur.

validate() – variant bazaya yazılmazdan ƏVVƏL məcburi yoxlama: şablon sualı, layihədən kənar sual, aralıqdan kənar fayl, bir
variantda təkrar – varsa variant yazılmır (səhv heç vaxt şagirdə çatmır)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session


def base_key(db: Session, ta, e) -> str:
    from ..models import SchoolClass
    from ..services import class_grade
    g = class_grade(db, db.get(SchoolClass, ta.class_id))
    return f'{ta.subject}|{g}|{e.kind}|{e.no}|{e.semester}'


def get(db: Session, ta, e):
    from ..models import KsqBase
    return db.scalar(select(KsqBase).where(KsqBase.key == base_key(db, ta, e)))


def _get_or_new(db: Session, ta, e):
    from ..models import KsqBase
    b = get(db, ta, e)
    if b is None:
        b = KsqBase(key=base_key(db, ta, e), topics=[], files=[], excluded=[], edits={})
        db.add(b)
        db.flush()
    return b


def remember(db: Session, ta, e, topics: list, files: dict, user_id: int | None = None) -> None:
    """Variantlar yarananda: mövzular və fayllar bazaya (əvvəlki istisna/düzəlişlər qalır)."""
    b = _get_or_new(db, ta, e)
    b.topics = [t for t, _ in topics]
    b.files = sorted({f for lst in files.values() for f in lst})
    b.updated_by = user_id


def exclude(db: Session, ta, e, key: str | None) -> None:
    if not key:
        return
    b = _get_or_new(db, ta, e)
    if key not in (b.excluded or []):
        b.excluded = [*(b.excluded or []), key]


def note_edit(db: Session, ta, e, key: str | None, fields: dict) -> None:
    if not key:
        return
    b = _get_or_new(db, ta, e)
    b.edits = {**(b.edits or {}), key: {k: fields[k] for k in ('text', 'options', 'correct', 'answer') if k in fields}}


def apply(db: Session, ta, e, cands: list) -> list:
    """Bazanı namizədlərə tətbiq edir: istisnalar atılır, düzəlişlər sualın üstünə yazılır."""
    b = get(db, ta, e)
    if b is None:
        return cands
    ex = set(b.excluded or [])
    out = []
    for c in cands:
        root = c.key.removesuffix(':o')
        if c.key in ex or root in ex:
            continue
        fix = (b.edits or {}).get(c.key) or (b.edits or {}).get(root)
        if fix:
            c.q = {**c.q, **{k: v for k, v in fix.items() if v is not None and (c.kind == 'mcq' or k not in ('options', 'correct'))}, 'edited_base': True}
        out.append(c)
    return out


def validate(variants: dict[int, list[dict]], allowed_files: set[int], file_of: dict[int, int], sources: set[str]) -> list[str]:
    """Məcburi yoxlama (yazmazdan əvvəl). Boş siyahı – hər şey qaydasındadır."""
    errs = []
    for sid, qs in variants.items():
        keys = [q.get('key') for q in qs]
        if len(set(keys)) != len(keys):
            errs.append(f'{sid}: variantda təkrar sual')
        for q in qs:
            if q.get('template'):
                errs.append(f'{sid}/{q.get("slot")}: şablon sualı')
            elif q.get('bank_id'):
                if q.get('source') not in sources:
                    errs.append(f'{sid}/{q.get("slot")}: layihədən kənar ({q.get("source")})')
                elif allowed_files and file_of.get(q['bank_id']) not in allowed_files:
                    errs.append(f'{sid}/{q.get("slot")}: aralıqdan kənar fayl')
            else:
                errs.append(f'{sid}/{q.get("slot")}: mənbəsiz sual')
    return errs
