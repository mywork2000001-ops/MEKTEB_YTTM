"""Bank suallarına standart yazır (BankQuestion.standard) – perspektiv plan dərsinin standartlarından (M8).

Qayda: plan dərsi → onun test faylı (plan_tests.locate, yalnız status 'ok'); faylın bütün dərslərinin standartlarının birləşməsi
TƏK standartdırsa – faylın standartı boş olan aktiv suallarına yazılır. Birdən çox standart / uzun (>64) – «qeyri-birmənalı», yazılmır.
Heç bir dərsə bağlanmayan fayl – «uyğunluq yoxdur». Mövcud (boş olmayan) standartlara toxunmur → təkrar işlətmək təhlükəsizdir.

DEFOLT QURU REJİM (heç nə yazmır). Yazı yalnız --apply ilə. DATABASE_URL-dəki baza (canlı baza – yalnız istifadəçinin razılığı ilə!).
İstifadə (backend qovluğunda):  py -m tools.fill_bank_standards [--apply]
"""
import argparse
import sys
from collections import defaultdict

MAX_LEN = 64


def collect(db) -> dict[int, set[str]]:
    """{bank_file_id: {standartlar}} – bütün planlı dərslər üzrə (bağlanan faylı olan hər dərs)."""
    from sqlalchemy import select

    from app.models import PlanLesson, TeachingAssignment
    from app.plan_tests import TaCtx, locate
    out: dict[int, set[str]] = defaultdict(set)
    for ta in db.scalars(select(TeachingAssignment)):
        lessons = [l for l in db.scalars(select(PlanLesson).where(PlanLesson.assignment_id == ta.id)) if l.standards]
        if not lessons:
            continue
        try:
            ctx = TaCtx(db, ta)
        except Exception:
            continue
        for pl in lessons:
            try:
                _g, found, _no = locate(db, ta, pl, limit=1, _c=ctx)
            except Exception:
                continue
            if found is None or found.status != 'ok' or not found.files:
                continue
            for st in pl.standards:
                if isinstance(st, str) and st.strip():
                    out[found.files[0].id].add(st.strip())
    return out


def plan(db, file_stds: dict[int, set[str]]) -> dict:
    """Quru hesab: {'fill': {file_id: standard}, filled, ambiguous, no_mapping} – sual sayı ilə (yalnız standartı boş aktiv suallar)."""
    from sqlalchemy import func, select

    from app.models import BankQuestion
    empty = (BankQuestion.standard.is_(None)) | (BankQuestion.standard == '')
    per_file = dict(db.execute(select(BankQuestion.file_id, func.count()).where(BankQuestion.active.is_(True), empty)
                               .group_by(BankQuestion.file_id)).all())
    fill: dict[int, str] = {}
    c = {'filled': 0, 'ambiguous': 0, 'no_mapping': 0}
    for fid, n in per_file.items():
        stds = file_stds.get(fid)
        if not stds:
            c['no_mapping'] += n
        elif len(stds) == 1 and len(next(iter(stds))) <= MAX_LEN:
            fill[fid] = next(iter(stds))
            c['filled'] += n
        else:
            c['ambiguous'] += n
    return {'fill': fill, **c}


def apply(db, fill: dict[int, str]) -> int:
    from sqlalchemy import update

    from app.models import BankQuestion
    n = 0
    for fid, std in fill.items():
        r = db.execute(update(BankQuestion).where(BankQuestion.file_id == fid, BankQuestion.active.is_(True),
                                                  (BankQuestion.standard.is_(None)) | (BankQuestion.standard == ''))
                       .values(standard=std))
        n += r.rowcount or 0
    db.commit()
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--apply', action='store_true', help='yaz (defolt – quru rejim)')
    a = ap.parse_args(argv)
    from app.db import SessionLocal
    with SessionLocal() as db:
        p = plan(db, collect(db))
        print(f'{"YAZILIR" if a.apply else "QURU REJİM (heç nə yazılmır)"}: '
              f'dolacaq {p["filled"]} sual ({len(p["fill"])} fayl) · qeyri-birmənalı {p["ambiguous"]} · uyğunluq yoxdur {p["no_mapping"]}')
        if a.apply:
            print(f'Yazıldı: {apply(db, p["fill"])} sual')
    return 0


if __name__ == '__main__':
    sys.exit(main())
