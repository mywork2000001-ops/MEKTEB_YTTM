"""sorğu: ümumi qiymət və tövsiyə suallarında «bal» sözü yoxdur – şagird cavabı sözlə seçir

Revision ID: a7c9e1b3d5f6
Revises: e4a6c8d0f2b3
Create Date: 2026-10-06 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c9e1b3d5f6'
down_revision: Union[str, Sequence[str], None] = 'e4a6c8d0f2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEXTS = [
    ('Müəllimin işini 1–10 bal ilə qiymətləndirin.', 'Ümumilikdə müəllimin işi sizcə necədir?'),
    ('Bu müəllimi dostlarınıza tövsiyə edərdinizmi? (0 – heç vaxt, 10 – mütləq)', 'Bu müəllimi dostlarınıza tövsiyə edərdinizmi?'),
]


def upgrade() -> None:
    for old, new in _TEXTS:
        op.get_bind().execute(sa.text('UPDATE survey_questions SET text = :new WHERE text = :old'), {'old': old, 'new': new})


def downgrade() -> None:
    for old, new in _TEXTS:
        op.get_bind().execute(sa.text('UPDATE survey_questions SET text = :old WHERE text = :new'), {'old': old, 'new': new})
