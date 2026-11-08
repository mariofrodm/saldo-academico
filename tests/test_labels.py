import uuid

import pytest

from backend import demo, labels
from backend.db import db, many, one
from backend.seed import seed


def snapshot(conn):
    result = {}
    mutable = {'users': {'name'}, 'categories': {'name'}, 'obligations': {'title'},
               'goals': {'name'}, 'recurring': {'title'}, 'knowledge': {'title', 'body', 'source'}}
    for table in ('users', 'categories', 'obligations', 'payments', 'goals', 'savings', 'recurring',
                  'knowledge', 'services', 'sessions', 'conversations', 'requests', 'provider_calls', 'tool_runs', 'budgets'):
        order = {'sessions': 'token_hash', 'budgets': 'period'}.get(table, 'id')
        result[table] = [{key: value for key, value in row.items() if key not in mutable.get(table, set())}
                         for row in many(conn, f'SELECT * FROM {table} ORDER BY {order}')]
    return result


def dirty_labels(conn):
    demo.populate_demo(conn)
    conn.execute("UPDATE users SET name='Ana',token_limit=60000,tokens_used=123,tokens_reserved=5 WHERE id=2")
    conn.execute("UPDATE users SET name='Administración de pruebas' WHERE id=1")
    conn.execute("UPDATE obligations SET title='Sueldo de noviembre ficticio' WHERE id=1")
    conn.execute("UPDATE obligations SET title='Demo · Material de estudio' WHERE id=2")
    conn.execute("UPDATE obligations SET title='Diseño gráfico 09/2026 · cliente ficticio' WHERE title LIKE 'Diseño gráfico 09/2026%'")
    conn.execute("UPDATE categories SET name='Demo · Cafés y snacks' WHERE user_id=2 AND name='Cafés y snacks'")
    conn.execute("INSERT INTO categories(user_id,name,kind) VALUES(2,'Demo · Universidad','expense')")
    conn.execute("UPDATE goals SET name='Meta de prueba · Fondo de emergencia' WHERE id=1")
    conn.execute("UPDATE recurring SET title='Demo · Alquiler mensual' WHERE id=(SELECT min(id) FROM recurring)")
    conn.execute('UPDATE knowledge SET source=%s WHERE id=1', (labels.LEGACY_SOURCE,))
    conversation_id, request_id = uuid.uuid4(), uuid.uuid4()
    conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,2,'rag')", (conversation_id,))
    conn.execute("""INSERT INTO requests(id,conversation_id,user_id,service,prompt,response,status)
        VALUES(%s,%s,2,'rag','Pregunta de prueba','Respuesta académica','success')""", (request_id, conversation_id))
    conn.execute("INSERT INTO budgets(period,used,reserved) VALUES('day:2026-11-08',123,5)")


def test_label_cleanup_preserves_finances_history_credentials_and_quota(client, auth):
    with db() as conn:
        dirty_labels(conn)
        before = snapshot(conn)
        audit_before = many(conn, 'SELECT * FROM audit ORDER BY id')
        other = one(conn, """INSERT INTO users(email,name,password_hash,role)
            VALUES('otra@example.test','Cuenta de prueba externa','unchanged','user') RETURNING *""")
        other_category = one(conn, """INSERT INTO categories(user_id,name,kind)
            VALUES(%s,'Demo · Otra categoría','expense') RETURNING *""", (other['id'],))
        result = labels.cleanup_labels(conn)
        assert result['total_changed_rows'] >= 9
        assert result['dry_run'] is False and result['already_applied'] is False
        # Other users' records are outside the financial cleanup scope.
        assert one(conn, 'SELECT * FROM users WHERE id=%s', (other['id'],)) == other
        assert one(conn, 'SELECT * FROM categories WHERE id=%s', (other_category['id'],)) == other_category
        after = snapshot(conn)
        after['users'] = [row for row in after['users'] if row['id'] != other['id']]
        after['categories'] = [row for row in after['categories'] if row['id'] != other_category['id']]
        assert after == before
        assert one(conn, 'SELECT name,token_limit,tokens_used,tokens_reserved,email FROM users WHERE id=2') == {
            'name': 'Ana', 'token_limit': 60000, 'tokens_used': 123, 'tokens_reserved': 5, 'email': 'demo@example.test'}
        assert one(conn, 'SELECT title FROM obligations WHERE id=1')['title'] == 'Sueldo de noviembre'
        assert one(conn, 'SELECT title FROM obligations WHERE id=2')['title'] == 'Material de estudio'
        assert one(conn, "SELECT name FROM categories WHERE user_id=2 AND name='Universidad (2)'")
        assert one(conn, 'SELECT source FROM knowledge WHERE id=1')['source'] == 'Guía de finanzas personales'
        assert many(conn, 'SELECT * FROM audit WHERE action<>%s ORDER BY id', (labels.VERSION,)) == audit_before
        assert one(conn, 'SELECT count(*) AS n FROM audit WHERE action=%s', (labels.VERSION,))['n'] == 1
        all_before_second = {table: many(conn, f'SELECT * FROM {table} ORDER BY id')
                             for table in ('users', 'categories', 'obligations', 'goals', 'recurring', 'knowledge', 'audit')}
        second = labels.cleanup_labels(conn)
        assert second['total_changed_rows'] == 0 and second['already_applied'] is True
        for table, rows in all_before_second.items():
            assert many(conn, f'SELECT * FROM {table} ORDER BY id') == rows
        # Cleaning labels must not make the established seed duplicate its data.
        assert demo.populate_demo(conn)['already_present'] is True


