"""Add donor PIN security and profile columns

Revision ID: e1a2b3c4d5e6
Revises: f99e3749c73f
Create Date: 2026-08-27 12:00:00.000000

Adds the following missing columns to the donors table:
- pin_reset_required    (Boolean)  — flag set by admin when resetting a donor's PIN
- pin_last_changed_at   (DateTime) — when the donor last changed their own PIN
- pin_last_reset_at     (DateTime) — when an admin last reset the donor's PIN
- pin_last_reset_by     (String)   — which admin user reset the PIN
- failed_pin_attempts   (Integer)  — consecutive failed login attempts counter
- pin_locked_until      (DateTime) — account lockout expiry after too many failures
- gender                (String)   — donor gender (optional)
- emergency_contact     (String)   — emergency contact phone (optional)
- donor_notes           (Text)     — notes from admin or donor (optional)
- is_public             (Boolean)  — profile visibility toggle
- profile_photo_data    (LargeBinary) — binary photo data
- profile_photo_mimetype (String)  — MIME type of the photo
- total_donations       (Integer)  — summary count of all donations
- available_after_date  (Date)     — computed 90-day availability date
- last_status_recalculated_at (DateTime) — when availability was last recalculated
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5e6'
down_revision = 'f99e3749c73f'
branch_labels = None
depends_on = None


def _column_exists(table_name, column_name, connection):
    """Return True if column already exists — safe for re-runs."""
    try:
        insp = sa.inspect(connection)
        columns = [c['name'] for c in insp.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade():
    conn = op.get_bind()

    # All new columns to add to 'donors' table, with their definitions
    new_columns = [
        ('pin_reset_required',          sa.Column('pin_reset_required',         sa.Boolean(),        nullable=True)),
        ('pin_last_changed_at',         sa.Column('pin_last_changed_at',        sa.DateTime(),       nullable=True)),
        ('pin_last_reset_at',           sa.Column('pin_last_reset_at',          sa.DateTime(),       nullable=True)),
        ('pin_last_reset_by',           sa.Column('pin_last_reset_by',          sa.String(100),      nullable=True)),
        ('failed_pin_attempts',         sa.Column('failed_pin_attempts',        sa.Integer(),        nullable=True)),
        ('pin_locked_until',            sa.Column('pin_locked_until',           sa.DateTime(),       nullable=True)),
        ('gender',                      sa.Column('gender',                     sa.String(20),       nullable=True)),
        ('emergency_contact',           sa.Column('emergency_contact',          sa.String(15),       nullable=True)),
        ('donor_notes',                 sa.Column('donor_notes',                sa.Text(),           nullable=True)),
        ('is_public',                   sa.Column('is_public',                  sa.Boolean(),        nullable=True)),
        ('profile_photo_data',          sa.Column('profile_photo_data',         sa.LargeBinary(),    nullable=True)),
        ('profile_photo_mimetype',      sa.Column('profile_photo_mimetype',     sa.String(30),       nullable=True)),
        ('total_donations',             sa.Column('total_donations',            sa.Integer(),        nullable=True)),
        ('available_after_date',        sa.Column('available_after_date',       sa.Date(),           nullable=True)),
        ('last_status_recalculated_at', sa.Column('last_status_recalculated_at',sa.DateTime(),       nullable=True)),
        ('weight',                      sa.Column('weight',                     sa.Float(),          nullable=True)),
    ]

    with op.batch_alter_table('donors', schema=None) as batch_op:
        for col_name, col_def in new_columns:
            if not _column_exists('donors', col_name, conn):
                batch_op.add_column(col_def)

    # Add index on pin_reset_required for fast admin queries (if not already there)
    try:
        with op.batch_alter_table('donors', schema=None) as batch_op:
            batch_op.create_index('ix_donors_pin_reset_required', ['pin_reset_required'], unique=False)
    except Exception:
        pass  # Index may already exist

    # Set sensible defaults for existing rows
    try:
        op.execute(
            "UPDATE donors SET pin_reset_required = FALSE WHERE pin_reset_required IS NULL"
        )
        op.execute(
            "UPDATE donors SET failed_pin_attempts = 0 WHERE failed_pin_attempts IS NULL"
        )
        op.execute(
            "UPDATE donors SET is_public = TRUE WHERE is_public IS NULL"
        )
        op.execute(
            "UPDATE donors SET total_donations = 0 WHERE total_donations IS NULL"
        )
    except Exception:
        pass  # Non-critical — rows may already have values


def downgrade():
    columns_to_drop = [
        'pin_reset_required',
        'pin_last_changed_at',
        'pin_last_reset_at',
        'pin_last_reset_by',
        'failed_pin_attempts',
        'pin_locked_until',
        'gender',
        'emergency_contact',
        'donor_notes',
        'is_public',
        'profile_photo_data',
        'profile_photo_mimetype',
        'total_donations',
        'available_after_date',
        'last_status_recalculated_at',
        'weight',
    ]

    with op.batch_alter_table('donors', schema=None) as batch_op:
        try:
            batch_op.drop_index('ix_donors_pin_reset_required')
        except Exception:
            pass
        for col_name in columns_to_drop:
            try:
                batch_op.drop_column(col_name)
            except Exception:
                pass
