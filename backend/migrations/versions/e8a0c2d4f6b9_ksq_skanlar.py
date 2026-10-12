"""KSQ/BSQ cavab kartı skanları: exam_scans.

Revision ID: e8a0c2d4f6b9
Revises: d7f9b1c3e5a8
Create Date: 2026-10-12 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e8a0c2d4f6b9'
down_revision: Union[str, Sequence[str], None] = 'd7f9b1c3e5a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exam_scans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('exam_id', sa.Integer(), sa.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('crop_key', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='pending'),
        sa.Column('reading', sa.JSON(), nullable=True),
        sa.Column('read_by', sa.String(length=20), nullable=True),
        sa.Column('marks', sa.JSON(), nullable=True),
        sa.Column('points', sa.Float(), nullable=True),
        sa.Column('flagged', sa.JSON(), nullable=True),
        sa.Column('history', sa.JSON(), nullable=True),
        sa.Column('error', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('exam_id', 'student_id'),
    )


def downgrade() -> None:
    op.drop_table('exam_scans')
