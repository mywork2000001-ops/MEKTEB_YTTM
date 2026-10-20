"""Şagirdlər – məktəbin ortaq siyahısı.
- Müəllim yalnız dərs dediyi siniflərin şagirdlərini görür; admin – bütün məktəbi.
- Eyni ad + doğum tarixi ilə ikinci şagird yaranmır (409); portal kodu bütün müəllimlər üçün eynidir.
- Rəsmi Uşaq İD / pinkod / şəxsiyyət vəsiqəsi qəbul edilmir və saxlanmır."""
from __future__ import annotations

import datetime as dt
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.rules import level
from ..models import GroupMember, Role, SchoolClass, Student, User
from ..security import hash_password, make_qr_token, new_pin, pin_decrypt, pin_encrypt
from sqlalchemy.exc import IntegrityError

from .common import (ConfirmIn, audit, bad, can_see_class, check_confirm, get_or_404, my_class_ids, my_student_ids,
                     need_school, settings_unlocked)

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
        else:                                   # əsas sinif + əlavə üzvlər
            st = st.where(or_(Student.class_id == class_id,
                              Student.id.in_(select(GroupMember.student_id).where(GroupMember.group_id == class_id))))
    elif mine is not None:                      # öz siniflərim + dərs dediyim qrup/əlavə siniflərin üzvləri
        st = st.where(Student.id.in_(my_student_ids(db, user)))
    if q:
        st = st.where(func.lower(Student.full_name).contains(q.strip().lower()))
    rows = list(db.execute(st.order_by(SchoolClass.name, Student.full_name)))
    uids = [s.user_id for s, _ in rows if s.user_id]
    seen = dict(db.execute(select(User.id, User.guide_seen_version).where(User.id.in_(uids))).all()) if uids else {}
    return [{**student_out(s, n), 'guide_seen': (seen.get(s.user_id) or 0) >= 1} for s, n in rows]    # «🎬 ✓» – giriş videosuna baxıb


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
    force: bool = False                            # «Bu başqa şagirddir» – oxşar ad xəbərdarlığına baxmayaraq yarat


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
            tmpl = ('Bu şagird artıq var: {name}, {cname} sinfində (arxivdə – passivdir)' if s.archived_at
                    else 'Bu şagird artıq var: {name}, {cname} sinfində')
            e = bad(409, tmpl, name=s.full_name, cname=cname)
            e.detail.update(student_id=s.id, archived=s.archived_at is not None, class_name=cname)
            raise e


def next_portal_code(db: Session, c: SchoolClass, bump: int = 0) -> str:
    """Sinif ID-si + növbəti nömrə (XB-021). Həm şagird kodları, həm də istifadəçi loginləri ilə toqquşmur."""
    codes = db.scalars(select(Student.portal_code).where(Student.portal_code.like(f'{c.code}-%')))
    n = max((int(x.rsplit('-', 1)[1]) for x in codes if x.rsplit('-', 1)[1].isdigit()), default=0) + 1 + bump
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
    if not body.force:                               # yumşaq yoxlama: «Huseyn» ≈ «Hüseyn», söz sırası, ata adı
        similar = similar_students(db, sid, name, body.birth_date)
        if similar:
            e = bad(409, 'Oxşar şagird artıq var: {name} ({cls}). Eyni şagirddirsə – onu bu sinfə əlavə sinif kimi əlavə edin',
                    name=similar[0]['full_name'], cls=similar[0]['class_name'])
            e.detail['possible_duplicate'] = similar
            raise e
    pin = new_pin()
    for attempt in range(5):                         # eyni anda iki idxal eyni kodu götürsə – növbəti nömrə ilə təkrar
        code = next_portal_code(db, c, attempt)
        try:
            with db.begin_nested():
                acc = User(role=Role.student, login=code, password_hash=hash_password(pin), full_name=name, school_id=sid)
                db.add(acc)
                db.flush()
                s = Student(school_id=sid, created_by=user.id, portal_code=code, user_id=acc.id, initial_pin=pin_encrypt(pin),
                            **{**body.model_dump(exclude={'group_id', 'force'}), 'full_name': name})
                db.add(s)
                db.flush()
            break
        except IntegrityError:
            if attempt == 4:
                raise bad(409, 'Şagird kodu yaradıla bilmədi – bir az sonra yenidən yoxlayın')
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


