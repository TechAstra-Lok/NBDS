"""Add blood bank directory

Revision ID: b1b1d4d4ef09
Revises: 0863441bfaf3
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1b1d4d4ef09'
down_revision = '0863441bfaf3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'blood_banks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('hospital_name', sa.String(length=200), nullable=True),
        sa.Column('parent_organization', sa.String(length=200), nullable=True),
        sa.Column('service_type', sa.String(length=60), nullable=True),
        sa.Column('province', sa.String(length=60), nullable=True),
        sa.Column('district', sa.String(length=80), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=True),
        sa.Column('local_level', sa.String(length=120), nullable=True),
        sa.Column('ward', sa.String(length=20), nullable=True),
        sa.Column('tole', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('website', sa.String(length=250), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('google_maps', sa.String(length=500), nullable=True),
        sa.Column('emergency_available', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blood_banks_district'), 'blood_banks', ['district'], unique=False)
    op.create_index(op.f('ix_blood_banks_is_active'), 'blood_banks', ['is_active'], unique=False)
    op.create_index(op.f('ix_blood_banks_name'), 'blood_banks', ['name'], unique=False)
    op.create_index(op.f('ix_blood_banks_province'), 'blood_banks', ['province'], unique=False)
    op.create_index(op.f('ix_blood_banks_status'), 'blood_banks', ['status'], unique=False)
    op.create_index(op.f('ix_blood_banks_uuid'), 'blood_banks', ['uuid'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_blood_banks_uuid'), table_name='blood_banks')
    op.drop_index(op.f('ix_blood_banks_status'), table_name='blood_banks')
    op.drop_index(op.f('ix_blood_banks_province'), table_name='blood_banks')
    op.drop_index(op.f('ix_blood_banks_name'), table_name='blood_banks')
    op.drop_index(op.f('ix_blood_banks_is_active'), table_name='blood_banks')
    op.drop_index(op.f('ix_blood_banks_district'), table_name='blood_banks')
    op.drop_table('blood_banks')
