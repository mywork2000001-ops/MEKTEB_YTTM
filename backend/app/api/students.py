"""Şagirdlər – məktəbin ortaq siyahısı.
- Müəllim yalnız dərs dediyi siniflərin şagirdlərini görür; admin – bütün məktəbi.
- Eyni ad + doğum tarixi ilə ikinci şagird yaranmır (409); portal kodu bütün müəllimlər üçün eynidir.
- Rəsmi Uşaq İD / pinkod / şəxsiyyət vəsiqəsi qəbul edilmir və saxlanmır."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import level
from ..models import GroupMember, Role, SchoolClass, Student, User
from ..security import hash_password, make_qr_token, new_pin, pin_decrypt, pin_encrypt
from .common import (ConfirmIn, audit, can_see_class, check_confirm, get_or_404, my_class_ids, need_school,
                     settings_unlocked)

router = APIRouter(prefix='/api/students', tags=['students'])


def student_out(s: Student, cls_name: str | None = None):
    total = None
    if None not in (s.score_language, s.score_math, s.score_foreign):
        total = round(s.score_language + s.score_math + s.score_foreign, 1)
    return {'id': s.id, 'full_name': s.full_name, 'birth_date': s.birth_date, 'gender': s.gender,
            'class_id': s.class_id, 'class_name': cls_name, 'portal_code': s.portal_code,
            'score_language': s.score_language, 'score_math': s.score_math, 'score_foreign': s.score_foreign,
            'score_total': total, 'level': level(s.score_math), 'archived': s.archived_at is not None,
            'left_reason': s.left_reason, 'left_on': s.left_on,
            'archived_at': s.archived_at}


@router.get('')
def list_students(class_id: int | None = None, archived: bool = False, q: str | None = None,
                  user: User = Depends(staff), db: Session = Depends(get_db)):
    sid = need_school(user)
    st = (select(Student, SchoolClass.name).join(SchoolClass, SchoolClass.id == Student.class_id)
          .where(Student.school_id == sid,
                 Student.archived_at.is_not(None) if archived else Student.archived_at.is_(None)))
    mine = my_class_ids(db, user)
    if class_id:
        c = get_or_404(db, SchoolClass, class_id, 'Sinif')
        if not can_see_class(db, user, c):
            raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
        if c.kind == 'qrup':
            st = st.join(GroupMember, GroupMember.student_id == Student.id).where(GroupMember.group_id == c.id)
        else:
            st = st.where(Student.class_id == class_id)
    elif mine is not None:
        st = st.where(Student.class_id.in_(mine))
    if q:
        st = st.where(func.lower(Student.full_name).contains(q.strip().lower()))
    return [student_out(s, n) for s, n in db.execute(st.order_by(SchoolClass.name, Student.full_name))]


class StudentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')      # Uşaq İD, pinkod və s. göndərilsə – rədd edilir
    full_name: str = Field(min_length=5, max_length=200)
    class_id: int
    birth_date: dt.date | None = None
    gender: str | None = Field(None, pattern='^(Qız|Oğlan)$')
    score_language: float | None = Field(None, ge=0, le=100)
    score_math: float | None = Field(None, ge=0, le=100)
    score_foreign: float | None = Field(None, ge=0, le=100)
    group_id: int | None = None                    # bölünmə qrupundan əlavə edəndə – dərhal qrupa üzv olur


def _class_for_write(db: Session, user: User, class_id: int) -> SchoolClass:
    c = get_or_404(db, SchoolClass, class_id, 'Sinif')
    if c.kind == 'qrup':
        raise HTTPException(400, 'Şagird ana sinfə əlavə olunur; qrupa üzvlük qrup bölməsindən təyin edilir')
    if not can_see_class(db, user, c) or c.archived_at:
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    return c


def _dup(db: Session, school_id: int, name: str, birth: dt.date | None, exclude: int | None = None):
    st = select(Student, SchoolClass.name).join(SchoolClass, SchoolClass.id == Student.class_id).where(
        Student.school_id == school_id, func.lower(Student.full_name) == name.lower())
    if birth:
        st = st.where(Student.birth_date == birth)
    for s, cname in db.execute(st):
        if s.id != exclude and (birth or s.birth_date is None):
            where = f'{cname} sinfində' + (' (arxivdə – passivdir)' if s.archived_at else '')
            raise HTTPException(409, {'message': f'Bu şagird artıq var: {s.full_name}, {where}', 'student_id': s.id,
                                      'archived': s.archived_at is not None, 'class_name': cname})


def next_portal_code(db: Session, c: SchoolClass) -> str:
    """Sinif ID-si + növbəti nömrə (XB-021). Həm şagird kodları, həm də istifadəçi loginləri ilə toqquşmur."""
    codes = db.scalars(select(Student.portal_code).where(Student.portal_code.like(f'{c.code}-%')))
    n = max((int(x.rsplit('-', 1)[1]) for x in codes if x.rsplit('-', 1)[1].isdigit()), default=0) + 1
    while True:
        code = f'{c.code}-{n:03d}'
        if not (db.scalar(select(Student.id).where(func.upper(Student.portal_code) == code))
                or db.scalar(select(User.id).where(func.upper(User.login) == code))):
            return code
        n += 1


@router.post('')
def create_student(body: StudentIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    sid = need_school(user)
    c = _class_for_write(db, user, body.class_id)
    name = ' '.join(body.full_name.split())
    if body.birth_date and body.birth_date > dt.date.today():
        raise HTTPException(400, 'Doğum tarixi gələcəkdə ola bilməz')
    grp = None
    if body.group_id is not None:
        grp = get_or_404(db, SchoolClass, body.group_id, 'Qrup')
        if grp.kind != 'qrup' or grp.parent_id != c.id:
            raise HTTPException(400, 'Qrup bu sinfin bölünmə qrupu deyil')
    _dup(db, sid, name, body.birth_date)
    code = next_portal_code(db, c)
    pin = new_pin()
    acc = User(role=Role.student, login=code, password_hash=hash_password(pin), full_name=name, school_id=sid)
    db.add(acc)
    db.flush()
    s = Student(school_id=sid, created_by=user.id, portal_code=code, user_id=acc.id, initial_pin=pin_encrypt(pin),
                **{**body.model_dump(exclude={'group_id'}), 'full_name': name})
    db.add(s)
    db.flush()
    if grp:
        db.add(GroupMember(group_id=grp.id, student_id=s.id))
    audit(db, user, 'create', 'student', s.id, class_id=c.id)
    db.commit()
    return {**student_out(s, c.name), 'initial_pin': pin}       # PIN yalnız bir dəfə göstərilir


class StudentPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    full_name: str | None = Field(None, min_length=5, max_length=200)
    class_id: int | None = None
    birth_date: dt.date | None = None
    gender: str | None = Field(None, pattern='^(Qız|Oğlan)$')
    score_language: float | None = Field(None, ge=0, le=100)
    score_math: float | None = Field(None, ge=0, le=100)
    score_foreign: float | None = Field(None, ge=0, le=100)
    portal_code: str | None = Field(None, min_length=3, max_length=16, pattern=r'^[A-Za-z0-9\-]+$')   # giriş ID-si


def _student_for_write(db: Session, user: User, sid_: int) -> Student:
    s = get_or_404(db, Student, sid_, 'Şagird')
    c = db.get(SchoolClass, s.class_id)
    if s.school_id != user.school_id or not can_see_class(db, user, c):
        raise HTTPException(403, 'Bu şagird sizin siniflərinizdən deyil')
    return s


@router.patch('/{sid_}')
def update_student(sid_: int, body: StudentPatch, user: User = Depends(settings_unlocked),
                   db: Session = Depends(get_db)):
    s = _student_for_write(db, user, sid_)
    data = body.model_dump(exclude_unset=True)
    if 'full_name' in data:
        data['full_name'] = ' '.join(data['full_name'].split())
    if 'full_name' in data or 'birth_date' in data:
        _dup(db, s.school_id, data.get('full_name', s.full_name), data.get('birth_date', s.birth_date), s.id)
    if 'portal_code' in data:
        code = data['portal_code'].upper()
        if code != s.portal_code:
            taken = db.scalar(select(Student.id).where(func.upper(Student.portal_code) == code, Student.id != s.id)) or \
                db.scalar(select(User.id).where(func.upper(User.login) == code, User.id != (s.user_id or 0)))
            if taken:
                raise HTTPException(409, f'«{code}» giriş kodu artıq istifadə olunur')
            if s.user_id:
                db.get(User, s.user_id).login = code          # şagird yeni kodla daxil olur
        data['portal_code'] = code
    if 'class_id' in data and data['class_id'] != s.class_id:
        _class_for_write(db, user, data['class_id'])
        db.query(GroupMember).filter(GroupMember.student_id == s.id).delete()   # köhnə sinfin qruplarından çıxır
    for k, v in data.items():
        setattr(s, k, v)
    if 'full_name' in data and s.user_id:
        db.get(User, s.user_id).full_name = s.full_name
    audit(db, user, 'update', 'student', s.id, fields=sorted(data))
    db.commit()
    return student_out(s, db.get(SchoolClass, s.class_id).name)


class PinIn(BaseModel):
    pin: str | None = Field(None, pattern=r'^\d{4}$')        # boş – təsadüfi PIN


@router.post('/{sid_}/reset-pin')
def reset_pin(sid_: int, body: PinIn | None = None, user: User = Depends(settings_unlocked),
              db: Session = Depends(get_db)):
    """Yeni PIN: müəllim özü yazır (4 rəqəm) və ya təsadüfi yaradılır. Vərəqədə çap üçün ilkin PIN kimi saxlanır."""
    s = _student_for_write(db, user, sid_)
    pin = body.pin if body and body.pin else new_pin()
    acc = db.get(User, s.user_id) if s.user_id else None
    if acc is None:
        acc = User(role=Role.student, login=s.portal_code, full_name=s.full_name, school_id=s.school_id,
                   password_hash='')
        db.add(acc)
        db.flush()
        s.user_id = acc.id
    acc.password_hash = hash_password(pin)
    acc.failed_logins, acc.locked_until = 0, None
    s.initial_pin = pin_encrypt(pin)
    audit(db, user, 'update', 'student_pin', s.id)
    db.commit()
    return {'portal_code': s.portal_code, 'pin': pin}


class LeaveIn(ConfirmIn):
    reason: str | None = Field(None, max_length=300)       # «başqa məktəbə köçdü», «təhsilini dayandırdı» …
    left_on: dt.date | None = None


@router.post('/{sid_}/archive')
def archive_student(sid_: int, body: LeaveIn, user: User = Depends(settings_unlocked),
                    db: Session = Depends(get_db)):
    """Passiv et (məktəbdən gedib): siyahılardan, jurnaldan və portaldan çıxır, qiymətləri və tarixçəsi QALIR;
    «Arxiv»dən geri qaytarmaq və ya həmişəlik silmək olar."""
    s = _student_for_write(db, user, sid_)
    check_confirm(s.full_name, body.confirm)
    s.archived_at = dt.datetime.now(dt.timezone.utc)
    s.left_reason = (body.reason or '').strip() or None
    s.left_on = body.left_on or dt.date.today()
    if s.user_id:
        db.get(User, s.user_id).archived_at = s.archived_at      # portala giriş bağlanır
    audit(db, user, 'archive', 'student', s.id, reason=s.left_reason)
    db.commit()
    return {'ok': True}


@router.post('/{sid_}/restore')
def restore_student(sid_: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    s = _student_for_write(db, user, sid_)
    s.archived_at = None
    s.left_reason, s.left_on = None, None
    if s.user_id:
        db.get(User, s.user_id).archived_at = None
    audit(db, user, 'restore', 'student', s.id)
    db.commit()
    return {'ok': True}


@router.delete('/{sid_}')
def delete_student(sid_: int, body: ConfirmIn, user: User = Depends(settings_unlocked),
                   db: Session = Depends(get_db)):
    s = _student_for_write(db, user, sid_)
    if not s.archived_at:
        raise HTTPException(409, 'Əvvəlcə arxivə göndərin')
    check_confirm(s.full_name, body.confirm)
    db.query(GroupMember).filter(GroupMember.student_id == s.id).delete()
    acc = db.get(User, s.user_id) if s.user_id else None
    audit(db, user, 'delete', 'student', s.id)
    db.delete(s)
    db.flush()
    if acc:
        from ..models import AuditLog, ChatMessage, ChatReport
        used = (db.scalar(select(ChatMessage.id).where(ChatMessage.sender_id == acc.id).limit(1))
                or db.scalar(select(ChatReport.id).where(ChatReport.reporter_id == acc.id).limit(1))
                or db.scalar(select(AuditLog.id).where(AuditLog.user_id == acc.id).limit(1)))
        if used:
            # çat mesajları/jurnal qeydləri başqalarının yazışmasında qalır – hesab silinmir, anonimləşdirilir
            import secrets as _s
            acc.full_name, acc.login = 'Silinmiş şagird', f'silinib-{acc.id}'
            acc.password_hash = hash_password(_s.token_urlsafe(24))
            acc.avatar = acc.avatar_type = acc.avatar_v = None
            acc.archived_at = acc.archived_at or dt.datetime.now(dt.timezone.utc)
        else:
            db.delete(acc)
    db.commit()
    return {'ok': True}


@router.post('/by-class/{cid}/reset-pins')
def reset_class_pins(cid: int, only_missing: bool = False, user: User = Depends(settings_unlocked),
                     db: Session = Depends(get_db)):
    """Sinfin bütün şagirdlərinə yeni PIN (giriş vərəqələri üçün). PIN-lər yalnız bu cavabda bir dəfə qaytarılır."""
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.kind == 'qrup' or not can_see_class(db, user, c):
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    out = []
    for s in db.scalars(select(Student).where(Student.class_id == cid, Student.archived_at.is_(None))
                        .order_by(Student.full_name)):
        if only_missing and s.initial_pin and pin_decrypt(s.initial_pin):
            continue                                     # ilkin PIN hələ qüvvədədir – toxunulmur
        pin = new_pin()
        acc = db.get(User, s.user_id) if s.user_id else None
        if acc is None:
            acc = User(role=Role.student, login=s.portal_code, full_name=s.full_name, school_id=s.school_id,
                       password_hash='')
            db.add(acc)
            db.flush()
            s.user_id = acc.id
        acc.password_hash = hash_password(pin)
        acc.failed_logins, acc.locked_until = 0, None
        s.initial_pin = pin_encrypt(pin)
        out.append({'full_name': s.full_name, 'portal_code': s.portal_code, 'pin': pin, 'qr': _qr(db, s, pin)})
    audit(db, user, 'update', 'class_pins', cid, count=len(out))
    db.commit()
    return {'class_name': c.name, 'students': out}


@router.post('/login-sheets')
def login_sheets_all(fill_missing: bool = True, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Bütün siniflərim üçün giriş vərəqələri bir sənəddə. fill_missing: ilkin PIN-i olmayan (heç vaxt verilməyən və
    ya itən) şagirdlərə yeni PIN yaradılır; şagirdin özünün dəyişdiyi PIN-ə toxunulmur deyə vərəqədə «dəyişdirilib» qalır
    – yalnız hesabı olmayan və ya ilkin PIN-i heç saxlanmayan şagirdlərə verilir."""
    from .common import my_class_ids
    mine = my_class_ids(db, user)
    st = select(SchoolClass).where(SchoolClass.school_id == user.school_id, SchoolClass.archived_at.is_(None),
                                   SchoolClass.kind != 'qrup')
    if mine is not None:
        st = st.where(SchoolClass.id.in_(mine))
    out, created = [], 0
    for c in db.scalars(st.order_by(SchoolClass.name)):
        rows = []
        for s in db.scalars(select(Student).where(Student.class_id == c.id, Student.archived_at.is_(None))
                            .order_by(Student.full_name)):
            pin = pin_decrypt(s.initial_pin)
            acc = db.get(User, s.user_id) if s.user_id else None
            if fill_missing and pin is None and (acc is None or _pin_unknown(db, s)):
                pin = new_pin()
                if acc is None:
                    acc = User(role=Role.student, login=s.portal_code, full_name=s.full_name, school_id=s.school_id,
                               password_hash='')
                    db.add(acc)
                    db.flush()
                    s.user_id = acc.id
                acc.password_hash = hash_password(pin)
                acc.failed_logins, acc.locked_until = 0, None
                s.initial_pin = pin_encrypt(pin)
                created += 1
            rows.append({'full_name': s.full_name, 'portal_code': s.portal_code, 'pin': pin, 'qr': _qr(db, s, pin)})
        if rows:
            out.append({'class_name': c.name, 'students': rows})
    audit(db, user, 'export', 'login_sheets_all', None, classes=len(out), new_pins=created)
    db.commit()
    return {'classes': out, 'new_pins': created}


