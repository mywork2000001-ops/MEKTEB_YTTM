"""KSQ/BSQ kağız variantları: exam_variants (hər şagirdə fərqli 30 sual).

Revision ID: d7f9b1c3e5a8
Revises: c6e8a0b2d4f7
Create Date: 2026-10-12 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd7f9b1c3e5a8'
down_revision: Union[str, Sequence[str], None] = 'c6e8a0b2d4f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'exam_variants',
        sa.Column('exam_id', sa.Integer(), sa.ForeignKey('exams.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('questions', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('exam_id', 'code'),
    )


def downgrade() -> None:
    op.drop_table('exam_variants')
