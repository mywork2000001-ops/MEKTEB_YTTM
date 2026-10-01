"""Şagird və valideyn telefonları – yalnız sinif rəhbəri və admin (məxfilik: fənn müəllimi görmür, audit-ə nömrə yazılmır).
- bütün sinif bir cədvəldə: şagirdin telefonu + valideynlər (ad, qohumluq, telefon);
- Excel/CSV idxalı: əvvəl yoxlama (dry_run), sonra yazma; ad üzrə eşləşmə, boş xana mövcud nömrəni silmir;
- şablon (.xlsx) – sinfin şagird adları ilə hazır."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import staff
from ..domain.phones import name_key, norm_phone, read_table
from ..models import Student, User
from .common import audit
from .homeroom import GuardianIn, homeroom_class

router = APIRouter(prefix='/api/homeroom', tags=['phones'])
MAX_FILE = 2 * 1024 * 1024


def _studs(db: Session, cid: int) -> list[Student]:
    return list(db.scalars(select(Student).where(Student.class_id == cid, Student.archived_at.is_(None))
                           .order_by(Student.full_name)))


def _out(s: Student) -> dict:
    return {'student_id': s.id, 'full_name': s.full_name, 'phone': s.phone, 'guardians': s.guardians or []}


@router.get('/{cid}/phones')
def phones(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    rows = [_out(s) for s in _studs(db, c.id)]
    return {'class_name': c.name, 'students': rows,
            'filled': sum(bool(r['phone'] or any(g.get('phone') for g in r['guardians'])) for r in rows)}


class PhoneRow(BaseModel):
    student_id: int
    phone: str | None = Field(None, max_length=30)
    guardians: list[GuardianIn] = Field(default_factory=list, max_length=4)

    @field_validator('phone')
    @classmethod
    def _p(cls, v):
        return norm_phone(v)


@router.put('/{cid}/phones')
def save_phones(cid: int, body: list[PhoneRow], user: User = Depends(staff), db: Session = Depends(get_db)):
    """Toplu yadda saxlama: göndərilən şagirdlərin telefonu və valideynləri tam əvəzlənir."""
    c = homeroom_class(db, user, cid)
    studs = {s.id: s for s in _studs(db, c.id)}
    bad = [r.student_id for r in body if r.student_id not in studs]
    if bad:
        raise HTTPException(404, f'Bu şagirdlər sinifdə deyil: {bad}')
    for r in body:
        s = studs[r.student_id]
        s.phone = r.phone
        s.guardians = [g.model_dump() for g in r.guardians] or None
    audit(db, user, 'update', 'phones', c.id, count=len(body))           # nömrələr audit-ə yazılmır
    db.commit()
    return {'ok': True, 'count': len(body)}


@router.post('/{cid}/phones/import')
def import_phones(cid: int, dry_run: bool = True, file: UploadFile = File(...), user: User = Depends(staff),
                  db: Session = Depends(get_db)):
    c = homeroom_class(db, user, cid)
    name = (file.filename or '').lower()
    if not name.endswith(('.xlsx', '.csv')):
        raise HTTPException(400, 'Excel (.xlsx) və ya CSV faylı seçin')
    data = file.file.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise HTTPException(400, 'Fayl çox böyükdür (2 MB-a qədər)')
    try:
        rows = read_table(data, name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, 'Fayl oxunmadı – şablondan istifadə edin')
    studs = _studs(db, c.id)
    keys = {name_key(s.full_name): s for s in studs}
    report, matched = [], 0
    for r in rows:
        k = name_key(r['student'])
        s = keys.get(k) or next((v for kk, v in keys.items() if kk.startswith(k + ' ') or k.startswith(kk + ' ')), None)
        item = {'row': r['row'], 'name': r['student'], 'student': s.full_name if s else None, 'changes': [], 'errors': []}
        if not s:
            item['errors'].append('şagird sinifdə tapılmadı')
            report.append(item)
            continue
        guardians = [dict(g) for g in s.guardians or []]

        def put_g(relation: str, gname: str, raw: str):
            try:
                ph = norm_phone(raw)
            except ValueError as e:
                item['errors'].append(str(e))
                return
            if not gname and not ph:
                return
            cur = next((g for g in guardians if g.get('relation') == relation), None)
            if cur is None:
                if len(guardians) >= 4:
                    item['errors'].append('ən çox 4 valideyn')
                    return
                cur = {'name': gname or relation.capitalize(), 'relation': relation, 'phone': None}
                guardians.append(cur)
            if gname and len(gname) >= 2:
                cur['name'] = gname[:120]
            if ph:
                cur['phone'] = ph
            item['changes'].append(f"{relation}: {cur['name']}{' · ' + ph if ph else ''}")

        try:
            sp = norm_phone(r.get('student_phone'))
        except ValueError as e:
            sp = None
            item['errors'].append(str(e))
        if sp:
            item['changes'].append(f'şagird: {sp}')
        put_g('ana', r.get('mother', ''), r.get('mother_phone', ''))
        put_g('ata', r.get('father', ''), r.get('father_phone', ''))
        if item['changes']:
            matched += 1
            if not dry_run:
                if sp:
                    s.phone = sp
                s.guardians = [dict(g) for g in guardians] or None
        report.append(item)
    if not dry_run:
        audit(db, user, 'import', 'phones', c.id, count=matched)
        db.commit()
    return {'dry_run': dry_run, 'rows': len(rows), 'matched': matched,
            'errors': sum(bool(x['errors']) for x in report), 'report': report}


@router.get('/{cid}/phones/template')
def template(cid: int, user: User = Depends(staff), db: Session = Depends(get_db)):
    """Sinfin şagird adları ilə doldurulmuş şablon (mövcud nömrələr də yazılır – yalnız boşları doldurmaq olar)."""
    import openpyxl
    from openpyxl.styles import Font
    c = homeroom_class(db, user, cid)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Telefonlar'
    ws.append(['Şagird', 'Şagirdin telefonu', 'Ana', 'Ana telefonu', 'Ata', 'Ata telefonu'])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for s in _studs(db, c.id):
        g = {x.get('relation'): x for x in (s.guardians or [])}
        ws.append([s.full_name, s.phone or '', g.get('ana', {}).get('name', ''), g.get('ana', {}).get('phone') or '',
                   g.get('ata', {}).get('name', ''), g.get('ata', {}).get('phone') or ''])
    for col, w in zip('ABCDEF', (36, 20, 26, 20, 26, 20)):
        ws.column_dimensions[col].width = w
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fn = f'telefonlar-{c.code}.xlsx'
    return StreamingResponse(buf, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={'Content-Disposition': f'attachment; filename="{fn}"'})