def _student_for_write(db: Session, user: User, sid_: int, primary: bool = False) -> Student:
    """Redaktə (ad, PIN, doğum tarixi, sinfə keçirmə): öz sinfimin və ya dərs dediyim qrup/əlavə sinfin şagirdi.
    primary=True (arxiv, bərpa, silmə): yalnız şagirdin ƏSAS sinfinin müəllimi və ya admin."""
    s = get_or_404(db, Student, sid_, 'Şagird')
    if s.school_id != user.school_id:
        raise HTTPException(403, 'Bu şagird sizin siniflərinizdən deyil')
    if primary:
        if not can_see_class(db, user, db.get(SchoolClass, s.class_id)):
            raise HTTPException(403, 'Arxivə göndərmək, bərpa etmək və silmək yalnız şagirdin əsas sinfinin müəllimi və ya admin üçündür')
        return s
    ids = my_student_ids(db, user)
    if ids is not None and s.id not in ids:
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
                raise bad(409, '«{code}» giriş kodu artıq istifadə olunur', code=code)
            if s.user_id:
                db.get(User, s.user_id).login = code          # şagird yeni kodla daxil olur
        data['portal_code'] = code
    moved_from = None
    if 'class_id' in data and data['class_id'] != s.class_id:
        _class_for_write(db, user, data['class_id'])
        moved_from = s.class_id
        old_split = select(SchoolClass.id).where(SchoolClass.parent_id == s.class_id)
        db.query(GroupMember).filter(GroupMember.student_id == s.id, or_(GroupMember.group_id.in_(old_split),
                                     GroupMember.group_id == data['class_id'])).delete(synchronize_session=False)   # köhnə sinfin bölünmə qrupları
    for k, v in data.items():
        setattr(s, k, v)
    if 'full_name' in data and s.user_id:
        db.get(User, s.user_id).full_name = s.full_name
    extra = {'from_class': moved_from, 'to_class': s.class_id} if moved_from is not None else {}
    audit(db, user, 'update', 'student', s.id, fields=sorted(data), **extra)
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
    s = _student_for_write(db, user, sid_, primary=True)
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
    s = _student_for_write(db, user, sid_, primary=True)
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
    s = _student_for_write(db, user, sid_, primary=True)
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


# ---------------------------------------------------------------- təkrar şagirdlər (docs/sagird-coxlu-sinif-ve-birlesme-promtu.md §2)
_PATRO = {'oglu', 'qizi'}                                  # «oğlu/qızı» normallaşmadan sonra
_AZ_MAP = str.maketrans({'ə': 'a','ı': 'i', 'ü': 'u', 'ö': 'o', 'ş': 's', 'ç': 'c', 'ğ': 'g'})


def _norm_token(w: str) -> str:
    """casefold + NFKD (birləşdirici işarələr atılır) + az hərflər → latın: «Əhmədov»=«Ahmadov», «İlkin»=«Ilkin»."""
    w = unicodedata.normalize('NFKD', w.casefold())
    return ''.join(ch for ch in w if not unicodedata.combining(ch)).translate(_AZ_MAP)


def name_tokens(name: str) -> frozenset[str]:
    """Ad sözləri (ata adı və «oğlu/qızı» nəzərə alınmır, sıra və yazılış fərqi – ə/a, ş/s… – əhəmiyyətsizdir):
    «Əliyev Murad Rəşid oğlu» → {aliyev, murad}."""
    t = [_norm_token(w) for w in name.split()]
    if len(t) >= 3 and t[-1] in _PATRO:
        t = t[:-2]
    return frozenset(t)


