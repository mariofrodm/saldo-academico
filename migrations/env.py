import os
import certifi
from alembic import context
from sqlalchemy import create_engine

url=os.environ.get('DATABASE_URL_DIRECT',os.environ['DATABASE_URL']).replace('postgres://','postgresql://',1).replace('postgresql://','postgresql+psycopg://',1)
args={'sslrootcert':certifi.where()} if 'sslmode=verify-full' in url else {}
with create_engine(url,connect_args=args).connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction(): context.run_migrations()
