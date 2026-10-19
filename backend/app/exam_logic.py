"""KSQ/BSQ ortaq məntiq: imtahanın şagird siyahısı (əlavə imtahan – seçilmiş şagirdlər), onlayn və kağız nəticənin yanaşı
saxlanması və jurnala gedən yekun balın hesablanması (recompute_score), yarımil üçün əsas + əlavə imtahan qiyməti."""
from __future__ import annotations

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Exam, ExamScan, ExamScore, Student, TeachingAssignment
from .services import roster

CHOICES = ('online', 'paper', 'max', 'manual')


def exam_roster(db: Session, ta: TeachingAssignment, e: Exam) -> list[Student]:
    """İmtahana aid şagirdlər: əsas imtahan – bütün sinif, əlavə – yalnız extra_students (sinifdən çıxanlar düşür)."""
    st = roster(db, ta)
    if e.extra_students is None:
        return st
    ids = set(e.extra_students)
    return [s for s in st if s.id in ids]


def exam_label(e: Exam) -> str:
    return f'{e.kind}-{e.no}' + (f' · əlavə {e.extra_seq}' if e.extra_seq else '')


def scan_of(db: Session, exam_id: int, student_id: int, source: str) -> ExamScan | None:
    return db.scalar(select(ExamScan).where(ExamScan.exam_id == exam_id, ExamScan.student_id == student_id,
                                            ExamScan.source == source))


def recompute_score(db: Session, e: Exam, student_id: int) -> ExamScore | None:
    """Jurnala gedən yekun bal (ExamScore.points) – seçimə (chosen) görə. «manual» olanda toxunmur. Seçilən mənbədə nəticə
    yoxdursa – digərindən götürülür; heç bir qiymətləndirilmiş skan yoxdursa – bal olduğu kimi qalır (əl ilə yazılıb)."""
    score = db.get(ExamScore, (e.id, student_id))
    if score is not None and score.chosen == 'manual':
        return score
    got = {}
    for src in ('online', 'paper'):
        sc = scan_of(db, e.id, student_id, src)
        if sc is not None and sc.status == 'graded' and sc.points is not None:
            got[src] = sc
    if not got:
        return score
    if score is None:
        score = ExamScore(exam_id=e.id, student_id=student_id, chosen='max')
        db.add(score)
    ch = score.chosen if score.chosen in CHOICES else 'max'
    if ch in got:
        pick = got[ch]
    elif ch in ('online', 'paper'):
        pick = next(iter(got.values()))
    else:
        pick = max(got.values(), key=lambda x: x.points)
    score.points, score.item_marks, score.absent = pick.points, pick.marks, False
    db.flush()
    return score


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


def missed_ksq(exams: list[Exam], ksq: list[tuple[int, int | None]], today) -> list[int]:
    """Keçirilmiş (tarixi gəlib çatmış), lakin şagirdin qiyməti olmayan (buraxıb / bal yoxdur) KSQ nömrələri –
    yarımil qiyməti «şərti» sayılır, çatışmayan KSQ əlavə təyin edilməlidir (metodik qayda)."""
    held = {e.no for e in exams if e.kind == 'KSQ' and not e.extra_seq and e.date <= today}
    return [n for n, g in ksq if g is None and n in held]
