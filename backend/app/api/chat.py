"""Daxili çat – tam məxfilik.
Otaqlar: sinif (şagirdlər + həmin sinfin müəllimləri), «Müəllim otağı» (eyni məktəbin/UTİS-in müəllimləri),
şəxsi: şagird ↔ öz müəllimi, şagird ↔ sinif yoldaşı, müəllim ↔ eyni məktəbin müəllimi.
Heç kim (admin də) üzvü olmadığı yazışmanı görmür. Müəllim şagirdlərin şəxsi yazışmasını görmür –
yalnız «!» ilə bildirilən mesajı (/reports). Fayllar: şəkil, PDF, səs, video (≤ 2 GB, diskə axınla yazılır)."""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import current_user, staff
from ..models import (ChatMember, ChatMessage, ChatReport, ChatRoom, GroupMember, Role, SchoolClass, Student,
                      TeachingAssignment, User, now)
from .common import audit

router = APIRouter(prefix='/api/chat', tags=['chat'])
ALLOWED = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf',
           'audio/webm', 'audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/x-m4a', 'audio/aac',
           'video/mp4', 'video/webm', 'video/quicktime'}
MAX_BYTES = 2 * 1024 ** 3            # 2 GB (istifadəçinin tələbi)
CHUNK = 1024 * 1024


def upload_dir() -> Path:
    p = Path(settings().database_url.removeprefix('sqlite:///')).parent / 'uploads' \
        if settings().database_url.startswith('sqlite:///') else Path('data/uploads')
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_stream(file: UploadFile, dest: Path, limit: int = MAX_BYTES) -> int:
    """Faylı yaddaşa bütöv yükləmədən, 1 MB hissələrlə diskə yazır; limit keçiləndə yarımçıq fayl silinir."""
    size = 0
    try:
        with open(dest, 'wb') as out:
            while chunk := file.file.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, 'Fayl 2 GB-dan böyükdür')
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, 'Fayl boşdur')
    return size


# ---------------------------------------------------------------- kimin kimə çıxışı var
def _student(db: Session, u: User) -> Student | None:
    return db.scalar(select(Student).where(Student.user_id == u.id, Student.archived_at.is_(None))) \
        if u.role == Role.student else None


def _teacher_class_ids(db: Session, u: User) -> set[int]:
    """Müəllimin dərs dediyi siniflər (qrup -> ana sinif)."""
    rows = db.execute(select(SchoolClass.id, SchoolClass.parent_id).join(
        TeachingAssignment, TeachingAssignment.class_id == SchoolClass.id).where(
        TeachingAssignment.teacher_id == u.id, TeachingAssignment.archived_at.is_(None),
        SchoolClass.archived_at.is_(None))).all()
    return {p or c for c, p in rows}


def _student_teacher_ids(db: Session, s: Student) -> set[int]:
    groups = set(db.scalars(select(GroupMember.group_id).where(GroupMember.student_id == s.id)))
    return set(db.scalars(select(TeachingAssignment.teacher_id).where(
        TeachingAssignment.class_id.in_(groups | {s.class_id}), TeachingAssignment.archived_at.is_(None))))


def can_dm(db: Session, a: User, b: User) -> bool:
    if a.id == b.id or b.archived_at or a.school_id != b.school_id or not a.school_id:
        return False
    sa, sb = _student(db, a), _student(db, b)
    if sa and sb:
        return sa.class_id == sb.class_id
    if sa:
        return b.id in _student_teacher_ids(db, sa)
    if sb:
        return a.id in _student_teacher_ids(db, sb)
    return True                                                   # müəllim ↔ müəllim, eyni məktəb


def can_access(db: Session, u: User, room: ChatRoom) -> bool:
    if room.school_id != u.school_id:
        return False
    if room.kind == 'staff':
        return u.role in (Role.admin, Role.teacher)
    if room.kind == 'class':
        s = _student(db, u)
        return (s.class_id == room.class_id) if s else room.class_id in _teacher_class_ids(db, u)
    if room.kind == 'dm':
        ids = [int(x) for x in room.dm_key.split(':')[1:]]
        return u.id in ids
    return False


def _room(db: Session, u: User, room_id: int) -> ChatRoom:
    r = db.get(ChatRoom, room_id)
    if not r or not can_access(db, u, r):
        raise HTTPException(404, 'Söhbət tapılmadı')
    return r


