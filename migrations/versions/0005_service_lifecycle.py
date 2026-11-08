"""Retain service history on deletion and enforce recurring month boundaries."""
from alembic import op

revision='0005'
down_revision='0004'


def upgrade():
    op.execute('ALTER TABLE services ADD COLUMN deleted_at timestamptz')
    op.execute('ALTER TABLE services ADD CONSTRAINT services_deleted_disabled_check CHECK(deleted_at IS NULL OR NOT enabled)')
    op.execute("UPDATE recurring SET start_month=date_trunc('month',start_month)::date WHERE EXTRACT(DAY FROM start_month)<>1")
    op.execute('ALTER TABLE recurring ADD CONSTRAINT recurring_start_month_check CHECK(EXTRACT(DAY FROM start_month)=1)')


def downgrade():
    raise RuntimeError('No se elimina automáticamente el registro de bajas de asistentes; restaurar un backup probado.')
