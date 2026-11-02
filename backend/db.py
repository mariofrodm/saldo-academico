import os
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
import psycopg
import certifi
from psycopg.rows import dict_row


@contextmanager
def db():
    url=os.environ['DATABASE_URL']
    tls={'sslrootcert':certifi.where()} if 'sslmode=verify-full' in url else {}
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10, prepare_threshold=None, **tls) as conn:
        yield conn


def one(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def many(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def audit(conn, actor, action, entity, entity_id):
    conn.execute('INSERT INTO audit(actor_id,action,entity,entity_id) VALUES(%s,%s,%s,%s)',
                 (actor['id'], action, entity, str(entity_id)))
