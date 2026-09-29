"""Müəllim köməkçisi – FastAPI tətbiqi."""
import logging
import tempfile
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import scheduler
from .api import admin, analytics, auth, bank, chat, classes, exams, homeroom, imports, invites, journal, materials, plan, printing, portal, school, students, tasks

def bootstrap():
    """İlk açılış (hostinq): miqrasiyalar + baza boşdursa məktəb, admin, tədris ili, siniflər, cədvəl.
    Şagirdlər və planlar serverə kodla getmir – Tənzimləmələrdən yüklənir."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select
    from .config import settings
    from .db import SessionLocal
    from .models import User
    from .security import hash_password
    ini = Path(__file__).resolve().parents[1] / 'alembic.ini'
    cfg = Config(str(ini))
    cfg.set_main_option('script_location', str(ini.parent / 'migrations'))
    command.upgrade(cfg, 'head')
    with SessionLocal() as db:
        # köhnə login (hesenov.ferid) -> ID (M-001) – həmişə
        old = db.scalar(select(User).where(User.login == 'hesenov.ferid'))
        if old and not db.scalar(select(User).where(User.login == settings().admin_login)):
            old.login = settings().admin_login
            db.commit()
    pw = settings().admin_password
    if not pw:
        return
    import hashlib
    from .models import AppState
    applied = hashlib.sha256(pw.encode()).hexdigest()
    from .models import Role
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            # MK_ADMIN_PASSWORD hostinqdə DƏYİŞDİRİLİBSƏ – admin parolu bir dəfə ona keçir
            # (tətbiqdə sonradan dəyişdirilən parol, env dəyişmədikcə pozulmur)
            st = db.get(AppState, 'admin_pw_applied')
            if st is None:
                st = AppState(key='admin_pw_applied', value='')
                db.add(st)
            if st.value != applied:
                u = (db.scalar(select(User).where(User.login == settings().admin_login))
                     or db.scalar(select(User).where(User.role == Role.admin).order_by(User.id)))
                if u:
                    u.password_hash = hash_password(pw)
                    u.failed_logins, u.locked_until = 0, None
                st.value = applied
                db.commit()
                logging.getLogger('bootstrap').info('admin parolu hostinq dəyişəni ilə yeniləndi')
            return
        from .seed import seed
        seed(db, login=settings().admin_login, utis_xlsx=Path('/nonexistent'), plans_dir=None,
             out_dir=Path(tempfile.gettempdir()))
        u = db.scalar(select(User).where(User.login == settings().admin_login))
        u.password_hash = hash_password(pw)
        db.merge(AppState(key='admin_pw_applied', value=applied))
        db.commit()
        logging.getLogger('bootstrap').info('ilk quraşdırma: admin %s yaradıldı', u.login)


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title='Müəllim köməkçisi', version='0.1.0', lifespan=lifespan)

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob: https:; media-src 'self' blob:; "
       "frame-src https://www.youtube-nocookie.com https://www.youtube.com; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")


@app.middleware('http')
async def security_headers(request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h.setdefault('X-Content-Type-Options', 'nosniff')
    h.setdefault('X-Frame-Options', 'DENY')
    h.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    h.setdefault('Permissions-Policy', 'camera=(self), microphone=(self), geolocation=()')
    h.setdefault('Content-Security-Policy', CSP)
    if request.url.path.startswith('/api/'):
        h.setdefault('Cache-Control', 'no-store')
    from .config import settings as _s
    if _s().cookie_secure:
        h.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return resp
app.include_router(auth.router)
app.include_router(bank.router)
app.include_router(school.router)
app.include_router(classes.router)
app.include_router(students.router)
app.include_router(plan.router)
app.include_router(journal.router)
app.include_router(exams.router)
app.include_router(tasks.router)
app.include_router(portal.router)
app.include_router(chat.router)
app.include_router(analytics.router)
app.include_router(homeroom.router)
app.include_router(imports.router)
app.include_router(materials.router)
app.include_router(invites.router)
app.include_router(admin.router)
app.include_router(printing.router)


@app.get('/api/health')
def health():
    return {'ok': True}


# ---------------------------------------------------------------- interfeys (frontend/dist) – tək xidmət kimi yayım
DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if DIST.is_dir():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def spa(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'Tapılmadı')
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / 'index.html', headers={'Cache-Control': 'no-cache'})
