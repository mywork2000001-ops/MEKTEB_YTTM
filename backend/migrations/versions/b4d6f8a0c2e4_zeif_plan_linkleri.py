"""Zəif qrup tempi planlarında köhnə test faylı seçimlərini sil (docs/zeif-plan-test-linkleri-promtu.md).

Plan yeni proqramla sıra № üzrə yeniləndiyindən köhnə planın əl seçimləri (lesson_bank_links) başqa mövzuların altında qalmışdı.
Silinir: proqram mənbəyi «Zəif qrup tempi (2 il)» olan sinif dərslərində 13.10.2026-dan sonrakı dərslərin seçimləri –
həmin dərslər avtomatik uyğunluğa qayıdır.

Revision ID: b4d6f8a0c2e4
Revises: a3c5e7b9d1f3
Create Date: 2026-10-13 23:30:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b4d6f8a0c2e4'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7b9d1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM lesson_bank_links WHERE plan_lesson_id IN (
            SELECT pl.id FROM plan_lessons pl
            JOIN teaching_assignments ta ON ta.id = pl.assignment_id
            JOIN plan_programs pp ON pp.id = ta.program_id
            WHERE pp.source = 'Zəif qrup tempi (2 il)' AND pl.date > '2026-10-13')
    """)


def downgrade() -> None:
    pass
