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


# ---------------------------------------------------------------- məlumat sağlamlığı (yalnız oxuma)
@router.get('/roster-health')
def roster_health(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Sinif/şagird/proqram/jurnal məlumatının sağlamlığı: say + ən çox 50 nümunə (yalnız id, ad, sinif). Heç nə yazmır."""
    from sqlalchemy import func
    from ..models import Attendance, AuditLog, GroupMember, JournalEntry, Mark, SchoolClass, Student, TeachingAssignment
    from ..services import class_grade
    from .classes import _ctx
    from .common import current_year, need_school
    from .students import dup_pairs
    sid = need_school(user)
    year = current_year(db, sid)
    cats: dict[str, dict] = {}

    def put(key: str, rows: list[dict]):
        cats[key] = {'count': len(rows), 'examples': rows[:50]}

    classes = list(db.scalars(select(SchoolClass).where(SchoolClass.school_id == sid, SchoolClass.year_id == year.id,
                                                        SchoolClass.archived_at.is_(None)).order_by(SchoolClass.name)))
    cname = {c.id: c.name for c in classes}
    ctx = _ctx(db, classes, user)
    one = lambda c: {'id': c.id, 'name': c.name, 'class': c.name}
    put('classes_no_students', [one(c) for c in classes if ctx['prim'].get(c.id, 0) + ctx['extra'].get(c.id, 0) == 0])
    put('classes_no_teacher', [one(c) for c in classes if not ctx['teachers'].get(c.id)])
    put('classes_no_grade', [one(c) for c in classes if c.kind != 'qrup' and class_grade(db, c) is None])

    studs = list(db.scalars(select(Student).where(Student.school_id == sid, Student.archived_at.is_(None))
                            .order_by(Student.full_name)))
    srow = lambda s: {'id': s.id, 'name': s.full_name, 'class': cname.get(s.class_id)}
    put('students_no_account', [srow(s) for s in studs if not s.user_id])
    uids = [s.user_id for s in studs if s.user_id and not s.initial_pin]
    logged = set(db.scalars(select(AuditLog.user_id).where(AuditLog.user_id.in_(uids)).distinct())) if uids else set()
    put('students_pin_unknown', [srow(s) for s in studs if not s.initial_pin and (not s.user_id or s.user_id not in logged)])
    put('students_no_birth_date', [srow(s) for s in studs if not s.birth_date])

    tas = list(db.execute(select(TeachingAssignment, SchoolClass.name).join(SchoolClass, SchoolClass.id == TeachingAssignment.class_id)
                          .where(SchoolClass.school_id == sid, SchoolClass.year_id == year.id, SchoolClass.archived_at.is_(None),
                                 TeachingAssignment.archived_at.is_(None))))
    put('assignments_no_program', [{'id': t.id, 'name': f'{cn} – {t.subject}', 'class': cn} for t, cn in tas if not t.program_id])

    pairs = dup_pairs(db, sid)
    put('duplicate_pairs', [{'id': p['a'].id, 'name': f"{p['a'].full_name} ≈ {p['b'].full_name}",
                             'class': f"{p['class_a']} / {p['class_b']}"} for p in pairs])

    # sinfin tərkibi (əsas sinif + əlavə üzvlər; qrupda yalnız üzvlər)
    members: dict[int, set[int]] = {}
    for s in studs:
        members.setdefault(s.class_id, set()).add(s.id)
    active_ids = {s.id for s in studs}
    for gid, stid in db.execute(select(GroupMember.group_id, GroupMember.student_id)):
        if stid in active_ids and gid in cname:
            members.setdefault(gid, set()).add(stid)
    ta_by_id = {t.id: (t, cn) for t, cn in tas}

    if ta_by_id:
        ids = list(ta_by_id)
        # yazılmış dərslər (auto=False), harada ki, tərkibin hamısı üçün davamiyyət yoxdur
        entries = list(db.execute(select(JournalEntry.id, JournalEntry.assignment_id, JournalEntry.date)
                                  .where(JournalEntry.assignment_id.in_(ids), JournalEntry.auto.is_(False))
                                  .order_by(JournalEntry.date.desc())))
        att = dict(db.execute(select(Attendance.entry_id, func.count()).join(Student, Student.id == Attendance.student_id)
                              .join(JournalEntry, JournalEntry.id == Attendance.entry_id)
                              .where(JournalEntry.assignment_id.in_(ids), Student.archived_at.is_(None))
                              .group_by(Attendance.entry_id)).all())
        part = []
        for eid, taid, d in entries:
            t, cn = ta_by_id[taid]
            n = len(members.get(t.class_id, ()))
            if n and att.get(eid, 0) < n:
                part.append({'id': eid, 'name': f'{cn} – {t.subject}, {d:%d.%m.%Y}', 'class': cn})
        put('lessons_attendance_incomplete', part)

        # formativ qiyməti 14 gündən çoxdur olmayan şagird (dərs bağlılığı üzrə)
        first = dict(db.execute(select(JournalEntry.assignment_id, func.min(JournalEntry.date))
                                .where(JournalEntry.assignment_id.in_(ids), JournalEntry.auto.is_(False))
                                .group_by(JournalEntry.assignment_id)).all())
        last = {(a, s): d for a, s, d in db.execute(
            select(JournalEntry.assignment_id, Mark.student_id, func.max(JournalEntry.date))
            .join(Mark, Mark.entry_id == JournalEntry.id).where(JournalEntry.assignment_id.in_(ids))
            .group_by(JournalEntry.assignment_id, Mark.student_id))}
        edge = dt.date.today() - dt.timedelta(days=14)
        names = {s.id: s.full_name for s in studs}
        stale = []
        for taid, (t, cn) in ta_by_id.items():
            if taid not in first:
                continue                                    # hələ dərs yazılmayıb
            for stid in sorted(members.get(t.class_id, ())):
                if (last.get((taid, stid)) or first[taid]) <= edge:
                    stale.append({'id': stid, 'name': names.get(stid, ''), 'class': f'{cn} – {t.subject}'})
        put('students_no_recent_mark', stale)
    else:
        put('lessons_attendance_incomplete', [])
        put('students_no_recent_mark', [])
    return {'school_id': sid, 'year': year.name, 'categories': cats}
