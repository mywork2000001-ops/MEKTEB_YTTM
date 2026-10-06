"""plan dərsinin P0010 test faylı – müəllimin seçimi

Revision ID: a9c3e5f7b1d2
Revises: f4b8d2a6c1e3
Create Date: 2026-10-06 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9c3e5f7b1d2'
down_revision: Union[str, Sequence[str], None] = 'f4b8d2a6c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if 'lesson_bank_links' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'lesson_bank_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_lesson_id', sa.Integer(), sa.ForeignKey('plan_lessons.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('bank_files.id', ondelete='SET NULL'), nullable=True),
        sa.Column('set_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('lesson_bank_links')