def _admin(user: User):
    if user.role != Role.admin:
        raise HTTPException(403, 'Yalnız admin')


def _weight(db: Session, sid_: int) -> dict:
    from ..models import Attendance, Mark, TaskAttempt
    n = lambda m: db.scalar(select(func.count()).select_from(m).where(m.student_id == sid_)) or 0
    return {'marks': n(Mark), 'attempts': n(TaskAttempt), 'attendance': n(Attendance)}


def dup_pairs(db: Session, school_id: int) -> list[dict]:
    """Ehtimal olunan təkrar şagird cütləri (aktiv, eyni məkan): ad sözləri eyni və ya biri digərinin içində («Nihad» – «Nihad Əliyev»,
    «Əhmədov Hüseyn» – «Hüseyn Əhmədov»); doğum tarixləri fərqlidirsə – təkrar deyil. [{level, a, b, class_a, class_b}]"""
    rows = list(db.execute(select(Student, SchoolClass.name).join(SchoolClass, SchoolClass.id == Student.class_id)
                           .where(Student.school_id == school_id, Student.archived_at.is_(None))))
    toks = [name_tokens(s.full_name) for s, _ in rows]
    out = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            (a, ca), (b, cb), ta, tb = rows[i], rows[j], toks[i], toks[j]
            if not (ta <= tb or tb <= ta):                # «Nihad» ⊂ «Nihad Əliyev»; «Əhmədov Hüseyn» = «Hüseyn Əhmədov»
                continue
            if a.birth_date and b.birth_date and a.birth_date != b.birth_date:
                continue                                  # doğum tarixi fərqlidir – başqa uşaqdır
            same = ' '.join(a.full_name.split()).casefold() == ' '.join(b.full_name.split()).casefold()
            lvl = ('tam' if same and a.birth_date and a.birth_date == b.birth_date else 'eyni ad' if same
                   else 'ad və soyad eyni' if ta == tb and len(ta) >= 2 else 'oxşar ad')
            out.append({'level': lvl, 'a': a, 'b': b, 'class_a': ca, 'class_b': cb})
    return out


def similar_students(db: Session, school_id: int, name: str, birth: dt.date | None) -> list[dict]:
    """Yeni şagirdə oxşar aktiv şagirdlər (ad sözlərinin altçoxluğu; doğum tarixi ziddiyyət təşkil etmir)."""
    tn = name_tokens(name)
    if not tn:
        return []
    out = []
    for s, cname in db.execute(select(Student, SchoolClass.name).join(SchoolClass, SchoolClass.id == Student.class_id)
                               .where(Student.school_id == school_id, Student.archived_at.is_(None))):
        t = name_tokens(s.full_name)
        if not (tn <= t or t <= tn):
            continue
        if birth and s.birth_date and birth != s.birth_date:
            continue
        out.append({'id': s.id, 'full_name': s.full_name, 'class_name': cname, 'class_id': s.class_id, 'birth_date': s.birth_date})
    return out[:5]


@router.get('/duplicates')
def duplicates(user: User = Depends(staff), db: Session = Depends(get_db)):
    """Ehtimal olunan təkrar şagirdlər (yalnız admin)."""
    _admin(user)
    one = lambda s, c: {'id': s.id, 'full_name': s.full_name, 'class_name': c, 'portal_code': s.portal_code,
                        'birth_date': s.birth_date, **_weight(db, s.id)}
    out = [{'level': p['level'], 'a': one(p['a'], p['class_a']), 'b': one(p['b'], p['class_b'])}
           for p in dup_pairs(db, need_school(user))]
    rank = {'tam': 0, 'eyni ad': 1, 'ad və soyad eyni': 2, 'oxşar ad': 3}
    return sorted(out, key=lambda x: (rank[x['level']], x['a']['full_name']))


