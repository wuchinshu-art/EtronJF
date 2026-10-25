"""add paid_type to leave_types

Revision ID: b1e2d3c4a5f6
Revises: ad12e45f6a7b
Create Date: 2026-10-24 19:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1e2d3c4a5f6'
down_revision: Union[str, None] = 'ad12e45f6a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 擴充 leave_types 資料表以支援給薪方式 paid_type (FULL, HALF, UNPAID)
    with op.batch_alter_table('leave_types') as batch_op:
        batch_op.add_column(sa.Column('paid_type', sa.String(length=10), server_default='FULL', nullable=False))

    # 資料轉換 (Data Migration for existing leave types)
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE leave_types SET paid_type = 'UNPAID' WHERE is_paid = 0 OR is_paid = false;"))
    conn.execute(sa.text("UPDATE leave_types SET paid_type = 'FULL' WHERE is_paid = 1 OR is_paid = true;"))


def downgrade() -> None:
    with op.batch_alter_table('leave_types') as batch_op:
        batch_op.drop_column('paid_type')
