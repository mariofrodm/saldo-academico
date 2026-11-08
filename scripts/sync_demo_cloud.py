"""Explicit transfer of the marked demonstration account's financial domain.

Export (local only):
  python -m scripts.sync_demo_cloud export --output evidencias-locales/ana.json
Plan (production Neon only, no changes):
  python -m scripts.sync_demo_cloud import --snapshot evidencias-locales/ana.json
Apply requires --apply, --confirm-email demo@example.test, a recent private
PGDMP --backup and --expected-before-hash from the plan. The existing financial
domain is also saved beside that backup before replacement. Authentication,
AI history, quotas, services and every other user's domain are preserved.
The opt-in --allow-legacy-seed recognizes only the exact original unmarked
three-account/six-table seed profile; it never creates a previous audit marker.

content_sha256 covers all six tables after deterministic ID normalization;
therefore it remains equal when PostgreSQL generates different destination IDs.
It is an integrity/conciliation checksum, not a signature or proof of ownership.
The PGDMP header check does not replace pg_restore validation of the full backup.
"""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import parse_qs, urlsplit
from psycopg import Error as DatabaseError

from backend.db import db, many, one


EMAIL = 'demo@example.test'
FORMAT = 'saldo-finance-snapshot-v1'
ACTION = 'sync_demo_finances_v1'
MARKERS = {'seed_account_v1', 'demo_seed_v1', ACTION}
LEGACY_PROFILE = 'initial-seed-20261102'
TABLES = ('categories', 'recurring', 'obligations', 'payments', 'goals', 'savings')
COLUMNS = {
    'categories': ('id', 'name', 'kind', 'active'),
    'recurring': ('id', 'category_id', 'title', 'amount', 'start_month', 'active'),
    'obligations': ('id', 'category_id', 'title', 'planned', 'due_date', 'recurring_id', 'voided'),
    'payments': ('id', 'obligation_id', 'amount', 'paid_on', 'created_at'),
    'goals': ('id', 'name', 'target', 'deadline', 'active'),
    'savings': ('id', 'goal_id', 'amount', 'moved_on', 'created_at'),
}
REFERENCES = {'category_id': 'categories', 'recurring_id': 'recurring',
              'obligation_id': 'obligations', 'goal_id': 'goals'}
MONEY = re.compile(r'^-?\d{1,13}\.\d{2}$')
LOCAL_HOSTS = {'db', 'localhost', '127.0.0.1', '::1'}


def encoded(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, '.2f')
    raise TypeError('Tipo de dato no exportable')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False, default=encoded).encode('utf-8')


def content_hash(tables):
    mappings = {table: {row['id']: index + 1 for index, row in enumerate(sorted(tables[table], key=lambda r: r['id']))}
                for table in TABLES}
    normalized = {}
    for table in TABLES:
        normalized[table] = []
        for row in sorted(tables[table], key=lambda r: r['id']):
            value = dict(row, id=mappings[table][row['id']])
            for column, target in REFERENCES.items():
                if column in value and value[column] is not None:
                    value[column] = mappings[target][value[column]]
            normalized[table].append(value)
    return hashlib.sha256(canonical(normalized)).hexdigest()


def positive_id(value):
    return type(value) is int and 0 < value < 2**63


def amount(value, *, positive=True):
    if not isinstance(value, str) or not MONEY.fullmatch(value):
        raise ValueError('Los importes deben ser cadenas decimales exactas de dos posiciones')
    result = Decimal(value)
    if (positive and result <= 0) or (not positive and result == 0):
        raise ValueError('Importe fuera del dominio permitido')
    return result


def checked_date(value):
    if not isinstance(value, str):
        raise ValueError('Fecha inválida')
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError('La fecha debe usar YYYY-MM-DD')
    return result


def checked_time(value):
    if not isinstance(value, str):
        raise ValueError('Marca temporal inválida')
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('La marca temporal debe incluir zona horaria')
    if result.astimezone(timezone.utc).isoformat() != value:
        raise ValueError('La marca temporal debe usar su representación ISO canónica en UTC')
    return result


