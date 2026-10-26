"""make leave_types global (remove per-company restriction)

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-26 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_leave_types;"))

    # SQLite 中變更約束與 nullable 需要 batch_alter_table 重建表格
    with op.batch_alter_table('leave_types', schema=None) as batch_op:
        # 將 company_id 調整為可為空 (nullable=True)
        batch_op.alter_column('company_id',
                              existing_type=sa.String(length=50),
                              nullable=True)
        # 移除舊有公司與代碼複合唯一約束（若存在）
        try:
            batch_op.drop_constraint('uq_company_leave_code', type_='unique')
        except Exception:
            pass
        # 建立全局 code 唯一鍵約束
        batch_op.create_unique_constraint('uq_leave_types_code', ['code'])

    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_leave_types;"))

    # 復原時如果 company_id 為 NULL，需補預設公司代碼
    conn.execute(sa.text("UPDATE leave_types SET company_id = 'ETJ-TW' WHERE company_id IS NULL;"))

    with op.batch_alter_table('leave_types', schema=None) as batch_op:
        try:
            batch_op.drop_constraint('uq_leave_types_code', type_='unique')
        except Exception:
            pass
        batch_op.create_unique_constraint('uq_company_leave_code', ['company_id', 'code'])
        batch_op.alter_column('company_id',
                              existing_type=sa.String(length=50),
                              nullable=False)

    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
