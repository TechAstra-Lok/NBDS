"""Add Blood Bank Auth models

Revision ID: 79e548adfbf6
Revises: c031439da5e2
Create Date: 2026-07-09 23:33:22.878170

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79e548adfbf6'
down_revision = 'c031439da5e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('blood_bank_accounts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('blood_bank_id', sa.Integer(), nullable=False),
    sa.Column('login_id', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('password_change_required', sa.Boolean(), nullable=True),
    sa.Column('account_status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('password_changed_at', sa.DateTime(), nullable=True),
    sa.Column('is_locked', sa.Boolean(), nullable=True),
    sa.Column('failed_login_attempts', sa.Integer(), nullable=True),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['blood_bank_id'], ['blood_banks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('blood_bank_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_blood_bank_accounts_blood_bank_id'), ['blood_bank_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_blood_bank_accounts_login_id'), ['login_id'], unique=True)

    op.create_table('blood_bank_login_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('login_time', sa.DateTime(), nullable=True),
    sa.Column('ip_address', sa.String(length=50), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['blood_bank_accounts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('blood_bank_login_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_blood_bank_login_history_account_id'), ['account_id'], unique=False)

    op.create_table('blood_bank_password_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['blood_bank_accounts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('blood_bank_password_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_blood_bank_password_history_account_id'), ['account_id'], unique=False)


def downgrade():
    with op.batch_alter_table('blood_bank_password_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blood_bank_password_history_account_id'))
    op.drop_table('blood_bank_password_history')
    
    with op.batch_alter_table('blood_bank_login_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blood_bank_login_history_account_id'))
    op.drop_table('blood_bank_login_history')
    
    with op.batch_alter_table('blood_bank_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blood_bank_accounts_login_id'))
        batch_op.drop_index(batch_op.f('ix_blood_bank_accounts_blood_bank_id'))
    op.drop_table('blood_bank_accounts')
