"""Yazılı (kağız) test / sınaq / sərbəst yazılı iş (docs/yazili-sinaq-ve-skan-duymesi-promtu.md §A).

exams cədvəli:
- kind: String(3) -> String(5)  (KSQ | BSQ | TEST | SINAQ | YI)
- online_task_id (FK online_tasks, SET NULL), batch_id (FK test_batches, SET NULL) – bağlı onlayn tapşırıq / sınaq paketi
- to_journal (bool, standart TRUE – mövcud KSQ/BSQ dəyişmir): nəticə jurnala yalnız müəllim seçərsə düşür
- variant_mode: same | different

Mövcud sətirlərə toxunulmur (yalnız yeni sütunlar). Downgrade: yeni növlü imtahanlar (TEST/SINAQ/YI) silinir, sütunlar atılır.

Revision ID: 3f8a6c1e9b47
Revises: e8a0c2d4f6b1
Create Date: 2026-10-19 18:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '3f8a6c1e9b47'
down_revision: Union[str, Sequence[str], None] = 'e8a0c2d4f6b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exams') as b:
        b.alter_column('kind', existing_type=sa.String(length=3), type_=sa.String(length=5), existing_nullable=False)
        b.add_column(sa.Column('online_task_id', sa.Integer(), sa.ForeignKey('online_tasks.id', ondelete='SET NULL', name='fk_exams_online_task_id'), nullable=True))
        b.add_column(sa.Column('batch_id', sa.Integer(), sa.ForeignKey('test_batches.id', ondelete='SET NULL', name='fk_exams_batch_id'), nullable=True))
        b.add_column(sa.Column('to_journal', sa.Boolean(), nullable=False, server_default=sa.true()))
        b.add_column(sa.Column('variant_mode', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM exams WHERE kind NOT IN ('KSQ', 'BSQ')")          # uşaq sətirlər (variant, skan, bal) CASCADE ilə silinir
    with op.batch_alter_table('exams') as b:
        b.drop_column('variant_mode')
        b.drop_column('to_journal')
        b.drop_column('batch_id')
        b.drop_column('online_task_id')
        b.alter_column('kind', existing_type=sa.String(length=5), type_=sa.String(length=3), existing_nullable=False)


