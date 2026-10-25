"""add_org_effective_and_expiry_dates

Revision ID: 7a3c8e1b9d4f
Revises: 24f46cc63859
Create Date: 2026-10-23 14:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a3c8e1b9d4f'
down_revision: Union[str, None] = '24f46cc63859'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_organizations;"))
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('effective_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('expiry_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('expiry_date')
        batch_op.drop_column('effective_date')
    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