class MergeIn(BaseModel):
    keep_id: int
    drop_id: int
    confirm: str                       # saxlanan şagirdin adı (geri qaytarılmır)


def _replace_json_ids(db: Session, drop: int, keep: int) -> int:
    """JSON-da saxlanan şagird siyahıları: tapşırıq, material, məşğələ qrupu, sınaq seriyası."""
    from ..models import ExamSeries, ExtraCourse, Material, OnlineTask
    fix = lambda ids: list(dict.fromkeys(keep if i == drop else i for i in ids))
    n = 0
    for m in (OnlineTask, Material):
        for o in db.scalars(select(m).where(m.student_ids.is_not(None))):
            if drop in (o.student_ids or []):
                o.student_ids, n = fix(o.student_ids), n + 1
    for c in db.scalars(select(ExtraCourse)):
        a = dict(c.audience or {})
        if drop in (a.get('student_ids') or []):
            a['student_ids'] = fix(a['student_ids'])
            c.audience, n = a, n + 1
    for s in db.scalars(select(ExamSeries)):
        if any(drop in (t.get('student_ids') or []) for t in s.targets or []):
            s.targets = [{**t, 'student_ids': fix(t['student_ids']) if t.get('student_ids') else t.get('student_ids')}
                         for t in s.targets]
            n += 1
    return n


def merge_students(db: Session, keep: Student, drop: Student) -> dict:
    """Bütün istinadlar drop → keep (cədvəllər metadata-dan – yeni cədvəl də düşmür). Toqquşmada (eyni dərsdə ikisinin də
    qeydi) saxlananınkı qalır; test cəhdində – təhvil verilmiş olan qalır."""
    import sqlalchemy as sa
    from ..db import Base
    from ..models import now
    moved, dropped = 0, 0
    db.flush()
    for t in Base.metadata.sorted_tables:
        if t.name == 'students':
            continue
        for col in [c for c in t.columns if any(fk.column.table.name == 'students' for fk in c.foreign_keys)]:
            pk = list(t.primary_key.columns)
            keys = [[c.name for c in pk]] if col in pk and len(pk) > 1 else []
            keys += [[c.name for c in u.columns] for u in t.constraints
                     if isinstance(u, sa.UniqueConstraint) and col.name in [c.name for c in u.columns]]
            for key in keys:
                other = [k for k in key if k != col.name]
                for r in db.execute(sa.select(t).where(col == drop.id)).mappings().all():
                    cond = [t.c[k] == r[k] for k in other]
                    kr = db.execute(sa.select(t).where(col == keep.id, *cond)).mappings().first()
                    if kr is None:
                        continue
                    if t.name == 'task_attempts' and r['submitted_at'] and not kr['submitted_at']:
                        db.execute(sa.delete(t).where(col == keep.id, *cond))      # saxlananınki boşdur – təhvil verilmiş qalır
                    else:
                        db.execute(sa.delete(t).where(col == drop.id, *cond))
                    dropped += 1
            moved += db.execute(sa.update(t).where(col == drop.id).values({col.name: keep.id})).rowcount or 0
    js = _replace_json_ids(db, drop.id, keep.id)
    # silinənin əsas sinfi – saxlananın əlavə sinfi olur (Nihad: IX və XI – bir şagird, iki sinif)
    if drop.class_id != keep.class_id and not db.get(GroupMember, (drop.class_id, keep.id)):
        db.add(GroupMember(group_id=drop.class_id, student_id=keep.id))
    db.query(GroupMember).filter(GroupMember.group_id == keep.class_id, GroupMember.student_id == keep.id).delete()
    if drop.birth_date and not keep.birth_date:
        b, drop.birth_date = drop.birth_date, None             # unikal (məktəb + ad + doğum tarixi) toqquşmasın
        db.flush()
        keep.birth_date = b
    for f in ('gender', 'score_language', 'score_math', 'score_foreign', 'phone', 'guardians'):
        if getattr(keep, f) in (None, '', []) and getattr(drop, f) not in (None, '', []):
            setattr(keep, f, getattr(drop, f))
    drop.archived_at, drop.left_on = now(), dt.date.today()
    drop.left_reason = f'Birləşdirildi → {keep.portal_code} ({keep.full_name})'[:300]
    if drop.user_id and (acc := db.get(User, drop.user_id)):
        acc.archived_at = now()                                # portal hesabı bağlanır – şagird saxlanan ID ilə girir
    db.flush()                                                 # əvvəl yaz – sonra köhnə ORM vəziyyətini at
    db.expire_all()
    return {'moved': moved, 'conflicts': dropped, 'json': js}


