"""Add QR codes to inventory and reservations

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('blood_inventory', schema=None) as batch_op:
        batch_op.add_column(sa.Column('qr_code', sa.String(length=80), nullable=True))
        batch_op.create_index(batch_op.f('ix_blood_inventory_qr_code'), ['qr_code'], unique=True)

    with op.batch_alter_table('blood_reservations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('qr_code', sa.String(length=80), nullable=True))
        batch_op.create_index(batch_op.f('ix_blood_reservations_qr_code'), ['qr_code'], unique=True)


def downgrade():
    with op.batch_alter_table('blood_reservations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blood_reservations_qr_code'))
        batch_op.drop_column('qr_code')

    with op.batch_alter_table('blood_inventory', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blood_inventory_qr_code'))
        batch_op.drop_column('qr_code')
