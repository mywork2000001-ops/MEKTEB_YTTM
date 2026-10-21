"""Dəftər yoxlaması: material_submissions.ai_check (JSON, nullable) – yalnız yeni sütun.

Revision ID: c4e8a2f6b1d9
Revises: b2d6f0a4c8e1
Create Date: 2026-10-21 20:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4e8a2f6b1d9'
down_revision: Union[str, Sequence[str], None] = 'b2d6f0a4c8e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('material_submissions', sa.Column('ai_check', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('material_submissions', 'ai_check')
