"""Müddətsiz testlər (miqrasiyasız): `duration_min == 0` – taymer yoxdur, `closes_at == NO_DEADLINE` – son tarix yoxdur.
Bütün modullar (portal, tasks, exams_online, exam_series, topic_tests, auto_tests) vaxt hesabını yalnız buradan alır.
KSQ/BSQ (ksq_online) və viktorina bu qaydaya tabe deyil."""
from __future__ import annotations

import datetime as dt

NO_DEADLINE = dt.datetime(2100, 1, 1, tzinfo=dt.timezone.utc)
UNLIMITED_MIN = 0
NOT_DONE = 'işlənməyib'        # müddətsiz test açıqdır, şagird hələ təhvil verməyib (hesabat statusu)

GIVEN = ('yazıb', 'yazmayıb', NOT_DONE)     # «təyin olunub» sayılan statuslar (yazıb/təyin hesabı)


def _aware(t: dt.datetime) -> dt.datetime:
    return t.astimezone(dt.timezone.utc) if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def is_unlimited(t) -> bool:
    """Son tarix yoxdur (OnlineTask və ya closes_at olan hər şey)."""
    return _aware(t.closes_at) >= NO_DEADLINE


def no_timer(t) -> bool:
    return not t.duration_min


def closes_or_none(c: dt.datetime | None) -> dt.datetime:
    """Müəllim bağlanma tarixi verməyibsə – son tarix yoxdur."""
    return _aware(c) if c else NO_DEADLINE


def attempt_deadline(t, start: dt.datetime) -> dt.datetime:
    """Şagirdin cəhdinin bitmə vaxtı: taymer yoxdursa – testin bağlanması (müddətsizdə NO_DEADLINE)."""
    closes = _aware(t.closes_at)
    if no_timer(t):
        return closes
    return min(_aware(start) + dt.timedelta(minutes=t.duration_min), closes)


def fits_window(duration_min: int, opens: dt.datetime, closes: dt.datetime) -> bool:
    """Həll müddəti açıq qalma aralığına sığır (0 – həmişə sığır)."""
    return not duration_min or duration_min <= (_aware(closes) - _aware(opens)).total_seconds() / 60