def validate_snapshot(snapshot, *, require_scenario=True):
    expected = {'format', 'email', 'markers', 'exported_at', 'tables', 'content_sha256'}
    if not isinstance(snapshot, dict) or set(snapshot) not in (expected, expected | {'legacy_seed_profile'}):
        raise ValueError('Formato de snapshot inválido')
    if snapshot['format'] != FORMAT or snapshot['email'] != EMAIL:
        raise ValueError('Solo se permite el formato y la cuenta de demostración establecidos')
    markers = snapshot['markers']
    legacy = not require_scenario and snapshot.get('legacy_seed_profile') == LEGACY_PROFILE and markers == []
    if 'legacy_seed_profile' in snapshot and not legacy:
        raise ValueError('El perfil legacy solo documenta un respaldo previo sin marcadores')
    if not isinstance(markers, list) or (not markers and not legacy) or any(type(item) is not str or item not in MARKERS for item in markers):
        raise ValueError('Faltan marcadores permitidos de la cuenta inicializada')
    if require_scenario and 'demo_seed_v1' not in markers:
        raise ValueError('El origen debe contener el escenario completo identificado')
    checked_time(snapshot['exported_at'])
    tables = snapshot['tables']
    if not isinstance(tables, dict) or set(tables) != set(TABLES):
        raise ValueError('Se requieren exactamente las seis tablas financieras')
    indexes = {}
    for table in TABLES:
        rows = tables[table]
        if not isinstance(rows, list) or len(rows) > 20000:
            raise ValueError('Cantidad de registros no permitida')
        indexes[table] = {}
        for row in rows:
            if not isinstance(row, dict) or set(row) != set(COLUMNS[table]) or not positive_id(row['id']):
                raise ValueError('Columnas o identificadores no permitidos')
            if row['id'] in indexes[table]:
                raise ValueError('Identificador repetido dentro de una tabla')
            indexes[table][row['id']] = row
            for column, value in row.items():
                if column in ('active', 'voided') and type(value) is not bool:
                    raise ValueError('Estado no booleano')
                if column in ('name', 'title'):
                    maximum = 80 if table == 'categories' else 100 if table == 'goals' else 160
                    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                        raise ValueError('Nombre o concepto inválido')
                if column in ('amount', 'planned', 'target'):
                    amount(value, positive=table != 'savings')
                if column in ('start_month', 'due_date', 'paid_on', 'deadline', 'moved_on'):
                    when = checked_date(value)
                    if column == 'start_month' and when.day != 1:
                        raise ValueError('El inicio de recurrente debe ser el primer día del mes')
                if column == 'created_at':
                    checked_time(value)
            if table == 'categories' and row['kind'] not in ('income', 'expense'):
                raise ValueError('Tipo de categoría inválido')
    for table in TABLES:
        for row in tables[table]:
            for column, target in REFERENCES.items():
                if column not in row:
                    continue
                value = row[column]
                if column == 'recurring_id' and value is None:
                    continue
                if not positive_id(value) or value not in indexes[target]:
                    raise ValueError('Referencia fuera del dominio exportado')
    category_keys = [(r['name'], r['kind']) for r in tables['categories']]
    if len(category_keys) != len(set(category_keys)):
        raise ValueError('Categoría duplicada')
    recurring_keys = [(r['recurring_id'], r['due_date']) for r in tables['obligations'] if r['recurring_id'] is not None]
    if len(recurring_keys) != len(set(recurring_keys)):
        raise ValueError('Instancia recurrente duplicada')
    paid = {ident: Decimal(0) for ident in indexes['obligations']}
    for row in tables['payments']:
        parent = indexes['obligations'][row['obligation_id']]
        paid[row['obligation_id']] += amount(row['amount'])
        if parent['voided'] or paid[row['obligation_id']] > amount(parent['planned']):
            raise ValueError('Pago de un registro anulado o superior al compromiso')
    balances = {ident: Decimal(0) for ident in indexes['goals']}
    for row in sorted(tables['savings'], key=lambda r: (r['moved_on'], r['id'])):
        balances[row['goal_id']] += amount(row['amount'], positive=False)
        if balances[row['goal_id']] < 0:
            raise ValueError('Los movimientos producirían saldo de ahorro negativo')
    if snapshot['content_sha256'] != content_hash(tables):
        raise ValueError('El contenido no coincide con su SHA-256')
    return snapshot


