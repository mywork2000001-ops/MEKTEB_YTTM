"""çat: söhbəti özündə silmək (chat_members.cleared_id – bu id-yə qədərki mesajlar həmin istifadəçiyə görünmür)

Revision ID: a7c2e5f8b3d1
Revises: e9a2b4c6d8f1
Create Date: 2026-10-03 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c2e5f8b3d1'
down_revision: Union[str, Sequence[str], None] = 'e9a2b4c6d8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chat_members') as b:
        b.add_column(sa.Column('cleared_id', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('chat_members') as b:
        b.drop_column('cleared_id')
