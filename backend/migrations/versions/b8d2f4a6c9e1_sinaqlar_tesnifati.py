"""«Sınaqlar» mənbəyinin fayllarının yenidən təsnifatı: hamısı sınaq (OBM mövzu sınaqları, RF MS1…5 əvvəl «mövzu» idi),
adsız buraxılış sınaqlarına XI sinif. Admin əl ilə kilidlədiyi fayllara toxunulmur.

Revision ID: b8d2f4a6c9e1
Revises: a7c9e1b3d5f6
Create Date: 2026-10-06 18:00:00

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d2f4a6c9e1'
down_revision: Union[str, Sequence[str], None] = 'a7c9e1b3d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.bank.classify import classify
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, label, kind, grades, meta_locked FROM bank_files "
                                "WHERE source_key = 'sinaqlar'")).all()
    for fid, label, kind, grades, locked in rows:
        if locked:
            continue
        if isinstance(grades, str):
            grades = json.loads(grades)
        c = classify('sinaqlar', label or '')
        if (kind, grades or []) != (c['kind'], c['grades']):
            bind.execute(sa.text('UPDATE bank_files SET kind = :k, grades = :g WHERE id = :i')
                         .bindparams(sa.bindparam('g', type_=sa.JSON)), {'k': c['kind'], 'g': c['grades'], 'i': fid})


def downgrade() -> None:
    pass                                           # köhnə (səhv) təsnifat geri qaytarılmır