def exact_legacy_seed(conn, uid):
    """Recognize only the original known seed, never arbitrary unmarked data."""
    accounts = many(conn, 'SELECT email,role,active FROM users ORDER BY email')
    expected_accounts = [
        {'email': 'admin@example.test', 'role': 'admin', 'active': True},
        {'email': 'bi@example.test', 'role': 'bi', 'active': True},
        {'email': EMAIL, 'role': 'user', 'active': True},
    ]
    if accounts != expected_accounts:
        raise ValueError('El destino no coincide con las tres cuentas iniciales permitidas')
    categories = many(conn, 'SELECT user_id,name,kind,active FROM categories ORDER BY name')
    expected_categories = [
        {'user_id': uid, 'name': 'Alimentación', 'kind': 'expense', 'active': True},
        {'user_id': uid, 'name': 'Sueldo', 'kind': 'income', 'active': True},
        {'user_id': uid, 'name': 'Universidad', 'kind': 'expense', 'active': True},
    ]
    if categories != expected_categories or one(conn, 'SELECT count(*) AS n FROM recurring')['n']:
        raise ValueError('El destino no coincide con categorías y recurrentes del seed original')
    obligations = many(conn, '''SELECT o.user_id,c.name AS category,o.title,o.planned,o.due_date,o.recurring_id,o.voided
                    FROM obligations o JOIN categories c ON c.id=o.category_id ORDER BY c.name''')
    expected_obligations = [
        {'user_id': uid, 'category': name, 'title': title, 'planned': Decimal(planned),
         'due_date': date(2026, 11, 5), 'recurring_id': None, 'voided': False}
        for name, title, planned in (
            ('Alimentación', 'Alimentación noviembre', '1000.00'),
            ('Sueldo', 'Sueldo de noviembre ficticio', '6000.00'),
            ('Universidad', 'Universidad noviembre', '900.00'))]
    payments = many(conn, '''SELECT o.user_id,c.name AS category,p.amount,p.paid_on
                    FROM payments p JOIN obligations o ON o.id=p.obligation_id
                    JOIN categories c ON c.id=o.category_id ORDER BY c.name''')
    expected_payments = [{'user_id': uid, 'category': name, 'amount': Decimal(value), 'paid_on': date(2026, 11, 5)}
                         for name, value in (('Alimentación', '1000.00'), ('Sueldo', '6000.00'), ('Universidad', '400.00'))]
    goals = many(conn, 'SELECT user_id,name,target,deadline,active FROM goals ORDER BY id')
    expected_goals = [{'user_id': uid, 'name': 'Fondo de emergencia', 'target': Decimal('5000.00'),
                       'deadline': date(2027, 4, 30), 'active': True}]
    savings = many(conn, '''SELECT g.user_id,g.name,s.amount,s.moved_on
                           FROM savings s JOIN goals g ON g.id=s.goal_id ORDER BY s.id''')
    expected_savings = [{'user_id': uid, 'name': 'Fondo de emergencia', 'amount': Decimal('500.00'), 'moved_on': date(2026, 11, 5)}]
    if obligations != expected_obligations or payments != expected_payments or goals != expected_goals or savings != expected_savings:
        raise ValueError('El dominio destino fue alterado o no es el seed original exacto')


def marked_user(conn, *, full_scenario=False, lock=False, allow_legacy_seed=False):
    suffix = ' FOR UPDATE' if lock else ''
    user = one(conn, 'SELECT id,email,role FROM users WHERE email=%s'+suffix, (EMAIL,))
    if not user or user['role'] != 'user':
        raise ValueError('Se exige la cuenta inicializada demo@example.test con rol user')
    rows = many(conn, '''SELECT DISTINCT action FROM audit WHERE actor_id=%s AND (
                        (entity_id=%s AND action=ANY(%s)) OR
                        (action=%s AND entity='financial_snapshot_sha256' AND entity_id~'^[0-9a-f]{64}$'))
                        ORDER BY action''', (user['id'], str(user['id']), ['seed_account_v1', 'demo_seed_v1'], ACTION))
    markers = [row['action'] for row in rows]
    if not markers and allow_legacy_seed and not full_scenario:
        exact_legacy_seed(conn, user['id'])
    elif not markers or (full_scenario and 'demo_seed_v1' not in markers):
        raise ValueError('La cuenta no tiene los marcadores de escenario requeridos')
    return user, markers


def reject_cross_user_references(conn, uid):
    invalid = one(conn, '''SELECT EXISTS(
        SELECT 1 FROM recurring r JOIN categories c ON c.id=r.category_id
        WHERE (r.user_id=%s)<>(c.user_id=%s)
        UNION ALL SELECT 1 FROM obligations o JOIN categories c ON c.id=o.category_id
        WHERE (o.user_id=%s)<>(c.user_id=%s)
        UNION ALL SELECT 1 FROM obligations o JOIN recurring r ON r.id=o.recurring_id
        WHERE (o.user_id=%s)<>(r.user_id=%s)) AS invalid''', (uid, uid, uid, uid, uid, uid))
    if invalid['invalid']:
        raise ValueError('Hay referencias financieras cruzadas con otro usuario; no se modifica nada')