def _qr(db: Session, s: Student, pin: str | None) -> str | None:
    """Vərəqədəki QR (avtomatik giriş) – yalnız ilkin PIN məlum olanda: PIN-ini özü dəyişən şagirdin əvəzinə daxil olunmasın."""
    if not pin or not s.user_id:
        return None
    acc = db.get(User, s.user_id)
    return make_qr_token(acc.id, acc.password_hash) if acc else None


def _pin_unknown(db: Session, s: Student) -> bool:
    """PIN heç kimə məlum deyil (məs. UTİS importundan sonra vərəqə çap olunmayıb) – yenisini vermək təhlükəsizdir.
    Şagird özü qeydiyyatdan keçibsə (created_by boş – PIN ekranda göstərilib) və ya heç olmasa bir dəfə daxil olubsa /
    PIN-ini dəyişibsə, PIN-i bilir – ona toxunulmur (hesabından kənarda qalmasın)."""
    from ..models import AuditLog
    if s.created_by is None:
        return False
    return not db.scalar(select(AuditLog.id).where(AuditLog.user_id == s.user_id).limit(1))


@router.get('/by-class/{cid}/login-sheet')
def login_sheet(cid: int, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Giriş vərəqəsi: şagirdin giriş kodu və İLKİN PIN-i (şagird PIN-i dəyişibsə – null)."""
    c = get_or_404(db, SchoolClass, cid, 'Sinif')
    if c.kind == 'qrup' or not can_see_class(db, user, c):
        raise HTTPException(403, 'Bu sinif sizin siniflərinizdən deyil')
    rows = [{'full_name': s.full_name, 'portal_code': s.portal_code, 'pin': pin_decrypt(s.initial_pin),
             'qr': _qr(db, s, pin_decrypt(s.initial_pin))}
            for s in db.scalars(select(Student).where(Student.class_id == cid, Student.archived_at.is_(None))
                                .order_by(Student.full_name))]
    audit(db, user, 'export', 'login_sheet', cid, count=len(rows))
    db.commit()
    return {'class_name': c.name, 'students': rows}
