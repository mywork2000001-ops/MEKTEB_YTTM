"""XI peşə sinfi ↔ UTİS «11 p» (yalnız bağlantı boşdursa; şagirdlər fayl idxalı ilə gəlir)

Revision ID: e7f1b3c5d9a2
Revises: d5e2a7b9c1f3
Create Date: 2026-09-30 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e7f1b3c5d9a2'
down_revision: Union[str, Sequence[str], None] = 'd5e2a7b9c1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE classes SET utis_class = '11 p' WHERE name = 'XI peşə sinfi' AND utis_class IS NULL"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE classes SET utis_class = NULL WHERE name = 'XI peşə sinfi' AND utis_class = '11 p'"))