def read_snapshot(conn, *, full_scenario=False, lock=False, allow_legacy_seed=False):
    user, markers = marked_user(conn, full_scenario=full_scenario, lock=lock, allow_legacy_seed=allow_legacy_seed)
    uid = user['id']
    reject_cross_user_references(conn, uid)
    tables = {}
    for table in TABLES:
        columns = ','.join('t.'+column for column in COLUMNS[table])
        if table == 'payments':
            query = f'SELECT {columns} FROM payments t JOIN obligations p ON p.id=t.obligation_id WHERE p.user_id=%s ORDER BY t.id'
        elif table == 'savings':
            query = f'SELECT {columns} FROM savings t JOIN goals p ON p.id=t.goal_id WHERE p.user_id=%s ORDER BY t.id'
        else:
            query = f'SELECT {columns} FROM {table} t WHERE t.user_id=%s ORDER BY t.id'
        tables[table] = json.loads(canonical(many(conn, query, (uid,))))
    snapshot = {'format': FORMAT, 'email': EMAIL, 'markers': markers,
                'exported_at': datetime.now(timezone.utc).isoformat(), 'tables': tables,
                'content_sha256': content_hash(tables)}
    if not markers:
        snapshot['legacy_seed_profile'] = LEGACY_PROFILE
    return validate_snapshot(snapshot, require_scenario=full_scenario)


def export_snapshot(conn):
    if os.getenv('APP_ENV') != 'local':
        raise ValueError('La exportación exige APP_ENV=local explícito')
    return read_snapshot(conn, full_scenario=True)


def private_path(path):
    candidate = Path(path).absolute()
    if candidate.is_symlink():
        raise ValueError('El archivo privado no puede ser un enlace simbólico')
    result = candidate.parent.resolve()/candidate.name
    if not set(result.parts) & {'evidencias-locales', 'backups', '.local-secrets'}:
        raise ValueError('Los archivos solo se guardan bajo evidencias-locales, backups o .local-secrets')
    if not result.parent.is_dir():
        raise ValueError('El directorio privado de salida debe existir')
    return result


def write_private(path, value):
    path = private_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(canonical(value)+b'\n')
    return path


def verified_backup(path):
    path = private_path(path)
    info = path.lstat()
    age = datetime.now(timezone.utc).timestamp()-info.st_mtime
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size < 128 or not -300 <= age <= 86400:
        raise ValueError('El backup debe ser regular, privado, reciente y no vacío')
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        if handle.read(5) != b'PGDMP':
            raise ValueError('Se exige un backup PostgreSQL en formato custom PGDMP')
        handle.seek(0)
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return path, digest.hexdigest()


