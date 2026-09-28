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


def start():
    global _sched
    minutes = settings().bank_sync_minutes
    if minutes <= 0 or _sched:
        return
    _sched = BackgroundScheduler(timezone='Asia/Baku')
    # ilk yoxlama işə düşəndən 1 dəqiqə sonra, sonra hər N dəqiqədən bir; üst-üstə düşmür
    _sched.add_job(_bank_job, 'interval', minutes=minutes, id='bank_sync', max_instances=1, coalesce=True,
                   next_run_time=dt.datetime.now() + dt.timedelta(minutes=1))
    _sched.start()


def stop():
    global _sched
    if _sched:
        _sched.shutdown(wait=False)
        _sched = None
