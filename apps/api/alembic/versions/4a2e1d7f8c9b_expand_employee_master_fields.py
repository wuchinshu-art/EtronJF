"""expand employee master fields with personal contact and employment data

Revision ID: 4a2e1d7f8c9b
Revises: 173ef1db1ffc
Create Date: 2026-10-23 13:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a2e1d7f8c9b'
down_revision: Union[str, None] = '173ef1db1ffc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 擴充 employees 表欄位
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('english_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('national_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('birth_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('gender', sa.String(length=20), server_default='NOT_SPECIFIED', nullable=False))
        batch_op.add_column(sa.Column('nationality', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('marital_status', sa.String(length=20), server_default='SINGLE', nullable=False))
        
        batch_op.add_column(sa.Column('personal_email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('mobile_phone', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('residential_address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('permanent_address', sa.String(length=255), nullable=True))
        
        batch_op.add_column(sa.Column('emergency_contact_name', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('emergency_contact_relationship', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('emergency_contact_phone', sa.String(length=30), nullable=True))
        
        batch_op.add_column(sa.Column('job_title', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('job_grade', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('employment_type', sa.String(length=20), server_default='REGULAR', nullable=False))
        batch_op.add_column(sa.Column('default_shift_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('probation_end_date', sa.Date(), nullable=True))
        
        batch_op.create_index('ix_employees_national_id', ['national_id'], unique=False)
        batch_op.create_foreign_key('fk_employees_default_shift_id', 'shifts', ['default_shift_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_constraint('fk_employees_default_shift_id', type_='foreignkey')
        batch_op.drop_index('ix_employees_national_id')
        batch_op.drop_column('probation_end_date')
        batch_op.drop_column('default_shift_id')
        batch_op.drop_column('employment_type')
        batch_op.drop_column('job_grade')
        batch_op.drop_column('job_title')
        batch_op.drop_column('emergency_contact_phone')
        batch_op.drop_column('emergency_contact_relationship')
        batch_op.drop_column('emergency_contact_name')
        batch_op.drop_column('permanent_address')
        batch_op.drop_column('residential_address')
        batch_op.drop_column('mobile_phone')
        batch_op.drop_column('personal_email')
        batch_op.drop_column('marital_status')
        batch_op.drop_column('nationality')
        batch_op.drop_column('gender')
        batch_op.drop_column('birth_date')
        batch_op.drop_column('national_id')
        batch_op.drop_column('english_name')
