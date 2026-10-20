"""Kağız KSQ/BSQ nəticə paketi (docs/ksq-kagiz-netice-paketi-promtu.md §2.2).

- exams.send_on_scan (bool, standart FALSE): kart qiymətləndirilən kimi həmin şagirdə paket açılır;
- exam_deliveries: şagird üzrə göndəriş statusu (göndərilib / baxıb).
Mövcud sətirlərə toxunulmur (yalnız yeni sütun və cədvəl).

Revision ID: 5b2d7e9f1a64
Revises: 3f8a6c1e9b47
Create Date: 2026-10-19 21:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '5b2d7e9f1a64'
down_revision: Union[str, Sequence[str], None] = '3f8a6c1e9b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exams') as b:
        b.add_column(sa.Column('send_on_scan', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'exam_deliveries',
        sa.Column('exam_id', sa.Integer(), sa.ForeignKey('exams.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('via', sa.String(length=8), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('exam_deliveries')
    with op.batch_alter_table('exams') as b:
        b.drop_column('send_on_scan')
