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
SESSION_MAX_AGE = 60 * 60 * 24 * 180          # 180 gün – hər istifadədə yenilənir (telefonda bir dəfə daxil ol)
SESSION_RENEW_AFTER = 60 * 60 * 24             # sessiya 1 gündən köhnədirsə, /me zamanı yenisi verilir
QR_MAX_AGE = 60 * 60 * 24 * 365                # giriş vərəqəsindəki QR bir tədris ili etibarlıdır
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


def session_age(token: str | None) -> float | None:
    """Sessiyanın yaşı (saniyə) – yeniləmə üçün."""
    if not token:
        return None
    try:
        _, ts = _ser().loads(token, max_age=SESSION_MAX_AGE, return_timestamp=True)
        return (dt.datetime.now(dt.timezone.utc) - ts).total_seconds()
    except (BadSignature, SignatureExpired):
        return None


def _qr() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings().secret_key, salt='mk-qr-login')


def make_qr_token(user_id: int, pw_hash: str) -> str:
    """Giriş vərəqəsindəki QR: kamera ilə oxunur → avtomatik giriş. PIN dəyişəndə etibarsız olur (hash barmaq izi)."""
    return _qr().dumps({'u': user_id, 'p': pw_hash[-12:]})


def read_qr_token(token: str) -> dict | None:
    try:
        return _qr().loads(token, max_age=QR_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def _fernet(purpose: str = 'mk-pin'):
    import base64, hashlib
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256((purpose + ':' + settings().secret_key).encode()).digest())
    return Fernet(key)


def secret_encrypt(text: str) -> str:
    """Müəllimin API açarı – serverin açarı ilə şifrələnir, heç vaxt geri göstərilmir (yalnız son 4 simvol)."""
    return _fernet('mk-ai-key').encrypt(text.encode()).decode()


def secret_decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet('mk-ai-key').decrypt(token.encode()).decode()
    except Exception:                                        # noqa: BLE001 – açar dəyişibsə
        return None


def pin_encrypt(pin: str) -> str:
    """İlkin PIN – giriş vərəqəsi çapı üçün serverin açarı ilə şifrələnir (şagird dəyişəndə silinir)."""
    return _fernet().encrypt(pin.encode()).decode()


def pin_decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:                                        # noqa: BLE001 – açar dəyişibsə
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
