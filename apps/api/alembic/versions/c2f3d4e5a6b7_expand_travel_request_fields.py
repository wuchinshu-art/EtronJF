"""expand travel request fields for standard application form

Revision ID: c2f3d4e5a6b7
Revises: b1e2d3c4a5f6
Create Date: 2026-10-24 19:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f3d4e5a6b7'
down_revision: Union[str, None] = 'b1e2d3c4a5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 擴充 travel_requests 資料表以支援標準出差申請單全部欄位
    with op.batch_alter_table('travel_requests') as batch_op:
        batch_op.add_column(sa.Column('region_type', sa.String(length=20), server_default='DOMESTIC', nullable=False))
        batch_op.add_column(sa.Column('start_time', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('end_time', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('estimated_nights', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('transport_modes', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('transport_other', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('needs_accommodation', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('accommodation_plan', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('companions', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('visiting_target', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('planned_agenda', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('expected_results', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('estimated_transport_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
        batch_op.add_column(sa.Column('estimated_accommodation_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
        batch_op.add_column(sa.Column('estimated_daily_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
        batch_op.add_column(sa.Column('estimated_other_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
        batch_op.add_column(sa.Column('estimated_total_cost', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False))
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('travel_requests') as batch_op:
        batch_op.drop_column('notes')
        batch_op.drop_column('estimated_total_cost')
        batch_op.drop_column('estimated_other_cost')
        batch_op.drop_column('estimated_daily_cost')
        batch_op.drop_column('estimated_accommodation_cost')
        batch_op.drop_column('estimated_transport_cost')
        batch_op.drop_column('expected_results')
        batch_op.drop_column('planned_agenda')
        batch_op.drop_column('visiting_target')
        batch_op.drop_column('companions')
        batch_op.drop_column('accommodation_plan')
        batch_op.drop_column('needs_accommodation')
        batch_op.drop_column('transport_other')
        batch_op.drop_column('transport_modes')
        batch_op.drop_column('estimated_nights')
        batch_op.drop_column('end_time')
        batch_op.drop_column('start_time')
        batch_op.drop_column('region_type')