def _ensure(db: Session, **kw) -> ChatRoom:
    r = db.scalar(select(ChatRoom).filter_by(**kw))
    if not r:
        r = ChatRoom(**kw)
        db.add(r)
        db.flush()
    return r


def _unread(db: Session, u: User, r: ChatRoom) -> int:
    m = db.get(ChatMember, (r.id, u.id))
    last = m.last_read_id if m else 0
    return db.scalar(select(func.count()).select_from(ChatMessage).where(
        ChatMessage.room_id == r.id, ChatMessage.id > last, ChatMessage.sender_id != u.id,
        ChatMessage.deleted_at.is_(None))) or 0


def _title(db: Session, u: User, r: ChatRoom) -> str:
    if r.kind == 'staff':
        return 'Müəllim otağı'
    if r.kind == 'class':
        return f'{db.get(SchoolClass, r.class_id).name} – sinif söhbəti'
    other = next(int(x) for x in r.dm_key.split(':')[1:] if int(x) != u.id)
    return db.get(User, other).full_name


@router.get('/rooms')
def rooms(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Mövcud otaqlar; sinif və müəllim otaqları lazım olduqda avtomatik yaranır."""
    if not u.school_id:
        return []
    if u.role == Role.student:
        s = _student(db, u)
        if s:
            _ensure(db, school_id=u.school_id, kind='class', class_id=s.class_id)
    else:
        _ensure(db, school_id=u.school_id, kind='staff', class_id=None)
        for cid in _teacher_class_ids(db, u):
            _ensure(db, school_id=u.school_id, kind='class', class_id=cid)
    db.commit()
    out = []
    for r in db.scalars(select(ChatRoom).where(ChatRoom.school_id == u.school_id)):
        if can_access(db, u, r):
            last = db.scalar(select(ChatMessage).where(ChatMessage.room_id == r.id, ChatMessage.deleted_at.is_(None))
                             .order_by(ChatMessage.id.desc()))
            out.append({'id': r.id, 'kind': r.kind, 'title': _title(db, u, r), 'unread': _unread(db, u, r),
                        'last': last and {'text': (last.text or last.file_name or '')[:80], 'at': last.created_at}})
    order = {'staff': 0, 'class': 1, 'dm': 2}
    return sorted(out, key=lambda x: (order[x['kind']], x['title']))


@router.get('/contacts')
def contacts(u: User = Depends(current_user), db: Session = Depends(get_db)):
    cand = db.scalars(select(User).where(User.school_id == u.school_id, User.archived_at.is_(None), User.id != u.id))
    return [{'id': x.id, 'full_name': x.full_name, 'role': x.role} for x in cand if can_dm(db, u, x)]


class DmIn(BaseModel):
    user_id: int


@router.post('/dm')
def open_dm(body: DmIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    other = db.get(User, body.user_id)
    if not other or not can_dm(db, u, other):
        raise HTTPException(403, 'Bu istifadəçi ilə yazışma mümkün deyil')
    a, b = sorted((u.id, other.id))
    r = _ensure(db, school_id=u.school_id, kind='dm', dm_key=f'dm:{a}:{b}')
    db.commit()
    return {'id': r.id, 'kind': 'dm', 'title': other.full_name}


def msg_out(m: ChatMessage, db: Session) -> dict:
    return {'id': m.id, 'sender_id': m.sender_id, 'sender': db.get(User, m.sender_id).full_name,
            'text': None if m.deleted_at else m.text, 'deleted': m.deleted_at is not None, 'at': m.created_at,
            'file': None if m.deleted_at or not m.file_key else {'name': m.file_name, 'type': m.file_type,
                                                                 'size': m.file_size, 'url': f'/api/chat/files/{m.id}'}}


@router.get('/rooms/{room_id}/messages')
def messages(room_id: int, after_id: int = 0, before_id: int | None = None, limit: int = 50,
             u: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _room(db, u, room_id)
    st = select(ChatMessage).where(ChatMessage.room_id == r.id, ChatMessage.id > after_id)
    if before_id:
        st = st.where(ChatMessage.id < before_id)
    rows = list(db.scalars(st.order_by(ChatMessage.id.desc()).limit(min(limit, 200))))[::-1]
    return [msg_out(m, db) for m in rows]


@router.post('/rooms/{room_id}/messages')
def send(room_id: int, text: str | None = Form(None), file: UploadFile | None = File(None),
         u: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _room(db, u, room_id)
    text = (text or '').strip() or None
    if not text and not file:
        raise HTTPException(400, 'Boş mesaj')
    if text and len(text) > 4000:
        raise HTTPException(400, 'Mesaj çox uzundur (4000 simvol)')
    m = ChatMessage(room_id=r.id, sender_id=u.id, text=text)
    if file:
        ctype = (file.content_type or '').split(';')[0]
        if ctype not in ALLOWED:
            raise HTTPException(400, 'Yalnız şəkil, PDF, səs və ya video faylı')
        key = secrets.token_hex(16)
        size = save_stream(file, upload_dir() / key)
        m.file_name, m.file_key, m.file_type, m.file_size = (file.filename or 'fayl')[:200], key, ctype, size
    db.add(m)
    db.commit()
    return msg_out(m, db)


@router.get('/files/{message_id}')
def get_file(message_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(ChatMessage, message_id)
    if not m or not m.file_key or m.deleted_at:
        raise HTTPException(404, 'Fayl tapılmadı')
    _room(db, u, m.room_id)
    return FileResponse(upload_dir() / m.file_key, media_type=m.file_type, filename=m.file_name)


@router.post('/rooms/{room_id}/read')
def mark_read(room_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _room(db, u, room_id)
    last = db.scalar(select(func.max(ChatMessage.id)).where(ChatMessage.room_id == r.id)) or 0
    m = db.get(ChatMember, (r.id, u.id)) or ChatMember(room_id=r.id, user_id=u.id)
    m.last_read_id = last
    db.merge(m)
    db.commit()
    return {'ok': True}


@router.delete('/messages/{message_id}')
def delete_message(message_id: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(ChatMessage, message_id)
    if not m or m.sender_id != u.id:
        raise HTTPException(404, 'Mesaj tapılmadı')
    m.deleted_at = now()
    db.commit()
    return {'ok': True}


class ReportIn(BaseModel):
    reason: str | None = Field(None, max_length=300)


@router.post('/messages/{message_id}/report')
def report(message_id: int, body: ReportIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """«!» – şagird ona yazılan mesajı müəlliminə bildirir (öz mesajını yox)."""
    m = db.get(ChatMessage, message_id)
    if not m or m.deleted_at:
        raise HTTPException(404, 'Mesaj tapılmadı')
    _room(db, u, m.room_id)
    s = _student(db, u)
    if not s:
        raise HTTPException(403, 'Bildiriş şagirdlər üçündür')
    if m.sender_id == u.id:
        raise HTTPException(400, 'Öz mesajınızı bildirə bilməzsiniz')
    if db.scalar(select(ChatReport).where(ChatReport.message_id == m.id, ChatReport.reporter_id == u.id)):
        raise HTTPException(409, 'Artıq bildirmisiniz')
    db.add(ChatReport(message_id=m.id, reporter_id=u.id, class_id=s.class_id, reason=body.reason))
    audit(db, u, 'create', 'chat_report', m.id)
    db.commit()
    return {'ok': True}


@router.get('/reports')
def reports(u: User = Depends(staff), db: Session = Depends(get_db)):
    """Müəllim yalnız öz siniflərinin şagirdlərinin BİLDİRDİYİ mesajları görür (bütün yazışmanı yox)."""
    cids = _teacher_class_ids(db, u)
    out = []
    for rep, m in db.execute(select(ChatReport, ChatMessage).join(ChatMessage).where(ChatReport.class_id.in_(cids))
                             .order_by(ChatReport.id.desc())):
        out.append({'id': rep.id, 'reason': rep.reason, 'at': rep.created_at, 'resolved': rep.resolved_at is not None,
                    'reporter': db.get(User, rep.reporter_id).full_name,
                    'class_name': db.get(SchoolClass, rep.class_id).name,
                    'message': msg_out(m, db) | {'text': m.text}})
    return out


@router.post('/reports/{report_id}/resolve')
def resolve(report_id: int, u: User = Depends(staff), db: Session = Depends(get_db)):
    rep = db.get(ChatReport, report_id)
    if not rep or rep.class_id not in _teacher_class_ids(db, u):
        raise HTTPException(404, 'Bildiriş tapılmadı')
    rep.resolved_at = now()
    audit(db, u, 'update', 'chat_report', rep.id, resolved=True)
    db.commit()
    return {'ok': True}
