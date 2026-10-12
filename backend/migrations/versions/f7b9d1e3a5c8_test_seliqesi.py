"""Köhnə mövzu testləri və sınaqların səliqəsi: bağlanmamışlarda həll müddəti ən azı 45 dəq; heç kimin başlamadığı
təkrar surətlər silinir (nəticəsi olan test silinmir). Məntiq: app/api/tasks.py::tidy_tasks.

Revision ID: f7b9d1e3a5c8
Revises: e5a7c9d1f3b6
Create Date: 2026-10-12 15:00:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'f7b9d1e3a5c8'
down_revision: Union[str, Sequence[str], None] = 'e5a7c9d1f3b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.api.tasks import tidy_tasks
    print('test tidy:', tidy_tasks(op.get_bind()))      # ASCII – konsolun kodlaşdırması nə olursa olsun


def downgrade() -> None:
    pass                                         # silinən boş surətlər geri qaytarılmır
