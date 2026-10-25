"""add_shift_break_interval_and_flex_minutes

Revision ID: 8b4d9e2c1a5f
Revises: 7a3c8e1b9d4f
Create Date: 2026-10-23 16:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b4d9e2c1a5f'
down_revision: Union[str, None] = '7a3c8e1b9d4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_shifts;"))
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('break_start_time', sa.String(5), nullable=True))
        batch_op.add_column(sa.Column('break_end_time', sa.String(5), nullable=True))
        batch_op.add_column(sa.Column('flex_minutes', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))

    # 資料轉換 (Data Migration for existing shifts)
    conn.execute(sa.text("UPDATE shifts SET break_start_time = '12:00', break_end_time = '13:00', flex_minutes = 30 WHERE id = 'SHIFT-STD-8H';"))
    conn.execute(sa.text("UPDATE shifts SET break_start_time = '23:30', break_end_time = '00:30', flex_minutes = 0 WHERE id = 'SHIFT-NIGHT-TW';"))
    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('flex_minutes')
        batch_op.drop_column('break_end_time')
        batch_op.drop_column('break_start_time')
    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
