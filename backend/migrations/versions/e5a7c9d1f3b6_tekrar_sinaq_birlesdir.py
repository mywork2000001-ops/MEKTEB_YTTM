"""«Yenidən göndər» ilə yaranmış ayrıca sınaq paketləri mənbə sınağına birləşdirilir (siyahıda təkrar sətir olmasın).

Şərt: tapşırıq audit jurnalında `copied_from` ilə yaranıb, özü və mənbəyi sınaqdır, öz paketində yalnız bu tapşırıq var.
Zəncir (surətin surəti) – id artan sıra ilə işlənir, mənbə əvvəlcə öz kökünə keçir.

Revision ID: e5a7c9d1f3b6
Revises: d4f6a8c0e2b4
Create Date: 2026-10-12 12:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5a7c9d1f3b6'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8c0e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.api.exams_online import merge_resend_batches
    merge_resend_batches(op.get_bind())


def downgrade() -> None:
    pass                                        # birləşdirmə geri qaytarılmır (məlumat itmir – yalnız paket bağı)
