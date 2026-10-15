"""Əlavə KSQ/BSQ (docs/tasks/ksq-bsq-elave-ve-iki-netice.md, mərhələ 1).

- exams: extra_of (əsas imtahan), extra_seq (əsasda 0), extra_students (JSON); unikal: (assignment_id, kind, semester, no, extra_seq)

Revision ID: c5e7a9b1d3f6
Revises: b4d6f8a0c2e4
Create Date: 2026-10-15 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5e7a9b1d3f6'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQLite-da adsız UNIQUE-ləri batch rejimində adlandırmaq üçün (PostgreSQL-də reflect adı özü verir)
_NC = {'uq': 'uq_%(table_name)s_%(column_0_name)s'}


def _swap_unique(table: str, old_cols: list[str], new_name: str, new_cols: list[str]) -> None:
    """Köhnə UNIQUE (old_cols) silinir, yenisi yaradılır. PostgreSQL – reflect olunan ad; SQLite – batch + naming_convention."""
    insp = sa.inspect(op.get_bind())
    old = next((u['name'] for u in insp.get_unique_constraints(table) if list(u['column_names']) == old_cols), None)
    with op.batch_alter_table(table, naming_convention=_NC) as b:
        b.drop_constraint(old or f'uq_{table}_{old_cols[0]}', type_='unique')
        b.create_unique_constraint(new_name, new_cols)


def upgrade() -> None:
    with op.batch_alter_table('exams') as b:
        b.add_column(sa.Column('extra_of', sa.Integer(), nullable=True))
        b.add_column(sa.Column('extra_seq', sa.Integer(), nullable=False, server_default='0'))
        b.add_column(sa.Column('extra_students', sa.JSON(), nullable=True))
        b.create_foreign_key('fk_exams_extra_of', 'exams', ['extra_of'], ['id'], ondelete='SET NULL')
    _swap_unique('exams', ['assignment_id', 'kind', 'semester', 'no'], 'uq_exams_extra',
                 ['assignment_id', 'kind', 'semester', 'no', 'extra_seq'])



def downgrade() -> None:
    # əlavə imtahanlar (və onların nəticələri) silinir – köhnə sxemdə yoxdur
    for t in ('exam_scans', 'exam_scores', 'exam_variants', 'online_tasks'):
        col = 'exam_id'
        op.execute(f'DELETE FROM {t} WHERE {col} IN (SELECT id FROM exams WHERE extra_seq > 0)')
    op.execute('DELETE FROM exams WHERE extra_seq > 0')
    with op.batch_alter_table('exams', naming_convention=_NC) as b:
        b.drop_constraint('uq_exams_extra', type_='unique')
        b.create_unique_constraint('uq_exams_assignment_id', ['assignment_id', 'kind', 'semester', 'no'])
        b.drop_constraint('fk_exams_extra_of', type_='foreignkey')
        b.drop_column('extra_students')
        b.drop_column('extra_seq')
        b.drop_column('extra_of')
