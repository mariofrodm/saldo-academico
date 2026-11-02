from alembic import op

revision='0002'
down_revision='0001'

def upgrade():
    op.execute('ALTER TABLE requests ADD COLUMN pending_tokens bigint NOT NULL DEFAULT 0 CHECK(pending_tokens>=0)')
    op.execute('ALTER TABLE requests ADD COLUMN pending_day text')
    op.execute('ALTER TABLE requests ADD COLUMN pending_minute text')
    op.execute('ALTER TABLE requests ADD COLUMN pending_model text')
    op.execute('ALTER TABLE requests ADD COLUMN pending_started timestamptz')

def downgrade():
    raise RuntimeError('No se eliminan reservas ni historial automáticamente.')
