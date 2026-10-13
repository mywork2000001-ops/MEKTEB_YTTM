"""Admin: ehtiyat nüsxə (JSON ixrac). Pulsuz hostinq bazası silinə bilər – müntəzəm endirin.
Geri yükləmə: tools/restore_backup.py (yeni boş bazaya, məs. Neon)."""
import base64
import datetime as dt
import decimal
import json

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Base, get_db
from ..deps import admin_only
from ..models import User
from .common import audit

router = APIRouter(prefix='/api/admin', tags=['admin'])


@router.get('/jobs')
def jobs(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Son fon işləri (app/joblog.py): bank, sertifikat, kart oxunuşu, avtomatik testlər, xətalar."""
    from ..joblog import read
    return read(db)


@router.get('/resources')
def resources(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Pulsuz hostinq limitləri üçün: bazanın ölçüsü, fayllar (file_blobs), bu ay kart skanı və Claude oxunuşu."""
    from sqlalchemy import func, text
    from ..models import ExamScan
    from ..storage import DbStorage
    size = None
    try:
        if db.bind.dialect.name == 'postgresql':
            size = db.scalar(text('select pg_database_size(current_database())'))
        else:
            size = db.scalar(text('select page_count * page_size from pragma_page_count(), pragma_page_size()'))
    except Exception:                                   # noqa: BLE001
        size = None
    m0 = dt.datetime.now(dt.timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    scans = db.scalar(select(func.count()).select_from(ExamScan).where(ExamScan.created_at >= m0)) or 0
    read = db.scalar(select(func.count()).select_from(ExamScan).where(ExamScan.updated_at >= m0, (ExamScan.read_by.like('claude%') | ExamScan.read_by.like('openrouter%') | ExamScan.read_by.like('gemini%')))) or 0
    from ..config import settings
    from ..domain.ksq_reader import month_usage
    return {'db_bytes': size, 'files_bytes': DbStorage.used_bytes(db), 'scans_month': scans, 'claude_reads_month': read,
            'ai_usage': {**month_usage(db), 'limit': settings().ksq_monthly_limit},
            'limits': {'neon_storage_bytes': 512 * 1024 * 1024, 'render_hours': 750}}
SKIP = {'file_blobs'}                               # fayllar ayrıca (həcmli) – ixraca daxil deyil


def _val(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, bytes):
        return {'$b64': base64.b64encode(v).decode()}
    if isinstance(v, decimal.Decimal):
        return float(v)
    if hasattr(v, 'value'):                         # Enum
        return v.value
    return v


@router.get('/backup')
def backup(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    data = {'format': 'muellim-komekcisi-backup', 'version': 1, 'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'tables': {}}
    for t in Base.metadata.sorted_tables:
        if t.name in SKIP:
            continue
        data['tables'][t.name] = [{k: _val(v) for k, v in row._mapping.items()} for row in db.execute(select(t))]
    audit(db, user, 'export', 'backup', None, tables=len(data['tables']))
    db.commit()
    name = f'muellim-komekcisi-{dt.date.today():%Y%m%d}.json'
    return Response(json.dumps(data, ensure_ascii=False), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="{name}"'})