def import_snapshot(conn, snapshot, *, apply=False, confirm_email=None, backup_path=None, expected_before_hash=None,
                    allow_legacy_seed=False):
    if os.getenv('APP_ENV') != 'production':
        raise ValueError('La importación exige APP_ENV=production explícito')
    validate_snapshot(snapshot)
    backup = backup_digest = None
    if apply:
        if confirm_email != EMAIL or not backup_path or not expected_before_hash:
            raise ValueError('Aplicar exige confirmar la cuenta, un backup y el hash previo del plan')
        backup, backup_digest = verified_backup(backup_path)
    with conn.transaction():
        before = read_snapshot(conn, lock=apply, allow_legacy_seed=allow_legacy_seed)
        user, _ = marked_user(conn, allow_legacy_seed=allow_legacy_seed)
        uid = user['id']
        report = {'dry_run': not apply, 'email': EMAIL,
                  'before_sha256': before['content_sha256'], 'source_sha256': snapshot['content_sha256'],
                  'before_counts': {table: len(before['tables'][table]) for table in TABLES},
                  'source_counts': {table: len(snapshot['tables'][table]) for table in TABLES},
                  'legacy_seed_accepted': before.get('legacy_seed_profile') == LEGACY_PROFILE,
                  'preserved': ['users', 'sessions', 'conversations', 'requests', 'provider_calls',
                                'tool_runs', 'budgets', 'services', 'knowledge', 'other_users_finances']}
        if not apply:
            return report
        if before['content_sha256'] != expected_before_hash:
            raise ValueError('Los datos destino cambiaron desde el plan; genera un plan nuevo')
        if before['content_sha256'] == snapshot['content_sha256']:
            report.update(applied=False, unchanged=True, after_sha256=before['content_sha256'])
            return report
        before_path = backup.with_name(backup.name+'.domain-'+before['content_sha256'][:12]+'.json')
        # Written before any deletion, even if the transaction subsequently rolls back.
        write_private(before_path, before)
        conn.execute('DELETE FROM payments WHERE obligation_id IN (SELECT id FROM obligations WHERE user_id=%s)', (uid,))
        conn.execute('DELETE FROM savings WHERE goal_id IN (SELECT id FROM goals WHERE user_id=%s)', (uid,))
        for table in ('obligations', 'recurring', 'goals', 'categories'):
            conn.execute(f'DELETE FROM {table} WHERE user_id=%s', (uid,))
        mappings = {table: {} for table in TABLES}
        for table in TABLES:
            for source in sorted(snapshot['tables'][table], key=lambda row: row['id']):
                row = {key: value for key, value in source.items() if key != 'id'}
                for column, target in REFERENCES.items():
                    if column in row and row[column] is not None:
                        row[column] = mappings[target][row[column]]
                if table not in ('payments', 'savings'):
                    row['user_id'] = uid
                columns = ','.join(row)
                placeholders = ','.join(['%s']*len(row))
                created = one(conn, f'INSERT INTO {table}({columns}) VALUES({placeholders}) RETURNING id', tuple(row.values()))
                mappings[table][source['id']] = created['id']
        # The first genuine sync event establishes provenance for legacy accounts.
        # It is in this same transaction and rolls back if reconciliation fails.
        conn.execute('INSERT INTO audit(actor_id,action,entity,entity_id) VALUES(%s,%s,%s,%s)',
                     (uid, ACTION, 'financial_snapshot_sha256', snapshot['content_sha256']))
        after = read_snapshot(conn)
        if after['content_sha256'] != snapshot['content_sha256']:
            raise ValueError('La conciliación posterior falló; se revierte toda la importación')
        report.update(after_sha256=after['content_sha256'], backup_sha256=backup_digest,
                      domain_backup=str(before_path), applied=True)
        return report


def connection_scope(command):
    parsed = urlsplit(os.environ.get('DATABASE_URL', ''))
    if command == 'export':
        if os.getenv('APP_ENV') != 'local' or parsed.hostname not in LOCAL_HOSTS:
            raise ValueError('La exportación exige PostgreSQL local y APP_ENV=local')
    elif os.getenv('APP_ENV') != 'production' or not (parsed.hostname or '').endswith('.neon.tech') or parse_qs(parsed.query).get('sslmode') != ['verify-full']:
        raise ValueError('La importación exige Neon con TLS verify-full y APP_ENV=production')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    exporter = commands.add_parser('export')
    exporter.add_argument('--output', required=True)
    importer = commands.add_parser('import')
    importer.add_argument('--snapshot', required=True)
    importer.add_argument('--apply', action='store_true')
    importer.add_argument('--confirm-email')
    importer.add_argument('--backup')
    importer.add_argument('--expected-before-hash')
    importer.add_argument('--allow-legacy-seed', action='store_true',
                          help='Reconoce únicamente el perfil inicial exacto de tres cuentas sin marcador previo.')
    args = parser.parse_args()
    try:
        connection_scope(args.command)
        with db() as conn:
            if args.command == 'export':
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                snapshot = export_snapshot(conn)
                write_private(args.output, snapshot)
                result = {'exported': True, 'email': EMAIL, 'content_sha256': snapshot['content_sha256'],
                          'counts': {table: len(snapshot['tables'][table]) for table in TABLES}}
            else:
                source = Path(args.snapshot)
                if source.stat().st_size > 10*1024*1024:
                    raise ValueError('Snapshot demasiado grande')
                snapshot = json.loads(source.read_text())
                result = import_snapshot(conn, snapshot, apply=args.apply, confirm_email=args.confirm_email,
                                         backup_path=args.backup, expected_before_hash=args.expected_before_hash,
                                         allow_legacy_seed=args.allow_legacy_seed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError, DatabaseError):
        raise SystemExit('Sincronización detenida: revisar formato, entorno, marcadores, backup privado y hash del plan. No se imprimen credenciales.') from None


if __name__ == '__main__':
    main()
