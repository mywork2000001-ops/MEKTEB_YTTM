"""Müəllim köməkçisi – FastAPI tətbiqi."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import scheduler
from .api import auth, bank, chat, classes, exams, journal, plan, portal, school, students, tasks

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


@app.get('/api/health')
def health():
    return {'ok': True}
