"""analitika və çap: jurnal yazısının «auto» işarəsi (onlayn testdən), məktəbin sənəd ayarları (imza verənlər)

Mövcud yazılar: davamiyyəti, ev tapşırığı yoxlaması, ev tapşırığı, qeydi, əl ilə mövzusu olmayan və bütün qiymətləri
onlayn testdən gələn yazılar «auto» işarələnir (müəllim saxlamayıb).

Revision ID: b8d3f1a6c2e4
Revises: a7c2e5f8b3d1
Create Date: 2026-10-03 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d3f1a6c2e4'
down_revision: Union[str, Sequence[str], None] = 'a7c2e5f8b3d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('journal_entries') as b:
        b.add_column(sa.Column('auto', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('schools') as b:
        b.add_column(sa.Column('doc_settings', sa.JSON(), nullable=True))
    op.execute(sa.text("""
        UPDATE journal_entries SET auto = :t
        WHERE homework IS NULL AND note IS NULL AND topic IS NULL
          AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.entry_id = journal_entries.id)
          AND NOT EXISTS (SELECT 1 FROM homework_checks h WHERE h.entry_id = journal_entries.id)
          AND EXISTS (SELECT 1 FROM marks m WHERE m.entry_id = journal_entries.id)
          AND NOT EXISTS (SELECT 1 FROM marks m WHERE m.entry_id = journal_entries.id AND m.task_id IS NULL)
    """).bindparams(t=True))


def downgrade() -> None:
    with op.batch_alter_table('schools') as b:
        b.drop_column('doc_settings')
    with op.batch_alter_table('journal_entries') as b:
        b.drop_column('auto')
