"""Add transfer and low stock alert tables

Revision ID: a1b2c3d4e5f6
Revises: b1b1d4d4ef09
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'b1b1d4d4ef09'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'blood_transfers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_bank_id', sa.Integer(), nullable=False),
        sa.Column('destination_bank_id', sa.Integer(), nullable=False),
        sa.Column('blood_group', sa.String(length=5), nullable=False),
        sa.Column('component', sa.String(length=50), nullable=False),
        sa.Column('units', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_blood_transfers_created_at'), 'blood_transfers', ['created_at'], unique=False)
    op.create_index(op.f('ix_blood_transfers_destination_bank_id'), 'blood_transfers', ['destination_bank_id'], unique=False)
    op.create_index(op.f('ix_blood_transfers_source_bank_id'), 'blood_transfers', ['source_bank_id'], unique=False)
    op.create_index(op.f('ix_blood_transfers_status'), 'blood_transfers', ['status'], unique=False)
    op.create_index(op.f('ix_blood_transfers_blood_group'), 'blood_transfers', ['blood_group'], unique=False)

    op.create_table(
        'low_stock_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('blood_bank_id', sa.Integer(), nullable=False),
        sa.Column('blood_group', sa.String(length=5), nullable=False),
        sa.Column('component', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_low_stock_alerts_blood_bank_id'), 'low_stock_alerts', ['blood_bank_id'], unique=False)
    op.create_index(op.f('ix_low_stock_alerts_blood_group'), 'low_stock_alerts', ['blood_group'], unique=False)
    op.create_index(op.f('ix_low_stock_alerts_created_at'), 'low_stock_alerts', ['created_at'], unique=False)
    op.create_index(op.f('ix_low_stock_alerts_severity'), 'low_stock_alerts', ['severity'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_low_stock_alerts_severity'), table_name='low_stock_alerts')
    op.drop_index(op.f('ix_low_stock_alerts_created_at'), table_name='low_stock_alerts')
    op.drop_index(op.f('ix_low_stock_alerts_blood_group'), table_name='low_stock_alerts')
    op.drop_index(op.f('ix_low_stock_alerts_blood_bank_id'), table_name='low_stock_alerts')
    op.drop_table('low_stock_alerts')

    op.drop_index(op.f('ix_blood_transfers_blood_group'), table_name='blood_transfers')
    op.drop_index(op.f('ix_blood_transfers_status'), table_name='blood_transfers')
    op.drop_index(op.f('ix_blood_transfers_source_bank_id'), table_name='blood_transfers')
    op.drop_index(op.f('ix_blood_transfers_destination_bank_id'), table_name='blood_transfers')
    op.drop_index(op.f('ix_blood_transfers_created_at'), table_name='blood_transfers')
    op.drop_table('blood_transfers')
