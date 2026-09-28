"""Domen qaydaları: səviyyə, KSQ/BSQ qiyməti, risk balı, reytinq. Bütün hədlər və çəkilər parametrdir (Settings)."""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------- parametrlər (standart dəyərlər)
LEVEL_HIGH = 70.0     # Yüksək >= 70
LEVEL_MID = 40.0      # Orta 40–69,9; Zəif < 40

# KSQ/BSQ: faizin yuxarı sərhədi -> qiymət (0–30 → 2, 31–60 → 3, 61–80 → 4, 81–100 → 5)
GRADE_BANDS: list[tuple[float, int]] = [(30, 2), (60, 3), (80, 4), (100, 5)]

RISK_WEIGHTS = {
    'ix_riyaziyyat': 25,     # IX sinif riyaziyyat balı < 40
    'formativ': 25,          # son 5 formativ qiymətin ortası < 3
    'ksq': 20,               # son KSQ < 31%
    'davamiyyet': 15,        # davamiyyət < 85%
    'tapshiriq': 15,         # tapşırıq icrası < 60%
}
RISK_THRESHOLDS = {'ix_riyaziyyat': 40, 'formativ': 3.0, 'ksq': 31, 'davamiyyet': 85, 'tapshiriq': 60}
RISK_YELLOW, RISK_RED = 30, 60

RATING_WEIGHTS = {'qiymet': 0.40, 'ksq': 0.30, 'tapshiriq': 0.15, 'davamiyyet': 0.15}
ABSENCE_WARN_PCT = 25.0


def level(score: float | None, high: float = LEVEL_HIGH, mid: float = LEVEL_MID) -> str | None:
    if score is None:
        return None
    if score >= high:
        return 'Yüksək'
    if score >= mid:
        return 'Orta'
    return 'Zəif'


def percent(points: float, max_points: float) -> float:
    if max_points <= 0:
        raise ValueError('Maksimal bal müsbət olmalıdır')
    if points < 0 or points > max_points:
        raise ValueError('Bal 0 ilə maksimal bal arasında olmalıdır')
    return round(points / max_points * 100, 1)


