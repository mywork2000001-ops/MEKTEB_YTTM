"""Şagirdə cavab kartı və apelyasiya (mərhələ 3–4).

- exams.results_published_at – müəllim «nəticəni şagirdlərə göstər» etdikdən sonra; exams.appeal_until – apelyasiya müddəti
- exam_appeals – sual üzrə apelyasiya (bank ünvanı snapshot, qərar, hamıya tətbiq)
- bank_questions.needs_review – apelyasiyada açar səhv çıxdı, bank yoxlanmalıdır (avtomatik dəyişmə yoxdur)

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
        b.add_column(sa.Column('appeal_until', sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table('bank_questions') as b:
        b.add_column(sa.Column('needs_review', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'exam_appeals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('exam_id', sa.Integer(), sa.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
        sa.Column('slot', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False, server_default='paper'),
        sa.Column('bank_id', sa.Integer(), nullable=True),
        sa.Column('bank_ref', sa.JSON(), nullable=True),
        sa.Column('my_answer', sa.Text(), nullable=True),
        sa.Column('correct_at_time', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False, server_default='open'),
        sa.Column('teacher_reply', sa.Text(), nullable=True),
        sa.Column('apply_all', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('decided_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('exam_id', 'student_id', 'slot', 'source'),
    )


def downgrade() -> None:
    op.drop_table('exam_appeals')
    with op.batch_alter_table('bank_questions') as b:
        b.drop_column('needs_review')
    with op.batch_alter_table('exams') as b:
        b.drop_column('appeal_until')
        b.drop_column('results_published_at')
