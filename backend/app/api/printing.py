"""PDF: interfeysin hazırladığı çap sənədi (HTML) serverdə Chromium ilə A4 PDF-ə çevrilir.
Təhlükəsizlik: JavaScript söndürülür, heç bir xarici sorğu edilmir (yalnız data: şəkillər/şriftlər), ölçü limiti,
eyni anda bir sənəd (pulsuz serverin yaddaşı)."""
from __future__ import annotations

import os
import re
import threading
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import User
from .common import audit

router = APIRouter(prefix='/api/print', tags=['print'])
_lock = threading.Lock()
MAX_HTML = 4 * 1024 * 1024


class PdfIn(BaseModel):
    html: str = Field(min_length=10, max_length=MAX_HTML)
    title: str = Field('sened', max_length=120)
    landscape: bool = False


def render_pdf(html: str, landscape: bool = False) -> bytes:
    from playwright.sync_api import sync_playwright
    from ..bank.sync import CHROME_DEFAULTS
    from ..config import settings
    exe = settings().chrome_path or next((p for p in CHROME_DEFAULTS if os.path.exists(p)), None)
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        try:
            ctx = b.new_context(java_script_enabled=False)
            page = ctx.new_page()
            page.route('**/*', lambda r: r.continue_() if r.request.url.startswith(('data:', 'about:')) else r.abort())
            page.set_content(html, wait_until='load', timeout=30_000)
            # sənədin CSS-i (@page: A4, kənarlar, altbilgidə tarix və «Səhifə X / Y») əsasdır
            return page.pdf(format='A4', landscape=landscape, print_background=True, prefer_css_page_size=True,
                            margin={'top': '12mm', 'bottom': '15mm', 'left': '12mm', 'right': '12mm'})
        finally:
            b.close()


@router.post('/pdf')
def pdf(body: PdfIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not _lock.acquire(timeout=60):
        raise HTTPException(503, 'Server məşğuldur – bir az sonra yenidən yoxlayın')
    try:
        data = render_pdf(body.html, body.landscape)
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(500, f'PDF hazırlanmadı: {str(e)[:120]}')
    finally:
        _lock.release()
    name = re.sub(r'[^\w\- .]+', '', body.title, flags=re.U).strip() or 'sened'
    audit(db, user, 'export', 'pdf', None, title=body.title[:80])
    db.commit()
    return Response(data, media_type='application/pdf',
                    headers={'Content-Disposition': f"attachment; filename=\"sened.pdf\"; filename*=UTF-8''{quote(name)}.pdf"})
