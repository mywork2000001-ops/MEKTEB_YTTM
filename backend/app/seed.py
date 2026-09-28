"""İlkin doldurma (təkrar işə salmaq təhlükəsizdir – mövcud olanlar ötürülür).

    python -m app.seed [--utis KOD] [--login M-001]

Yaradır: məktəb, admin (Həsənov Fərid), 2026–2027 tədris ili + bayramlar, siniflər və dərs cədvəli,
UTİS siyahısından şagirdlər (portal kodu + 4 rəqəmli PIN). İlk parol və PIN-lər YALNIZ bir dəfə
data/ilk_giris_*.csv faylına yazılır (repoya düşmür) – çap edib paylayın, sonra faylı silin."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .domain import calendar as cal
from .importers.utis import read_utis
from .models import (AcademicYear, Holiday, PlanLesson, Role, School, SchoolClass, Student, TeachingAssignment,
                     User)
from .services import import_plan
from .security import hash_password, new_password, new_pin

DESKTOP = Path.home() / 'Desktop' / 'Tom planlama'
UTIS_XLSX = DESKTOP / 'Utis_siyahi (27).xlsx'
DIM_XLSX = DESKTOP / 'TOM-şagirdlər buraxılış balları (1).xlsx'
PLANS_DIR = DESKTOP / '01 Aktual dərs proqramları 2026-2027'
DATA = Path(__file__).resolve().parent.parent / 'data'

CODES = {'xb': 'XB', 'xb_q': 'XBQ', 'xc': 'XC', 'xe': 'XE', 'xia': 'XIA', 'xip': 'XIP'}


def _one(db: Session, model, **where):
    return db.scalar(select(model).filter_by(**where))


def add_students(db: Session, sc: SchoolClass, students, created_by: int | None) -> list[tuple[str, str, str, str]]:
    """UTİS siyahısından sinfə şagird əlavə edir (ad + doğum tarixi təkrarlanırsa ötürür).
    Qaytarır: (sinif, ad, giriş kodu, PIN) – PIN yalnız bu anda məlumdur."""
    out = []
    used = {int(x.rsplit('-', 1)[1]) for x in db.scalars(select(Student.portal_code)
            .where(Student.portal_code.like(f'{sc.code}-%'))) if x.rsplit('-', 1)[1].isdigit()}
    for s in students:
        if _one(db, Student, school_id=sc.school_id, full_name=s.name, birth_date=s.birth_date):
            continue
        n = max(used, default=0) + 1                        # sinfin növbəti nömrəsi: XE-001, XE-002, …
        used.add(n)
        code = f'{sc.code}-{n:03d}'
        pin = new_pin()
        u = User(role=Role.student, login=code, password_hash=hash_password(pin), full_name=s.name,
                 school_id=sc.school_id)
        db.add(u)
        db.flush()
        db.add(Student(school_id=sc.school_id, class_id=sc.id, full_name=s.name, birth_date=s.birth_date,
                       gender=s.gender, portal_code=code, user_id=u.id, score_language=s.score_language,
                       score_math=s.score_math, score_foreign=s.score_foreign, created_by=created_by))
        db.flush()
        out.append((sc.name, s.name, code, pin))
    return out


def seed(db: Session, utis: str | None = None, login: str = 'M-001',
         utis_xlsx: Path = UTIS_XLSX, dim_xlsx: Path = DIM_XLSX, out_dir: Path = DATA,
         plans_dir: Path | None = PLANS_DIR) -> dict:
    report = {'created': [], 'secrets_file': None}
    secrets_rows: list[tuple[str, str, str, str]] = []

    school = _one(db, School, name=cal.SCHOOL_TOM)
    if not school:
        school = School(name=cal.SCHOOL_TOM, short_name='Rafiq Nuriyev adına 6 nömrəli TOM', utis=utis,
                        region='Qarabağ RTİ', bells={str(i + 1): b for i, b in enumerate(cal.BELLS)})
        db.add(school)
        db.flush()
        report['created'].append('məktəb')
    elif utis and not school.utis:
        school.utis = utis

    admin = _one(db, User, login=login)
    if not admin:
        pw = new_password()
        admin = User(role=Role.admin, login=login, password_hash=hash_password(pw),
                     full_name='Həsənov Fərid Oktay oğlu', school_id=school.id, subjects=['Riyaziyyat'])
        db.add(admin)
        db.flush()
        secrets_rows.append(('admin', admin.full_name, login, pw))
        report['created'].append('admin')

    year = _one(db, AcademicYear, school_id=school.id, name='2026–2027')
    if not year:
        year = AcademicYear(school_id=school.id, name='2026–2027', start=cal.YEAR_START, sem1_end=cal.SEM1_END,
                            sem2_start=cal.SEM2_START, end=cal.YEAR_END, is_current=True)
        db.add(year)
        db.flush()
        db.add_all(Holiday(year_id=year.id, date=d, name=n) for d, n in cal.OFF_DAYS.items())
        report['created'].append(f'tədris ili + {len(cal.OFF_DAYS)} bayram/tətil günü')

    roster = read_utis(utis_xlsx, dim_xlsx) if utis_xlsx.exists() else None
    by_code: dict[str, SchoolClass] = {}
    for c in cal.CLASSES:
        sc = _one(db, SchoolClass, school_id=school.id, year_id=year.id, name=c.name)
        if not sc:
            sc = SchoolClass(school_id=school.id, year_id=year.id, name=c.name, code=CODES[c.code],
                             kind='qrup' if c.parent else c.kind, utis_class=c.utis_class,
                             parent_id=by_code[c.parent].id if c.parent else None,
                             split_with=c.split_with,
                             bells={str(k): v for k, v in c.bells.items()} if c.bells else None,
                             created_by=admin.id)
            db.add(sc)
            db.flush()
            report['created'].append(f'sinif {c.name}')
        by_code[c.code] = sc
        ta = _one(db, TeachingAssignment, teacher_id=admin.id, class_id=sc.id, subject='Riyaziyyat')
        if not ta:
            ta = TeachingAssignment(teacher_id=admin.id, class_id=sc.id, subject='Riyaziyyat',
                                    weekly_hours=c.weekly_hours, has_summative=c.has_summative,
                                    slots={str(k): v for k, v in c.slots.items() if v})
            db.add(ta)
            db.flush()
        if plans_dir and not _one(db, PlanLesson, assignment_id=ta.id):
            f = next((x for x in sorted(plans_dir.glob('*.docx')) if x.name.startswith(c.plan_prefix + ' –')), None)
            if f:
                rep = import_plan(db, ta, f)
                report['created'].append(f'{c.name}: plan {rep["lessons"]} dərs')
        if roster and c.utis_class in roster.classes:
            rows = add_students(db, sc, roster.classes[c.utis_class], admin.id)
            secrets_rows += rows
            if rows:
                report['created'].append(f'{c.name}: {len(rows)} şagird')
    db.commit()

    if secrets_rows:
        out_dir.mkdir(parents=True, exist_ok=True)
        f = out_dir / f'ilk_giris_{dt.datetime.now():%Y%m%d_%H%M%S}.csv'
        with open(f, 'w', newline='', encoding='utf-8-sig') as fh:        # Excel Azərbaycan hərflərini düz açsın
            w = csv.writer(fh, delimiter=';')
            w.writerow(['Sinif', 'Ad', 'Giriş kodu', 'Parol / PIN'])
            w.writerows(secrets_rows)
        report['secrets_file'] = str(f)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--utis', help='məktəbin UTİS kodu (sonra tənzimləmələrdə də yazıla bilər)')
    ap.add_argument('--login', default='M-001')
    a = ap.parse_args()
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(Path(__file__).resolve().parent.parent / 'alembic.ini')), 'head')
    with SessionLocal() as db:
        r = seed(db, a.utis, a.login)
    print('Yaradıldı:', ', '.join(r['created']) or 'heç nə (hamısı artıq var)')
    if r['secrets_file']:
        print('İlk parol və PIN-lər:', r['secrets_file'], '– çap edin, sonra silin.')


if __name__ == '__main__':
    main()
