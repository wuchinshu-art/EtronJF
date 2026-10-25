"""add_timezone_to_shifts

Revision ID: d3e4f5a6b7c8
Revises: c2f3d4e5a6b7
Create Date: 2026-10-25 10:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2f3d4e5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_shifts;"))
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(50), server_default='Asia/Taipei', nullable=False))

    # 資料轉換 (Data Migration for existing shifts)
    conn.execute(sa.text("UPDATE shifts SET timezone = 'Asia/Taipei' WHERE timezone IS NULL;"))
    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.drop_column('timezone')
    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
