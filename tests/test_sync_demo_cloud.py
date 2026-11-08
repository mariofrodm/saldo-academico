import copy
from datetime import datetime, timezone
import os
from pathlib import Path
import uuid

import pytest

from backend.db import db, many, one
from scripts import sync_demo_cloud as sync


def snapshot():
    data = {'format': sync.FORMAT, 'email': sync.EMAIL, 'markers': ['demo_seed_v1', 'seed_account_v1'],
            'exported_at': '2026-11-08T12:00:00+00:00', 'tables': {
                'categories': [{'id': 101, 'name': 'Vivienda', 'kind': 'expense', 'active': True}],
                'recurring': [{'id': 301, 'category_id': 101, 'title': 'Alquiler mensual', 'amount': '200.00', 'start_month': '2026-12-01', 'active': True}],
                'obligations': [{'id': 401, 'category_id': 101, 'title': 'Alquiler', 'planned': '200.00', 'due_date': '2026-11-01', 'recurring_id': None, 'voided': False}],
                'payments': [{'id': 501, 'obligation_id': 401, 'amount': '50.00', 'paid_on': '2026-11-01', 'created_at': '2026-11-08T12:00:00+00:00'}],
                'goals': [{'id': 201, 'name': 'Computadora para trabajo freelance', 'target': '4500.00', 'deadline': '2027-02-28', 'active': True}],
                'savings': [{'id': 601, 'goal_id': 201, 'amount': '1050.00', 'moved_on': '2026-11-08', 'created_at': '2026-11-08T12:00:00+00:00'}],
            }}
    data['content_sha256'] = sync.content_hash(data['tables'])
    return data


def backup(tmp_path):
    directory = tmp_path/'backups'
    directory.mkdir(exist_ok=True)
    path = directory/'before.dump'
    # Unit fixture only: production additionally needs a pg_restore-verified full dump.
    path.write_bytes(b'PGDMP'+b'0'*256)
    path.chmod(0o600)
    return path


def finance_rows(conn, uid):
    return sync.read_snapshot(conn)['tables'] if uid == 2 else {
        table: many(conn, f'SELECT * FROM {table} WHERE user_id=%s ORDER BY id', (uid,))
        for table in ('categories', 'recurring', 'obligations', 'goals')}


def test_dry_run_reads_only_and_apply_preserves_identity_ai_other_users(client, monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    incoming = snapshot()
    conversation, request = uuid.uuid4(), uuid.uuid4()
    with db() as conn:
        conn.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES('existing-token',2,'existing-csrf',now()+interval '1 hour')")
        conn.execute('UPDATE users SET tokens_used=1234,token_limit=100000 WHERE id=2')
        conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,2,'rag')", (conversation,))
        conn.execute("INSERT INTO requests(id,conversation_id,user_id,service,prompt,status) VALUES(%s,%s,2,'rag','Historial','success')", (request, conversation))
        conn.execute("INSERT INTO provider_calls(request_id,model,input_tokens,output_tokens,usage_kind) VALUES(%s,'model',20,10,'provider')", (request,))
        conn.execute("INSERT INTO tool_runs(request_id,name,arguments,result) VALUES(%s,'financial_overview','{}','{}')", (request,))
        conn.execute("INSERT INTO budgets(period,used) VALUES('day:2026-11-08',1234)")
        other_category = one(conn, "INSERT INTO categories(user_id,name,kind) VALUES(1,'Otro usuario','expense') RETURNING id")['id']
        other_goal = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(1,'Otra meta',100,'2027-01-01') RETURNING id")['id']
        other_recurring = one(conn, "INSERT INTO recurring(user_id,category_id,title,amount,start_month) VALUES(1,%s,'Otro recurrente',10,'2027-01-01') RETURNING id", (other_category,))['id']
        other_obligation = one(conn, "INSERT INTO obligations(user_id,category_id,title,planned,due_date,recurring_id) VALUES(1,%s,'Otro compromiso',10,'2027-01-01',%s) RETURNING id", (other_category, other_recurring))['id']
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,5,'2027-01-01')", (other_obligation,))
        conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,5,'2027-01-01')", (other_goal,))
        preserved_tables = ('users', 'sessions', 'conversations', 'requests', 'provider_calls', 'tool_runs', 'budgets', 'services', 'knowledge')
        preserved = {table: many(conn, f'SELECT * FROM {table}') for table in preserved_tables}
        other_before = finance_rows(conn, 1)
        other_payments = many(conn, 'SELECT * FROM payments WHERE obligation_id=%s', (other_obligation,))
        other_savings = many(conn, 'SELECT * FROM savings WHERE goal_id=%s', (other_goal,))
        before = sync.read_snapshot(conn)
        plan = sync.import_snapshot(conn, incoming)
        assert plan['dry_run'] and plan['source_counts'] == {table: 1 for table in sync.TABLES}
        assert sync.read_snapshot(conn)['content_sha256'] == before['content_sha256']
    with db() as conn:
        result = sync.import_snapshot(conn, incoming, apply=True, confirm_email=sync.EMAIL,
                                      backup_path=backup(tmp_path), expected_before_hash=plan['before_sha256'])
        assert result['applied'] and result['after_sha256'] == incoming['content_sha256']
        assert sync.validate_snapshot(__import__('json').loads(Path(result['domain_backup']).read_text()), require_scenario=False)['content_sha256'] == before['content_sha256']
        assert Path(result['domain_backup']).stat().st_mode & 0o077 == 0
        after = sync.read_snapshot(conn)
        assert after['tables']['goals'][0]['id'] != 201
        assert after['tables']['savings'][0]['amount'] == '1050.00'
        for table in preserved_tables:
            assert many(conn, f'SELECT * FROM {table}') == preserved[table], table
        assert finance_rows(conn, 1) == other_before
        assert many(conn, 'SELECT * FROM payments WHERE obligation_id=%s', (other_obligation,)) == other_payments
        assert many(conn, 'SELECT * FROM savings WHERE goal_id=%s', (other_goal,)) == other_savings
        assert one(conn, 'SELECT action,entity_id FROM audit WHERE action=%s', (sync.ACTION,)) == {'action': sync.ACTION, 'entity_id': incoming['content_sha256']}
        # A repeated application does not churn IDs or financial rows.
        second = sync.import_snapshot(conn, incoming, apply=True, confirm_email=sync.EMAIL,
                                      backup_path=tmp_path/'backups'/'before.dump', expected_before_hash=incoming['content_sha256'])
        assert second['unchanged'] and not second['applied']
        assert sync.read_snapshot(conn)['tables'] == after['tables']


