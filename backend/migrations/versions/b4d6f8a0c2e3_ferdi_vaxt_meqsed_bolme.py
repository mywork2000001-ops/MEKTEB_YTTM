"""fərdi qrup: dərs vaxtları, hazırlıq məqsədi; proqramdan bölmə seçimi

Revision ID: b4d6f8a0c2e3
Revises: a3c5e7f9b1d2
Create Date: 2026-10-04 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b4d6f8a0c2e3'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7f9b1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(table: str) -> set[str] | None:
    insp = sa.inspect(op.get_bind())
    return {c['name'] for c in insp.get_columns(table)} if insp.has_table(table) else None


def _add(table: str, col: sa.Column) -> None:
    """Yalnız cədvəl var və sütun yoxdursa (yarımçıq tətbiq olunmuş yerli bazalar üçün də təhlükəsiz)."""
    have = _cols(table)
    if have is not None and col.name not in have:
        with op.batch_alter_table(table) as b:
            b.add_column(col)


def upgrade() -> None:
    _add('teaching_assignments', sa.Column('times', sa.JSON(), nullable=True))
    _add('teaching_assignments', sa.Column('program_sections', sa.JSON(), nullable=True))
    _add('assignment_programs', sa.Column('sections', sa.JSON(), nullable=True))
    _add('classes', sa.Column('purpose', sa.String(20), nullable=True))


def downgrade() -> None:
    for table, col in (('classes', 'purpose'), ('assignment_programs', 'sections'),
                       ('teaching_assignments', 'program_sections'), ('teaching_assignments', 'times')):
        if col in (_cols(table) or set()):
            with op.batch_alter_table(table) as b:
                b.drop_column(col)