@router.post('/merge')
def merge(body: MergeIn, user: User = Depends(settings_unlocked), db: Session = Depends(get_db)):
    """Təkrar şagirdi birləşdir (yalnız admin; geri qaytarılmır – saxlanan şagirdin adını yazmaqla təsdiq)."""
    _admin(user)
    if body.keep_id == body.drop_id:
        raise HTTPException(400, 'Eyni şagird')
    keep, drop = get_or_404(db, Student, body.keep_id, 'Şagird'), get_or_404(db, Student, body.drop_id, 'Şagird')
    if keep.school_id != user.school_id or drop.school_id != user.school_id:
        raise HTTPException(404, 'Şagird tapılmadı')
    if drop.archived_at or keep.archived_at:
        raise HTTPException(400, 'Arxivdəki şagird birləşdirilmir')
    check_confirm(keep.full_name, body.confirm)
    code, name, dcode = keep.portal_code, keep.full_name, drop.portal_code
    r = merge_students(db, keep, drop)
    audit(db, user, 'merge', 'student', body.keep_id, dropped=body.drop_id, dropped_code=dcode, **r)
    db.commit()
    return {**r, 'keep': body.keep_id, 'portal_code': code, 'full_name': name}


def merge_named(db: Session, rules: list[tuple[set[str], dict[int, bool]]]) -> list[str]:
    """Konkret təkrarların birləşdirilməsi (miqrasiya b3c5d7e9f1a2 – istifadəçinin göstərişi ilə). Hər qayda: ad sözləri +
    {sinif rəqəmi: saxlanılsın?}. Yalnız birmənalı halda: həmin məkanda hər sinif rəqəmində dəqiq bir uyğun aktiv şagird,
    doğum tarixləri ziddiyyətsiz. Əks halda – heç nə edilmir (səbəb qaytarılır). Hesabat ASCII – yalnız id/ID kodu."""
    from collections import defaultdict
    from ..services import class_grade
    log = []
    rows = list(db.execute(select(Student, SchoolClass).join(SchoolClass, SchoolClass.id == Student.class_id)
                           .where(Student.archived_at.is_(None))))
    for words, want in rules:
        per: dict[int, list] = defaultdict(list)
        for st, c in rows:
            if {_norm_token(w) for w in words} <= name_tokens(st.full_name):
                per[st.school_id].append((st, class_grade(db, c)))
        if not per:
            log.append(f'grades {sorted(want)}: not found')
        for school, got in per.items():
            by_g = {g: [st for st, gg in got if gg == g] for g in want}
            if any(len(v) != 1 for v in by_g.values()):
                log.append(f'school {school} grades {sorted(want)}: ambiguous {[len(v) for v in by_g.values()]} - skipped')
                continue
            keep = next(by_g[g][0] for g, k in want.items() if k)
            drops = [by_g[g][0] for g, k in want.items() if not k]
            if any(d.birth_date and keep.birth_date and d.birth_date != keep.birth_date for d in drops):
                log.append(f'school {school}: birth dates differ - skipped')
                continue
            for d in drops:
                code = d.portal_code
                merge_students(db, keep, d)
                log.append(f'school {school}: merged student {d.id} ({ascii(code)}) into {keep.id} ({ascii(keep.portal_code)})')
    return log
