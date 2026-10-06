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


def _topic_journal_job():
    """Bağlanmış mövzu testlərinin nəticəsi formativ jurnala (mövzunun dərsinə)."""
    from .task_journal import run_due
    with SessionLocal() as db:
        n = run_due(db)
        if n:
            log.info('mövzu testi → jurnal: %s test', n)


def _auto_tests_job():
    """Avtomatik mövzu testləri – bu günün dərslərinə (sinifdə «auto_tests» açıqdırsa)."""
    from .auto_tests import run
    with SessionLocal() as db:
        n = run(db)
        if n:
            log.info('avtomatik mövzu testi: %s', n)


def _exam_series_job():
    """Sınaq seriyaları: vaxtı çatan yuvaya növbəti sınaq, bankdakı yeni sınaqlar növbəyə."""
    from .api.exam_series import run_series
    with SessionLocal() as db:
        n = run_series(db)
        if n:
            log.info('sınaq seriyası: %s sınaq', n)


def _certificates_job():
    """Sertifikatlar: bağlanmış sınaqlar, seriyalar, buraxılmış mövzu testləri (app/certificates.py)."""
    from .certificates import issue_due
    with SessionLocal() as db:
        n = issue_due(db)
        if n:
            log.info('sertifikat: %s', n)


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
    if _sched:                                   # mövzu testi → jurnal işi həmişə lazımdır
        return
    _sched = BackgroundScheduler(timezone='Asia/Baku')
    _sched.add_job(_topic_journal_job, 'interval', minutes=15, id='topic_journal', max_instances=1, coalesce=True)
    _sched.add_job(_certificates_job, 'interval', minutes=15, id='certificates', max_instances=1, coalesce=True,
                   next_run_time=dt.datetime.now() + dt.timedelta(minutes=4))
    _sched.add_job(_exam_series_job, 'interval', minutes=15, id='exam_series', max_instances=1, coalesce=True,
                   next_run_time=dt.datetime.now() + dt.timedelta(minutes=3))
    _sched.add_job(_auto_tests_job, 'interval', minutes=15, id='auto_tests', max_instances=1, coalesce=True,
                   next_run_time=dt.datetime.now() + dt.timedelta(minutes=2))
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
