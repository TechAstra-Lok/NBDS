"""Add inventory expiry and movement tracking

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('blood_inventory', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expiry_date', sa.String(length=20), nullable=True))

    op.create_table(
        'blood_inventory_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('movement_type', sa.String(length=30), nullable=False),
        sa.Column('units', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_blood_inventory_movements_created_at'), 'blood_inventory_movements', ['created_at'], unique=False)
    op.create_index(op.f('ix_blood_inventory_movements_inventory_id'), 'blood_inventory_movements', ['inventory_id'], unique=False)
    op.create_index(op.f('ix_blood_inventory_movements_movement_type'), 'blood_inventory_movements', ['movement_type'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_blood_inventory_movements_movement_type'), table_name='blood_inventory_movements')
    op.drop_index(op.f('ix_blood_inventory_movements_inventory_id'), table_name='blood_inventory_movements')
    op.drop_index(op.f('ix_blood_inventory_movements_created_at'), table_name='blood_inventory_movements')
    op.drop_table('blood_inventory_movements')

    with op.batch_alter_table('blood_inventory', schema=None) as batch_op:
        batch_op.drop_column('expiry_date')
