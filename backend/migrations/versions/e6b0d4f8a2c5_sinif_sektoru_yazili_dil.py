"""Sinfin sektoru və yazılı imtahanın dili: classes.sector, classes.exam_language, exams.language – yalnız nullable sütunlar, məlumat dəyişmir.

Revision ID: e6b0d4f8a2c5
Revises: d5a9c3e7b1f4
Create Date: 2026-10-24 15:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e6b0d4f8a2c5'
down_revision: Union[str, Sequence[str], None] = 'd5a9c3e7b1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('classes', sa.Column('sector', sa.String(length=4), nullable=True))
    op.add_column('classes', sa.Column('exam_language', sa.String(length=8), nullable=True))
    op.add_column('exams', sa.Column('language', sa.String(length=8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exams') as b:
        b.drop_column('language')
    with op.batch_alter_table('classes') as b:
        b.drop_column('exam_language')
        b.drop_column('sector')