def round_half_up(x: float) -> int:
    """Adi (məktəb) yuvarlaqlaşdırması: 2,5 → 3. Python round() «bank» üsuludur (2,5 → 2) – işlətmə."""
    from decimal import Decimal, ROUND_HALF_UP
    return int(Decimal(str(x)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def summative_grade(pct: float, bands: list[tuple[float, int]] = GRADE_BANDS) -> int:
    """Faiz -> qiymət. Hədlər tam faizlə verilir (30 → 0–30, 31–60 ...); kəsr faiz yuxarı həddə görə müqayisə olunur:
    30,4% hələ 2 sayılır, 30,5% və yuxarı 3 (məktəb qaydası dəqiqləşərsə, hədlər Parametrlər bölməsindən dəyişir)."""
    p = round_half_up(pct)
    for upper, grade in bands:
        if p <= upper:
            return grade
    return bands[-1][1]


# ---------------------------------------------------------------- risk
@dataclass
class RiskInput:
    ix_math: float | None = None             # IX sinif riyaziyyat balı (0–100)
    last_formative: list[int] = field(default_factory=list)   # xronoloji
    last_ksq_pct: float | None = None
    attendance_pct: float | None = None
    homework_pct: float | None = None


@dataclass
class RiskResult:
    score: int
    status: str        # Yaşıl | Sarı | Qırmızı
    factors: list[dict]


def risk_score(x: RiskInput, w: dict = RISK_WEIGHTS, t: dict = RISK_THRESHOLDS,
               yellow: int = RISK_YELLOW, red: int = RISK_RED) -> RiskResult:
    """Şəffaf risk balı: hər amil ya tam çəkisini verir, ya 0. Məlumat yoxdursa amil nəzərə alınmır (izahda yazılır)."""
    factors = []

    def add(key, label, value, bad, shown):
        if value is None:
            factors.append({'amil': key, 'izah': f'{label}: məlumat yoxdur', 'bal': 0})
            return 0
        pts = w[key] if bad else 0
        factors.append({'amil': key, 'izah': f'{label}: {shown}', 'bal': pts})
        return pts

    s = 0
    s += add('ix_riyaziyyat', 'IX sinif riyaziyyat balı', x.ix_math,
             x.ix_math is not None and x.ix_math < t['ix_riyaziyyat'], fmt(x.ix_math))
    f5 = x.last_formative[-5:]
    avg = sum(f5) / len(f5) if f5 else None
    s += add('formativ', f'Son {len(f5)} formativ qiymətin ortası', avg,
             avg is not None and avg < t['formativ'], fmt(avg, 2))
    s += add('ksq', 'Son KSQ', x.last_ksq_pct,
             x.last_ksq_pct is not None and x.last_ksq_pct < t['ksq'], fmt(x.last_ksq_pct) + '%')
    s += add('davamiyyet', 'Davamiyyət', x.attendance_pct,
             x.attendance_pct is not None and x.attendance_pct < t['davamiyyet'], fmt(x.attendance_pct) + '%')
    s += add('tapshiriq', 'Tapşırıq icrası', x.homework_pct,
             x.homework_pct is not None and x.homework_pct < t['tapshiriq'], fmt(x.homework_pct) + '%')
    status = 'Qırmızı' if s >= red else 'Sarı' if s >= yellow else 'Yaşıl'
    return RiskResult(s, status, factors)


def fmt(v: float | None, digits: int = 1) -> str:
    """Azərbaycan formatı: onluq ayırıcı vergül."""
    if v is None:
        return '—'
    return f'{v:.{digits}f}'.replace('.', ',')


# ---------------------------------------------------------------- reytinq
def rating_score(avg_grade: float | None, ksq_avg_pct: float | None, homework_pct: float | None,
                 attendance_pct: float | None, w: dict = RATING_WEIGHTS) -> float | None:
    """0–100 şkalası. Qiymət ortası 2–5 → 0–100. Məlumatı olmayan komponentin çəkisi qalanlara bölünür;
    qiymət və KSQ-nin ikisi də yoxdursa – reytinq yoxdur."""
    comps = {
        'qiymet': None if avg_grade is None else (avg_grade - 2) / 3 * 100,
        'ksq': ksq_avg_pct,
        'tapshiriq': homework_pct,
        'davamiyyet': attendance_pct,
    }
    have = {k: v for k, v in comps.items() if v is not None}
    if comps['qiymet'] is None and comps['ksq'] is None:
        return None          # yalnız davamiyyət/ev tapşırığı ilə reytinq verilmir (nəticə göstəricisi lazımdır)
    tw = sum(w[k] for k in have)
    return round(sum(w[k] * v for k, v in have.items()) / tw, 1)


def rank(items: list[tuple[str, float | None]]) -> list[tuple[str, float | None, int | None]]:
    """Bərabər bal – eyni yer (1, 2, 2, 4). Balı olmayanlar sonda, yersiz."""
    scored = sorted([i for i in items if i[1] is not None], key=lambda i: -i[1])
    out, prev, place = [], None, 0
    for n, (k, v) in enumerate(scored, 1):
        if v != prev:
            place, prev = n, v
        out.append((k, v, place))
    return out + [(k, None, None) for k, v in items if v is None]


def absence_warning(missed: int, total: int, limit_pct: float = ABSENCE_WARN_PCT) -> bool:
    return total > 0 and missed / total * 100 > limit_pct


def semester_grade(ksq_grades: list[int], bsq_grade: int | None) -> int | None:
    """Yarımil qiyməti = (KSQ qiymətləri cəmi / sayı) × 0,4 + BSQ × 0,6, adi yuvarlaqlaşdırma.
    KSQ və ya BSQ yoxdursa qiymət çıxarılmır (None)."""
    if not ksq_grades or bsq_grade is None:
        return None
    from decimal import Decimal, ROUND_HALF_UP
    v = Decimal(sum(ksq_grades)) / len(ksq_grades) * Decimal('0.4') + Decimal(bsq_grade) * Decimal('0.6')
    return int(v.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def grade_from_points(points: float, max_points: float) -> int:
    """KSQ/BSQ bal → qiymət. Faiz xam dəyərdən hesablanır (ikiqat yuvarlaqlaşdırma olmasın)."""
    if max_points <= 0:
        raise ValueError('Maksimal bal 0-dan böyük olmalıdır')
    return summative_grade(points / max_points * 100)
