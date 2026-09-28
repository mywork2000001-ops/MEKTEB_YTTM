"""Müəllim köməkçisi – FastAPI tətbiqi."""
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import scheduler
from .api import analytics, auth, bank, chat, classes, exams, journal, plan, portal, school, students, tasks

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title='Müəllim köməkçisi', version='0.1.0', lifespan=lifespan)
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
