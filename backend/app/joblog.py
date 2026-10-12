"""Fon işlərinin jurnalı (docs/qalan-isler-promtu.md A1): Render loqunu müəllim görmür – fon işlərinin INFO/xəta mesajları
bazada (AppState «job_log», son 80 qeyd) saxlanır və Tənzimləmələr → Jurnal → «Son fon işləri»ndə göstərilir."""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading

KEY = 'job_log'
KEEP = 80
LOGGERS = ('scheduler', 'bootstrap', 'bank', 'auto_tests', 'app.domain.ksq_reader', 'app.api.exam_scans', 'joblog')
_busy = threading.local()


class DbLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_busy, 'on', False):                     # öz yazısı zamanı yaranan loq – təkrar girmə
            return
        _busy.on = True
        try:
            from .db import SessionLocal
            from .models import AppState
            item = {'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'name': record.name,
                    'level': record.levelname, 'msg': record.getMessage()[:400]}
            with SessionLocal() as db:
                st = db.get(AppState, KEY)
                rows = json.loads(st.value) if st and st.value else []
                rows = [*rows, item][-KEEP:]
                if st is None:
                    db.add(AppState(key=KEY, value=json.dumps(rows, ensure_ascii=False)))
                else:
                    st.value = json.dumps(rows, ensure_ascii=False)
                db.commit()
        except Exception:                                     # noqa: BLE001 – jurnal yazılmasa tətbiq işləməyə davam edir
            pass
        finally:
            _busy.on = False


def install() -> None:
    h = DbLogHandler(level=logging.INFO)
    for name in LOGGERS:
        lg = logging.getLogger(name)
        if not any(isinstance(x, DbLogHandler) for x in lg.handlers):
            lg.addHandler(h)


def read(db) -> list[dict]:
    from .models import AppState
    st = db.get(AppState, KEY)
    return list(reversed(json.loads(st.value))) if st and st.value else []
