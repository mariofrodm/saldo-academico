from pathlib import Path
from alembic import op

revision='0001'
down_revision=None

def upgrade():
    source=Path(__file__).resolve().parents[1]/'0001.sql'
    for statement in source.read_text().split(';'):
        if statement.strip(): op.execute(statement)

def downgrade():
    raise RuntimeError('No hay downgrade destructivo automático; restaurar un backup probado.')
