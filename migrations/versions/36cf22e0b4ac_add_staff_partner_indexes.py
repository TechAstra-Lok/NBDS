"""add_staff_partner_indexes

Revision ID: 36cf22e0b4ac
Revises: 0863441bfaf3
Create Date: 2026-06-28 10:26:36.391603

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '36cf22e0b4ac'
down_revision = '0863441bfaf3'
branch_labels = None
depends_on = None


def upgrade():
    # Keep columns nullable for backward-compatibility with legacy donors.
    # The application layer enforces email/pin_hash on new registrations.
    # Only create the unique index on email (skipping NOT NULL enforcement).
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_donors_email', ['email'])

    # success_stories.social_link: leave nullable to avoid breaking existing rows
    # (no DDL change needed – already nullable in schema)


def downgrade():
    with op.batch_alter_table('donors', schema=None) as batch_op:
        batch_op.drop_constraint('uq_donors_email', type_='unique')