def test_apply_failure_rolls_back_every_financial_change(client, monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    incoming = snapshot()
    with db() as conn:
        before = sync.read_snapshot(conn)
    original = sync.one
    def fail_on_goal(conn, query, params=()):
        if query.startswith('INSERT INTO goals('):
            raise RuntimeError('Fallo simulado después de varias inserciones')
        return original(conn, query, params)
    monkeypatch.setattr(sync, 'one', fail_on_goal)
    with db() as conn:
        with pytest.raises(RuntimeError):
            sync.import_snapshot(conn, incoming, apply=True, confirm_email=sync.EMAIL,
                                 backup_path=backup(tmp_path), expected_before_hash=before['content_sha256'])
        assert sync.read_snapshot(conn)['tables'] == before['tables']
        assert not one(conn, 'SELECT id FROM audit WHERE action=%s', (sync.ACTION,))
    assert len(list((tmp_path/'backups').glob('*.json'))) == 1


@pytest.mark.parametrize('change', [
    lambda s: s.update(email='otra@example.test'),
    lambda s: s.update(markers=['unmarked']),
    lambda s: s.update(markers=['seed_account_v1']),
    lambda s: s['tables']['categories'][0].update(user_id=999),
    lambda s: s['tables']['obligations'][0].update(category_id=999),
    lambda s: s['tables']['obligations'][0].update(recurring_id=999),
    lambda s: s['tables']['payments'][0].update(obligation_id=999),
    lambda s: s['tables']['savings'][0].update(goal_id=999),
    lambda s: s['tables']['savings'][0].update(amount='-1.00'),
    lambda s: s['tables']['payments'][0].update(amount='201.00'),
    lambda s: s['tables']['payments'][0].update(amount='0.00'),
    lambda s: s['tables']['payments'][0].update(amount=1.5),
    lambda s: s['tables']['obligations'][0].update(voided=True),
    lambda s: s['tables']['categories'][0].update(id=True),
    lambda s: s['tables']['categories'][0].update(active='true'),
    lambda s: s['tables']['categories'][0].update(kind='other'),
    lambda s: s['tables']['goals'][0].update(target='NaN'),
    lambda s: s['tables']['goals'][0].update(deadline='2027-02-30'),
    lambda s: s['tables']['recurring'][0].update(start_month='2027-01-02'),
    lambda s: s['tables']['payments'][0].update(created_at='2026-11-08T12:00:00'),
    lambda s: s['tables']['categories'].append(copy.deepcopy(s['tables']['categories'][0])),
    lambda s: s.update(content_sha256='0'*64),
])
def test_snapshot_rejects_invalid_scope_relationships_amounts_and_hash(change):
    value = snapshot()
    change(value)
    with pytest.raises((ValueError, KeyError)):
        sync.validate_snapshot(value)


@pytest.mark.parametrize('missing', ['confirmation', 'backup', 'hash'])
def test_apply_requires_confirmation_backup_and_current_plan(client, monkeypatch, tmp_path, missing):
    monkeypatch.setenv('APP_ENV', 'production')
    with db() as conn:
        before = sync.read_snapshot(conn)
        options = {'apply': True, 'confirm_email': sync.EMAIL, 'backup_path': backup(tmp_path), 'expected_before_hash': before['content_sha256']}
        options[{'confirmation': 'confirm_email', 'backup': 'backup_path', 'hash': 'expected_before_hash'}[missing]] = None
        with pytest.raises(ValueError):
            sync.import_snapshot(conn, snapshot(), **options)
        assert sync.read_snapshot(conn)['tables'] == before['tables']


def test_apply_refuses_stale_plan_unmarked_account_and_cross_user_references(client, monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    path = backup(tmp_path)
    with db() as conn:
        with pytest.raises(ValueError, match='cambiaron'):
            sync.import_snapshot(conn, snapshot(), apply=True, confirm_email=sync.EMAIL, backup_path=path, expected_before_hash='0'*64)
        conn.execute("DELETE FROM audit WHERE actor_id=2 AND action='seed_account_v1'")
        with pytest.raises(ValueError, match='marcadores'):
            sync.import_snapshot(conn, snapshot())
        conn.execute("INSERT INTO audit(actor_id,action,entity,entity_id) VALUES(2,'seed_account_v1','users','2')")
        conn.execute("INSERT INTO obligations(user_id,category_id,title,planned,due_date) VALUES(1,2,'Referencia cruzada',10,'2026-11-01')")
        with pytest.raises(ValueError, match='cruzadas'):
            sync.import_snapshot(conn, snapshot())


def test_export_requires_local_full_scenario_and_import_requires_production(client, monkeypatch):
    with db() as conn:
        with pytest.raises(ValueError, match='marcadores'):
            sync.export_snapshot(conn)
        from backend.demo import populate_demo
        populate_demo(conn)
        value = sync.export_snapshot(conn)
        assert sync.validate_snapshot(value)['content_sha256'] == value['content_sha256']
        assert len(value['tables']['obligations']) > 100
        with pytest.raises(ValueError, match='production'):
            sync.import_snapshot(conn, value)
        monkeypatch.setenv('APP_ENV', 'production')
        with pytest.raises(ValueError, match='local'):
            sync.export_snapshot(conn)


@pytest.mark.parametrize('environment,url,command', [
    ('production', 'postgresql://user:secret@localhost/db', 'import'),
    ('local', 'postgresql://user:secret@ep.example.neon.tech/db?sslmode=verify-full', 'import'),
    ('production', 'postgresql://user:secret@ep.example.neon.tech/db?sslmode=require', 'import'),
    ('production', 'postgresql://user:secret@other.example/db?sslmode=verify-full', 'import'),
    ('production', 'postgresql://user:secret@db/db', 'export'),
    ('local', 'postgresql://user:secret@ep.example.neon.tech/db?sslmode=verify-full', 'export'),
])
def test_cli_rejects_wrong_database_or_environment(monkeypatch, environment, url, command):
    monkeypatch.setenv('APP_ENV', environment)
    monkeypatch.setenv('DATABASE_URL', url)
    with pytest.raises(ValueError):
        sync.connection_scope(command)


def test_cli_accepts_local_export_and_verified_neon_import(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'local')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:secret@db/db')
    sync.connection_scope('export')
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:secret@ep.example.neon.tech/db?sslmode=verify-full')
    sync.connection_scope('import')


def test_backup_checks_private_recent_custom_format_and_output_location(tmp_path):
    path = backup(tmp_path)
    assert len(sync.verified_backup(path)[1]) == 64
    path.chmod(0o644)
    with pytest.raises(ValueError):
        sync.verified_backup(path)
    path.chmod(0o600)
    path.write_bytes(b'not-a-dump'+b'0'*256)
    with pytest.raises(ValueError):
        sync.verified_backup(path)
    path.write_bytes(b'PGDMP'+b'0'*256)
    old = datetime.now(timezone.utc).timestamp()-90000
    os.utime(path, (old, old))
    with pytest.raises(ValueError):
        sync.verified_backup(path)
    with pytest.raises(ValueError):
        sync.write_private(tmp_path/'public.json', snapshot())


def test_content_hash_survives_id_remapping_and_detects_value_changes():
    original = snapshot()
    remapped = copy.deepcopy(original)
    for table in sync.TABLES:
        for row in remapped['tables'][table]:
            row['id'] += 9000
            for key in sync.REFERENCES:
                if key in row and row[key] is not None:
                    row[key] += 9000
    assert sync.content_hash(remapped['tables']) == original['content_sha256']
    remapped['tables']['savings'][0]['amount'] = '1049.00'
    assert sync.content_hash(remapped['tables']) != original['content_sha256']


def legacy_seed(conn):
    # Exact published seed from 2026-11-02, before provenance audits existed.
    conn.execute('DELETE FROM audit')
    conn.execute("UPDATE obligations SET title='Sueldo de noviembre ficticio' WHERE title='Sueldo de noviembre'")


def test_legacy_opt_in_recognizes_exact_seed_without_inventing_prior_marker(client, monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    incoming = snapshot()
    with db() as conn:
        legacy_seed(conn)
        with pytest.raises(ValueError, match='marcadores'):
            sync.import_snapshot(conn, incoming)
        before = sync.read_snapshot(conn, allow_legacy_seed=True)
        assert before['markers'] == [] and before['legacy_seed_profile'] == sync.LEGACY_PROFILE
        assert not one(conn, 'SELECT id FROM audit')
        plan = sync.import_snapshot(conn, incoming, allow_legacy_seed=True)
        assert plan['legacy_seed_accepted'] and plan['dry_run']
        assert not one(conn, 'SELECT id FROM audit')
        with pytest.raises(ValueError):
            sync.validate_snapshot(before, require_scenario=True)
        result = sync.import_snapshot(conn, incoming, apply=True, allow_legacy_seed=True,
                                      confirm_email=sync.EMAIL, backup_path=backup(tmp_path),
                                      expected_before_hash=plan['before_sha256'])
        assert result['applied'] and result['legacy_seed_accepted']
        assert many(conn, 'SELECT action FROM audit') == [{'action': sync.ACTION}]
        after = sync.read_snapshot(conn)
        assert after['markers'] == [sync.ACTION]
        assert after['content_sha256'] == incoming['content_sha256']
        import json
        saved = json.loads(Path(result['domain_backup']).read_text())
        assert saved['markers'] == [] and saved['legacy_seed_profile'] == sync.LEGACY_PROFILE
        assert sync.validate_snapshot(saved, require_scenario=False)


@pytest.mark.parametrize('mutation', [
    "INSERT INTO users(email,name,password_hash,role) VALUES('otra@example.test','Otra','hash','user')",
    "UPDATE users SET active=false WHERE email='bi@example.test'",
    "UPDATE users SET role='admin' WHERE email='bi@example.test'",
    "UPDATE users SET email='otra@example.test' WHERE email='bi@example.test'",
    "UPDATE categories SET name='Otro nombre' WHERE id=2",
    "INSERT INTO categories(user_id,name,kind) VALUES(1,'Datos ajenos','expense')",
    "UPDATE obligations SET title='Registro cambiado' WHERE id=1",
    "UPDATE obligations SET planned=6001 WHERE id=1",
    "UPDATE payments SET amount=999 WHERE obligation_id=2",
    "UPDATE payments SET paid_on='2026-11-04' WHERE obligation_id=2",
    "UPDATE goals SET target=5001 WHERE id=1",
    "UPDATE savings SET amount=501 WHERE id=1",
    "INSERT INTO recurring(user_id,category_id,title,amount,start_month) VALUES(2,2,'Nuevo',10,'2027-01-01')",
])
def test_legacy_opt_in_rejects_changed_data_or_foreign_accounts(client, monkeypatch, mutation):
    monkeypatch.setenv('APP_ENV', 'production')
    with db() as conn:
        legacy_seed(conn)
        conn.execute(mutation)
        with pytest.raises(ValueError):
            sync.import_snapshot(conn, snapshot(), allow_legacy_seed=True)
        assert not one(conn, 'SELECT id FROM audit')
