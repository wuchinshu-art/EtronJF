"""create persons table and link to employees

Revision ID: 9c5e0f1a2b3d
Revises: 8b4d9e2c1a5f
Create Date: 2026-10-23 18:00:00.000000

"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c5e0f1a2b3d'
down_revision: Union[str, None] = '8b4d9e2c1a5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 建立 persons 人員個資主檔表
    op.create_table(
        'persons',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('national_id', sa.String(length=50), nullable=True),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('english_name', sa.String(length=100), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('gender', sa.String(length=20), server_default='NOT_SPECIFIED', nullable=False),
        sa.Column('nationality', sa.String(length=50), nullable=True),
        sa.Column('marital_status', sa.String(length=20), server_default='SINGLE', nullable=False),
        sa.Column('personal_email', sa.String(length=255), nullable=True),
        sa.Column('mobile_phone', sa.String(length=30), nullable=True),
        sa.Column('residential_address', sa.String(length=255), nullable=True),
        sa.Column('permanent_address', sa.String(length=255), nullable=True),
        sa.Column('emergency_contact_name', sa.String(length=50), nullable=True),
        sa.Column('emergency_contact_relationship', sa.String(length=30), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_persons_national_id', 'persons', ['national_id'], unique=False)

    # 2. 於 employees 新增 person_id 欄位
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('person_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_employees_person_id', ['person_id'], unique=False)
        batch_op.create_foreign_key('fk_employees_person_id', 'persons', ['person_id'], ['id'], ondelete='RESTRICT')

    # 3. 資料移轉：將既有 employees 歷史資料平滑抽取並生成對應之 Person 主檔
    conn = op.get_bind()
    employees_res = conn.execute(sa.text("""
        SELECT id, full_name, english_name, national_id, birth_date, gender, nationality,
               marital_status, personal_email, mobile_phone, residential_address,
               permanent_address, emergency_contact_name, emergency_contact_relationship,
               emergency_contact_phone
        FROM employees
    """)).fetchall()

    # 依 national_id 或 id 分組生成 Person
    person_cache = {}
    for row in employees_res:
        emp_id = row[0]
        full_name = row[1]
        english_name = row[2]
        nat_id = row[3]
        birth_date = row[4]
        gender = row[5] or 'NOT_SPECIFIED'
        nationality = row[6]
        marital_status = row[7] or 'SINGLE'
        p_email = row[8]
        phone = row[9]
        res_addr = row[10]
        perm_addr = row[11]
        e_name = row[12]
        e_rel = row[13]
        e_phone = row[14]

        # 若有 national_id，相同 national_id 共用同一個 Person
        cache_key = nat_id if nat_id else f"emp_{emp_id}"
        if cache_key in person_cache:
            person_id = person_cache[cache_key]
        else:
            person_id = str(uuid.uuid4())
            person_cache[cache_key] = person_id
            conn.execute(sa.text("""
                INSERT INTO persons (
                    id, national_id, full_name, english_name, birth_date, gender, nationality,
                    marital_status, personal_email, mobile_phone, residential_address,
                    permanent_address, emergency_contact_name, emergency_contact_relationship,
                    emergency_contact_phone, created_at, updated_at
                ) VALUES (
                    :id, :national_id, :full_name, :english_name, :birth_date, :gender, :nationality,
                    :marital_status, :personal_email, :mobile_phone, :residential_address,
                    :permanent_address, :emergency_contact_name, :emergency_contact_relationship,
                    :emergency_contact_phone, datetime('now'), datetime('now')
                )
            """), {
                "id": person_id,
                "national_id": nat_id,
                "full_name": full_name,
                "english_name": english_name,
                "birth_date": birth_date,
                "gender": gender,
                "nationality": nationality,
                "marital_status": marital_status,
                "personal_email": p_email,
                "mobile_phone": phone,
                "residential_address": res_addr,
                "permanent_address": perm_addr,
                "emergency_contact_name": e_name,
                "emergency_contact_relationship": e_rel,
                "emergency_contact_phone": e_phone,
            })

        # 回填 employees.person_id
        conn.execute(sa.text("""
            UPDATE employees SET person_id = :person_id WHERE id = :emp_id
        """), {"person_id": person_id, "emp_id": emp_id})


def downgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_constraint('fk_employees_person_id', type_='foreignkey')
        batch_op.drop_index('ix_employees_person_id')
        batch_op.drop_column('person_id')

    op.drop_index('ix_persons_national_id', table_name='persons')
    op.drop_table('persons')
