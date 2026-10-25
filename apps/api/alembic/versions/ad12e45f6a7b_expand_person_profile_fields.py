"""expand person profile fields
Revision ID: ad12e45f6a7b
Revises: 9c5e0f1a2b3d
Create Date: 2026-10-23 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad12e45f6a7b'
down_revision: Union[str, None] = '9c5e0f1a2b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 擴充 persons 資料表欄位以支援完整新進員工基本資料表
    with op.batch_alter_table('persons') as batch_op:
        batch_op.add_column(sa.Column('blood_type', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('military_service_status', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('driving_licenses', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('transportation_modes', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('height_cm', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('weight_kg', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('contact_phone', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('emergency_contact_mobile', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('education_history', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('work_experience', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('persons') as batch_op:
        batch_op.drop_column('work_experience')
        batch_op.drop_column('education_history')
        batch_op.drop_column('emergency_contact_mobile')
        batch_op.drop_column('contact_phone')
        batch_op.drop_column('weight_kg')
        batch_op.drop_column('height_cm')
        batch_op.drop_column('transportation_modes')
        batch_op.drop_column('driving_licenses')
        batch_op.drop_column('military_service_status')
        batch_op.drop_column('blood_type')
