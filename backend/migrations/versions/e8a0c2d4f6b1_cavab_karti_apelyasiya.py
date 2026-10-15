"""Şagirdə cavab kartı (mərhələ 3): exams.results_published_at – müəllim «nəticəni şagirdlərə göstər» etdikdən sonra.

Revision ID: e8a0c2d4f6b1
Revises: c5e7a9b1d3f6
Create Date: 2026-10-15 15:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e8a0c2d4f6b1'
down_revision: Union[str, Sequence[str], None] = 'c5e7a9b1d3f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exams') as b:
        b.add_column(sa.Column('results_published_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('exams') as b:
        b.drop_column('results_published_at')
