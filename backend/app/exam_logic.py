"""KSQ/BSQ ortaq məntiq: imtahanın şagird siyahısı (əlavə imtahan – seçilmiş şagirdlər), yarımil üçün əsas + əlavə imtahan qiyməti."""
from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from .models import Exam, Student, TeachingAssignment
from .services import roster


def exam_roster(db: Session, ta: TeachingAssignment, e: Exam) -> list[Student]:
    """İmtahana aid şagirdlər: əsas imtahan – bütün sinif, əlavə – yalnız extra_students (sinifdən çıxanlar düşür)."""
    st = roster(db, ta)
    if e.extra_students is None:
        return st
    ids = set(e.extra_students)
    return [s for s in st if s.id in ids]


def exam_label(e: Exam) -> str:
    return f'{e.kind}-{e.no}' + (f' · əlavə {e.extra_seq}' if e.extra_seq else '')


def final_grades(exams: list[Exam], grade_of: Callable[[Exam], int | None]) -> tuple[list[tuple[int, int | None]], int | None]:
    """Yarımil üçün şagirdin KSQ [(no, qiymət)] və BSQ qiyməti. Əlavə imtahan ayrıca sayılmır: əsas imtahanın qiyməti =
    əsas və onun əlavələrinin ən yüksəyi (buraxıb əlavədə yazana – əlavənin qiyməti)."""
    extras: dict[int, list[Exam]] = {}
    for x in exams:
        if x.extra_seq and x.extra_of:
            extras.setdefault(x.extra_of, []).append(x)

    def eff(e: Exam) -> int | None:
        gs = [g for g in (grade_of(y) for y in (e, *extras.get(e.id, []))) if g is not None]
        return max(gs) if gs else None
    base = [e for e in exams if not e.extra_seq]
    ksq = [(e.no, eff(e)) for e in base if e.kind == 'KSQ']
    bsq = next((eff(e) for e in base if e.kind == 'BSQ'), None)
    return ksq, bsq
