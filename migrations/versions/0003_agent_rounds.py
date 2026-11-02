from alembic import op

revision='0003'
down_revision='0002'

def upgrade():
    op.execute('ALTER TABLE services DROP CONSTRAINT services_max_rounds_check')
    op.execute('ALTER TABLE services ADD CONSTRAINT services_max_rounds_check CHECK(max_rounds BETWEEN 2 AND 6)')
    op.execute('ALTER TABLE services ALTER COLUMN max_rounds SET DEFAULT 6')
    op.execute("UPDATE services SET max_rounds=6 WHERE id='goals' AND max_rounds=4")

def downgrade():
    raise RuntimeError('Revisar configuración de agentes antes de disminuir límites.')
