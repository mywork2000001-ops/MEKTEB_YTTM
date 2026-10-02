"""əlavə məşğələ: «Materiallar» bölməsindən material bağlantısı

Revision ID: b5c9d2e4f7a1
Revises: a4b8c1d3e6f9
Create Date: 2026-10-03 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b5c9d2e4f7a1'
down_revision: Union[str, Sequence[str], None] = 'a4b8c1d3e6f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('extra_sessions') as b:
        b.add_column(sa.Column('material_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('extra_sessions') as b:
        b.drop_column('material_ids')
