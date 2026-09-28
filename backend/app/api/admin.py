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
