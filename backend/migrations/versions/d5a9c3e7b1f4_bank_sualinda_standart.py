"""Bank sualında standart: bank_questions.standard (String 64, nullable) – yalnız yeni sütun, məlumat dəyişmir.

Doldurma ayrıca skriptlə (backend/tools/fill_bank_standards.py, defolt – quru rejim).

Revision ID: d5a9c3e7b1f4
Revises: c4e8a2f6b1d9
Create Date: 2026-10-24 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd5a9c3e7b1f4'
down_revision: Union[str, Sequence[str], None] = 'c4e8a2f6b1d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_questions', sa.Column('standard', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('bank_questions') as b:
        b.drop_column('standard')
