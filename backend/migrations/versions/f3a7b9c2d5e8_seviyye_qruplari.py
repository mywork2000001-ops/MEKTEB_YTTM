"""səviyyə qrupları: bölgü mənbəyi, kilid, bal, komponentlər; tarixçə

Revision ID: f3a7b9c2d5e8
Revises: e2f6a8b1c4d7
Create Date: 2026-10-05 00:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3a7b9c2d5e8'
down_revision: Union[str, Sequence[str], None] = 'e2f6a8b1c4d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('level_overrides') as b:
        b.add_column(sa.Column('source', sa.String(length=10), nullable=False, server_default='manual'))
        b.add_column(sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.true()))
        b.add_column(sa.Column('score', sa.Float(), nullable=True))
        b.add_column(sa.Column('components', sa.JSON(), nullable=True))
    op.create_table(
        'level_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assignment_id', sa.Integer(), sa.ForeignKey('teaching_assignments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('old', sa.String(length=10), nullable=True),
        sa.Column('new', sa.String(length=10), nullable=True),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('level_history')
    with op.batch_alter_table('level_overrides') as b:
        for c in ('components', 'score', 'locked', 'source'):
            b.drop_column(c)
