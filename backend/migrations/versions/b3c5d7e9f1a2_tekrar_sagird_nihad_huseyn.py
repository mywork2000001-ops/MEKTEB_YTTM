"""Təkrar şagirdlərin birləşdirilməsi (istifadəçinin göstərişi, 12.10.2026): Nihad – IX və XI (əsas: XI),
Hüseyn Əhmədov – X və XI (əsas: X). Əsas sinfin qeydi (ID ilə) qalır, digər sinif əlavə sinif olur.
Yalnız birmənalı halda (bax app/api/students.py::merge_named); əks halda heç nə edilmir.

Revision ID: b3c5d7e9f1a2
Revises: f7b9d1e3a5c8
Create Date: 2026-10-12 18:00:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b3c5d7e9f1a2'
down_revision: Union[str, Sequence[str], None] = 'f7b9d1e3a5c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.orm import Session
    from app.api.students import merge_named
    db = Session(bind=op.get_bind())
    log = merge_named(db, [({'Nihad'}, {11: True, 9: False}), ({'Hüseyn', 'Əhmədov'}, {10: True, 11: False})])
    db.flush()
    print('student merge:', log)                # ASCII – id və ID kodları


def downgrade() -> None:
    pass                                        # birləşdirmə geri qaytarılmır
