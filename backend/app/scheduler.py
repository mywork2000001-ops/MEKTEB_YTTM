"""Arxa plan işləri: test bazasının avtomatik yenilənməsi (viktorina.html dəyişəndə özü yenilənir)."""
import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .bank.sync import run_sync
from .config import settings
from .db import SessionLocal

log = logging.getLogger('scheduler')
_sched: BackgroundScheduler | None = None


def _bank_job():
    with SessionLocal() as db:
        r = run_sync(db, 'auto')
        log.info('bank sync: %s +%s ~%s -%s', r.status, r.added, r.updated, r.deactivated)


def awake_now(hours: str, now: dt.datetime | None = None) -> bool:
    """«7-23» – Bakı vaxtı ilə 07:00 ≤ saat < 23:00."""
    from zoneinfo import ZoneInfo
    a, b = (int(x) for x in hours.split('-'))
    h = (now or dt.datetime.now(ZoneInfo('Asia/Baku'))).hour
    return a <= h < b


def _keepalive_job():
    import os
    import httpx
    url = settings().keepalive_url or os.environ.get('RENDER_EXTERNAL_URL')
    if not url or not awake_now(settings().keepalive_hours):
        return
    try:
        httpx.get(url.rstrip('/') + '/api/health', timeout=30)
    except Exception as e:                                   # noqa: BLE001
        log.warning('keepalive: %s', e)


def start():
    global _sched
    import os
    minutes = settings().bank_sync_minutes
    keep = bool(settings().keepalive_url or os.environ.get('RENDER_EXTERNAL_URL'))
    if _sched or (minutes <= 0 and not keep):
        return
    _sched = BackgroundScheduler(timezone='Asia/Baku')
    if keep:
        _sched.add_job(_keepalive_job, 'interval', minutes=10, id='keepalive', max_instances=1, coalesce=True)
    if minutes <= 0:
        _sched.start()
        return
    # ilk yoxlama işə düşəndən 1 dəqiqə sonra, sonra hər N dəqiqədən bir; üst-üstə düşmür
    _sched.add_job(_bank_job, 'interval', minutes=minutes, id='bank_sync', max_instances=1, coalesce=True,
                   next_run_time=dt.datetime.now() + dt.timedelta(minutes=1))
    _sched.start()


def stop():
    global _sched
    if _sched:
        _sched.shutdown(wait=False)
        _sched = None
