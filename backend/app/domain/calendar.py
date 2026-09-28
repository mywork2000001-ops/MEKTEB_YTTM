"""Tədris təqvimi və dərs cədvəli (2026–2027). Mənbə: 05 Texniki/build.py (OFF lüğəti) və müəllimin həftəlik cədvəli.
Bu dəyərlər yalnız ilkin (seed) məlumatdır – bazada redaktə edilə bilən cədvəl kimi saxlanılır."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

YEAR_START = dt.date(2026, 9, 15)
YEAR_END = dt.date(2027, 6, 14)
SEM1_END = dt.date(2027, 1, 26)
SEM2_START = dt.date(2027, 2, 1)
BSQ_DATES = {1: SEM1_END, 2: YEAR_END}

OFF_DAYS: dict[dt.date, str] = {dt.date.fromisoformat(k): v for k, v in {
    '2026-11-09': 'Dövlət Bayrağı Günü',
    '2026-11-10': 'Zəfər Günü (8 noyabrın əvəzi)',
    '2026-12-30': 'Qış tətili / Yeni il bayramı',
    '2026-12-31': 'Qış tətili / Yeni il bayramı',
    '2027-01-01': 'Qış tətili / Yeni il bayramı',
    '2027-01-04': 'Qış tətili / Yeni il bayramı',
    '2027-01-05': 'Qış tətili / Yeni il bayramı',
    '2027-01-06': 'Qış tətili / Yeni il bayramı',
    '2027-01-20': 'Ümumxalq Hüzn Günü',
    '2027-01-27': 'Yarımillər arası tətil',
    '2027-01-28': 'Yarımillər arası tətil',
    '2027-01-29': 'Yarımillər arası tətil',
    '2027-03-08': 'Qadınlar Günü',
    '2027-03-09': 'Ramazan bayramı (təxmini)',
    '2027-03-10': 'Ramazan bayramı (təxmini)',
    '2027-03-19': 'Yaz tətili / Novruz bayramı',
    '2027-03-22': 'Yaz tətili / Novruz bayramı',
    '2027-03-23': 'Yaz tətili / Novruz bayramı',
    '2027-03-24': 'Yaz tətili / Novruz bayramı',
    '2027-03-25': 'Yaz tətili / Novruz bayramı',
    '2027-03-26': 'Yaz tətili / Novruz bayramı',
    '2027-05-10': 'Faşizm üzərində qələbə günü (9 mayın əvəzi)',
    '2027-05-17': 'Qurban bayramı (təxmini)',
    '2027-05-18': 'Qurban bayramı (təxmini)',
    '2027-05-28': 'Müstəqillik Günü',
}.items()}

WEEKDAYS = ['B.e.', 'Ç.a.', 'Ç.', 'C.a.', 'C.']
BELLS = ['08:50–09:35', '09:40–10:25', '10:35–11:20', '11:25–12:10', '12:15–13:00', '13:35–14:20', '14:25–15:10']


@dataclass(frozen=True)
class ClassSeed:
    code: str            # daxili açar
    name: str            # interfeysdə göstərilən ad
    kind: str            # 'TOM' | 'adi'
    weekly_hours: int
    plan_prefix: str     # 01 Aktual dərs proqramları – fayl adının əvvəli
    slots: dict[int, list[int]]   # həftə günü (0 = B.e.) -> dərs saatları
    has_summative: bool = True
    parent: str | None = None
    utis_class: str | None = None      # UTİS siyahısında sinif (şagirdlər buradan: Utis_siyahi.xlsx)


CLASSES: list[ClassSeed] = [
    ClassSeed('xb', 'X b', 'TOM', 5, 'X-b sinif – bütöv sinif', {2: [3, 7], 3: [1, 4], 4: [2]}, utis_class='10 b'),
    ClassSeed('xb_q', 'X b (riyaziyyat qrupu)', 'TOM', 5, 'X-b sinif – riyaziyyat qrupu', {0: [3, 5], 1: [3, 6, 7]},
              has_summative=False, parent='xb'),
    ClassSeed('xc', 'X c', 'TOM', 8, 'X-c sinif', {0: [6], 1: [2, 4], 2: [1, 2], 3: [6, 7], 4: [1]}, utis_class='10 c'),
    ClassSeed('xe', 'X e', 'TOM', 7, 'X-e sinif', {0: [2, 7], 1: [1, 5], 2: [6], 3: [5], 4: [6]}, utis_class='10 e'),   # istifadəçi təsdiqi 2026-09-28: X e = UTİS «10 e» (köhnə «X ə» vərəqi 10 ə idi – səhv)
    ClassSeed('xia', 'XI a', 'TOM', 7, 'XI-a sinif', {0: [4], 1: [], 2: [4, 5], 3: [2, 3], 4: [3, 4]}, utis_class='11 a 1'),
    ClassSeed('xip', 'XI peşə sinfi', 'adi', 4, 'XI peşə sinfi', {0: [1, 2], 1: [1], 2: [1]}),
]
CLASS_BY_CODE = {c.code: c for c in CLASSES}

SCHOOL_TOM = 'Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli tam orta ümumtəhsil məktəbi'
SCHOOL_ADI = 'Tərtər şəhər Rafiq Nuriyev adına 6 nömrəli ümumtəhsil məktəbi'


def school_title(kind: str) -> str:
    return SCHOOL_TOM if kind == 'TOM' else SCHOOL_ADI


def semester_of(d: dt.date) -> int:
    return 1 if d <= SEM1_END else 2


def is_school_day(d: dt.date, off: dict[dt.date, str] | None = None) -> bool:
    off = OFF_DAYS if off is None else off
    return YEAR_START <= d <= YEAR_END and d.weekday() < 5 and d not in off


def lesson_slots(slots: dict[int, list[int]], off: dict[dt.date, str] | None = None,
                 start: dt.date = YEAR_START, end: dt.date = YEAR_END) -> list[tuple[dt.date, int]]:
    """Cədvəl və təqvimə görə bütün dərs yuvaları (tarix, dərs saatı), xronoloji ardıcıllıqla."""
    out, d = [], start
    while d <= end:
        if is_school_day(d, off):
            for p in sorted(slots.get(d.weekday(), [])):
                out.append((d, p))
        d += dt.timedelta(days=1)
    return out


def check_plan_dates(plan_dates: list[dt.date], slots: dict[int, list[int]],
                     off: dict[dt.date, str] | None = None) -> dict:
    """Plandakı tarixləri cədvəl + təqvimdən hesablanan yuvalarla müqayisə edir. Planı dəyişmir, yalnız hesabat verir."""
    expected = [d for d, _ in lesson_slots(slots, off)]
    mismatches = []
    for i, (a, b) in enumerate(zip(plan_dates, expected), 1):
        if a != b:
            mismatches.append({'sira': i, 'planda': a.isoformat(), 'cedvelde': b.isoformat()})
    return {
        'plan_saat': len(plan_dates),
        'cedvel_saat': len(expected),
        'ferq': len(plan_dates) - len(expected),
        'uygunsuz_tarixler': len(mismatches),
        'ilk_uygunsuzluqlar': mismatches[:10],
        'tetile_dusen': [d.isoformat() for d in plan_dates if d in (OFF_DAYS if off is None else off)],
    }
