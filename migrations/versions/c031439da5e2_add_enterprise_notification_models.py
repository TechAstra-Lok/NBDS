"""Add Enterprise Notification Models

Revision ID: c031439da5e2
Revises: 21f91ae032c3
Create Date: 2026-07-06 08:20:29.914839

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'c031439da5e2'
down_revision = '21f91ae032c3'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'push_subscriptions' not in tables:
        op.create_table('push_subscriptions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('donor_id', sa.Integer(), nullable=False),
            sa.Column('platform', sa.String(length=20), nullable=False),
            sa.Column('token', sa.Text(), nullable=False),
            sa.Column('auth_key', sa.String(length=255), nullable=True),
            sa.Column('p256dh_key', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.ForeignKeyConstraint(['donor_id'], ['donors.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token', name='uq_push_subscriptions_token')
        )
        op.create_index(op.f('ix_push_subscriptions_donor_id'), 'push_subscriptions', ['donor_id'], unique=False)

    if 'notification_queue' not in tables:
        op.create_table('notification_queue',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('notification_id', sa.Integer(), nullable=False),
            sa.Column('channel', sa.String(length=20), nullable=False),
            sa.Column('payload', sa.Text(), nullable=True),
            sa.Column('priority', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=True),
            sa.Column('max_retries', sa.Integer(), nullable=True),
            sa.Column('next_attempt_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('error_log', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_notification_queue_notification_id'), 'notification_queue', ['notification_id'], unique=False)
        op.create_index(op.f('ix_notification_queue_status'), 'notification_queue', ['status'], unique=False)
        op.create_index(op.f('ix_notification_queue_next_attempt_at'), 'notification_queue', ['next_attempt_at'], unique=False)

    if 'donor_responses' not in tables:
        op.create_table('donor_responses',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('blood_request_id', sa.String(length=50), nullable=False),
            sa.Column('donor_id', sa.Integer(), nullable=False),
            sa.Column('response_type', sa.String(length=20), nullable=False),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['blood_request_id'], ['blood_requests.request_id'], ),
            sa.ForeignKeyConstraint(['donor_id'], ['donors.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_donor_responses_blood_request_id'), 'donor_responses', ['blood_request_id'], unique=False)
        op.create_index(op.f('ix_donor_responses_donor_id'), 'donor_responses', ['donor_id'], unique=False)

    with op.batch_alter_table('notification_delivery_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('provider_name', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('provider_response_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('opened_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('clicked_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('donor_notification_preferences', schema=None) as batch_op:
        batch_op.add_column(sa.Column('web_push_alerts', sa.Boolean(), server_default='1', nullable=True))
        batch_op.add_column(sa.Column('mobile_push_alerts', sa.Boolean(), server_default='1', nullable=True))
        batch_op.add_column(sa.Column('quiet_hours_start', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('quiet_hours_end', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('dnd_mode', sa.Boolean(), server_default='0', nullable=True))


def downgrade():
    with op.batch_alter_table('donor_notification_preferences', schema=None) as batch_op:
        batch_op.drop_column('dnd_mode')
        batch_op.drop_column('quiet_hours_end')
        batch_op.drop_column('quiet_hours_start')
        batch_op.drop_column('mobile_push_alerts')
        batch_op.drop_column('web_push_alerts')

    with op.batch_alter_table('notification_delivery_logs', schema=None) as batch_op:
        batch_op.drop_column('clicked_at')
        batch_op.drop_column('opened_at')
        batch_op.drop_column('provider_response_id')
        batch_op.drop_column('provider_name')

    op.drop_index(op.f('ix_donor_responses_donor_id'), table_name='donor_responses')
    op.drop_index(op.f('ix_donor_responses_blood_request_id'), table_name='donor_responses')
    op.drop_table('donor_responses')
    
    op.drop_index(op.f('ix_notification_queue_next_attempt_at'), table_name='notification_queue')
    op.drop_index(op.f('ix_notification_queue_status'), table_name='notification_queue')
    op.drop_index(op.f('ix_notification_queue_notification_id'), table_name='notification_queue')
    op.drop_table('notification_queue')
    
    op.drop_index(op.f('ix_push_subscriptions_donor_id'), table_name='push_subscriptions')
    op.drop_table('push_subscriptions')
