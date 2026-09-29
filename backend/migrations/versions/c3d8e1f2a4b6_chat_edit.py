"""çat: mesajın redaktəsi (edited_at)

Revision ID: c3d8e1f2a4b6
Revises: 9a4f6c2e1d55
Create Date: 2026-09-30 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3d8e1f2a4b6'
down_revision: Union[str, Sequence[str], None] = '9a4f6c2e1d55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chat_messages') as b:
        b.add_column(sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('chat_messages') as b:
        b.drop_column('edited_at')
