"""Defaults for new services; preserve administrator settings on existing ones."""
from alembic import op

revision='0004'
down_revision='0003'


def upgrade():
    op.execute("ALTER TABLE services ALTER COLUMN model SET DEFAULT 'openai/gpt-oss-120b'")
    op.execute('ALTER TABLE services ALTER COLUMN max_output SET DEFAULT 768')


def downgrade():
    op.execute("ALTER TABLE services ALTER COLUMN model SET DEFAULT 'openai/gpt-oss-20b'")
    op.execute('ALTER TABLE services ALTER COLUMN max_output SET DEFAULT 512')
