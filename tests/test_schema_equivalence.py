"""The hand-in SQL installs the same current schema as a clean migration run."""
from pathlib import Path
import uuid

import pytest
from psycopg import sql
from psycopg.errors import CheckViolation

from backend.db import db, many


def columns(conn, schema):
    return many(conn, '''SELECT table_name,column_name,data_type,is_nullable,column_default,is_identity
                        FROM information_schema.columns WHERE table_schema=%s
                        AND table_name<>'alembic_version' ORDER BY table_name,ordinal_position''', (schema,))


def checks(conn, schema):
    return many(conn, '''SELECT c.relname AS table_name,pg_get_constraintdef(t.oid) AS definition
                        FROM pg_constraint t JOIN pg_class c ON c.oid=t.conrelid
                        JOIN pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname=%s AND t.contype='c' ORDER BY c.relname,definition''', (schema,))


def test_current_sql_matches_clean_alembic_schema(isolated_database):
    temporary = 'schema_check_'+uuid.uuid4().hex[:12]
    source = Path(__file__).resolve().parents[1]/'backend'/'schema.sql'
    with db() as conn:
        migrated_columns, migrated_checks = columns(conn, 'public'), checks(conn, 'public')
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(temporary)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(temporary)))
        conn.execute(source.read_text())
        assert columns(conn, temporary) == migrated_columns
        assert checks(conn, temporary) == migrated_checks
        conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(temporary)))


def test_database_rejects_enabled_deleted_service_and_non_month_schedule(client):
    with pytest.raises(CheckViolation), db() as conn:
        conn.execute("UPDATE services SET enabled=true,deleted_at=now() WHERE id='rag'")
    with pytest.raises(CheckViolation), db() as conn:
        conn.execute("INSERT INTO recurring(user_id,category_id,title,amount,start_month) VALUES(2,2,'Inválido',10,'2027-01-02')")
