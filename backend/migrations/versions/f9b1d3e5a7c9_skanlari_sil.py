"""Bütün siniflərdə kağız cavab kartlarının skanlarını sil – müəllim təzədən skan edir (docs/kart-skanlarini-silme-promtu.md).

Silinir: exam_scans (read_by ≠ 'online') və həmin şagird+imtahan üzrə exam_scores. Qalır: onlayn yazılar, variantlar, əl balları,
kəsik şəkilləri. Əvvəlcə ehtiyat: exam_scans_backup_20261013, exam_scores_backup_20261013 (downgrade – bərpa).

Revision ID: f9b1d3e5a7c9
Revises: e7a9c1d3f5b8
Create Date: 2026-10-13 21:00:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f9b1d3e5a7c9'
down_revision: Union[str, Sequence[str], None] = 'e7a9c1d3f5b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PAPER = "coalesce(read_by, '') <> 'online'"
PAIR = ("EXISTS (SELECT 1 FROM exam_scans c WHERE c.exam_id = exam_scores.exam_id AND c.student_id = exam_scores.student_id "
        "AND coalesce(c.read_by, '') <> 'online')")


def upgrade() -> None:
    # ehtiyat – silmə ilə eyni tranzaksiyada (yarımçıq vəziyyət qalmır)
    op.execute(f'CREATE TABLE exam_scores_backup_20261013 AS SELECT * FROM exam_scores WHERE {PAIR}')
    op.execute(f'CREATE TABLE exam_scans_backup_20261013 AS SELECT * FROM exam_scans WHERE {PAPER}')
    op.execute(f'DELETE FROM exam_scores WHERE {PAIR}')
    op.execute(f'DELETE FROM exam_scans WHERE {PAPER}')


def downgrade() -> None:
    # bərpa: yalnız olmayan sətirlər (təzə skan / bal üzərinə yazılmır)
    op.execute('INSERT INTO exam_scans SELECT * FROM exam_scans_backup_20261013 b '
               'WHERE NOT EXISTS (SELECT 1 FROM exam_scans c WHERE c.exam_id = b.exam_id AND c.student_id = b.student_id) '
               'AND NOT EXISTS (SELECT 1 FROM exam_scans c WHERE c.id = b.id)')
    op.execute('INSERT INTO exam_scores SELECT * FROM exam_scores_backup_20261013 b '
               'WHERE NOT EXISTS (SELECT 1 FROM exam_scores s WHERE s.exam_id = b.exam_id AND s.student_id = b.student_id)')
    op.execute('DROP TABLE exam_scans_backup_20261013')
    op.execute('DROP TABLE exam_scores_backup_20261013')