def test_label_cleanup_preview_does_not_write(client):
    with db() as conn:
        dirty_labels(conn)
        before = {table: many(conn, f'SELECT * FROM {table} ORDER BY id')
                  for table in ('users', 'categories', 'obligations', 'goals', 'recurring', 'knowledge', 'audit')}
        result = labels.cleanup_labels(conn, dry_run=True)
        assert result['total_changed_rows'] > 0 and result['dry_run'] is True
        for table, rows in before.items():
            assert many(conn, f'SELECT * FROM {table} ORDER BY id') == rows


def test_label_cleanup_reverts_all_updates_on_failure(client):
    with db() as conn:
        dirty_labels(conn)
        before = {table: many(conn, f'SELECT * FROM {table} ORDER BY id')
                  for table in ('users', 'categories', 'obligations', 'goals', 'recurring', 'knowledge', 'audit')}
        class FailAtAudit:
            def transaction(self):
                return conn.transaction()
            def execute(self, query, params=()):
                if query.startswith('INSERT INTO audit') and params[1] == labels.VERSION:
                    raise RuntimeError('Fallo controlado después de actualizar etiquetas')
                return conn.execute(query, params)
        with pytest.raises(RuntimeError, match='Fallo controlado'):
            labels.cleanup_labels(FailAtAudit())
        for table, rows in before.items():
            assert many(conn, f'SELECT * FROM {table} ORDER BY id') == rows


def test_label_cleanup_requires_local_established_account(client, monkeypatch):
    with db() as conn:
        for environment in ('production', ''):
            monkeypatch.setenv('APP_ENV', environment)
            with pytest.raises(ValueError, match='APP_ENV=local'):
                labels.cleanup_labels(conn)
        monkeypatch.setenv('APP_ENV', 'local')
        with pytest.raises(ValueError, match='cuenta local'):
            labels.cleanup_labels(conn, user_id=1)
        conn.execute('DELETE FROM audit WHERE actor_id=2')
        with pytest.raises(ValueError, match='marcador'):
            labels.cleanup_labels(conn)


def test_seed_creates_clean_names_and_preserves_existing_settings(client):
    with db() as conn:
        assert one(conn, 'SELECT name FROM users WHERE id=2')['name'] == 'Ana'
        assert one(conn, 'SELECT title FROM obligations WHERE id=1')['title'] == 'Sueldo de noviembre'
        assert one(conn, 'SELECT source FROM knowledge WHERE id=1')['source'] == 'Guía de finanzas personales'
        conn.execute("UPDATE users SET token_limit=60000,name='Ana' WHERE id=2")
    seed()
    with db() as conn:
        assert one(conn, 'SELECT token_limit FROM users WHERE id=2')['token_limit'] == 60000
        assert one(conn, "SELECT count(*) AS n FROM audit WHERE action='seed_account_v1'")['n'] == 1
        result = demo.populate_demo(conn)
        assert result['already_present'] is False
        for table, column in (('obligations', 'title'), ('categories', 'name'), ('goals', 'name'), ('recurring', 'title')):
            for row in many(conn, f'SELECT {column} FROM {table} WHERE user_id=2'):
                assert not labels.REFERENCE.search(row[column])


@pytest.mark.parametrize('value,expected', [
    ('Demo · Material de estudio', 'Material de estudio'),
    ('Sueldo de noviembre ficticio', 'Sueldo de noviembre'),
    ('Ana · datos ficticios', 'Ana'),
    ('Diseño · cliente ficticio', 'Diseño · cliente independiente'),
    ('Meta de prueba · Emergencia', 'Meta · Emergencia'),
    ('Transporte', 'Transporte'),
    ('Universidad (2)', 'Universidad (2)'),
    ('Demo · Curso (básico)', 'Curso (básico)'),
    ('Prueba', 'Registro'),
])
def test_clean_label_preserves_meaningful_names(value, expected):
    assert labels.clean_label(value) == expected
