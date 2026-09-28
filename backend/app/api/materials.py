"""Materiallar: müəllim sinfə/qrupa PDF (və ya başqa fayl) tapşırıq, video link dərs, link və ya qeyd göndərir.
Tapşırıqda şagird cavab (fayl və ya mətn) təhvil verir; müəllim qiymət və şərh yazır.
Fayllar ortaq saxlamada (MK_STORAGE: db / gdrive / local)."""
from __future__ import annotations

import datetime as dt
from typing import Literal
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user, require, staff
from ..models import GroupMember, Material, MaterialSubmission, Role, SchoolClass, Student, TeachingAssignment, User, now
from ..services import own_assignment, roster
from ..storage import get_storage, storage_for_key, upload_limit
from .common import audit, get_or_404

router = APIRouter(prefix='/api', tags=['materials'])
student_only = require(Role.student)
FILE_TYPES = {'application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'audio/mpeg', 'audio/webm',
              'audio/ogg', 'audio/mp4', 'video/mp4', 'video/webm', 'video/quicktime',
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/msword'}


def aware(t: dt.datetime | None) -> dt.datetime | None:
    return t if t is None or t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _save_file(db: Session, f: UploadFile) -> tuple[str, str, str, int]:
    ctype = (f.content_type or '').split(';')[0]
    if ctype not in FILE_TYPES:
        raise HTTPException(400, 'Fayl növü qəbul edilmir (PDF, Word, PowerPoint, şəkil, səs, video)')
    key, size = get_storage().save(f.file, (f.filename or 'fayl')[:200], ctype, upload_limit(), db)
    if not size:
        raise HTTPException(400, 'Fayl boşdur')
    return key, (f.filename or 'fayl')[:200], ctype, size


def _file_out(kind: str, obj_id: int, o) -> dict | None:
    if not o.file_key:
        return None
    return {'name': o.file_name, 'type': o.file_type, 'size': o.file_size, 'url': f'/api/files/{kind}/{obj_id}'}


def material_out(m: Material) -> dict:
    return {'id': m.id, 'kind': m.kind, 'title': m.title, 'body': m.body, 'url': m.url, 'due_at': aware(m.due_at),
            'needs_submission': m.needs_submission, 'student_ids': m.student_ids, 'created_at': aware(m.created_at),
            'file': _file_out('material', m.id, m)}


def _stream(o, db: Session):
    st = storage_for_key(o.file_key)
    if st.kind == 'local':
        from fastapi.responses import FileResponse
        return FileResponse(st.root / o.file_key, media_type=o.file_type, filename=o.file_name)
    return StreamingResponse(st.stream(o.file_key, db), media_type=o.file_type, headers={
        'Content-Length': str(o.file_size), 'Content-Disposition': f"inline; filename*=UTF-8''{quote(o.file_name)}"})


# ---------------------------------------------------------------- müəllim
@router.post('/materials/{ta_id}')
def create_material(ta_id: int, kind: Literal['task', 'video', 'link', 'note'] = Form(...),
                    title: str = Form(..., min_length=2, max_length=200), body: str | None = Form(None),
                    url: str | None = Form(None), due_at: dt.datetime | None = Form(None),
                    needs_submission: bool = Form(False), student_ids: str | None = Form(None),
                    file: UploadFile | None = File(None), user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    if url:
        u = urlparse(url.strip())
        if u.scheme not in ('http', 'https') or not u.netloc:
            raise HTTPException(400, 'Link http:// və ya https:// ilə başlamalıdır')
    if kind in ('video', 'link') and not url:
        raise HTTPException(400, 'Video/link üçün ünvan lazımdır')
    if kind == 'task' and not (file and file.filename) and not (body or '').strip():
        raise HTTPException(400, 'Tapşırıq üçün fayl (PDF) və ya mətn lazımdır')
    ids = None
    if student_ids:
        ids = [int(x) for x in student_ids.split(',') if x.strip().isdigit()]
        if not ids or set(ids) - {s.id for s in roster(db, ta)}:
            raise HTTPException(400, 'Şagirdlər bu sinifdən/qrupdan seçilməlidir')
    m = Material(assignment_id=ta.id, kind=kind, title=title.strip(), body=(body or '').strip() or None,
                 url=url.strip() if url else None, due_at=aware(due_at),
                 needs_submission=needs_submission or kind == 'task', student_ids=ids, created_by=user.id)
    if file and file.filename:
        m.file_key, m.file_name, m.file_type, m.file_size = _save_file(db, file)
    db.add(m)
    db.flush()
    audit(db, user, 'create', 'material', m.id, kind=kind)
    db.commit()
    return material_out(m)


@router.get('/materials/{ta_id}')
def list_materials(ta_id: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    n = len(roster(db, ta))
    out = []
    for m in db.scalars(select(Material).where(Material.assignment_id == ta.id, Material.archived_at.is_(None))
                        .order_by(Material.created_at.desc())):
        subs = db.scalars(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id)).all()
        out.append({**material_out(m), 'submitted': len(subs), 'graded': sum(s.grade is not None for s in subs),
                    'targets': len(m.student_ids) if m.student_ids else n})
    return out


@router.get('/materials/{ta_id}/{mid}/submissions')
def submissions(ta_id: int, mid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    m = get_or_404(db, Material, mid, 'Material')
    if m.assignment_id != ta.id:
        raise HTTPException(404, 'Material tapılmadı')
    subs = {s.student_id: s for s in db.scalars(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id))}
    rows = []
    for st in roster(db, ta):
        if m.student_ids and st.id not in m.student_ids:
            continue
        s = subs.get(st.id)
        rows.append({'student_id': st.id, 'full_name': st.full_name, 'submission': s and {
            'id': s.id, 'text': s.text, 'submitted_at': aware(s.submitted_at), 'late': s.late, 'grade': s.grade,
            'comment': s.comment, 'file': _file_out('submission', s.id, s)}})
    return {'material': material_out(m), 'rows': rows}


class GradeIn(BaseModel):
    grade: int | None = Field(None, ge=2, le=5)
    comment: str | None = Field(None, max_length=2000)


@router.put('/materials/{ta_id}/submissions/{sid}')
def grade_submission(ta_id: int, sid: int, body: GradeIn, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    s = get_or_404(db, MaterialSubmission, sid, 'Cavab')
    if db.get(Material, s.material_id).assignment_id != ta.id:
        raise HTTPException(404, 'Cavab tapılmadı')
    s.grade, s.comment = body.grade, body.comment
    audit(db, user, 'update', 'submission_grade', s.id, grade=body.grade)
    db.commit()
    return {'ok': True}


@router.post('/materials/{ta_id}/{mid}/archive')
def archive_material(ta_id: int, mid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    ta = own_assignment(db, user, ta_id)
    m = get_or_404(db, Material, mid, 'Material')
    if m.assignment_id != ta.id:
        raise HTTPException(404, 'Material tapılmadı')
    m.archived_at = now()
    audit(db, user, 'archive', 'material', m.id)
    db.commit()
    return {'ok': True}


# ---------------------------------------------------------------- şagird
def _student(db: Session, u: User) -> Student:
    s = db.scalar(select(Student).where(Student.user_id == u.id, Student.archived_at.is_(None)))
    if not s:
        raise HTTPException(404, 'Şagird qeydi tapılmadı')
    return s


def _my_materials(db: Session, s: Student) -> list[Material]:
    groups = set(db.scalars(select(GroupMember.group_id).where(GroupMember.student_id == s.id)))
    ta_ids = list(db.scalars(select(TeachingAssignment.id).join(SchoolClass).where(
        SchoolClass.id.in_(groups | {s.class_id}), TeachingAssignment.archived_at.is_(None))))
    return [m for m in db.scalars(select(Material).where(Material.assignment_id.in_(ta_ids), Material.archived_at.is_(None))
                                  .order_by(Material.created_at.desc()))
            if m.student_ids is None or s.id in m.student_ids]


@router.get('/portal/materials')
def my_materials(user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = _student(db, user)
    out = []
    for m in _my_materials(db, s):
        ta = db.get(TeachingAssignment, m.assignment_id)
        sub = db.scalar(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id,
                                                         MaterialSubmission.student_id == s.id))
        out.append({**material_out(m), 'subject': ta.subject, 'teacher': db.get(User, ta.teacher_id).full_name,
                    'submission': sub and {'text': sub.text, 'submitted_at': aware(sub.submitted_at), 'late': sub.late,
                                           'grade': sub.grade, 'comment': sub.comment,
                                           'file': _file_out('submission', sub.id, sub)}})
    return out


@router.post('/portal/materials/{mid}/submit')
def submit(mid: int, text: str | None = Form(None), file: UploadFile | None = File(None),
           user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = _student(db, user)
    m = next((x for x in _my_materials(db, s) if x.id == mid), None)
    if not m or not m.needs_submission:
        raise HTTPException(404, 'Tapşırıq tapılmadı')
    if not (file and file.filename) and not (text or '').strip():
        raise HTTPException(400, 'Cavab üçün fayl və ya mətn əlavə edin')
    sub = db.scalar(select(MaterialSubmission).where(MaterialSubmission.material_id == m.id,
                                                     MaterialSubmission.student_id == s.id))
    if sub and sub.grade is not None:
        raise HTTPException(409, 'Cavab artıq qiymətləndirilib – dəyişmək olmaz')
    sub = sub or MaterialSubmission(material_id=m.id, student_id=s.id)
    sub.text = (text or '').strip() or None
    if file and file.filename:
        sub.file_key, sub.file_name, sub.file_type, sub.file_size = _save_file(db, file)
    sub.submitted_at = now()
    sub.late = bool(m.due_at and sub.submitted_at > aware(m.due_at))
    db.add(sub)
    db.commit()
    return {'ok': True, 'late': sub.late}


# ---------------------------------------------------------------- fayllar (giriş yoxlaması ilə)
@router.get('/files/{kind}/{obj_id}')
def get_file(kind: Literal['material', 'submission'], obj_id: int, user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    if kind == 'material':
        m = get_or_404(db, Material, obj_id, 'Fayl')
        ta = db.get(TeachingAssignment, m.assignment_id)
        ok = ta.teacher_id == user.id if user.role != Role.student else \
            any(x.id == m.id for x in _my_materials(db, _student(db, user)))
        obj = m
    else:
        sub = get_or_404(db, MaterialSubmission, obj_id, 'Fayl')
        m = db.get(Material, sub.material_id)
        ta = db.get(TeachingAssignment, m.assignment_id)
        ok = ta.teacher_id == user.id if user.role != Role.student else _student(db, user).id == sub.student_id
        obj = sub
    if not ok or not obj.file_key:
        raise HTTPException(404, 'Fayl tapılmadı')
    return _stream(obj, db)
