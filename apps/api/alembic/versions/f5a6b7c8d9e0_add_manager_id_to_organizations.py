"""add manager_id to organizations

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-10-26 20:48:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_organizations;"))

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('manager_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_organizations_manager_id_employees',
            'employees',
            ['manager_id'],
            ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_index('ix_organizations_manager_id', ['manager_id'], unique=False)

    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_organizations;"))

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_index('ix_organizations_manager_id')
        batch_op.drop_constraint('fk_organizations_manager_id_employees', type_='foreignkey')
        batch_op.drop_column('manager_id')

    conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
