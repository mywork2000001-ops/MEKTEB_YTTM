"""Parollar (argon2), sessiya kukisi (imzalı), girişə limit."""
from __future__ import annotations

import datetime as dt
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

_ph = PasswordHasher()
# Şagird PIN-i (4 rəqəm) üçün yüngül parametrlər: onlayn təxmini hesab kilidi qoruyur; pulsuz serverdə 76 PIN tez hazırlanır
_ph_pin = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
SESSION_COOKIE = 'mk_session'
SESSION_MAX_AGE = 60 * 60 * 24 * 14           # 14 gün
MAX_FAILED = 5                                 # 5 səhv cəhd -> 15 dəqiqə kilid
LOCK_MINUTES = 15


def hash_password(p: str) -> str:
    return (_ph_pin if len(p) == 4 and p.isdigit() else _ph).hash(p)


def verify_password(h: str, p: str) -> bool:
    try:
        return _ph.verify(h, p)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _ser() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings().secret_key, salt='mk-session')


def make_session(user_id: int, pw_hash: str) -> str:
    # parol dəyişəndə köhnə sessiyalar etibarsız olsun deyə hash-in son hissəsi daxil edilir
    return _ser().dumps({'u': user_id, 'p': pw_hash[-12:]})


def read_session(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        return _ser().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def new_pin() -> str:
    return f'{secrets.randbelow(10000):04d}'


def new_password(n: int = 10) -> str:
    alphabet = 'abcdefghjkmnpqrstuvwxyzACDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(secrets.choice(alphabet) for _ in range(n))


def is_locked(locked_until: dt.datetime | None) -> bool:
    if not locked_until:
        return False
    if locked_until.tzinfo is None:                          # SQLite tz saxlamır
        locked_until = locked_until.replace(tzinfo=dt.timezone.utc)
    return locked_until > dt.datetime.now(dt.timezone.utc)
